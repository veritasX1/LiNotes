"""Wraps the user-facing German texts of a Kotlin file in tr() for translation.

    python3 tools/i18n_wrap_kotlin.py <file.kt> [--write] [--skip "Text" ...] [--skip-lines 10-20 ...]

A small scanner finds real string literals (comments, char and raw strings are skipped).
String templates become placeholders: "Hallo $name, ${a.b} da" -> tr("Hallo {name}, {b} da", "name" to name, "b" to a.b).
Left alone: JSON/HTTP/crypto/log/regex/date-pattern arguments, comparisons, when-branch keys,
const vals, annotations and anything that does not look like a sentence or label."""

import json
import re
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from i18n_wrap import ui_like  # noqa: E402

SKIP_BEFORE = re.compile(
    r"(?:\b(?:optString|getString|optInt|optLong|optDouble|optBoolean|optJSONArray|optJSONObject|getJSONObject|"
    r"getJSONArray|getInt|getLong|getDouble|getBoolean|put|has|remove|opt|isNull|getInstance|setRequestProperty|request|"
    r"ofPattern|Regex|toRegex|startsWith|endsWith|split|replace|contains|substringBefore|substringAfter|substringAfterLast|"
    r"substringBeforeLast|indexOf|equals|BigInteger|Suppress|SuppressLint|putBoolean|putString|putInt|putLong|putFloat|"
    r"getFloat|getSharedPreferences|Intent|setType|setAction|putExtra|getStringExtra|getBooleanExtra|NotificationChannel|"
    r"parse|File|createTempFile|setDataAndType|setPackage|loadLibrary|w|d|e|i|v|wtf|tr|trn|ofLocalizedDate|"
    r"forLanguageTag|Locale|charset|Charset|forName|digest|toByteArray|encodeToByteArray|textOf|span|attr|setAttribute|"
    r"getAttribute|key|getQueryParameter|appendQueryParameter|authority|scheme|path|encodedPath|mimeType|setMimeType|"
    r"ACTION|setClassName|ComponentName|Uri|fromParts|systemService|getSystemService|createChannel)\(\s*$"
    r"|(?:==|!=|\bis|\bin|!in)\s*$|@\w*\(?\s*$|\bconst\s+val\s+\w+\s*(?::\s*\w+)?\s*=\s*$|\bLog\.\w+\(\s*$)")
SKIP_AFTER = re.compile(r"^\s*(?:->|==|!=|\.(?:equals|toRegex|lowercase|uppercase)\b)")


def scan(src):
    """Yields (start, end, parts) for every ordinary string literal; parts = [str | ('expr', code)]."""
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        if src.startswith("//", i):
            i = src.find("\n", i)
            i = n if i < 0 else i
        elif src.startswith("/*", i):
            j = src.find("*/", i + 2)
            i = n if j < 0 else j + 2
        elif src.startswith('"""', i):
            j = src.find('"""', i + 3)
            i = n if j < 0 else j + 3
        elif c == "'":
            j = i + 1
            while j < n and src[j] != "'":
                j += 2 if src[j] == "\\" else 1
            i = j + 1
        elif c == '"':
            start, parts, buf, j = i, [], "", i + 1
            while j < n and src[j] != '"':
                ch = src[j]
                if ch == "\\":
                    buf += src[j:j + 2]
                    j += 2
                elif ch == "$" and j + 1 < n and src[j + 1] == "{":
                    if buf:
                        parts.append(buf)
                        buf = ""
                    depth, k = 1, j + 2
                    while k < n and depth:
                        if src[k] == "{":
                            depth += 1
                        elif src[k] == "}":
                            depth -= 1
                        elif src[k] == '"':      # nested string inside the expression
                            k += 1
                            while k < n and src[k] != '"':
                                k += 2 if src[k] == "\\" else 1
                        k += 1
                    parts.append(("expr", src[j + 2:k - 1]))
                    j = k
                elif ch == "$" and j + 1 < n and (src[j + 1].isalpha() or src[j + 1] == "_"):
                    if buf:
                        parts.append(buf)
                        buf = ""
                    m = re.match(r"[A-Za-z_][A-Za-z0-9_]*", src[j + 1:])
                    parts.append(("expr", m.group(0)))
                    j += 1 + len(m.group(0))
                else:
                    buf += ch
                    j += 1
            if buf:
                parts.append(buf)
            yield start, j + 1, parts
            i = j + 1
        else:
            i += 1


def unescape(raw):
    return re.sub(r"\\(.)", lambda m: {"n": "\n", "t": "\t", "\\": "\\", '"': '"', "$": "$", "'": "'"}.get(m.group(1), m.group(1)), raw)


def name_for(expr, used):
    e = expr.strip()
    m = re.fullmatch(r"(?:[\w.]+\.)?(\w+)", e)
    if m:
        base = m.group(1)
    else:
        call = re.match(r"(?:[\w.]+\.)?(\w+)\s*\(", e)
        base = {"size": "count", "count": "count", "userName": "person", "humanSize": "size", "shortId": "id",
                "optString": "name", "format": "value"}.get(call.group(1), call.group(1)) if call else "value"
        if e.endswith(".size") or e.endswith(".length"):
            base = "count"
    base = re.sub(r"\W", "", base) or "value"
    name, k = base, 2
    while name in used and used[name] != e:
        name, k = f"{base}{k}", k + 1
    used[name] = e
    return name


def process(path, write=False, skip=(), skip_lines=()):
    src = open(path, encoding="utf-8").read()
    edits, keys = [], []
    for start, end, parts in scan(src):
        text_only = "".join(p for p in parts if isinstance(p, str))
        plain = unescape(text_only)
        if not ui_like(plain) or plain in skip:
            continue
        if any(a <= src.count("\n", 0, start) + 1 <= b for a, b in skip_lines):
            continue
        line_start = src.rfind("\n", 0, start) + 1
        before = src[max(line_start, start - 120):start]
        if SKIP_BEFORE.search(before) or SKIP_AFTER.match(src[end:end + 20]):
            continue
        if re.match(r"\s*(?:import|package|@)", src[line_start:start]):
            continue
        used, args, template_raw, key = {}, [], "", ""
        for p in parts:
            if isinstance(p, str):
                template_raw += p
                key += unescape(p)
            else:
                name = name_for(p[1], used)
                template_raw += "{" + name + "}"
                key += "{" + name + "}"
                if f'"{name}" to' not in " ".join(args):
                    args.append(f'"{name}" to ({p[1].strip()})' if not re.fullmatch(r"[\w.]+", p[1].strip()) else f'"{name}" to {p[1].strip()}')
        new = f'tr("{template_raw}"' + (", " + ", ".join(args) if args else "") + ")"
        edits.append((start, end, new))
        line_no = src.count("\n", 0, start) + 1
        keys.append((line_no, key))
    out = src
    for s, e, new in sorted(edits, reverse=True):
        out = out[:s] + new + out[e:]
    if write and edits:
        if "import io.github.veritasx1.linotes.i18n.tr" not in out and "package io.github.veritasx1.linotes.i18n" not in out:
            out = re.sub(r"^(package [^\n]+\n)", r"\1\nimport io.github.veritasx1.linotes.i18n.tr\n", out, count=1)
        open(path, "w", encoding="utf-8").write(out)
    return keys


if __name__ == "__main__":
    args = sys.argv[1:]
    write = "--write" in args
    opts, current, paths = {"--skip": [], "--skip-lines": []}, None, []
    for a in args:
        if a in opts:
            current = a
        elif a != "--write":
            (opts[current] if current else paths).append(a)
    lines = [tuple(map(int, r.split("-"))) for r in opts["--skip-lines"]]
    for path in paths:
        keys = process(path, write, opts["--skip"], lines)
        print(f"# {path}: {len(keys)} Texte")
        for line, key in keys:
            print(f"{line:5}  {json.dumps(key, ensure_ascii=False)}")
