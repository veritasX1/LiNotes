"""Translations. German is the source language: the code keeps its German texts and passes them
through _(); locale/<lang>.json maps each German text to its translation. A missing entry shows
German, so nothing breaks. The same catalogue is used by the Android app (copied at build time).

Placeholders use {name}: _("„{name}“ entfernt", name=title). Plural forms follow the Unicode CLDR
categories (one, few, many, other) so languages like Russian or Arabic can be added later:
    "{n} Notizen": {"one": "{n} note", "other": "{n} notes"}
"""

import json
import os
from pathlib import Path

LANGUAGES = {"de": "Deutsch", "en": "English", "fr": "Français"}
RTL = {"ar", "he", "fa", "ur"}
_FOLDER = Path(__file__).with_name("locale")
_catalog = None
_language = None


def system_language():
    for variable in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(variable, "")
        for part in value.split(":"):
            code = part.split("_")[0].split(".")[0].lower()
            if code in LANGUAGES:
                return code
            if code and code not in ("c", "posix"):
                return "en"     # a language we do not have yet: English is understood more widely than German
    return "de"


def language():
    """The chosen language: the setting in the app, else the system language."""
    global _language
    if _language is None:
        forced = os.environ.get("LINOTES_LANGUAGE")
        if forced in LANGUAGES:
            _language = forced
            return _language
        # Read ui.json directly: texts are translated while modules load, before the data layer exists.
        data = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
        try:
            chosen = json.loads((data / "linotes" / "ui.json").read_text()).get("language")
        except (OSError, ValueError, AttributeError):
            chosen = None
        _language = chosen if chosen in LANGUAGES else system_language()
    return _language


def set_language(code):
    """Remember the choice (None = system); takes effect after a restart."""
    from . import uiprefs
    uiprefs.put("language", code)


def is_rtl():
    return language() in RTL


def _load():
    global _catalog
    if _catalog is None:
        _catalog = {}
        if language() != "de":
            try:
                _catalog = json.loads((_FOLDER / f"{language()}.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                _catalog = {}
    return _catalog


def plural_category(n, lang=None):
    lang = lang or language()
    n = abs(n)
    if lang == "fr":
        return "one" if n < 2 else "other"
    if lang == "ru":
        if n % 10 == 1 and n % 100 != 11:
            return "one"
        if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
            return "few"
        return "many"
    if lang == "ar":
        if n == 0:
            return "zero"
        if n == 1:
            return "one"
        if n == 2:
            return "two"
        if 3 <= n % 100 <= 10:
            return "few"
        if 11 <= n % 100 <= 99:
            return "many"
        return "other"
    return "one" if n == 1 else "other"


def _(text, **values):
    """Translate a German text; values fill {placeholders}."""
    translated = _load().get(text, text)
    if isinstance(translated, dict):
        translated = translated.get("other") or text
    if values:
        try:
            return translated.format(**values)
        except (KeyError, IndexError, ValueError):
            return text.format(**values)
    return translated


def ngettext(singular, plural, n, **values):
    """Plural: German singular/plural as source, translations by CLDR category."""
    entry = _load().get(plural) or _load().get(singular)
    if isinstance(entry, dict):
        text = entry.get(plural_category(n)) or entry.get("other") or (singular if n == 1 else plural)
    else:
        text = singular if n == 1 else plural
    try:
        return text.format(n=n, **values)
    except (KeyError, IndexError, ValueError):
        return (singular if n == 1 else plural).format(n=n, **values)


def N_(text):
    """Marks a text for translation where it is stored or compared as data; translate when shown."""
    return text
