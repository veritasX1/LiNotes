"""A note exported as PDF: every line arrives, photos are embedded, one page per A4."""

import subprocess
import sys
import tempfile
from pathlib import Path

import gi

gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from linotes import report  # noqa: E402


def test_note_pdf_contains_text_lists_and_photo(tmp_path):
    photo = tmp_path / "foto.png"
    pixbuf = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, 400, 300)
    pixbuf.fill(0x3366CCFF)
    pixbuf.savev(str(photo), "png", [], [])
    blocks = [
        {"t": "title", "x": "Einkauf & Co"},
        {"t": "body", "x": "fett und <kursiv>", "s": [[0, 4, "b"], [9, 17, "i"]]},
        {"t": "number", "x": "eins"}, {"t": "number", "x": "zwei"},
        {"t": "check", "x": "Milch", "c": True}, {"t": "check", "x": "Brot"},
        {"t": "image", "f": "local:foto"},
    ] + [{"t": "body", "x": f"Zeile {n}"} for n in range(80)]
    path = tmp_path / "notiz.pdf"
    report.write_note_pdf(blocks, str(path), "Einkauf · 01.10.2026", image_path=lambda _ref: photo)
    text = subprocess.run(["pdftotext", str(path), "-"], capture_output=True, text=True, check=True).stdout
    for expected in ("Einkauf & Co", "fett und <kursiv>", "1. eins", "2. zwei", "Milch", "Brot", "Zeile 79", "Seite 2"):
        assert expected in text
    images = subprocess.run(["pdfimages", "-list", str(path)], capture_output=True, text=True, check=True).stdout
    sizes = [line.split()[3:5] for line in images.splitlines()[2:]]
    assert sizes == [["400", "300"]], images


def test_broken_spans_fall_back_to_plain_text():
    assert report.block_markup({"x": "a<b", "s": [[0, 9, "b"]]}) == "<b>a&lt;b</b>"
    assert report.block_markup({"x": "abc", "s": [["x"]]}) == "abc"


def main():
    with tempfile.TemporaryDirectory() as folder:
        test_note_pdf_contains_text_lists_and_photo(Path(folder))
    test_broken_spans_fall_back_to_plain_text()
    print("ok – Notiz als PDF")


if __name__ == "__main__":
    main()
