"""Helpers around the synced objects: notes, folders, lists, boards."""

import datetime
import re
import time


# --- notes ------------------------------------------------------

TAG = re.compile(r"(?<![\w#])#([^\W\d_][\w-]{0,40})", re.UNICODE)

BLOCK_TYPES = (
    "title", "heading", "subheading", "body", "mono", "quote",
    "bullet", "dash", "number", "check", "image",
)


def note_blocks(note):
    return note["data"].get("body") or []


def blocks_title(blocks):
    for block in blocks:
        text = block.get("x", "").strip()
        if text:
            return text[:120]
    return ""


def note_title(note, locked_label="Gesperrte Notiz"):
    """Locked notes keep their title visible, like in Apple's Notes (only the
    content is behind the notes password)."""
    data = note["data"]
    if data.get("enc"):
        return data.get("title") or locked_label
    return blocks_title(note_blocks(note)) or data.get("title") or "Neue Notiz"


def note_preview(note):
    """The text after the title, like the second line in Apple's Notes list."""
    if note["data"].get("enc"):
        return ""
    lines = [block.get("x", "").strip() for block in note_blocks(note)]
    lines = [line for line in lines if line]
    return " ".join(lines[1:])[:160]


def note_image(note):
    if note["data"].get("enc"):
        return None
    for block in note_blocks(note):
        if block.get("t") == "image" and block.get("f"):
            return block["f"]
    return None


def note_tags(note):
    if note["data"].get("enc"):
        return set()
    tags = set()
    for block in note_blocks(note):
        tags.update(tag.lower() for tag in TAG.findall(block.get("x", "")))
    return tags


NOTE_LINK = "n:"
MENTION = "m:"


def link_target(span_name):
    """The note id of a note link span ("n:<id>"), otherwise None."""
    return span_name[len(NOTE_LINK):] if isinstance(span_name, str) and span_name.startswith(NOTE_LINK) else None


FOOTNOTE = "fn:"


def footnote_text(span_name):
    """The text of a footnote span ("fn:<text>") – a Profi-Funktion – otherwise None."""
    return span_name[len(FOOTNOTE):] if isinstance(span_name, str) and span_name.startswith(FOOTNOTE) else None


def footnotes(blocks):
    """The footnote texts of a note in reading order (numbered 1, 2, … in the text) – for the list
    under the note and the PDF (Android: Model.footnotes)."""
    result = []
    for block in blocks:
        for span in sorted(block.get("s") or [], key=lambda span: span[0] if span else 0):
            text = footnote_text(span[2]) if len(span) == 3 else None
            if text is not None:
                result.append(text)
    return result


def mention_target(span_name):
    """The user id of an @-mention span ("m:<id>"), otherwise None."""
    if isinstance(span_name, str) and span_name.startswith(MENTION) and span_name[len(MENTION):].isdigit():
        return int(span_name[len(MENTION):])
    return None


def mentions_of(blocks, user_id):
    """How often a user is @-mentioned in the blocks (for notifications)."""
    return sum(1 for block in blocks for span in block.get("s") or []
               if len(span) == 3 and mention_target(span[2]) == user_id)


def refresh_note_links(block, title_of, name_of=None):
    """Note links show the current title of the linked note (like Apple's Notes), mentions
    the current name ("@Name"). title_of(id)/name_of(uid) return it or None (gone – the old
    text stays). Returns the block itself when nothing changed, otherwise an updated copy."""
    spans = block.get("s") or []
    links = []
    for span in spans:
        try:
            start, end, name = span
        except ValueError:
            continue
        target = link_target(name)
        person = mention_target(name)
        title = title_of(target) if target else None
        if person is not None and name_of:
            title = name_of(person)
            title = "@" + title if title and title != "?" else None
        text = block.get("x", "")
        if title and title != text[int(start):int(end)]:
            links.append((int(start), int(end), title))
    if not links:
        return block
    text = block.get("x", "")
    new_spans = [list(span) for span in spans if len(span) == 3]
    # Back to front, so the offsets of earlier links stay valid.
    for start, end, title in sorted(links, reverse=True):
        text = text[:start] + title + text[end:]
        delta = len(title) - (end - start)
        for span in new_spans:
            if span[0] >= end:
                span[0] += delta
            elif span[0] > start:
                span[0] = start
            if span[1] >= end:
                span[1] += delta
            elif span[1] > start:
                span[1] = start + len(title)
    updated = dict(block)
    updated["x"] = text
    updated["s"] = sorted(span for span in new_spans if span[0] < span[1])
    return updated


def link_choices(notes, exclude=None, query="", limit=8):
    """Notes offered after typing ">>": newest first, filtered by the typed text."""
    query = query.strip().lower()
    found = [n for n in notes if n["id"] != exclude and not n["data"].get("trashed")
             and (not query or query in note_title(n).lower())]
    found.sort(key=lambda n: -modified(n))
    return found[:limit]


def block_lines(blocks):
    """One comparable string per block (text, or the kind and file for images and files)."""
    return [f"{b.get('t')}:{b.get('x', '')}{b.get('f', '')}" for b in blocks]


def changed_lines(old, new):
    """Indices in `new` of lines that are new or changed compared to `old` (longest common
    subsequence, like a diff). Mirrors Model.changedLines on Android."""
    n, m = len(old), len(new)
    length = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            length[i][j] = length[i + 1][j + 1] + 1 if old[i] == new[j] else max(length[i + 1][j], length[i][j + 1])
    kept, i, j = set(), 0, 0
    while i < n and j < m:
        if old[i] == new[j]:
            kept.add(j)
            i, j = i + 1, j + 1
        elif length[i + 1][j] >= length[i][j + 1]:
            i += 1
        else:
            j += 1
    return sorted(set(range(m)) - kept)


def note_text(note):
    return "\n".join(block.get("x", "") for block in note_blocks(note))


def modified(obj):
    return obj["data"].get("modified") or obj.get("updated") or 0


def created(obj):
    return obj["data"].get("created") or modified(obj)


NOTE_SORTS = (("modified", "Bearbeitungsdatum"), ("created", "Erstellungsdatum"), ("title", "Titel"))


def sort_notes(notes, order="modified"):
    """Like Apple: pinned notes first, then by edit date, creation date (both
    newest first, grouped by day) or title (A–Z, no date groups).
    Returns [(note, group, timestamp shown in the row)]."""
    stamp = created if order == "created" else modified
    pinned = [note for note in notes if note["data"].get("pinned") and not note["data"].get("trashed")]
    others = [note for note in notes if note not in pinned]
    for part in (pinned, others):
        if order == "title":
            part.sort(key=lambda note: note_title(note).casefold())
        else:
            part.sort(key=stamp, reverse=True)
    return [(note, "Angeheftet", stamp(note)) for note in pinned] + \
        [(note, ("Notizen" if pinned else "") if order == "title" else date_group(stamp(note)), stamp(note))
         for note in others]


def date_group(timestamp, today=None):
    """Heute / Gestern / Vorherige 7 Tage / Vorherige 30 Tage / Monat Jahr."""
    today = today or datetime.date.today()
    day = datetime.date.fromtimestamp(timestamp)
    delta = (today - day).days
    if delta <= 0:
        return "Heute"
    if delta == 1:
        return "Gestern"
    if delta < 7:
        return "Vorherige 7 Tage"
    if delta < 30:
        return "Vorherige 30 Tage"
    if day.year == today.year:
        return MONTHS[day.month - 1]
    return f"{MONTHS[day.month - 1]} {day.year}"


MONTHS = [
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
]

WEEKDAYS = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]


def short_date(timestamp):
    """Like Apple's list: time today, weekday this week, date otherwise."""
    moment = datetime.datetime.fromtimestamp(timestamp)
    today = datetime.date.today()
    delta = (today - moment.date()).days
    if delta <= 0:
        return moment.strftime("%H:%M")
    if delta == 1:
        return "Gestern"
    if delta < 7:
        return WEEKDAYS[moment.weekday()]
    return moment.strftime("%d.%m.%y")


def long_date(timestamp):
    moment = datetime.datetime.fromtimestamp(timestamp)
    return f"{moment.day}. {MONTHS[moment.month - 1]} {moment.year} um {moment:%H:%M}"


def now():
    return time.time()


def empty_note_body():
    return [{"t": "title", "x": ""}]


# --- tables (like Apple's tables in Notes) ----------------------------
# Block {"t": "table", "r": [["A", "B"], ["C", "D"]], "x": "A | B\nC | D"}: "r" are the rows of
# cell texts, "x" the same as plain text so search, previews and older versions still have it.

def table_rows(block):
    """The cells as a rectangle of strings (missing cells filled in, at least 1×1)."""
    rows = [[str(cell) for cell in row] for row in (block.get("r") or []) if isinstance(row, list)]
    width = max((len(row) for row in rows), default=0) or 1
    rows = [row + [""] * (width - len(row)) for row in rows] or [[""]]
    return rows


def table_text(rows):
    return "\n".join(" | ".join(row) for row in rows)


def table_block(rows):
    rows = table_rows({"r": rows})
    return {"t": "table", "r": rows, "x": table_text(rows)}


def new_table(columns=3, rows=3):
    return table_block([[""] * columns for _ in range(rows)])


def is_empty_body(blocks):
    """Nothing typed, no picture, file or divider (whitespace does not count)."""
    return all(b.get("t", "body") not in ("image", "file", "divider", "table") and not b.get("x", "").strip() for b in blocks)


# --- folders ----------------------------------------------------

def folder_parent(sync, folder):
    """Parent folder id, or None at the top (also when the parent is gone)."""
    parent = folder["data"].get("parent")
    return parent if parent and parent != folder["id"] and sync.get(parent) else None


def folder_sort_key(folder):
    return (folder["data"].get("order", 0), folder["data"].get("name", "").lower())


def folder_tree(sync, folders):
    """[(folder, depth)] depth-first. A folder whose parent is not among
    `folders` starts a tree of its own (e.g. a shared folder in a private one)."""
    ids = {folder["id"] for folder in folders}
    children = {}
    for folder in folders:
        parent = folder_parent(sync, folder)
        children.setdefault(parent if parent in ids else None, []).append(folder)
    result, seen = [], set()

    def walk(parent, depth):
        for folder in sorted(children.get(parent, []), key=folder_sort_key):
            if folder["id"] in seen:
                continue
            seen.add(folder["id"])
            result.append((folder, depth))
            walk(folder["id"], depth + 1)
    walk(None, 0)
    return result


def folder_descendants(sync, folder_id):
    """Ids of all folders below `folder_id` (not including it)."""
    found, todo = set(), [folder_id]
    folders = sync.objects("folder")
    while todo:
        current = todo.pop()
        for folder in folders:
            if folder["data"].get("parent") == current and folder["id"] not in found and folder["id"] != folder_id:
                found.add(folder["id"])
                todo.append(folder["id"])
    return found


def folder_path(sync, folder):
    """"Projekte › LiNotes › Entwicklung" – for move dialogs."""
    names, current, guard = [], folder, 0
    while current is not None and guard < 32:
        names.append(current["data"].get("name", "Ordner"))
        parent = folder_parent(sync, current)
        current = sync.get(parent) if parent else None
        guard += 1
    return " › ".join(reversed(names))


# --- board cards ------------------------------------------------

# Like Apple's Reminders: none, low, medium, high – shown as ! / !! / !!! before the title.
PRIORITIES = [(None, "Keine"), ("niedrig", "Niedrig"), ("mittel", "Mittel"), ("hoch", "Hoch")]
PRIORITY_MARKS = {"niedrig": "!", "mittel": "!!", "hoch": "!!!"}


def board_columns(sync, board_id):
    return sorted((c for c in sync.objects("column") if c["data"].get("board") == board_id),
                  key=lambda c: c["data"].get("order", 0))


def done_fields(sync, board_id, column_id):
    """A card counts as done while it is in the last column; remember since when."""
    columns = board_columns(sync, board_id)
    if columns and columns[-1]["id"] == column_id:
        return {"done_at": time.time()}
    return {"done_at": None}


def history_entry(sync, column_id):
    """One step of a card's status history. The column name is kept as it was,
    so the history stays readable after a column is renamed or deleted."""
    column = sync.get(column_id)
    return {"c": column_id, "n": column["data"].get("name", "") if column else "",
            "at": time.time(), "by": sync.user_id}


def new_card_fields(sync, column_id):
    """Fields every new card gets: who created it when, and the first history step."""
    return {"created_by": sync.user_id, "created": time.time(), "history": [history_entry(sync, column_id)]}


def move_fields(sync, card, column_id):
    """Fields for moving a card to another column: done date and history.
    The history is written on every board; only development projects show it."""
    data = card["data"]
    if column_id == data.get("column"):
        return {"column": column_id}
    return {"column": column_id, **done_fields(sync, data.get("board"), column_id),
            "history": list(data.get("history") or []) + [history_entry(sync, column_id)]}


def is_dev_board(sync, board_id):
    board = sync.get(board_id)
    return bool(board and board["data"].get("dev"))


def archived(obj):
    """In the archive (notes, lists, boards, plans) – a mark on the object, so for everyone it is shared with."""
    return bool(obj and obj["data"].get("archived"))


def set_archived(sync, object_id, on):
    obj = sync.get(object_id)
    if obj is None:
        return
    data = dict(obj["data"])
    if on:
        data["archived"] = time.time()
    else:
        data.pop("archived", None)
    sync.put(obj["kind"], data, obj.get("share"), object_id)


def short_id(object_id):
    return object_id[:8]


def card_search_text(card, user_name=None):
    """Everything a card can be found by: id, title, notes, impact, verification, version,
    commits, file and evidence names, the person in charge. Lower case (casefold)."""
    data = card["data"]
    parts = [card["id"], data.get("title"), data.get("notes"), data.get("impact"), data.get("verification"),
             data.get("version")]
    parts += [f"{c.get('h', '')} {c.get('m', '')}" for c in data.get("commits") or []]
    parts += [item.get("n", "") for item in (data.get("files") or []) + (data.get("evidence") or [])]
    if user_name is not None and data.get("assignee") is not None:
        parts.append(user_name(data["assignee"]))
    return " ".join(str(part) for part in parts if part).casefold()


def card_matches(card, query, user_name=None):
    """Every word of the query is somewhere in the card (the same in Android's Model.cardMatches)."""
    words = query.casefold().split()
    if not words:
        return True
    text = card_search_text(card, user_name)
    return all(word in text for word in words)


def moment_label(timestamp):
    moment = datetime.datetime.fromtimestamp(timestamp)
    delta = (datetime.date.today() - moment.date()).days
    if delta == 0:
        return f"heute, {moment:%H:%M}"
    if delta == 1:
        return f"gestern, {moment:%H:%M}"
    return moment.strftime("%d.%m.%Y")


def card_dates(card, dev=False):
    """Erstellt … · Bearbeitet … · Erledigt … (whatever is known).
    Ordinary boards keep it short: created and done only."""
    data = card["data"]
    parts = []
    if data.get("created"):
        parts.append("Erstellt " + moment_label(data["created"]))
    if dev and card.get("updated") and (not data.get("created") or card["updated"] - data["created"] > 60):
        parts.append("Bearbeitet " + moment_label(card["updated"]))
    if data.get("done_at"):
        parts.append("Erledigt " + moment_label(data["done_at"]))
    return " · ".join(parts)


# --- default containers -----------------------------------------

def default_private_folder(user_id):
    return f"notes-{user_id}"


def default_list(user_id):
    return f"list-{user_id}"


def default_board(user_id):
    return f"board-{user_id}"


DEFAULT_COLUMNS = [("offen", "Offen"), ("arbeit", "In Arbeit"), ("fertig", "Erledigt")]


def ensure_defaults(sync):
    """Create the standard folder, list and board once (stable ids).
    Everything starts private; sharing is a deliberate step."""
    user_id = sync.user_id
    if sync.get(default_private_folder(user_id)) is None and default_private_folder(user_id) not in sync.state["remote"]:
        sync.put("folder", {"name": "Notizen", "order": 0}, None, default_private_folder(user_id), notify=False)
    if sync.get(default_list(user_id)) is None and default_list(user_id) not in sync.state["remote"]:
        sync.put("list", {"name": "Einkaufsliste", "color": "gelb", "grocery": True, "order": 0},
                 None, default_list(user_id), notify=False)
    board = default_board(user_id)
    if sync.get(board) is None and board not in sync.state["remote"]:
        sync.put("board", {"name": "Aufgaben", "order": 0}, None, board, notify=False)
        for order, (key, name) in enumerate(DEFAULT_COLUMNS):
            sync.put("column", {"board": board, "name": name, "order": order}, None, f"{board}-{key}", notify=False)


# --- groceries ----------------------------------------------------

GROCERY_CATEGORIES = [
    ("Obst & Gemüse", [
        "apfel", "äpfel", "banane", "birne", "orange", "zitrone", "limette", "traube", "beere",
        "erdbeer", "himbeer", "heidelbeer", "kirsche", "pfirsich", "nektarine", "mango", "ananas",
        "kiwi", "melone", "pflaume", "tomate", "gurke", "salat", "paprika", "zwiebel", "knoblauch",
        "kartoffel", "möhre", "karotte", "zucchini", "aubergine", "brokkoli", "blumenkohl", "kohl",
        "spinat", "lauch", "porree", "sellerie", "pilz", "champignon", "avocado", "ingwer",
        "petersilie", "schnittlauch", "basilikum", "radieschen", "rucola", "mais", "kürbis", "obst",
        "gemüse", "kräuter", "fenchel", "spargel", "rote bete",
    ]),
    ("Brot & Backwaren", [
        "brot", "brötchen", "toast", "baguette", "croissant", "brezel", "kuchen", "zwieback",
        "knäcke", "semmel", "laugen", "wrap", "tortilla",
    ]),
    ("Milchprodukte & Eier", [
        "milch", "butter", "käse", "joghurt", "quark", "sahne", "schmand", "creme fraiche",
        "crème fraîche", "frischkäse", "mozzarella", "parmesan", "feta", "ei", "eier", "margarine",
        "kefir", "buttermilch", "skyr", "gouda",
    ]),
    ("Fleisch & Fisch", [
        "fleisch", "hähnchen", "huhn", "pute", "rind", "schwein", "hack", "wurst", "schinken",
        "salami", "speck", "bacon", "würstchen", "fisch", "lachs", "thunfisch", "garnele",
        "aufschnitt", "steak", "schnitzel", "leberwurst",
    ]),
    ("Tiefkühl", [
        "tk", "tiefkühl", "eis", "speiseeis", "vanilleeis", "schokoeis", "eiscreme", "eis am stiel",
        "pizza", "pommes", "fischstäbchen", "gefroren",
    ]),
    ("Vorrat", [
        "nudel", "spaghetti", "reis", "mehl", "zucker", "salz", "öl", "essig", "linsen", "bohnen",
        "kichererbsen", "dose", "konserve", "müsli", "haferflocken", "cornflakes", "honig",
        "marmelade", "nutella", "erdnussbutter", "backpulver", "hefe", "brühe", "tomatenmark",
        "passierte", "polenta", "couscous", "quinoa", "olivenöl", "rapsöl", "sonnenblumenöl",
    ]),
    ("Gewürze & Soßen", [
        "pfeffer", "gewürz", "paprikapulver", "curry", "ketchup", "senf", "mayo", "soße", "sauce",
        "sojasauce", "zimt", "oregano", "chili", "vanille",
    ]),
    ("Getränke", [
        "wasser", "saft", "cola", "limo", "bier", "wein", "sekt", "kaffee", "tee", "sprudel",
        "schorle", "kakao", "energy", "eistee", "milchshake",
    ]),
    ("Süßes & Snacks", [
        "schokolade", "chips", "keks", "gummibär", "bonbon", "nüsse", "nuss", "cracker", "riegel",
        "popcorn", "salzstangen", "süßigkeit",
    ]),
    ("Drogerie", [
        "zahnpasta", "zahnbürste", "shampoo", "duschgel", "seife", "deo", "creme", "rasier",
        "taschentuch", "toilettenpapier", "klopapier", "watte", "pflaster", "tampon", "binde",
        "windel", "sonnencreme", "spülung",
    ]),
    ("Haushalt", [
        "spülmittel", "waschmittel", "müllbeutel", "müllsack", "küchenrolle", "schwamm", "reiniger",
        "alufolie", "frischhaltefolie", "backpapier", "batterie", "glühbirne", "spültabs", "tabs",
        "weichspüler", "kerze", "servietten",
    ]),
    ("Tierbedarf", ["katzenfutter", "hundefutter", "futter", "katzenstreu", "leckerli"]),
]

OTHER_CATEGORY = "Sonstiges"
CATEGORY_ORDER = [name for name, _words in GROCERY_CATEGORIES] + [OTHER_CATEGORY]


def grocery_category(text):
    lowered = " " + text.lower() + " "
    # The longest matching keyword wins ("reis" over "eis"); very short
    # keywords must be whole words ("ei" is not "Eistee").
    best = None
    for name, words in GROCERY_CATEGORIES:
        for word in words:
            key = word.strip()
            if len(key) <= 3:
                found = re.search(r"(?<!\w)" + re.escape(key) + r"(?!\w)", lowered) is not None
            else:
                found = key in lowered
            if found and (best is None or len(key) > best[1]):
                best = (name, len(key))
    return best[0] if best else OTHER_CATEGORY


def evidence_fields(sync, content):
    """Metadata of a verification record: integrity (SHA-256), when and by whom it was attached."""
    import hashlib
    import time
    return {"h": hashlib.sha256(content).hexdigest(), "at": time.time(), "by": sync.user_id}
