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

    def request(self, method, path, body=None, timeout=20, raw=False, content_type=None):
        url = self.server + path
        headers = {"Accept": "application/json", "User-Agent": "LiNotes-Linux/1.0"}
        data = None
        if body is not None and content_type is None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        elif body is not None:
            data = body
            headers["Content-Type"] = content_type
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

    def login(self, username, password, device):
        return self.request("POST", "/api/login", {"username": username, "password": password, "device": device})

    def register(self, invite, username, name, password, device):
        return self.request("POST", "/api/register", {
            "invite": invite, "username": username, "name": name,
            "password": password, "device": device,
        })

    def logout(self):
        return self.request("POST", "/api/logout", {})

    def me(self):
        return self.request("GET", "/api/me")

    def change_password(self, old, new, device):
        return self.request("POST", "/api/password", {"old": old, "new": new, "device": device})

    def invite(self):
        return self.request("POST", "/api/invites", {})["code"]

    # --- sync ---------------------------------------------------

    def pull(self, since, wait=0):
        return self.request("GET", f"/api/sync?since={int(since)}&wait={int(wait)}", timeout=wait + 20)

    def push(self, changes):
        return self.request("POST", "/api/sync", {"changes": changes}, timeout=40)["results"]

    # --- files --------------------------------------------------

    def upload(self, content, mime, space, name="datei"):
        boundary = "----linotes" + secrets.token_hex(12)
        parts = []
        parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"space\"\r\n\r\n{space}\r\n".encode())
        parts.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{name}\"\r\n"
            f"Content-Type: {mime}\r\n\r\n".encode()
        )
        parts.append(content)
        parts.append(f"\r\n--{boundary}--\r\n".encode())
        body = b"".join(parts)
        return self.request(
            "POST", "/api/files", body, timeout=120,
            content_type="multipart/form-data; boundary=" + boundary,
        )["id"]

    def download(self, file_id):
        return self.request("GET", f"/api/files/{file_id}", raw=True, timeout=120)
