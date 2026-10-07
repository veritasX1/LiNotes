"""Comment heads in the person's colour (way C, Olaf 07.10.): "[Name dd.mm. HH:MM]" in a card's notes takes the
colour the board gives that person; the notes stay plain text. The same cases are in Android's CommentColorsTest."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from linotes import model  # noqa: E402

NOTES = ("Olaf: bitte prüfen\n\n[Claude 07.10. 12:11] 🟠 gezogen\n\n[Jean-Marie 07.10. 19:36] 🟣 behoben\n"
         "Text mit [Claude 07.10. 12:11] mittendrin")


class Sync:
    """Just enough of the sync engine: one board shared with Olaf (1) and Claude (4), two cards."""
    user_id = 1

    def __init__(self, colors=None):
        self.store = {
            "b": {"id": "b", "kind": "board", "share": "s", "data": {"name": "LiMail", "dev": True, "colors": colors}},
            "s": {"id": "s", "kind": "share", "data": {"keys": {"1": "", "4": ""}}},
            "c1": {"id": "c1", "kind": "card", "data": {"board": "b", "notes": NOTES}},
            "c2": {"id": "c2", "kind": "card", "data": {"board": "other", "notes": "[Erna 01.10. 08:00] anderswo"}},
        }

    def get(self, object_id):
        return self.store.get(object_id)

    def objects(self, kind=None):
        return [o for o in self.store.values() if kind is None or o["kind"] == kind]

    def share_members(self, share_id):
        share = self.get(share_id) if share_id else None
        return sorted(int(uid) for uid in share["data"]["keys"]) if share else []

    def user_name(self, user_id):
        return {1: "Olaf", 4: "Claude"}.get(user_id, "?")

    def update(self, object_id, notify=True, **fields):
        self.store[object_id]["data"].update(fields)


def main():
    # Heads at a line's start only – a quoted "[Claude …]" in the middle of a line is text.
    heads = model.comment_heads(NOTES)
    assert [name for _s, _e, name in heads] == ["Claude", "Jean-Marie"]
    start, end, _name = heads[1]
    assert NOTES[start:end] == "[Jean-Marie 07.10. 19:36]"
    # The card's preview joins the lines: there every head counts.
    assert [n for _s, _e, n in model.comment_heads(" ".join(NOTES.split()), line_start=False)] == ["Claude", "Jean-Marie", "Claude"]
    assert model.comment_heads("") == [] and model.comment_heads(None) == []
    assert model.comment_heads("[Claude 7.10. 12:11] kein Kopf") == []

    # „Tante Erna“: a board without colours colours nothing; unknown keys are ignored.
    assert model.comment_colors(Sync(), "b") == {}
    assert model.comment_colors(Sync({"Claude": "orange", "Olaf": "gold"}), "b") == {"Claude": "#E07A00"}
    assert model.comment_colors(Sync(), "missing") == {}

    # Who can get a colour: the board's people and whoever commented on its cards – not other boards' commenters.
    assert model.comment_names(Sync(), "b") == ["Claude", "Jean-Marie", "Olaf"]

    gtk_checks()
    print("ok – Kommentar-Kopfzeilen in der Farbe der Person")


def gtk_checks():
    """The card dialog's buffer and the card's preview (needs GTK, not a window)."""
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import Gtk
    from linotes import kanban

    buffer = Gtk.TextBuffer()
    buffer.set_text(NOTES)
    colors = {"Jean-Marie": "#9B51E0"}
    kanban.color_comment_heads(buffer, colors)
    tag = buffer.get_tag_table().lookup("head#9B51E0")
    start, end, _name = model.comment_heads(NOTES)[1]
    assert buffer.get_iter_at_offset(start).starts_tag(tag) and buffer.get_iter_at_offset(end).ends_tag(tag)
    assert not buffer.get_iter_at_offset(model.comment_heads(NOTES)[0][0]).has_tag(tag)   # Claude has no colour
    # Typing in front moves the head: coloured again at its new place, the old range cleared.
    buffer.insert(buffer.get_start_iter(), "Neu\n")
    kanban.color_comment_heads(buffer, colors)
    assert buffer.get_iter_at_offset(start + 4).starts_tag(tag) and not buffer.get_iter_at_offset(start).has_tag(tag)
    # Saving takes the text only – nothing of the colour gets into the notes.
    assert buffer.get_text(*buffer.get_bounds(), False) == "Neu\n" + NOTES

    label = Gtk.Label()
    kanban.set_comment_text(label, "[Jean-Marie 07.10. 19:36] <b>&", colors)
    assert label.get_use_markup() and label.get_text() == "[Jean-Marie 07.10. 19:36] <b>&"
    assert "#9B51E0" in label.get_label()
    kanban.set_comment_text(label, "[Jean-Marie 07.10. 19:36] x", {})
    assert not label.get_use_markup() and label.get_label() == "[Jean-Marie 07.10. 19:36] x"

    # „Farben der Personen“: each choice is kept in the board at once; "Keine" takes it out, none left = no field.
    from gi.repository import Adw
    Adw.init()
    sync = Sync({"Claude": "orange"})
    dialog = kanban.CommentColorsDialog(sync, "b")
    assert list(dialog.rows) == ["Claude", "Jean-Marie", "Olaf"] and dialog.rows["Claude"].get_selected() == 3
    dialog.rows["Jean-Marie"].set_selected(1)
    assert sync.get("b")["data"]["colors"] == {"Claude": "orange", "Jean-Marie": "purple"}
    dialog.rows["Claude"].set_selected(0)
    dialog.rows["Jean-Marie"].set_selected(6)
    assert sync.get("b")["data"]["colors"] == {"Jean-Marie": "yellow"}
    dialog.rows["Jean-Marie"].set_selected(0)
    assert sync.get("b")["data"]["colors"] is None


if __name__ == "__main__":
    main()
