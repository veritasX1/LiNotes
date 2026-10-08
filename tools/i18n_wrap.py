"""Wraps the user-facing German texts of a Python module in _() for translation.

    python3 tools/i18n_wrap.py linux/linotes/window.py [--write] [--skip "Text" ...]

Reads the syntax tree, so only real string literals are touched. f-strings become
_("… {name} …", name=expr). Left alone: dict keys, comparisons, subscripts, docstrings,
print/log/exception arguments, CSS classes, icon names, settings keys and anything that
does not look like a sentence or label. Without --write it prints what it would change."""

import ast
import json
import re
import sys

SKIP_FUNCS = {"print", "get", "put", "pop", "setdefault", "startswith", "endswith", "split", "rsplit", "join",
              "replace", "strip", "open", "Path", "getattr", "setattr", "hasattr", "add_css_class", "remove_css_class",
              "set_css_classes", "set_name", "connect", "lookup_action", "activate_action", "require_version",
              "SimpleAction", "new", "set_accels_for_action", "get_object", "load_from_data", "load_from_string",
              "_", "N_", "ngettext", "format", "strftime", "strptime", "fromisoformat", "match", "search", "sub",
              "compile", "findall", "fullmatch", "encode", "decode", "debug", "info", "warning", "error", "exception",
              "update_property", "set_icon_name", "icon_button", "glyph", "Image", "new_from_icon_name", "lookup_icon",
              "set_property", "get_property", "emit", "signal_new", "markup_escape_text", "upload", "download", "request",
              "_request", "post", "delete", "query", "execute", "environ", "keyval_from_name", "parse", "add_pattern",
              "add_mime_type", "set_initial_name", "unlink", "exists", "mkdir", "uri", "Variant", "VariantType", "endswith"}
SKIP_KWARGS = {"css_classes", "icon_name", "start_icon_name", "name", "key", "action_name", "detailed_action_name",
               "mime_type", "pattern", "encoding", "mode", "sep", "end", "file", "kind", "type", "application_id",
               "application_icon", "website", "issue_url", "developer_name", "copyright", "license_type", "version"}


def ui_like(s):
    if len(s) < 2 or not re.search(r"[A-Za-zÄÖÜäöüß]", s):
        return False
    if re.fullmatch(r"[a-z0-9_.:/\-#%{}$<>=!]+", s):
        return False
    if s.startswith(("http", "/", "#", "%", "application/", "image/", "text/", "audio/", "<", "win.", "app.", "<?")):
        return False
    if re.fullmatch(r"[A-Z0-9_]+", s):          # constants
        return False
    return bool(re.search(r"[A-ZÄÖÜ][a-zäöüß]|[äöüßÄÖÜ„“…–]| [a-zäöü]", s))


def call_name(node):
    f = node.func
    return f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else ""


class Finder(ast.NodeVisitor):
    def __init__(self, skip, skip_assign=(), skip_calls=()):
        self.found = []          # (node, kind)
        self.parents = []
        self.skip = skip
        self.skip_assign = set(skip_assign)
        self.skip_calls = set(skip_calls)

    def generic_visit(self, node):
        self.parents.append(node)
        super().generic_visit(node)
        self.parents.pop()

    def context_blocks(self, node):
        parent = self.parents[-1] if self.parents else None
        if isinstance(parent, ast.Expr):                 # docstring or bare string
            return True
        if isinstance(parent, ast.Compare):
            return True
        if isinstance(parent, ast.Subscript) and parent.slice is node:
            return True
        if isinstance(parent, ast.Dict) and node in parent.keys:
            return True
        if isinstance(parent, ast.keyword) and parent.arg in SKIP_KWARGS:
            return True
        for p in self.parents:
            if isinstance(p, ast.Assign) and any(isinstance(tg, ast.Name) and tg.id in self.skip_assign for tg in p.targets):
                return True
        for p in reversed(self.parents):
            if isinstance(p, ast.Call):
                if call_name(p) in SKIP_FUNCS or call_name(p) in self.skip_calls:
                    return True
                break
            if isinstance(p, (ast.FunctionDef, ast.ClassDef, ast.Module, ast.Lambda)):
                break
        for p in self.parents:
            if isinstance(p, ast.Raise):
                return False   # exception messages are shown to the user via error dialogs
        return False

    def visit_Constant(self, node):
        if isinstance(node.value, str) and ui_like(node.value) and node.value not in self.skip and not self.context_blocks(node):
            self.found.append((node, "const"))

    def visit_JoinedStr(self, node):
        text = "".join(v.value for v in node.values if isinstance(v, ast.Constant))
        if ui_like(text) and not self.context_blocks(node):
            self.found.append((node, "fstring"))
            return          # do not descend: the parts are handled together
        self.generic_visit(node)


def placeholder(expr, used):
    if isinstance(expr, ast.Name):
        base = expr.id.lstrip("_") or "v"
    elif isinstance(expr, ast.Attribute):
        base = expr.attr.lstrip("_") or "v"
    elif isinstance(expr, ast.Call) and isinstance(expr.func, (ast.Name, ast.Attribute)):
        base = {"len": "count", "get": "name", "user_name": "person", "human_size": "size", "stamp": "date",
                "strftime": "date", "short_id": "id", "str": "value", "int": "number"}.get(call_name(expr), call_name(expr).lstrip("_") or "v")
    else:
        base = "value"
    name, i = base, 2
    while name in used and used[name] != ast.dump(expr):
        name, i = f"{base}{i}", i + 1
    used[name] = ast.dump(expr)
    return name


def convert(source, node, kind):
    seg = ast.get_source_segment(source, node)
    if kind == "const":
        return f"_({json.dumps(node.value, ensure_ascii=False)})", node.value
    used, args, template = {}, [], ""
    for part in node.values:
        if isinstance(part, ast.Constant):
            template += part.value.replace("{", "{{").replace("}", "}}")
        else:
            name = placeholder(part.value, used)
            spec = ""
            if part.conversion and part.conversion != -1:
                spec += "!" + chr(part.conversion)
            if part.format_spec is not None:
                fs = "".join(v.value for v in part.format_spec.values if isinstance(v, ast.Constant))
                spec += ":" + fs
            template += "{" + name + spec + "}"
            expr_src = ast.get_source_segment(source, part.value)
            if f"{name}=" not in [a.split("=")[0] + "=" for a in args]:
                args.append(f"{name}={expr_src}")
    return f"_({json.dumps(template, ensure_ascii=False)}{', ' if args else ''}{', '.join(args)})", template


def process(path, write=False, skip=(), skip_assign=(), skip_calls=()):
    source = open(path, encoding="utf-8").read()
    tree = ast.parse(source)
    finder = Finder(set(skip), skip_assign, skip_calls)
    finder.visit(tree)
    lines = source.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    def pos(lineno, col):  # col is a UTF-8 byte offset
        line = lines[lineno - 1]
        return offsets[lineno - 1] + len(line.encode("utf-8")[:col].decode("utf-8", "ignore"))
    edits, keys = [], []
    for node, kind in finder.found:
        new, key = convert(source, node, kind)
        edits.append((pos(node.lineno, node.col_offset), pos(node.end_lineno, node.end_col_offset), new))
        keys.append((node.lineno, key))
    out = source
    for start, end, new in sorted(edits, reverse=True):
        out = out[:start] + new + out[end:]
    if write and edits:
        if "from .i18n import" not in out:
            # after the last top-level import
            body = ast.parse(source).body
            last = max((n.end_lineno for n in body if isinstance(n, (ast.Import, ast.ImportFrom))), default=0)
            out_lines = out.splitlines(keepends=True)
            # line numbers shift only inside edited lines; imports precede all UI strings
            out_lines.insert(last, "from .i18n import _\n")
            out = "".join(out_lines)
        ast.parse(out)   # must still be valid Python
        open(path, "w", encoding="utf-8").write(out)
    return keys


if __name__ == "__main__":
    args = sys.argv[1:]
    write = "--write" in args
    opts = {"--skip": [], "--skip-assign": [], "--skip-call": []}
    current = None
    paths = []
    for a in args:
        if a in opts:
            current = a
        elif a == "--write":
            pass
        elif current:
            opts[current].append(a)
        else:
            paths.append(a)
    for path in paths:
        keys = process(path, write, opts["--skip"], opts["--skip-assign"], opts["--skip-call"])
        print(f"# {path}: {len(keys)} Texte")
        for line, key in keys:
            print(f"{line:5}  {key}")
