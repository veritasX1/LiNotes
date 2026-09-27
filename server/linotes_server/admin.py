"""Administration from the command line.

    python -m linotes_server.admin invite      create a one-time invite code
    python -m linotes_server.admin users       list accounts
    python -m linotes_server.admin sessions    list signed-in devices

There are no passwords: accounts are created in the app with an invite
code and are protected by keys that never leave the devices.
"""

import os
import sys
import datetime

from .store import Store


def main(argv):
    store = Store(os.environ.get("LINOTES_DATA", "./data"))
    command = argv[1] if len(argv) > 1 else ""
    if command == "invite":
        print(store.create_invite())
    elif command == "users":
        for user in store.users():
            print(user["id"], user["username"], user["name"])
    elif command == "sessions":
        for user in store.users():
            for session in store.sessions(user["id"]):
                seen = datetime.datetime.fromtimestamp(session["seen"]).strftime("%Y-%m-%d %H:%M")
                print(user["username"], "|", session["device"], "| zuletzt", seen)
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
