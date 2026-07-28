#!/usr/bin/env python3
"""Exports all Nextcloud users incl. last login as CSV.

Uses the Nextcloud Provisioning API (OCS). The configured account
needs admin or subadmin rights in order to view the user list.
"""

import argparse
import csv
import os
import sys
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

OCS_HEADERS = {
    "OCS-APIRequest": "true",
    "Accept": "application/json",
}

FIELDNAMES = [
    "user_id",
    "display_name",
    "email",
    "enabled",
    "last_login",
    "groups",
    "language",
    "backend",
    "phone",
    "storage_used_mb",
    "storage_total_mb",
]

BYTES_PER_MB = 1024 * 1024


class OCSError(Exception):
    pass


class NextcloudUserClient:
    def __init__(self, base_url: str, username: str, app_password: str):
        self.session = requests.Session()
        self.session.auth = (username, app_password)
        self.base_url = base_url.rstrip("/")

    def _get(self, path: str, params: dict = None):
        params = dict(params or {})
        params["format"] = "json"
        response = self.session.get(
            f"{self.base_url}{path}",
            headers=OCS_HEADERS,
            params=params,
            timeout=30,
        )
        if response.status_code == 401:
            raise OCSError("Authentication failed (401). Check username/app password.")
        if response.status_code == 403:
            raise OCSError("Access denied (403). The account needs admin/subadmin rights.")
        if response.status_code != 200:
            raise OCSError(f"Unexpected status {response.status_code} for {path!r}")

        payload = response.json()
        meta = payload.get("ocs", {}).get("meta", {})
        if meta.get("statuscode") not in (100, 200):
            raise OCSError(f"OCS error for {path!r}: {meta.get('message')}")

        return payload["ocs"]["data"]

    def list_user_ids(self):
        limit = 100
        offset = 0
        user_ids = []
        while True:
            data = self._get("/ocs/v2.php/cloud/users", {"limit": limit, "offset": offset})
            batch = data.get("users", [])
            if not batch:
                break
            user_ids.extend(batch)
            if len(batch) < limit:
                break
            offset += limit
        return user_ids

    def get_user(self, user_id: str):
        return self._get(f"/ocs/v2.php/cloud/users/{user_id}")


def format_last_login(last_login_ms) -> str:
    if not last_login_ms:
        return "never"
    dt = datetime.fromtimestamp(int(last_login_ms) / 1000, tz=timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")


# For storage values, Nextcloud sometimes returns negative sentinel values
# instead of actual byte counts (see OC\Files\FileInfo::SPACE_*).
QUOTA_SENTINELS = {
    -1: "not computed",
    -2: "unknown",
    -3: "unlimited",
}


def format_quota_value(value_bytes) -> str:
    if value_bytes is None:
        return ""
    if value_bytes in QUOTA_SENTINELS:
        return QUOTA_SENTINELS[value_bytes]
    return f"{value_bytes / BYTES_PER_MB:.2f}"


def user_to_row(user_id: str, data: dict) -> dict:
    quota = data.get("quota") or {}
    return {
        "user_id": user_id,
        "display_name": data.get("displayname") or "",
        "email": data.get("email") or "",
        "enabled": "yes" if data.get("enabled") else "no",
        "last_login": format_last_login(data.get("lastLogin")),
        "groups": ";".join(data.get("groups") or []),
        "language": data.get("language") or "",
        "backend": data.get("backend") or "",
        "phone": data.get("phone") or "",
        "storage_used_mb": format_quota_value(quota.get("used")),
        "storage_total_mb": format_quota_value(quota.get("total")),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="users.csv", help="Target CSV file")
    args = parser.parse_args()

    load_dotenv()
    base_url = os.environ.get("NEXTCLOUD_URL")
    username = os.environ.get("NEXTCLOUD_USERNAME")
    app_password = os.environ.get("NEXTCLOUD_APP_PASSWORD")

    if not all([base_url, username, app_password]):
        print("Missing configuration. Please create .env (see .env.example).", file=sys.stderr)
        sys.exit(1)

    client = NextcloudUserClient(base_url, username, app_password)

    try:
        user_ids = client.list_user_ids()
    except OCSError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    rows = []
    for user_id in user_ids:
        try:
            data = client.get_user(user_id)
        except OCSError as exc:
            print(f"Warning: skipped user {user_id!r} ({exc})", file=sys.stderr)
            continue
        rows.append(user_to_row(user_id, data))

    rows.sort(key=lambda r: r["user_id"].lower())

    with open(args.output, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)

    print(f"{len(rows)} users exported to: {args.output}")


if __name__ == "__main__":
    main()
