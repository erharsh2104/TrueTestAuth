"""Reset a forgotten password (admin tool; run on the machine that hosts the app).

    python reset_password.py --list          show every account
    python reset_password.py alice_cs        prompt for a new password for alice_cs

The new password is typed at a hidden prompt, so it never appears in the shell
history or on screen. It also clears any "too many attempts" lock on the account.
A backup copy of the database is made first.
"""

from __future__ import annotations

import argparse
import getpass
import os
import shutil
import sys
import time

from data_manager import DB_FILE, MIN_PASSWORD_LENGTH, DataManager


def main() -> int:
    parser = argparse.ArgumentParser(description="Reset a TrueTestAuth password.")
    parser.add_argument("username", nargs="?", help="account to reset")
    parser.add_argument("--list", action="store_true", help="list all accounts and exit")
    args = parser.parse_args()

    if not os.path.exists(DB_FILE):
        print(f"No database found at {DB_FILE}")
        return 1
    dm = DataManager()

    if args.list or not args.username:
        for u in dm.get_all_faculty() + dm.get_all_students():
            print(f"{u['username']:16s} {u['role']:8s} {u['full_name']}")
        return 0

    username = args.username.strip()
    user = dm.get_user(username) or dm.get_user(username.lower())
    if not user:
        print(f"No account named {username!r}. Use --list to see the accounts.")
        return 1
    username = user["username"]

    pw1 = getpass.getpass(f"New password for {username} (min {MIN_PASSWORD_LENGTH} characters): ")
    if len(pw1) < MIN_PASSWORD_LENGTH:
        print(f"Too short: use at least {MIN_PASSWORD_LENGTH} characters. Nothing was changed.")
        return 1
    if getpass.getpass("Type it again: ") != pw1:
        print("The two entries differ. Nothing was changed.")
        return 1

    backup = f"{DB_FILE}.bak-{time.strftime('%Y%m%d-%H%M%S')}"
    shutil.copy2(DB_FILE, backup)
    dm.reset_password(username, pw1)
    print(f"Password for {username} updated. (Backup of the database: {backup})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
