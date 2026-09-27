"""Write a hierarchical KiCad 7 schematic from a `circuit.Circuit`.

Every pin gets a short wire stub ending in a net label (local label for nets
used on one sheet, global label for nets shared between sheets, power symbol
for GND/+3V3/+5V). Parts are packed into titled, framed blocks.
"""
import os

import symlib
from circuit import NC, POWER_SYMBOLS, stable_uuid
from sexp import Sym, dump

G = 2.54
STUB = 2.54
PAPERS = [("A4", 297, 210), ("A3", 420, 297), ("A2", 594, 420), ("A1", 841, 594), ("A0", 1189, 841)]
MARGIN = 12.7
TITLE_H = 40.0
CELL_GAP = 5.08
BLOCK_PAD = 5.08
BLOCK_HEAD = 7.62


def snap(v, g=G):
    return round(v / g) * g


def r4(v):
    return round(v, 4)


def font(size=1.27, bold=False, italic=False):
    f = [Sym("font"), [Sym("size"), size, size]]
    if bold:
        f.append(Sym("bold"))
    if italic:
        f.append(Sym("italic"))
    return f


def effects(size=1.27, justify=None, hide=False, bold=False):
    e = [Sym("effects"), font(size, bold)]
    if justify:
        e.append([Sym("justify")] + [Sym(j) for j in justify.split()])
    if hide:
        e.append(Sym("hide"))
    return e


def outward(angle):
    return {0: (-1, 0), 180: (1, 0), 90: (0, 1), 270: (0, -1)}[angle % 360]


def label_len(text, glob=False):
    return len(text) * 1.05 + (4.0 if glob else 1.0)


class UnitCell:
    """Placement data for one unit of one part."""

    def __init__(self, part, unit, net_scope):
        self.part = part
        self.unit = unit
        sym = part.sym
        bb = sym.bbox.get(unit) or sym.bbox.get(0) or [-2.54, -2.54, 2.54, 2.54]
        # symbol bbox in schematic orientation (relative to origin)
        x0, x1 = bb[0], bb[2]
        y0, y1 = -bb[3], -bb[1]
        # include visible Reference/Value text
        from sexp import find, find_all
        texts = {"Reference": (part.ref or part.prefix) + "9", "Value": part.value}
        if part.prefix.startswith("#"):
            texts.pop("Reference")
        if True:
            for lp in find_all(sym.node, "property"):
                if lp[1] not in texts:
                    continue
                at_ = find(lp, "at")
                eff = find(lp, "effects")
                if any(x == "hide" for x in eff):
                    continue
                tx, ty = float(at_[1]), -float(at_[2])
                ang = float(at_[3]) if len(at_) > 3 else 0
                just = find(eff, "justify")
                j = [str(v) for v in just[1:]] if just else []
                w = len(texts[lp[1]]) * 1.1
                if "left" in j:
                    a, b = 0, w
                elif "right" in j:
                    a, b = -w, 0
                else:
                    a, b = -w / 2, w / 2
                if ang in (90, 270):
                    x0, x1 = min(x0, tx - 1), max(x1, tx + 1)
                    y0, y1 = min(y0, ty - b), max(y1, ty - a)
                else:
                    x0, x1 = min(x0, tx + a), max(x1, tx + b)
                    y0, y1 = min(y0, ty - 1), max(y1, ty + 1)
        ext = {"l": 0.0, "r": 0.0, "u": 0.0, "d": 0.0}
        self.pins = []
        seen = set()
        for pin in sym.pins:
            if pin.unit != unit:
                continue
            key = (pin.x, pin.y)
            if key in seen:
                continue
            grp = [q for q in sym.pins if q.unit == unit and (q.x, q.y) == key]
            vis = [q for q in grp if not q.hidden] or grp
            seen.add(key)
            net = part.nets.get(vis[0].number)
            for q in grp:
                if part.nets.get(q.number) != net:
                    raise ValueError("%s: stacked pins %s disagree" % (part.ref, [q.number for q in grp]))
            self.pins.append((vis[0], net))
            if net is NC or net is None:
                continue
            dx, dy = outward(pin.angle)
            if net in POWER_SYMBOLS:
                L = STUB + 5.0
            else:
                L = STUB + label_len(net, net_scope.get(net) == "global")
            px, py = pin.x, -pin.y
            if dx < 0:
                ext["l"] = max(ext["l"], (x0 - px) + L)
            if dx > 0:
                ext["r"] = max(ext["r"], (px - x1) + L)
            if dy < 0:
                ext["u"] = max(ext["u"], (y0 - py) + L)
            if dy > 0:
                ext["d"] = max(ext["d"], (py - y1) + L)
        # room for reference/value text
        ext["u"] = max(ext["u"], 3.0)
        ext["d"] = max(ext["d"], 3.0)
        self.left = x0 - ext["l"]
        self.top = y0 - ext["u"]
        self.w = (x1 + ext["r"]) - self.left
        self.h = (y1 + ext["d"]) - self.top
        self.origin = None


class SchWriter:
    def __init__(self, circuit, outdir):
        self.c = circuit
        self.outdir = outdir
        self.root_uuid = stable_uuid(circuit.name, "root")
        self.pwr_count = 0
        # net scope: global if the net appears on more than one sheet
        where = {}
        for s in circuit.sheets:
            for p in s.parts:
                for net in p.nets.values():
                    if net is NC or net is None:
                        continue
                    where.setdefault(net, set()).add(s.name)
        self.scope = {n: ("global" if len(v) > 1 else "local") for n, v in where.items()}

    # ------------------------------------------------------------------ layout
    def layout(self, sheet):
        blocks = []
        for b in sheet.blocks:
            cells = [UnitCell(p, u, self.scope) for p in b.parts for u in sorted(p.sym.units)]
            if not cells:
                continue
            blocks.append((b, cells))
        for name, pw, ph in PAPERS:
            if PAPERS.index((name, pw, ph)) < [p[0] for p in PAPERS].index(sheet.paper):
                continue
            ok, placed = self._pack(blocks, pw, ph)
            if ok:
                return name, pw, ph, placed
        raise ValueError("sheet %s does not fit on A0" % sheet.name)

    def _pack(self, blocks, pw, ph):
        usable_w = pw - 2 * MARGIN
        max_block_w = min(usable_w, max(usable_w / 2.0, 190.0))
        frames = []
        for b, cells in blocks:
            # row-wrap cells inside the block
            x = y = 0.0
            row_h = 0.0
            wmax = 0.0
            pos = []
            inner_w = max(max_block_w - 2 * BLOCK_PAD, max(c.w for c in cells))
            for c in cells:
                if x > 0 and x + c.w > inner_w:
                    x = 0.0
                    y += row_h + CELL_GAP
                    row_h = 0.0
                pos.append((c, x, y))
                x += c.w + CELL_GAP
                row_h = max(row_h, c.h)
                wmax = max(wmax, x - CELL_GAP)
            head = BLOCK_HEAD + (3.81 if b.notes else 0)
            bw = max(wmax + 2 * BLOCK_PAD, len(b.title) * 1.75 + 6, len(b.notes) * 1.1 + 6)
            bh = y + row_h + BLOCK_PAD * 2 + head
            b._head = head
            frames.append((b, pos, bw, bh))
        # shelf-pack blocks
        x, y = MARGIN, MARGIN
        row_h = 0.0
        placed = []
        for b, pos, bw, bh in frames:
            if x > MARGIN and x + bw > pw - MARGIN:
                x = MARGIN
                y += row_h + CELL_GAP
                row_h = 0.0
            if bw > pw - 2 * MARGIN:
                return False, None
            placed.append((b, pos, x, y, bw, bh))
            x += bw + CELL_GAP
            row_h = max(row_h, bh)
        bottom = y + row_h
        if bottom > ph - MARGIN - TITLE_H:
            # allow overlap with the title-block row only left of the title block
            return False, None
        return True, placed

    # --------------------------------------------------------------- emitting
    def _instances(self, sheet, ref, unit):
        path = "/" + self.root_uuid + "/" + stable_uuid(self.c.name, "sheet", sheet.name)
        return [Sym("instances"), [Sym("project"), self.c.name,
                                   [Sym("path"), path, [Sym("reference"), ref], [Sym("unit"), unit]]]]

    def _symbol(self, sheet, lib_id, at, unit, ref, value, footprint, uid, props=None,
                bom=True, board=True, rot=0, hide_ref=False, dnp=False):
        sym = symlib.get(lib_id)
        X, Y = at
        node = [Sym("symbol"), [Sym("lib_id"), lib_id], [Sym("at"), r4(X), r4(Y), rot], [Sym("unit"), unit],
                [Sym("in_bom"), Sym("yes" if bom else "no")], [Sym("on_board"), Sym("yes" if board else "no")],
                [Sym("dnp"), Sym("yes" if dnp else "no")], [Sym("uuid"), uid]]
        values = {"Reference": ref, "Value": value, "Footprint": footprint,
                  "Datasheet": sym.prop("Datasheet") or "~"}
        values.update(props or {})
        from sexp import find, find_all
        lib_props = {p[1]: p for p in find_all(sym.node, "property")}
        extra_y = 0
        for key, val in values.items():
            lp = lib_props.get(key)
            if lp is not None:
                at_ = find(lp, "at")
                px, py, pa = float(at_[1]), float(at_[2]), float(at_[3]) if len(at_) > 3 else 0
                # rotate library offset with the symbol
                if rot == 90:
                    px, py = -py, px
                    pa = (pa + 90) % 180
                eff = find(lp, "effects")
                hidden = any(x == "hide" for x in eff)
                just = find(eff, "justify")
                jtxt = " ".join(str(j) for j in just[1:]) if just else None
            else:
                px, py, pa, hidden, jtxt = 0, -extra_y, 0, True, None
                extra_y += 2.54
            if key == "Reference" and hide_ref:
                hidden = True
            if key not in ("Reference", "Value") and lp is None:
                hidden = True
            node.append([Sym("property"), key, val, [Sym("at"), r4(X + px), r4(Y - py), pa],
                         effects(justify=jtxt, hide=hidden)])
        for num in sorted({p.number for p in sym.pins if p.unit in (unit, 0)}):
            node.append([Sym("pin"), num, [Sym("uuid"), stable_uuid(uid, "pin", num)]])
        node.append(self._instances(sheet, ref, unit))
        return node

    def _label(self, net, x, y, d, uid):
        dx, dy = d
        ang = {(-1, 0): 180, (1, 0): 0, (0, -1): 90, (0, 1): 270}[d]
        glob = self.scope.get(net) == "global"
        if glob:
            just = "left" if ang in (0, 90) else "right"
            return [Sym("global_label"), net, [Sym("shape"), Sym("passive")], [Sym("at"), r4(x), r4(y), ang],
                    [Sym("fields_autoplaced")], effects(justify=just), [Sym("uuid"), uid],
                    [Sym("property"), "Intersheetrefs", "${INTERSHEET_REFS}", [Sym("at"), r4(x), r4(y), 0],
                     effects(justify=just, hide=True)]]
        just = "left bottom" if ang in (0, 90) else "right bottom"
        return [Sym("label"), net, [Sym("at"), r4(x), r4(y), ang], [Sym("fields_autoplaced")],
                effects(justify=just), [Sym("uuid"), uid]]

    def _power(self, sheet, net, x, y, d, uid):
        lib_id = POWER_SYMBOLS[net]
        if net == "GND":
            rot = {(0, 1): 0, (0, -1): 180, (1, 0): 90, (-1, 0): 270}[d]
        else:
            rot = {(0, -1): 0, (0, 1): 180, (1, 0): 270, (-1, 0): 90}[d]
        self.pwr_count += 1
        ref = "#PWR0%d" % self.pwr_count
        node = self._symbol(sheet, lib_id, (x, y), 1, ref, net, "", uid, bom=False, board=False, hide_ref=True)
        node[2][3] = rot
        # value text sits beyond the symbol, in the stub direction
        for item in node:
            if isinstance(item, list) and item and item[0] == "property" and item[1] == "Value":
                item[3] = [Sym("at"), r4(x + d[0] * 3.81), r4(y + d[1] * 3.81 + (0.6 if d[1] == 0 else 0)), 90 if rot in (90, 270) else 0]
                just = {(-1, 0): "right", (1, 0): "left"}.get(d)
                if rot == 90 and just:
                    just = {"right": "left", "left": "right"}[just]
                item[4] = effects(justify=just)
        return node

    def write_sheet(self, sheet, page):
        paper, pw, ph, placed = self.layout(sheet)
        sheet_uuid = stable_uuid(self.c.name, "sheetfile", sheet.name)
        items = []
        used_libs = set()
        for b, pos, bx, by, bw, bh in placed:
            items.append([Sym("rectangle"), [Sym("start"), r4(bx), r4(by)], [Sym("end"), r4(bx + bw), r4(by + bh)],
                          [Sym("stroke"), [Sym("width"), 0.254], [Sym("type"), Sym("dash")]],
                          [Sym("fill"), [Sym("type"), Sym("none")]],
                          [Sym("uuid"), stable_uuid(sheet.name, "frame", b.title)]])
            items.append([Sym("text"), b.title, [Sym("at"), r4(bx + 2.54), r4(by + 5.08), 0],
                          effects(size=2.0, justify="left bottom", bold=True),
                          [Sym("uuid"), stable_uuid(sheet.name, "title", b.title)]])
            if b.notes:
                items.append([Sym("text"), b.notes, [Sym("at"), r4(bx + 2.54), r4(by + 8.89), 0],
                              effects(size=1.27, justify="left bottom"),
                              [Sym("uuid"), stable_uuid(sheet.name, "notes", b.title)]])
            for cell, cx, cy in pos:
                ox = snap(bx + BLOCK_PAD + cx - cell.left)
                oy = snap(by + BLOCK_PAD + b._head + cy - cell.top)
                p = cell.part
                uid = stable_uuid(self.c.name, sheet.name, p.ref, cell.unit)
                used_libs.add(p.lib_id)
                items.append(self._symbol(sheet, p.lib_id, (ox, oy), cell.unit, p.ref, p.value, p.footprint, uid,
                                          props=p.fields, bom=p.bom, board=p.bom, dnp=p.dnp,
                                          hide_ref=p.prefix.startswith("#")))
                for pin, net in cell.pins:
                    x, y = ox + pin.x, oy - pin.y
                    pu = stable_uuid(uid, "net", pin.number)
                    if net is NC or net is None:
                        items.append([Sym("no_connect"), [Sym("at"), r4(x), r4(y)], [Sym("uuid"), pu]])
                        continue
                    d = outward(pin.angle)
                    ex, ey = x + d[0] * STUB, y + d[1] * STUB
                    items.append([Sym("wire"), [Sym("pts"), [Sym("xy"), r4(x), r4(y)], [Sym("xy"), r4(ex), r4(ey)]],
                                  [Sym("stroke"), [Sym("width"), 0], [Sym("type"), Sym("default")]],
                                  [Sym("uuid"), stable_uuid(pu, "w")]])
                    if net in POWER_SYMBOLS:
                        used_libs.add(POWER_SYMBOLS[net])
                        items.append(self._power(sheet, net, ex, ey, d, stable_uuid(pu, "p")))
                    else:
                        items.append(self._label(net, ex, ey, d, stable_uuid(pu, "l")))
        lib_symbols = [Sym("lib_symbols")] + [symlib.get(l).node for l in sorted(used_libs)]
        doc = [Sym("kicad_sch"), [Sym("version"), 20230121], [Sym("generator"), Sym("eeschema")],
               [Sym("uuid"), sheet_uuid], [Sym("paper"), paper], self._title_block(sheet.title, page),
               lib_symbols] + items
        with open(os.path.join(self.outdir, sheet.filename), "w", encoding="utf-8") as f:
            f.write(dump(doc) + "\n")
        return paper

    def _title_block(self, title, page):
        c = self.c
        return [Sym("title_block"), [Sym("title"), "%s - %s" % (c.title, title)], [Sym("date"), c.date],
                [Sym("rev"), c.rev], [Sym("company"), c.company],
                [Sym("comment"), 1, "Generated by tools/kigen from the Python design source - edit the source, not this file"]]

    def write_root(self, notes=()):
        items = []
        x, y = MARGIN + 10, MARGIN + 30
        w, h = 60.96, 20.32
        for i, s in enumerate(self.c.sheets):
            su = stable_uuid(self.c.name, "sheet", s.name)
            items.append([Sym("sheet"), [Sym("at"), r4(x), r4(y)], [Sym("size"), w, h], [Sym("fields_autoplaced")],
                          [Sym("stroke"), [Sym("width"), 0.1524], [Sym("type"), Sym("solid")]],
                          [Sym("fill"), [Sym("color"), 0, 0, 0, 0.0]],
                          [Sym("uuid"), su],
                          [Sym("property"), "Sheetname", s.title, [Sym("at"), r4(x), r4(y - 0.7112), 0],
                           effects(justify="left bottom")],
                          [Sym("property"), "Sheetfile", s.filename, [Sym("at"), r4(x), r4(y + h + 0.5846), 0],
                           effects(justify="left top", hide=False)],
                          [Sym("instances"), [Sym("project"), self.c.name,
                                              [Sym("path"), "/" + self.root_uuid, [Sym("page"), str(i + 2)]]]]])
            x += w + 20.32
            if x + w > 420 - MARGIN:
                x = MARGIN + 10
                y += h + 20.32
        ty = y + h + 20.32
        for i, line in enumerate(notes):
            items.append([Sym("text"), line, [Sym("at"), MARGIN + 10, r4(ty + i * 5.08), 0],
                          effects(size=2.0 if i == 0 else 1.5, justify="left bottom", bold=(i == 0)),
                          [Sym("uuid"), stable_uuid(self.c.name, "rootnote", i)]])
        doc = [Sym("kicad_sch"), [Sym("version"), 20230121], [Sym("generator"), Sym("eeschema")],
               [Sym("uuid"), self.root_uuid], [Sym("paper"), "A3"], self._title_block("Overview", 1),
               [Sym("lib_symbols")]] + items + [
            [Sym("sheet_instances"), [Sym("path"), "/", [Sym("page"), "1"]]]]
        with open(os.path.join(self.outdir, self.c.name + ".kicad_sch"), "w", encoding="utf-8") as f:
            f.write(dump(doc) + "\n")


def write(circuit, outdir, notes=()):
    os.makedirs(outdir, exist_ok=True)
    circuit.annotate()
    circuit.check()
    w = SchWriter(circuit, outdir)
    papers = {}
    for i, s in enumerate(circuit.sheets):
        papers[s.name] = w.write_sheet(s, i + 2)
    w.write_root(notes)
    return papers
