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


def note_title(note, locked_label="Gesperrte Notiz"):
    data = note["data"]
    if data.get("enc"):
        return locked_label
    for block in note_blocks(note):
        text = block.get("x", "").strip()
        if text:
            return text[:120]
    return data.get("title") or "Neue Notiz"


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


def note_text(note):
    return "\n".join(block.get("x", "") for block in note_blocks(note))


def modified(obj):
    return obj["data"].get("modified") or obj.get("updated") or 0


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
