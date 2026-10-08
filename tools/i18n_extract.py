"""Collects all translatable texts of both apps and checks the catalogues.

    python3 tools/i18n_extract.py            # list counts, missing and unused entries per language
    python3 tools/i18n_extract.py --missing fr   # print the German texts without a French translation

Ubuntu: _("…") / ngettext("…", "…", n) in linux/linotes/*.py (syntax tree).
Android: tr("…") / trn("…", "…", n) in android/app/src/main/**/*.kt (string scanner).
Catalogue: linux/linotes/locale/<lang>.json – the single source for both apps."""

import ast
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCALE = os.path.join(ROOT, "linux", "linotes", "locale")


def python_keys():
    keys = {}
    for path in glob.glob(os.path.join(ROOT, "linux", "linotes", "*.py")):
        tree = ast.parse(open(path, encoding="utf-8").read())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ("_", "ngettext"):
                for arg in node.args[: 1 if node.func.id == "_" else 2]:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        keys.setdefault(arg.value, set()).add("ubuntu")
                if node.func.id == "ngettext" and len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
                    keys.setdefault("__plural__", set()).add(node.args[1].value)
    return keys


KOTLIN_STRING = r'"((?:[^"\\$]|\\.|\$(?!\{)[^"\\]?)*)"'


def kotlin_keys():
    keys = {}
    for path in glob.glob(os.path.join(ROOT, "android", "app", "src", "main", "**", "*.kt"), recursive=True):
        src = open(path, encoding="utf-8").read()
        for match in re.finditer(r'\b(tr|trn)\(\s*"((?:[^"\\]|\\.)*)"(?:\s*,\s*"((?:[^"\\]|\\.)*)")?', src):
            for text in filter(None, (match.group(2), match.group(3) if match.group(1) == "trn" else None)):
                text = bytes(text, "utf-8").decode("unicode_escape").encode("latin-1").decode("utf-8") if "\\" in text else text
                keys.setdefault(text, set()).add("android")
    return keys


def main():
    keys = {}
    plural = set()
    for source in (python_keys(), kotlin_keys()):
        for key, where in source.items():
            if key == "__plural__":
                plural |= where
                continue
            keys.setdefault(key, set()).update(where)
    print(f"{len(keys)} Texte (Ubuntu {sum('ubuntu' in w for w in keys.values())}, "
          f"Android {sum('android' in w for w in keys.values())}, beide {sum(len(w) == 2 for w in keys.values())})")
    for path in sorted(glob.glob(os.path.join(LOCALE, "*.json"))):
        lang = os.path.basename(path)[:-5]
        catalog = json.load(open(path, encoding="utf-8"))
        missing = [k for k in keys if k not in catalog]
        unused = [k for k in catalog if k not in keys]
        bad = [k for k, v in catalog.items() if isinstance(v, str) and set(re.findall(r"\{(\w+)", k)) != set(re.findall(r"\{(\w+)", v))]
        print(f"  {lang}: {len(catalog)} Einträge, fehlen {len(missing)}, ungenutzt {len(unused)}, Platzhalter falsch {len(bad)}")
        if "--missing" in sys.argv and sys.argv[sys.argv.index("--missing") + 1] == lang:
            for k in missing:
                print(json.dumps(k, ensure_ascii=False))
        if bad and "--check" in sys.argv:
            for k in bad:
                print("  Platzhalter:", k, "→", catalog[k])
    if "--dump" in sys.argv:
        json.dump(sorted(keys), sys.stdout, ensure_ascii=False, indent=0)


if __name__ == "__main__":
    main()
