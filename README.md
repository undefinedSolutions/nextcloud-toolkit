# NextCloud Tree

Small command-line tools for exporting data from a Nextcloud instance
via the official Nextcloud APIs (WebDAV and Provisioning API):

- [`file_tree.py`](#1-file_treepy) — folder structure like the
  Linux `tree` command, including file count per folder
- [`users_export.py`](#2-users_exportpy) — list of all
  users incl. last login as CSV

Both scripts use the same `.env` configuration.

## Requirements

- Python 3.9+
- A Nextcloud app password (not a regular login password)
- For `users_export.py`: admin or subadmin rights for the
  configured account (needed to view the user list)

## Installation

```bash
git clone <repo-url>
cd NextCloud_Tree

python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Configuration

1. Generate an app password: Nextcloud → Settings → Security → "Create new app password"
2. Create `.env` from the template:

   ```bash
   cp .env.example .env
   ```

3. Fill in the values in `.env`:

   ```
   NEXTCLOUD_URL=https://cloud.example.com
   NEXTCLOUD_USERNAME=yourusername
   NEXTCLOUD_APP_PASSWORD=xxxxx-xxxxx-xxxxx-xxxxx-xxxxx
   ```

   The `.env` file is listed in `.gitignore` and will not be committed.

## 1. file_tree.py

Exports the folder structure of a Nextcloud instance via WebDAV — similar to
the Linux `tree` command, including a display of the file count per folder.

```
Mike (root) 2 files
├── Documents/ 3 files
│   ├── Invoices/ 20 files
│   └── note.txt
└── photo.jpg

2 directories, 24 files
```

### Usage

```bash
python file_tree.py
```

| Option         | Description                                    | Default              |
|----------------|-------------------------------------------------|-------------------------|
| `--path`       | Starting folder in Nextcloud                     | `/` (root)              |
| `--output`     | Target file for the export                       | `file_tree.txt`         |
| `--dirs-only`  | Show only folders, no files                       | off                      |
| `--max-depth`  | Maximum recursion depth                           | unlimited                |

Examples:

```bash
# Export only the "Documents" folder
python file_tree.py --path "/Documents"

# Folder structure only, max 3 levels deep
python file_tree.py --dirs-only --max-depth 3

# Export to a custom file
python file_tree.py --output tree.txt
```

### Notes

- The displayed file count refers to files located **directly** in the
  respective folder (not recursively including subfolders).
- For very large/deep structures, one WebDAV request is made per folder —
  the export can take a while accordingly.

## 2. users_export.py

Exports all Nextcloud users as CSV, incl. last login, email, groups,
storage usage, and more — via the Nextcloud Provisioning API (OCS).

### Usage

```bash
python users_export.py
```

| Option      | Description            | Default               |
|-------------|-------------------------|---------------------------|
| `--output`  | Target CSV file          | `users.csv`               |

The CSV uses `;` as the delimiter and contains the following columns:

`user_id`, `display_name`, `email`, `enabled`, `last_login`,
`groups`, `language`, `backend`, `phone`,
`storage_used_mb`, `storage_total_mb`

### Notes

- Requires admin or subadmin rights for the account configured in `.env`.
- `last_login` is output as a UTC timestamp; `never` if the user has
  never logged in.
- Groups are separated by `;` within the cell.

## Privacy Notice

Exported files (`file_tree.txt`, `test*.txt`, `*.csv`) contain
real data from your Nextcloud — folder names, user emails, phone numbers,
login times, etc. They are excluded from `.gitignore` by default and
should not be published.
