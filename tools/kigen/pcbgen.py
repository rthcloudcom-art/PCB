"""PCB helpers on top of KiCad 7 `pcbnew`: footprint creation from a Circuit,
bbox-based placement, net classes, Specctra round trip through Freerouting."""
import os
import re
import subprocess

import pcbnew

from circuit import stable_uuid
from sexp import find, find_all, parse

FP_DIR = "/usr/share/kicad/footprints"
MM = pcbnew.FromMM


def V(x, y):
    return pcbnew.VECTOR2I(MM(x), MM(y))


def load_kicad_netlist(path):
    """(ref, pin) -> KiCad net name, taken from `kicad-cli sch export netlist`."""
    tree = parse(open(path, encoding="utf-8").read())
    pin_net = {}
    for net in find_all(find(tree, "nets"), "net"):
        name = find(net, "name")[1]
        for n in find_all(net, "node"):
            pin_net[(find(n, "ref")[1], find(n, "pin")[1])] = name
    return pin_net


class BoardBuilder:
    def __init__(self, circuit, path, origin=(40.0, 40.0)):
        self.c = circuit
        self.path = path
        self.ox, self.oy = origin
        self.board = pcbnew.NewBoard(path)
        self.board.SetCopperLayerCount(4)
        ds = self.board.GetDesignSettings()
        ds.m_MinThroughDrill = MM(0.2)
        ds.m_HoleToHoleMin = MM(0.2)
        self.fps = {}  # ref -> FOOTPRINT
        self.part_of = {}  # ref -> Part
        self.block_of = {}  # ref -> block title
        self.nets = {}

    # ------------------------------------------------------------- creation
    def net(self, name):
        if name not in self.nets:
            n = pcbnew.NETINFO_ITEM(self.board, name)
            self.board.Add(n)
            self.nets[name] = n
        return self.nets[name]

    def add_footprints(self, pin_net):
        for s in self.c.sheets:
            sheet_uuid = stable_uuid(self.c.name, "sheet", s.name)
            for b in s.blocks:
                for p in b.parts:
                    if not p.footprint or p.ref.startswith("#"):
                        continue
                    lib, name = p.footprint.split(":", 1)
                    import symlib
                    fp = pcbnew.FootprintLoad(symlib.fp_lib_path(lib), name)
                    fp.SetFPID(pcbnew.LIB_ID(lib, name))
                    fp.SetReference(p.ref)
                    fp.SetValue(p.value)
                    unit = min(p.sym.units)
                    sym_uuid = stable_uuid(self.c.name, s.name, p.ref, unit)
                    fp.SetPath(pcbnew.KIID_PATH("/%s/%s" % (sheet_uuid, sym_uuid)))
                    self.board.Add(fp)
                    for pad in fp.Pads():
                        net = pin_net.get((p.ref, pad.GetNumber()))
                        if net:
                            pad.SetNet(self.net(net))
                    self.fps[p.ref] = fp
                    self.part_of[p.ref] = p
                    self.block_of[p.ref] = b.title

    # ------------------------------------------------------------ placement
    def bbox(self, fp):
        if getattr(fp, "_fab_bbox", False):
            bb = pcbnew.BOX2I()
            first = True
            for item in list(fp.Pads()) + [g for g in fp.GraphicalItems() if g.GetLayer() == pcbnew.F_Fab]:
                ib = item.GetBoundingBox()
                if first:
                    bb, first = ib, False
                else:
                    bb.Merge(ib)
        else:
            bb = fp.GetBoundingBox(False, False)
        return (pcbnew.ToMM(bb.GetX()) - self.ox, pcbnew.ToMM(bb.GetY()) - self.oy,
                pcbnew.ToMM(bb.GetRight()) - self.ox, pcbnew.ToMM(bb.GetBottom()) - self.oy)

    def put(self, ref, x, y, rot=0, anchor="tl", back=False):
        """Rotate, then move so the footprint bbox corner `anchor` lands on (x, y) (board mm)."""
        fp = self.fps[ref]
        if back and not fp.IsFlipped():
            fp.Flip(fp.GetPosition(), False)
        fp.SetOrientationDegrees(rot)
        x0, y0, x1, y1 = self.bbox(fp)
        ax = {"l": x0, "r": x1, "c": (x0 + x1) / 2}
        ay = {"t": y0, "b": y1, "c": (y0 + y1) / 2}
        dx = x - ax[anchor[1] if len(anchor) > 1 else "c"]
        dy = y - ay[anchor[0]]
        pos = fp.GetPosition()
        fp.SetPosition(pcbnew.VECTOR2I(pos.x + MM(dx), pos.y + MM(dy)))
        fp._placed = True

    def pack(self, refs, x0, y0, x1, y1, gap=1.0):
        """Row-pack footprints into a rectangle. Returns refs that did not fit."""
        x, y, row_h = x0, y0, 0.0
        overflow = []
        for ref in refs:
            fp = self.fps[ref]
            fp.SetOrientationDegrees(0)
            bx0, by0, bx1, by1 = self.bbox(fp)
            w, h = bx1 - bx0, by1 - by0
            if x > x0 and x + w > x1:
                x, y, row_h = x0, y + row_h + gap, 0.0
            if y + h > y1:
                overflow.append(ref)
            self.put(ref, x, y)
            x += w + gap
            row_h = max(row_h, h)
        return overflow

    def pack_free(self, refs, x0, y0, x1, y1, gap=0.8, step=0.5):
        """Place each footprint at the first free spot (scanning rows) inside the rectangle,
        avoiding everything already placed. Returns refs that found no room."""
        def side(fp):
            return "B" if fp.IsFlipped() else "F"

        def tht(fp):
            return not is_smd(fp)
        placed = [(self.bbox(f), side(f), tht(f)) for r, f in self.fps.items()
                  if getattr(f, "_placed", False) and r not in refs]
        missing = []
        for ref in refs:
            fp = self.fps[ref]
            fp.SetOrientationDegrees(0)
            bx0, by0, bx1, by1 = self.bbox(fp)
            w, h = bx1 - bx0, by1 - by0
            s_me, t_me = side(fp), tht(fp)
            spot = None
            y = y0
            while spot is None and y + h <= y1 + 1e-6:
                x = x0
                while x + w <= x1 + 1e-6:
                    ok = True
                    for (a0, b0, a1, b1), s_o, t_o in placed:
                        if s_o != s_me and not (t_o or t_me):
                            continue
                        if x < a1 + gap and a0 < x + w + gap and y < b1 + gap and b0 < y + h + gap:
                            ok = False
                            x = max(x + step, a1 + gap)
                            break
                    if ok:
                        spot = (x, y)
                        break
                y += step
            if spot is None:
                missing.append(ref)
                continue
            self.put(ref, spot[0], spot[1])
            placed.append((self.bbox(fp), s_me, t_me))
        return missing

    def overlaps(self, clearance=0.0):
        items = [(r, self.bbox(f)) for r, f in self.fps.items()]
        bad = []
        for i, (ra, a) in enumerate(items):
            for rb, b in items[i + 1:]:
                if self.fps[ra].IsFlipped() != self.fps[rb].IsFlipped():
                    if not (self.fps[ra].GetAttributes() & pcbnew.FP_THROUGH_HOLE or
                            self.fps[rb].GetAttributes() & pcbnew.FP_THROUGH_HOLE):
                        continue
                if a[0] < b[2] - clearance and b[0] < a[2] - clearance and \
                        a[1] < b[3] - clearance and b[1] < a[3] - clearance:
                    bad.append((ra, rb))
        return bad

    # ------------------------------------------------------------- graphics
    def outline(self, w, h, r=3.0):
        self.w, self.h = w, h
        pts = [(r, 0), (w - r, 0), (w, r), (w, h - r), (w - r, h), (r, h), (0, h - r), (0, r)]
        segs = [((r, 0), (w - r, 0)), ((w, r), (w, h - r)), ((w - r, h), (r, h)), ((0, h - r), (0, r))]
        for a, b in segs:
            s = pcbnew.PCB_SHAPE(self.board)
            s.SetShape(pcbnew.SHAPE_T_SEGMENT)
            s.SetLayer(pcbnew.Edge_Cuts)
            s.SetWidth(MM(0.1))
            s.SetStart(V(a[0] + self.ox, a[1] + self.oy))
            s.SetEnd(V(b[0] + self.ox, b[1] + self.oy))
            self.board.Add(s)
        import math
        k = r * (1 - 1 / math.sqrt(2))
        arcs = [((0, r), (k, k), (r, 0)), ((w - r, 0), (w - k, k), (w, r)),
                ((w, h - r), (w - k, h - k), (w - r, h)), ((r, h), (k, h - k), (0, h - r))]
        for st, md, en in arcs:
            s = pcbnew.PCB_SHAPE(self.board)
            s.SetShape(pcbnew.SHAPE_T_ARC)
            s.SetLayer(pcbnew.Edge_Cuts)
            s.SetWidth(MM(0.1))
            s.SetArcGeometry(V(st[0] + self.ox, st[1] + self.oy), V(md[0] + self.ox, md[1] + self.oy),
                             V(en[0] + self.ox, en[1] + self.oy))
            self.board.Add(s)
        del pts

    def slot(self, x0, y0, x1, y1, width=2.0):
        """Milled isolation slot (drawn as closed outline on Edge.Cuts)."""
        hw = width / 2.0
        if abs(x1 - x0) >= abs(y1 - y0):
            poly = [(x0, y0 - hw), (x1, y0 - hw), (x1, y0 + hw), (x0, y0 + hw)]
        else:
            poly = [(x0 - hw, y0), (x0 + hw, y0), (x0 + hw, y1), (x0 - hw, y1)]
        for i in range(4):
            a, b = poly[i], poly[(i + 1) % 4]
            s = pcbnew.PCB_SHAPE(self.board)
            s.SetShape(pcbnew.SHAPE_T_SEGMENT)
            s.SetLayer(pcbnew.Edge_Cuts)
            s.SetWidth(MM(0.1))
            s.SetStart(V(a[0] + self.ox, a[1] + self.oy))
            s.SetEnd(V(b[0] + self.ox, b[1] + self.oy))
            self.board.Add(s)

    def text(self, txt, x, y, size=1.5, layer=pcbnew.F_SilkS, angle=0):
        t = pcbnew.PCB_TEXT(self.board)
        t.SetText(txt)
        t.SetLayer(layer)
        t.SetPosition(V(x + self.ox, y + self.oy))
        t.SetTextSize(pcbnew.VECTOR2I(MM(size), MM(size)))
        t.SetTextThickness(MM(size * 0.15))
        t.SetTextAngleDegrees(angle)
        if layer in (pcbnew.B_SilkS,):
            t.SetMirrored(True)
        self.board.Add(t)

    def line(self, x0, y0, x1, y1, layer=pcbnew.F_SilkS, width=0.2):
        s = pcbnew.PCB_SHAPE(self.board)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetLayer(layer)
        s.SetWidth(MM(width))
        s.SetStart(V(x0 + self.ox, y0 + self.oy))
        s.SetEnd(V(x1 + self.ox, y1 + self.oy))
        self.board.Add(s)

    def zone(self, net, layer, poly, priority=0, clearance=0.3, min_width=0.25, keepout=False, name=""):
        z = pcbnew.ZONE(self.board)
        z.SetLayer(layer)
        if keepout:
            z.SetIsRuleArea(True)
            z.SetDoNotAllowCopperPour(True)
            z.SetDoNotAllowVias(False)
            z.SetDoNotAllowTracks(False)
            z.SetDoNotAllowPads(False)
            z.SetDoNotAllowFootprints(False)
        else:
            z.SetNet(self.net(net))
            z.SetLocalClearance(MM(clearance))
            z.SetMinThickness(MM(min_width))
            z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
            z.SetThermalReliefGap(MM(0.4))
            z.SetThermalReliefSpokeWidth(MM(0.5))
        z.SetAssignedPriority(priority)
        if name:
            z.SetZoneName(name)
        ol = z.Outline()
        ol.NewOutline()
        for x, y in poly:
            ol.Append(MM(x + self.ox), MM(y + self.oy))
        self.board.Add(z)
        return z

    # ---------------------------------------------------------------- rules
    def netclasses(self, classes, assign):
        """classes: name -> dict(track, clearance, via, drill); assign: [(wildcard, class)] on full net name."""
        import fnmatch
        ds = self.board.GetDesignSettings()
        ns = ds.m_NetSettings
        objs = {}
        for name, r in classes.items():
            nc = pcbnew.NETCLASS(name)
            nc.SetTrackWidth(MM(r["track"]))
            nc.SetClearance(MM(r["clearance"]))
            nc.SetViaDiameter(MM(r.get("via", 0.6)))
            nc.SetViaDrill(MM(r.get("drill", 0.3)))
            if name == "Default":
                ns.m_DefaultNetClass = nc
            else:
                ns.m_NetClasses[name] = nc
            objs[name] = nc
        for netname, n in self.nets.items():
            cls = "Default"
            for pat, c in assign:
                if fnmatch.fnmatchcase(netname, pat):
                    cls = c
                    break
            n.SetNetClass(objs[cls])
        return objs

    def save(self):
        self.board.Save(self.path)


# ------------------------------------------------------------- routing I/O
def load(board_path):
    """Load a board and resolve net classes from the project's wildcard patterns."""
    b = pcbnew.LoadBoard(board_path)
    b.SynchronizeNetsAndNetClasses(True)
    return b


def freeroute(board_path, dsn, ses, jar, java, passes=40, timeout=3600):
    b = load(board_path)
    if not pcbnew.ExportSpecctraDSN(b, dsn):
        raise RuntimeError("DSN export failed")
    cmd = [java, "-Djava.awt.headless=true", "-jar", jar, "-de", dsn, "-do", ses, "-mp", str(passes), "-mt", "4",
           "--gui.enabled=false"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    log = r.stdout + r.stderr
    if not os.path.exists(ses):
        raise RuntimeError("freerouting produced no session:\n" + log[-3000:])
    return log


def import_ses(board, ses_path):
    """Add wires and vias from a Specctra session file (KiCad 7 has no headless importer)."""
    tree = parse(open(ses_path, encoding="utf-8").read())
    routes = find(tree, "routes")
    res = find(routes, "resolution")
    scale = {"um": 1e-3, "mm": 1.0, "mil": 0.0254, "inch": 25.4}[str(res[1])] / float(res[2])
    layers = {board.GetLayerName(l): l for l in range(pcbnew.PCB_LAYER_ID_COUNT)}
    padstacks = {}
    lib = find(routes, "library_out")
    if lib:
        for ps in find_all(lib, "padstack"):
            m = re.search(r"_(\d+):(\d+)_um", ps[1])
            if m:
                padstacks[ps[1]] = (int(m.group(1)) / 1000.0, int(m.group(2)) / 1000.0)
    netmap = {n.GetNetname(): n for n in board.GetNetInfo().NetsByName().values()}
    ntracks = nvias = 0
    for net in find_all(find(routes, "network_out"), "net"):
        ni = netmap.get(net[1])
        for w in find_all(net, "wire"):
            path = find(w, "path")
            layer = layers[str(path[1])]
            width = float(path[2]) * scale
            pts = [float(v) * scale for v in path[3:]]
            xy = [(pts[i], -pts[i + 1]) for i in range(0, len(pts) - 1, 2)]
            for a, b in zip(xy, xy[1:]):
                t = pcbnew.PCB_TRACK(board)
                t.SetStart(pcbnew.VECTOR2I(MM(a[0]), MM(a[1])))
                t.SetEnd(pcbnew.VECTOR2I(MM(b[0]), MM(b[1])))
                t.SetWidth(MM(width))
                t.SetLayer(layer)
                if ni:
                    t.SetNet(ni)
                board.Add(t)
                ntracks += 1
        for v in find_all(net, "via"):
            dia, drill = padstacks.get(v[1], (0.6, 0.3))
            via = pcbnew.PCB_VIA(board)
            via.SetPosition(pcbnew.VECTOR2I(MM(float(v[2]) * scale), MM(-float(v[3]) * scale)))
            via.SetWidth(MM(dia))
            via.SetDrill(MM(drill))
            via.SetViaType(pcbnew.VIATYPE_THROUGH)
            via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
            if ni:
                via.SetNet(ni)
            board.Add(via)
            nvias += 1
    return ntracks, nvias


def write_project_netclasses(pro_path, classes, assign):
    """Store net classes + wildcard assignments in the KiCad 7 project file (where KiCad keeps them)."""
    import json
    pro = json.load(open(pro_path))
    ns = pro.setdefault("net_settings", {})
    base = dict(bus_width=12, diff_pair_gap=0.25, diff_pair_via_gap=0.25, diff_pair_width=0.2, line_style=0,
                microvia_diameter=0.3, microvia_drill=0.1, pcb_color="rgba(0, 0, 0, 0.000)",
                schematic_color="rgba(0, 0, 0, 0.000)", wire_width=6)
    out = []
    for name, r in classes.items():
        d = dict(base, name=name, clearance=r["clearance"], track_width=r["track"],
                 via_diameter=r.get("via", 0.6), via_drill=r.get("drill", 0.3))
        out.append(d)
    ns["classes"] = out
    ns["meta"] = {"version": 3}
    ns["netclass_assignments"] = None
    ns["netclass_patterns"] = [{"netclass": c, "pattern": p} for p, c in assign]
    json.dump(pro, open(pro_path, "w"), indent=2)


# ------------------------------------------------------- single-sided boards
def is_smd(fp):
    pads = list(fp.Pads())
    return bool(pads) and all(p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD for p in pads if p.GetNumber())


def flip_smd_to_bottom(bb):
    """Single-sided board: SMD parts sit on the copper (bottom) side."""
    for fp in bb.fps.values():
        if is_smd(fp) and not fp.IsFlipped():
            fp.Flip(fp.GetPosition(), False)


def dsn_single_layer(dsn_in, dsn_out, top_trace_cost=None, via_cost=None, strip_top=True):
    """Prepare a KiCad DSN for single-sided routing with wire jumpers.

    * THT padstacks lose their F.Cu shape, so the top layer can only link via to via:
      every top-layer run later becomes one insulated wire jumper.
    * autoroute_settings make top-layer traces and vias expensive so the router
      uses them only when the bottom layer has no way through.
    """
    top_trace_cost = float(os.environ.get("FR_TOP_COST", "25")) if top_trace_cost is None else top_trace_cost
    via_cost = int(os.environ.get("FR_VIA_COST", "400")) if via_cost is None else via_cost
    txt = open(dsn_in, encoding="utf-8").read()
    out, i = [], 0
    for m in re.finditer(r"\(padstack ", txt):
        start = m.start()
        depth, j = 0, start
        while True:
            ch = txt[j]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        block = txt[start:j + 1]
        if strip_top and "Via[" not in block.split("\n", 1)[0] and "B.Cu" in block:
            block = re.sub(r"\s*\(shape \((?:circle|rect|polygon|path) F\.Cu[^()]*(?:\([^()]*\)[^()]*)*\)\)", "", block)
        out.append(txt[i:start])
        out.append(block)
        i = j + 1
    out.append(txt[i:])
    txt = "".join(out)
    settings = ("    (autoroute_settings (fanout off) (autoroute on) (postroute on) (vias on)\n"
                "      (via_costs %d) (plane_via_costs 5) (start_ripup_costs 100)\n"
                "      (layer_rule F.Cu (active on) (preferred_direction horizontal)"
                " (preferred_direction_trace_costs %.1f) (against_preferred_direction_trace_costs %.1f))\n"
                "      (layer_rule B.Cu (active on) (preferred_direction vertical)"
                " (preferred_direction_trace_costs 1.0) (against_preferred_direction_trace_costs 1.2)))\n"
                % (via_cost, top_trace_cost, top_trace_cost))
    # must come right after the layer definitions (before any keepout / plane)
    last_layer = [m.end() for m in re.finditer(r"\(layer B\.Cu[\s\S]*?\n    \)\n", txt)]
    pos = last_layer[0] if last_layer else txt.index("(boundary")
    txt = txt[:pos] + settings + txt[pos:]
    open(dsn_out, "w", encoding="utf-8").write(txt)


def jumperize(board, ox=0.0, oy=0.0, drill=0.9, pad=2.0):
    """Turn each top-layer track run (via to via) into a wire-jumper footprint W<n>."""
    tracks = [t for t in board.GetTracks() if t.GetClass() == "PCB_TRACK" and t.GetLayer() == pcbnew.F_Cu]
    vias = [t for t in board.GetTracks() if t.GetClass() == "PCB_VIA"]
    key = lambda p: (p.x // 1000, p.y // 1000)  # noqa: E731  (1 um grid)
    adj = {}
    for t in tracks:
        a, b = key(t.GetStart()), key(t.GetEnd())
        adj.setdefault(a, []).append((b, t))
        adj.setdefault(b, []).append((a, t))
    via_at = {key(v.GetPosition()): v for v in vias}
    seen, jumpers = set(), []
    for start in list(adj):
        if start not in via_at:
            continue
        for nxt, t in adj[start]:
            if id(t) in seen:
                continue
            chain = [t]
            seen.add(id(t))
            cur = nxt
            while cur not in via_at and len(adj.get(cur, [])) == 2:
                (n1, t1), (n2, t2) = adj[cur]
                t_next, n_next = (t2, n2) if id(t1) in seen else (t1, n1)
                if id(t_next) in seen:
                    break
                seen.add(id(t_next))
                chain.append(t_next)
                cur = n_next
            jumpers.append((start, cur, chain))
    removed_vias = set()
    for n, (a, b, chain) in enumerate(jumpers, 1):
        net = chain[0].GetNet()
        fp = pcbnew.FOOTPRINT(board)
        fp.SetReference("W%d" % n)
        fp.SetValue("wire jumper")
        fp.SetAttributes(pcbnew.FP_THROUGH_HOLE)
        pa = pcbnew.VECTOR2I(a[0] * 1000, a[1] * 1000)
        pb = pcbnew.VECTOR2I(b[0] * 1000, b[1] * 1000)
        fp.SetPosition(pa)
        for num, pos in (("1", pa), ("2", pb)):
            p = pcbnew.PAD(fp)
            p.SetNumber(num)
            p.SetAttribute(pcbnew.PAD_ATTRIB_PTH)
            p.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
            p.SetSize(pcbnew.VECTOR2I(MM(pad), MM(pad)))
            p.SetDrillSize(pcbnew.VECTOR2I(MM(drill), MM(drill)))
            p.SetLayerSet(pcbnew.PAD.PTHMask())
            p.SetPos0(pcbnew.VECTOR2I(pos.x - pa.x, pos.y - pa.y))
            p.SetPosition(pos)
            p.SetNet(net)
            fp.Add(p)
        ln = pcbnew.FP_SHAPE(fp)
        ln.SetShape(pcbnew.SHAPE_T_SEGMENT)
        ln.SetLayer(pcbnew.F_SilkS)
        ln.SetWidth(MM(0.4))
        ln.SetStart(pa)
        ln.SetEnd(pb)
        ln.SetLocalCoord()
        fp.Add(ln)
        fp.Reference().SetPosition(pcbnew.VECTOR2I((pa.x + pb.x) // 2, (pa.y + pb.y) // 2 - MM(1.0)))
        fp.Reference().SetTextSize(pcbnew.VECTOR2I(MM(0.8), MM(0.8)))
        fp.Value().SetVisible(False)
        board.Add(fp)
        for t in chain:
            board.Remove(t)
        removed_vias |= {a, b}
    for k in removed_vias:
        if k in via_at:
            board.Remove(via_at[k])
    return jumpers
