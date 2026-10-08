"""Small HTTP client for the LiNotes server (standard library only)."""

import json
import secrets
import urllib.error
import urllib.request


class ApiError(Exception):

    def __init__(self, status, code, message=""):
        super().__init__(message or code)
        self.status = status
        self.code = code


class OfflineError(ApiError):

    def __init__(self, message=""):
        super().__init__(0, "offline", message)


class Api:

    def __init__(self, server, token=None):
        self.server = server.rstrip("/")
        self.token = token

    def request(self, method, path, body=None, timeout=20, raw=False, content_type=None, length=None):
        url = self.server + path
        headers = {"Accept": "application/json", "User-Agent": "LiNotes-Linux/2.0"}
        data = None
        if body is not None and content_type is None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        elif body is not None:
            data = body
            headers["Content-Type"] = content_type
            if length is not None:
                # A streamed body (iterator) needs its length up front.
                headers["Content-Length"] = str(length)
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                content = response.read()
        except urllib.error.HTTPError as error:
            try:
                code = json.loads(error.read()).get("error", "error")
            except Exception:
                code = "error"
            raise ApiError(error.code, code) from None
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as error:
            raise OfflineError(str(error)) from None
        if raw:
            return content
        return json.loads(content or b"{}")

    # --- accounts -----------------------------------------------

    def health(self):
        return self.request("GET", "/api/health", timeout=10)

    def login(self, username, auth, device):
        return self.request("POST", "/api/login", {"username": username, "auth": auth, "device": device})

    def register(self, invite, username, name, auth, identity, device):
        return self.request("POST", "/api/register", {
            "invite": invite, "username": username, "name": name,
            "auth": auth, "identity": identity, "device": device,
        })

    def logout(self):
        return self.request("POST", "/api/logout", {})

    def me(self):
        return self.request("GET", "/api/me")

    def rename(self, name):
        return self.request("POST", "/api/me/name", {"name": name})

    def invite(self):
        return self.request("POST", "/api/invites", {})["code"]

    # --- pairing / verification ---------------------------------

    def link_request(self, username, device):
        return self.request("POST", "/api/link/request", {"username": username, "device": device})["channel"]

    def verify_request(self, user_id):
        return self.request("POST", "/api/verify/request", {"user": user_id})["channel"]

    def channels(self):
        return self.request("GET", "/api/channels")["channels"]

    def relay_post(self, channel, role, body):
        return self.request("POST", f"/api/relay/{channel}", {"role": role, "body": body})

    def relay_get(self, channel, after=0, wait=0):
        return self.request("GET", f"/api/relay/{channel}?after={after}&wait={wait}", timeout=wait + 20)["messages"]

    def relay_close(self, channel):
        return self.request("DELETE", f"/api/relay/{channel}")

    # --- sync ---------------------------------------------------

    def pull(self, since, wait=0):
        return self.request("GET", f"/api/sync?since={int(since)}&wait={int(wait)}", timeout=wait + 20)

    def push(self, changes):
        return self.request("POST", "/api/sync", {"changes": changes}, timeout=40)["results"]

    def get_object(self, object_id):
        return self.request("GET", f"/api/objects/{object_id}")

    # --- files --------------------------------------------------

    def upload(self, content, share, name="datei", progress=None):
        """progress(sent, total) is called from this thread while the body streams out."""
        boundary = "----linotes" + secrets.token_hex(12)
        parts = []
        if share:
            parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"share\"\r\n\r\n{share}\r\n".encode())
        parts.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{name}\"\r\n"
            "Content-Type: application/octet-stream\r\n\r\n".encode()
        )
        parts.append(content)
        parts.append(f"\r\n--{boundary}--\r\n".encode())
        total = sum(len(part) for part in parts)

        def pieces():
            sent = 0
            for part in parts:
                for start in range(0, len(part), 64 * 1024):
                    piece = part[start:start + 64 * 1024]
                    yield piece
                    sent += len(piece)
                    if progress is not None:
                        progress(sent, total)

        return self.request(
            "POST", "/api/files", pieces(), timeout=120,
            content_type="multipart/form-data; boundary=" + boundary, length=total,
        )["id"]

    def download(self, file_id):
        return self.request("GET", f"/api/files/{file_id}", raw=True, timeout=120)
