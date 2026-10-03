"""Verification evidence on development cards: SHA-256, who/when, report (matrix, details, CSV)."""

import hashlib
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("GdkPixbuf", "2.0")

from gi.repository import GdkPixbuf  # noqa: E402

from linotes import model, report  # noqa: E402


class FakeSync:
    user_id = 7

    def __init__(self, objects, files):
        self.items = {o["id"]: o for o in objects}
        self.files = files

    def objects(self, kind):
        return [o for o in self.items.values() if o["kind"] == kind]

    def get(self, object_id):
        return self.items.get(object_id)

    def user_name(self, user):
        return {7: "Claude", 1: "Olaf"}.get(user, "?")

    def fetch_file(self, reference, share=None):
        return self.files[reference]


def main():
    with tempfile.TemporaryDirectory() as folder:
        folder = Path(folder)
        picture = folder / "screenshot.png"
        pixbuf = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, 120, 80)
        pixbuf.fill(0x2b6fe0ff)
        pixbuf.savev(str(picture), "png", [], [])
        protocol = b"Pruefprotokoll: 12/12 bestanden\n"

        sync = FakeSync([], {"srv1:a": picture})
        fields = model.evidence_fields(sync, protocol)
        assert fields["h"] == hashlib.sha256(protocol).hexdigest() and fields["by"] == 7 and fields["at"] > 0

        evidence = [
            {"f": "srv1:a", "n": "screenshot.png", "m": "image/png", "b": picture.stat().st_size,
             **model.evidence_fields(sync, picture.read_bytes())},
            {"f": "srv1:b", "n": "protokoll.txt", "m": "text/plain", "b": len(protocol), **fields},
        ]
        objects = [
            {"id": "board1", "kind": "board", "data": {"name": "Projekt", "dev": True}},
            {"id": "col1", "kind": "column", "data": {"board": "board1", "name": "Offen", "order": 1}},
            {"id": "col2", "kind": "column", "data": {"board": "board1", "name": "Erledigt", "order": 2}},
            {"id": "card1aaaaaaa", "kind": "card", "data": {"board": "board1", "column": "col2", "title": "Mit Nachweisen",
                                                            "verification": "Kriterien: …", "evidence": evidence}},
            {"id": "card2bbbbbbb", "kind": "card", "data": {"board": "board1", "column": "col1", "title": "Ohne"}},
        ]
        sync.items = {o["id"]: o for o in objects}

        data = report.build(sync, "board1")
        row = next(r for r in data["rows"] if r["id"] == "card1aaa")
        assert [e["name"] for e in row["evidence"]] == ["screenshot.png", "protokoll.txt"]
        assert row["evidence"][0]["image"] == str(picture) and row["evidence"][1]["image"] is None
        assert row["evidence"][1]["sha256"] == hashlib.sha256(protocol).hexdigest()
        assert row["evidence"][1]["by"] == "Claude" and row["evidence"][1]["size"] == f"{len(protocol)} Bytes"
        assert "SHA-256 " + fields["h"] in row["evidence_text"]
        other = next(r for r in data["rows"] if r["id"] == "card2bbb")
        assert other["evidence"] == [] and other["evidence_text"] == ""

        pdf = folder / "bericht.pdf"
        report.write_pdf(data, pdf)
        assert pdf.stat().st_size > 2000
        csv_path = folder / "bericht.csv"
        report.write_csv(data, csv_path)
        text = csv_path.read_text(encoding="utf-8-sig")
        assert "Nachweise" in text.splitlines()[0] and fields["h"] in text

        # A picture that cannot be fetched does not break the report.
        sync.files = {}
        broken = report.build(sync, "board1")
        assert next(r for r in broken["rows"] if r["id"] == "card1aaa")["evidence"][0]["image"] is None
        report.write_pdf(broken, folder / "ohne-bild.pdf")
    print("ok – Nachweise")


if __name__ == "__main__":
    main()
