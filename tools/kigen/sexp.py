"""Minimal S-expression reader/writer for KiCad files."""
import re

_TOKEN = re.compile(r'\s*(?:(\()|(\))|("(?:[^"\\]|\\.)*")|([^\s()"]+))')


class Sym(str):
    """Unquoted atom."""


def _unescape(s):
    if "\\" not in s:
        return s
    return re.sub(r"\\(.)", lambda m: "\n" if m.group(1) == "n" else m.group(1), s)


def parse(text):
    stack, cur = [], []
    pos = 0
    n = len(text)
    while pos < n:
        m = _TOKEN.match(text, pos)
        if not m:
            if text[pos:].strip() == "":
                break
            raise ValueError("bad sexp at %d" % pos)
        pos = m.end()
        lp, rp, qs, atom = m.groups()
        if lp:
            stack.append(cur)
            cur = []
        elif rp:
            done = cur
            cur = stack.pop()
            cur.append(done)
        elif qs is not None:
            cur.append(_unescape(qs[1:-1]))
        elif atom is not None:
            cur.append(Sym(atom))
    return cur[0] if len(cur) == 1 else cur


def _q(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def dump(node, indent=0):
    """Serialise a node. Lists are written one per line when they contain lists."""
    if isinstance(node, Sym):
        return str(node)
    if isinstance(node, str):
        return _q(node)
    if isinstance(node, bool):
        return "yes" if node else "no"
    if isinstance(node, float):
        s = ("%.4f" % node).rstrip("0").rstrip(".")
        return "0" if s in ("-0", "") else s
    if isinstance(node, int):
        return str(node)
    parts = [dump(x, indent + 1) for x in node]
    if any(isinstance(x, list) for x in node[1:]):
        pad = "\n" + "  " * (indent + 1)
        head = []
        rest = []
        for x, p in zip(node, parts):
            (rest if (isinstance(x, list) or rest) else head).append(p)
        return "(" + " ".join(head) + "".join(pad + p for p in rest) + "\n" + "  " * indent + ")"
    return "(" + " ".join(parts) + ")"


def find(node, key):
    for x in node:
        if isinstance(x, list) and x and x[0] == key:
            return x
    return None


def find_all(node, key):
    return [x for x in node if isinstance(x, list) and x and x[0] == key]
