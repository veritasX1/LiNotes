"""Files attached to notes (PDFs and others): block {"t": "file", …}, card with preview, PDF export."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gi  # noqa: E402

gi.require_version("Gtk", "4.0")

from linotes import report  # noqa: E402
from linotes.editor import NoteEditor, file_details, pdf_first_page  # noqa: E402

FILE = {"t": "file", "f": "local:abc", "n": "Bericht.pdf", "m": "application/pdf", "b": 1258291}


def main():
    editor = NoteEditor()
    editor.load_blocks([{"t": "title", "x": "T"}, FILE, {"t": "body", "x": "danach"}])
    assert editor.to_blocks() == [{"t": "title", "x": "T"}, FILE, {"t": "body", "x": "danach"}]
    # Attaching in the middle of a line: own line, typing goes on below.
    editor.load_blocks([{"t": "title", "x": "T"}, {"t": "body", "x": "eins"}])
    editor.buffer.place_cursor(editor.buffer.get_end_iter())
    other = dict(FILE, n="Liste.xlsx", m="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", b=2048)
    editor.insert_file(other)
    editor.buffer.insert_at_cursor("zwei")
    assert [b["t"] for b in editor.to_blocks()] == ["title", "body", "file", "body"] and editor.to_blocks()[2] == other
    # Backspace below a file does not merge the text into it.
    editor.buffer.place_cursor(editor.buffer.get_iter_at_line(3)[1])
    assert editor.handle_backspace() and editor.to_blocks()[3]["x"] == "zwei"
    assert file_details(FILE).endswith("1,2 MB") and file_details(other).endswith("2 KB")

    with tempfile.TemporaryDirectory() as folder:
        pdf = Path(folder) / "note.pdf"
        report.write_note_pdf(editor.to_blocks() + [FILE], pdf, "T")
        assert pdf.stat().st_size > 500
        preview = pdf_first_page(pdf)
        assert preview and preview.stat().st_size > 100
    print("ok – Dateien anhängen")


if __name__ == "__main__":
    main()
