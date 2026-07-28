#!/usr/bin/env python3
"""Export the folder structure of a Nextcloud instance via WebDAV, similar to `tree`."""

import argparse
import os
import sys
from urllib.parse import unquote, urljoin
from xml.etree import ElementTree

import requests
from dotenv import load_dotenv

DAV_NS = "DAV:"


class WebDAVError(Exception):
    pass


def qn(tag: str) -> str:
    return f"{{{DAV_NS}}}{tag}"


class NextcloudClient:
    def __init__(self, base_url: str, username: str, app_password: str):
        self.username = username
        self.session = requests.Session()
        self.session.auth = (username, app_password)
        self.dav_root = urljoin(base_url.rstrip("/") + "/", f"remote.php/dav/files/{username}/")

    def list_dir(self, path: str):
        """Returns the direct children of a folder: list of (name, is_dir)."""
        url = urljoin(self.dav_root, _quote_path(path))
        body = """<?xml version="1.0" encoding="utf-8"?>
<d:propfind xmlns:d="DAV:">
  <d:prop>
    <d:resourcetype/>
  </d:prop>
</d:propfind>"""
        response = self.session.request(
            "PROPFIND",
            url,
            headers={"Depth": "1", "Content-Type": "application/xml"},
            data=body,
            timeout=30,
        )
        if response.status_code == 401:
            raise WebDAVError("Authentication failed (401). Check username/app password.")
        if response.status_code == 404:
            raise WebDAVError(f"Path not found (404): {path!r}")
        if response.status_code not in (207, 200):
            raise WebDAVError(f"Unexpected status {response.status_code} for {path!r}")

        root = ElementTree.fromstring(response.content)
        self_href = self._normalized_href(root.find(qn("response")))

        entries = []
        for resp in root.findall(qn("response")):
            href = unquote(resp.findtext(qn("href")) or "")
            href_norm = href.rstrip("/")
            if href_norm == self_href:
                continue  # the folder itself

            name = href_norm.rsplit("/", 1)[-1]
            resourcetype = resp.find(f"{qn('propstat')}/{qn('prop')}/{qn('resourcetype')}")
            is_dir = resourcetype is not None and resourcetype.find(qn("collection")) is not None
            entries.append((name, is_dir))

        return entries

    def _normalized_href(self, first_response):
        href = unquote(first_response.findtext(qn("href")) or "")
        return href.rstrip("/")


def _quote_path(path: str) -> str:
    from urllib.parse import quote

    return quote(path.strip("/") + ("/" if path.strip("/") else ""))


def fetch_sorted_entries(client: NextcloudClient, path: str):
    """Returns ALL direct children of a folder (files + folders), regardless of --dirs-only.

    Counting the files per folder needs the unfiltered list; the filtering
    for --dirs-only only happens when displaying in build_tree().
    """
    entries = client.list_dir(path)
    entries.sort(key=lambda e: (not e[1], e[0].lower()))
    return entries


def format_file_count(count: int) -> str:
    return f"{count} file" if count == 1 else f"{count} files"


def build_tree(client: NextcloudClient, path: str, entries: list, prefix: str, lines: list,
               dirs_only: bool, max_depth: int, depth: int, counts: dict):
    display_entries = [e for e in entries if e[1]] if dirs_only else entries

    for i, (name, is_dir) in enumerate(display_entries):
        is_last = i == len(display_entries) - 1
        connector = "└── " if is_last else "├── "

        if is_dir:
            counts["dirs"] += 1
            child_path = f"{path.rstrip('/')}/{name}"
            try:
                child_entries = fetch_sorted_entries(client, child_path)
            except WebDAVError as exc:
                lines.append(f"{prefix}{connector}{name}/ [Error: {exc}]")
                continue

            child_file_count = sum(1 for _, d in child_entries if not d)
            lines.append(f"{prefix}{connector}{name}/ {format_file_count(child_file_count)}")

            if max_depth is None or depth < max_depth:
                extension = "    " if is_last else "│   "
                build_tree(client, child_path, child_entries, prefix + extension, lines,
                           dirs_only, max_depth, depth + 1, counts)
        else:
            counts["files"] += 1
            lines.append(f"{prefix}{connector}{name}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", default="/", help="Starting folder in Nextcloud (default: root)")
    parser.add_argument("--output", default="file_tree.txt", help="Output file")
    parser.add_argument("--dirs-only", action="store_true", help="Show only folders, no files")
    parser.add_argument("--max-depth", type=int, default=None, help="Maximum recursion depth")
    args = parser.parse_args()

    load_dotenv()
    base_url = os.environ.get("NEXTCLOUD_URL")
    username = os.environ.get("NEXTCLOUD_USERNAME")
    app_password = os.environ.get("NEXTCLOUD_APP_PASSWORD")

    if not all([base_url, username, app_password]):
        print("Missing configuration. Please create .env (see .env.example).", file=sys.stderr)
        sys.exit(1)

    client = NextcloudClient(base_url, username, app_password)

    try:
        root_entries = fetch_sorted_entries(client, args.path)
    except WebDAVError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    root_file_count = sum(1 for _, d in root_entries if not d)
    root_label = args.path if args.path != "/" else f"{username} (root)"
    lines = [f"{root_label} {format_file_count(root_file_count)}"]
    counts = {"dirs": 0, "files": 0}
    build_tree(client, args.path, root_entries, "", lines,
               args.dirs_only, args.max_depth, depth=1, counts=counts)

    lines.append("")
    if args.dirs_only:
        lines.append(f"{counts['dirs']} directories")
    else:
        lines.append(f"{counts['dirs']} directories, {counts['files']} files")

    output_text = "\n".join(lines)
    print(output_text)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(output_text + "\n")
    print(f"\nSaved to: {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
