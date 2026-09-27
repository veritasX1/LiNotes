"""Administration from the command line.

    python -m linotes_server.admin create-user USERNAME "Display Name"
    python -m linotes_server.admin invite
    python -m linotes_server.admin users
    python -m linotes_server.admin password USERNAME
"""

import getpass
import os
import sys

from .store import Store


def main(argv):
    store = Store(os.environ.get("LINOTES_DATA", "./data"))
    if len(argv) < 2:
        print(__doc__)
        return 1
    command = argv[1]
    if command == "create-user" and len(argv) >= 3:
        password = os.environ.get("LINOTES_PASSWORD") or getpass.getpass("Passwort: ")
        user_id = store.create_user(argv[2], argv[3] if len(argv) > 3 else argv[2], password)
        print(f"Benutzer {argv[2]} angelegt (id {user_id})")
    elif command == "invite":
        print(store.create_invite())
    elif command == "users":
        for user in store.users():
            print(user["id"], user["username"], user["name"])
    elif command == "password" and len(argv) >= 3:
        user = store.user_by_name(argv[2])
        if user is None:
            print("Unbekannter Benutzer")
            return 1
        password = os.environ.get("LINOTES_PASSWORD") or getpass.getpass("Neues Passwort: ")
        store.set_password(user["id"], password)
        print("Passwort geändert, alle Geräte abgemeldet.")
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
