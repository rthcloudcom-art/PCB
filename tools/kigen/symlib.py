"""Load KiCad symbol libraries, flatten `extends`, and expose pin geometry."""
import copy
import os
from dataclasses import dataclass

from sexp import Sym, find, find_all, parse

SYM_DIR = os.environ.get("KICAD_SYMBOL_DIR", "/usr/share/kicad/symbols")
FP_DIR = os.environ.get("KICAD_FOOTPRINT_DIR", "/usr/share/kicad/footprints")
# project libraries searched before the stock ones (see add_lib_dir)
SYM_DIRS = [SYM_DIR]
FP_DIRS = [FP_DIR]


def add_lib_dir(path):
    """Register a directory holding <lib>.kicad_sym and <lib>.pretty project libraries."""
    SYM_DIRS.insert(0, path)
    FP_DIRS.insert(0, path)


def _find(dirs, fname):
    for d in dirs:
        p = os.path.join(d, fname)
        if os.path.exists(p):
            return p
    return os.path.join(dirs[-1], fname)


def fp_lib_path(lib):
    return _find(FP_DIRS, lib + ".pretty")

_libs = {}


@dataclass
class Pin:
    number: str
    name: str
    etype: str
    x: float  # library coords (y up)
    y: float
    angle: int
    unit: int
    hidden: bool


class Symbol:
    def __init__(self, lib, name, node):
        self.lib = lib
        self.name = name
        self.node = node  # flattened s-expression, named "lib:name"
        self.pins = []
        self.units = set()
        self.bbox = {}  # unit -> [minx, miny, maxx, maxy] library coords
        for sub in find_all(node, "symbol"):
            _, unit, style = sub[1].rsplit("_", 2)
            unit, style = int(unit), int(style)
            if style > 1:
                continue
            for g in sub[2:]:
                if not isinstance(g, list):
                    continue
                if g[0] == "pin":
                    at = find(g, "at")
                    num = find(g, "number")[1]
                    nm = find(g, "name")[1]
                    hidden = any(x == "hide" for x in g)
                    self.pins.append(Pin(num, nm, str(g[1]), float(at[1]), float(at[2]),
                                         int(float(at[3])) if len(at) > 3 else 0, unit, hidden))
                    ln = find(g, "length")
                    L = float(ln[1]) if ln else 2.54
                    self._grow(unit, float(at[1]), float(at[2]))
                else:
                    for key in ("start", "end", "center", "mid"):
                        p = find(g, key)
                        if p:
                            self._grow(unit, float(p[1]), float(p[2]))
                    pts = find(g, "pts")
                    if pts:
                        for xy in find_all(pts, "xy"):
                            self._grow(unit, float(xy[1]), float(xy[2]))
                    if g[0] == "circle":
                        c, r = find(g, "center"), find(g, "radius")
                        if c and r:
                            cx, cy, rr = float(c[1]), float(c[2]), float(r[1])
                            self._grow(unit, cx - rr, cy - rr)
                            self._grow(unit, cx + rr, cy + rr)
            if unit:
                self.units.add(unit)
        if not self.units:
            self.units = {1}
        # unit 0 graphics/pins are common to every unit
        common = [p for p in self.pins if p.unit == 0]
        if common:
            self.pins = [p for p in self.pins if p.unit != 0]
            for u in self.units:
                for p in common:
                    self.pins.append(Pin(p.number, p.name, p.etype, p.x, p.y, p.angle, u, p.hidden))
        if 0 in self.bbox:
            for u in self.units:
                b0 = self.bbox[0]
                self._grow(u, b0[0], b0[1])
                self._grow(u, b0[2], b0[3])

    def _grow(self, unit, x, y):
        b = self.bbox.setdefault(unit, [x, y, x, y])
        b[0], b[1], b[2], b[3] = min(b[0], x), min(b[1], y), max(b[2], x), max(b[3], y)

    def prop(self, key):
        for p in find_all(self.node, "property"):
            if p[1] == key:
                return p[2]
        return None

    @property
    def is_power(self):
        return find(self.node, "power") is not None

    def pins_by_number(self, num):
        return [p for p in self.pins if p.number == num]


def _load_lib(lib):
    if lib not in _libs:
        path = _find(SYM_DIRS, lib + ".kicad_sym")
        tree = parse(open(path, encoding="utf-8").read())
        _libs[lib] = {s[1]: s for s in find_all(tree, "symbol")}
    return _libs[lib]


def _rename_units(node, old, new):
    for sub in find_all(node, "symbol"):
        if sub[1].startswith(old + "_"):
            sub[1] = new + sub[1][len(old):]


def _flatten(lib, name):
    syms = _load_lib(lib)
    node = copy.deepcopy(syms[name])
    ext = find(node, "extends")
    if ext is None:
        return node
    parent = _flatten(lib, ext[1])
    _rename_units(parent, ext[1], name)
    props = {p[1]: p for p in find_all(node, "property")}
    out = [Sym("symbol"), name]
    for item in parent[2:]:
        if isinstance(item, list) and item[0] == "property" and item[1] in props:
            out.append(props.pop(item[1]))
        else:
            out.append(item)
    # properties only defined on the child
    idx = max(i for i, x in enumerate(out) if isinstance(x, list) and x[0] == "property") + 1
    for p in props.values():
        out.insert(idx, p)
        idx += 1
    return out


_cache = {}


def get(lib_id):
    if lib_id not in _cache:
        lib, name = lib_id.split(":", 1)
        node = _flatten(lib, name)
        node[1] = lib_id
        _cache[lib_id] = Symbol(lib, name, node)
    return _cache[lib_id]


def footprint_pads(fp_id):
    """Return the set of pad numbers of a footprint (for pin/pad cross-checks)."""
    lib, name = fp_id.split(":", 1)
    path = os.path.join(fp_lib_path(lib), name + ".kicad_mod")
    tree = parse(open(path, encoding="utf-8").read())
    return {str(p[1]) for p in find_all(tree, "pad")}


def footprint_exists(fp_id):
    lib, name = fp_id.split(":", 1)
    return os.path.exists(os.path.join(fp_lib_path(lib), name + ".kicad_mod"))
