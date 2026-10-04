"""Link previews like Apple's: a web address alone on a line becomes a card with title, picture and
domain. Privacy as in Signal: only the device that inserts the link fetches the page (the site sees
that device's address, nothing else), the preview is stored encrypted in the note, other devices
fetch nothing. Off unless switched on (Darstellung → Link-Vorschau). Android: LinkPreview.kt."""

import html
import re
import urllib.parse
import urllib.request
from html.parser import HTMLParser

LONE_URL = re.compile(r"^\s*(https?://[^\s<>\"']+)\s*$")
PAGE_LIMIT = 512 * 1024        # only the head is needed
IMAGE_LIMIT = 3 * 1024 * 1024
IMAGE_SIZE = 600               # longest side of the stored picture
TIMEOUT = 8
AGENT = "Mozilla/5.0 (X11; Linux x86_64) LiNotes-Linkvorschau"


def lone_url(text):
    """The web address if the line holds nothing else (http/https only)."""
    match = LONE_URL.match(text or "")
    return match.group(1) if match else None


def domain(url):
    host = (urllib.parse.urlsplit(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


class _Head(HTMLParser):
    """Collects <title> and the <meta> tags of the page head."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta = {}
        self.title = ""
        self.in_title = False

    def handle_starttag(self, tag, attrs):
        attrs = {key.lower(): value or "" for key, value in attrs}
        if tag == "meta":
            key = (attrs.get("property") or attrs.get("name") or "").lower()
            if key and attrs.get("content") and key not in self.meta:
                self.meta[key] = attrs["content"].strip()
        elif tag == "title":
            self.in_title = True

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title += data


def parse(page, url):
    """Title, description, picture address and site name from a page's HTML (the same rules as
    Android's LinkPreview.parse)."""
    head = _Head()
    try:
        head.feed(page)
    except Exception:
        pass
    meta = head.meta

    def first(*keys):
        return next((html.unescape(meta[key]).strip() for key in keys if meta.get(key)), "")

    title = first("og:title", "twitter:title") or " ".join(head.title.split())
    image = first("og:image", "og:image:url", "twitter:image", "twitter:image:src")
    return {
        "title": " ".join(title.split())[:200],
        "description": " ".join(first("og:description", "twitter:description", "description").split())[:300],
        "image": urllib.parse.urljoin(url, image) if image else "",
        "site": first("og:site_name") or domain(url),
    }


def _get(url, limit, accept):
    request = urllib.request.Request(url, headers={"User-Agent": AGENT, "Accept": accept})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        if urllib.parse.urlsplit(response.geturl()).scheme not in ("http", "https"):
            raise ValueError("kein Web-Link")
        return response.read(limit), response.headers


def fetch(url):
    """Fetch a page (only its beginning) and its picture. Blocking – run in a thread."""
    if urllib.parse.urlsplit(url).scheme not in ("http", "https"):
        raise ValueError("kein Web-Link")
    body, headers = _get(url, PAGE_LIMIT, "text/html,application/xhtml+xml")
    if "html" not in (headers.get_content_type() or "html"):
        raise ValueError("keine Webseite")
    charset = headers.get_content_charset() or "utf-8"
    found = parse(body.decode(charset, errors="replace"), url)
    picture = None
    if found["image"]:
        try:
            data, image_headers = _get(found["image"], IMAGE_LIMIT, "image/*")
            if image_headers.get_content_type().startswith("image/"):
                picture = shrink(data)
        except Exception:
            picture = None  # a preview without picture is fine
    return {**found, "picture": picture}


def shrink(data):
    """The picture at most IMAGE_SIZE px on its longest side, as JPEG (PNG with transparency)."""
    import gi
    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import GdkPixbuf
    loader = GdkPixbuf.PixbufLoader()
    loader.write(data)
    loader.close()
    pixbuf = loader.get_pixbuf()
    if pixbuf is None:
        return None
    scale = min(1.0, IMAGE_SIZE / max(pixbuf.get_width(), pixbuf.get_height()))
    if scale < 1.0:
        pixbuf = pixbuf.scale_simple(max(1, int(pixbuf.get_width() * scale)), max(1, int(pixbuf.get_height() * scale)),
                                     GdkPixbuf.InterpType.BILINEAR)
    kind = "png" if pixbuf.get_has_alpha() else "jpeg"
    ok, buffer = pixbuf.save_to_bufferv(kind, ["quality"] if kind == "jpeg" else [], ["85"] if kind == "jpeg" else [])
    return bytes(buffer) if ok else None


def block(url, found, file_ref=None):
    """The note block. "x" keeps the address, so older LiNotes versions show it as a plain line."""
    result = {"t": "link", "x": url, "u": url, "n": found.get("title") or domain(url), "dm": found.get("site") or domain(url)}
    if found.get("description"):
        result["ds"] = found["description"]
    if file_ref:
        result["f"] = file_ref
    return result
