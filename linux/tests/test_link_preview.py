"""Link previews: lone web address, page parsing (same cases as Android's LinkPreviewTest), fetching
from a local test server (page, picture, plain title, no HTML)."""

import http.server
import io
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from linotes import linkpreview  # noqa: E402

OG = """<html><head><meta charset="utf-8"><title>Fallback</title>
<meta property="og:title" content="Gartenhaus &amp; Werkzeug">
<meta property="og:description" content="  Alles   für den Garten  ">
<meta property="og:image" content="/bild.png"><meta property="og:site_name" content="Baumarkt">
</head><body>…</body></html>"""
PLAIN = "<html><head><title>  Nur   ein Titel </title><meta name=description content='Kurz'></head></html>"


def png():
    import gi
    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import GdkPixbuf
    pixbuf = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, 1200, 800)
    pixbuf.fill(0x3388ccff)
    return bytes(pixbuf.save_to_bufferv("png", [], [])[1])


def main():
    assert linkpreview.lone_url("https://example.org/a?b=1") == "https://example.org/a?b=1"
    assert linkpreview.lone_url("  http://x.de  ") == "http://x.de"
    assert linkpreview.lone_url("siehe https://x.de") is None and linkpreview.lone_url("www.x.de") is None
    assert linkpreview.lone_url("ftp://x.de") is None and linkpreview.lone_url("") is None
    assert linkpreview.domain("https://www.Example.org/x") == "example.org"

    found = linkpreview.parse(OG, "https://shop.example.org/gartenhaus")
    assert found == {"title": "Gartenhaus & Werkzeug", "description": "Alles für den Garten",
                     "image": "https://shop.example.org/bild.png", "site": "Baumarkt"}, found
    assert linkpreview.parse(PLAIN, "https://www.x.de/") == {"title": "Nur ein Titel", "description": "Kurz", "image": "", "site": "x.de"}
    assert linkpreview.parse("<<kaputt", "https://x.de")["site"] == "x.de"

    picture = png()

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            pages = {"/seite": ("text/html; charset=utf-8", OG.encode()), "/bild.png": ("image/png", picture),
                     "/titel": ("text/html", PLAIN.encode()), "/datei": ("application/zip", b"PK")}
            kind, body = pages.get(self.path, ("text/plain", b"nein"))
            self.send_response(200 if self.path in pages else 404)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"

    result = linkpreview.fetch(base + "/seite")
    assert result["title"] == "Gartenhaus & Werkzeug" and result["image"] == base + "/bild.png"
    import gi
    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import GdkPixbuf
    loader = GdkPixbuf.PixbufLoader()
    loader.write(result["picture"])
    loader.close()
    assert max(loader.get_pixbuf().get_width(), loader.get_pixbuf().get_height()) == linkpreview.IMAGE_SIZE
    assert linkpreview.fetch(base + "/titel")["picture"] is None
    try:
        linkpreview.fetch(base + "/datei")
        raise AssertionError("keine Webseite erwartet")
    except ValueError:
        pass
    block = linkpreview.block(base + "/seite", result, "f1:n1")
    assert block == {"t": "link", "x": base + "/seite", "u": base + "/seite", "n": "Gartenhaus & Werkzeug", "dm": "Baumarkt",
                     "ds": "Alles für den Garten", "f": "f1:n1"}
    assert linkpreview.block("https://x.de", {})["n"] == "x.de"
    server.shutdown()
    print("ok – Link-Vorschau")


if __name__ == "__main__":
    main()
