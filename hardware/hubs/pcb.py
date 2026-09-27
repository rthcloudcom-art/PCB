#!/usr/bin/env python3
"""PCB for one AgriNode hub variant (single-sided with wire jumpers, 2-layer fallback).

    python3 pcb.py <variant>                 # placement + rules
    python3 pcb.py <variant> --route         # + Freerouting, finishing router, wire jumpers
    python3 pcb.py <variant> --import-ses    # rebuild from <variant>/outputs/route/*.ses

HUB_LAYERS=1: copper only on the bottom; SMD parts on the copper side, THT on top;
top-layer runs chosen by the router become insulated wire jumpers W1, W2, ...
HUB_LAYERS=2 (default): ordinary 2-layer board, everything on top. (Single-sided trial for the
smallest hub: 49 wire jumpers and 70 connections still unrouted, so 2 layers is the default.)
Run build.py <variant> first.
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "design"))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools", "kigen"))
os.environ.setdefault("KICAD7_FOOTPRINT_DIR", "/usr/share/kicad/footprints")
os.environ.setdefault("KICAD7_SYMBOL_DIR", "/usr/share/kicad/symbols")

import pcbnew  # noqa: E402

import hubs  # noqa: E402
import pcbgen  # noqa: E402

VARIANT = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else "hub-w"
c = hubs.make(VARIANT)
KICAD = os.path.join(HERE, VARIANT, "kicad")
OUT = os.path.join(HERE, VARIANT, "outputs")
PCB = os.path.join(KICAD, c.name + ".kicad_pcb")
JAR = os.environ.get("FREEROUTING_JAR", "/tmp/claude-0/fr/freerouting.jar")
JAVA = os.environ.get("FREEROUTING_JAVA", "/usr/lib/jvm/java-25-openjdk-amd64/bin/java")
TWO_LAYER = os.environ.get("HUB_LAYERS", "2") == "2"
PACK_GAP = float(os.environ.get("PACK_GAP", "2.0"))  # room for routing channels between parts
STITCH = os.environ.get("GND_STITCH", "0") == "1"   # optional: GND by stitching vias + pours (tried: no gain)

# board size per variant: the core occupies x < CORE_W, the uplink block sits to its right
CORE_W, H = 100.0, 96.0
EXTRA_W = {"hub-w": 14.0, "hub-l": 30.0, "hub-c": 30.0, "gw-lan": 50.0}
W = CORE_W + EXTRA_W[VARIANT]

NETCLASSES = {
    "Default": dict(track=0.5, clearance=0.5, via=1.2, drill=0.6),
    "Power": dict(track=0.8, clearance=0.5, via=1.2, drill=0.6),
    "Supply": dict(track=0.7, clearance=0.5, via=1.2, drill=0.6),
}
ASSIGN = [
    ("*VIN_BUCK", "Power"), ("*BUCK_SW", "Power"), ("*V5_BUCK", "Power"), ("*V5", "Power"),
    ("*VSYS", "Power"), ("*VBAT", "Power"), ("*BATT_*", "Power"),
    ("*VDC_*", "Power"), ("*VSOL_*", "Power"), ("*VUSB_*", "Power"), ("*VMOD_*", "Power"),
    ("+3V3", "Supply"), ("*VLED", "Supply"),
]


def width_of(netname):
    """Track width of a net from its net class (same patterns as the project file)."""
    import fnmatch
    for pat, cls in ASSIGN:
        if fnmatch.fnmatchcase(netname, pat):
            return NETCLASSES[cls]["track"]
    return NETCLASSES["Default"]["track"]


def main(route=False):
    c.annotate()
    pin_net = pcbgen.load_kicad_netlist(os.path.join(OUT, c.name + ".net"))
    bb = pcbgen.BoardBuilder(c, PCB, origin=(50.0, 50.0))
    bb.board.SetCopperLayerCount(2)
    ds = bb.board.GetDesignSettings()
    ds.m_TrackMinWidth = pcbgen.MM(0.5)
    ds.m_MinClearance = pcbgen.MM(0.5)
    ds.m_MinThroughDrill = pcbgen.MM(0.6)
    ds.m_ViasMinSize = pcbgen.MM(1.2)
    ds.m_ViasMinAnnularWidth = pcbgen.MM(0.25)
    bb.add_footprints(pin_net)
    for fp in bb.fps.values():   # library THT pads with a thin ring: >= 0.26 mm annular for coarse drilling
        for p in fp.Pads():
            d = p.GetDrillSize()
            if p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH and d.x == d.y and min(p.GetSize().x, p.GetSize().y) - d.x < pcbgen.MM(0.52):
                p.SetSize(pcbnew.VECTOR2I(max(p.GetSize().x, d.x + pcbgen.MM(0.52)), max(p.GetSize().y, d.y + pcbgen.MM(0.52))))
    if not TWO_LAYER:
        pcbgen.flip_smd_to_bottom(bb)
    bb.outline(W, H)
    place(bb)
    finish(bb, route)


def place(bb):
    def val(v):
        hits = [r for r, p in bb.part_of.items() if p.value == v]
        assert len(hits) == 1, (v, hits)
        return hits[0]

    def block(prefix):
        return [r for r, t in bb.block_of.items() if t.startswith(prefix)
                and not getattr(bb.fps[r], "_placed", False)]

    def pack(prefix, x0, y0, x1, y1):
        refs = block(prefix)
        refs.sort(key=lambda r: -(lambda b: (b[2] - b[0]) * (b[3] - b[1]))(bb.bbox(bb.fps[r])))
        over = bb.pack_free(refs, x0, y0, x1, y1, gap=PACK_GAP)
        grow = 0
        while over and grow < 30:          # spill into the neighbourhood, keep parts close
            grow += 5
            over = bb.pack_free(over, max(2, x0 - grow), max(2, y0 - grow), min(W - 2, x1 + grow),
                                min(H - 2, y1 + grow), gap=PACK_GAP)
        if over:
            print("  could not place: %s" % over)

    holes = sorted(r for r in bb.fps if r.startswith("H"))
    for r, (x, y) in zip(holes, ((5, 67), (W - 4, 51), (W - 4, H - 4), (86, H - 4))):
        bb.put(r, x, y, anchor="cc")

    # ESP32 on the top edge, antenna overhanging the edge (module mirrored when on the bottom side)
    esp = [r for r in block("ESP32-WROOM") if r.startswith("U")][0]
    fp = bb.fps[esp]
    fp._fab_bbox = True
    fp.SetOrientationDegrees(180 if fp.IsFlipped() else 0)
    fp.SetPosition(pcbgen.V(bb.ox + 50.0, bb.oy + 9.8))
    fp._placed = True

    # left edge: power inputs; right edge (top): USB-B for power + programming
    bb.put(val("DC 12V 5.5/2.1"), 0.0, 4.0, rot=0, anchor="tl")
    bb.put(val("DC IN 7-24V"), 0.0, 19.0, rot=90, anchor="tl")
    bb.put(val("SOLAR 6-24V"), 0.0, 31.0, rot=90, anchor="tl")
    bb.put(val("USB 5V / PROG"), W, 3.0, rot=270, anchor="tr")
    # bottom: 18650 cell
    bb.put(val("18650 Li-ion (protected)"), 2.0, H - 1.0, rot=0, anchor="bl")
    # buttons and headers along the top edge
    bb.put(val("RESET"), 17.5, 3.0, anchor="tl")
    bb.put(val("LED STRIP WS2813"), 29.0, 3.5, rot=90, anchor="tl")
    bb.put(val("I2C"), 29.0, 7.5, rot=90, anchor="tl")
    if VARIANT == "hub-w":
        bb.put(val("BOOT / PAIR"), 61.0, 3.0, anchor="tl")
        bb.put(val("PROG"), 61.0, 11.5, rot=90, anchor="tl")
    else:   # more nets leave the ESP32 right column: keep a 6 mm routing channel beside it
        bb.put(val("BOOT / PAIR"), 66.0, 3.0, anchor="tl")
        bb.put(val("PROG"), 64.5, 17.0, rot=90, anchor="tl")
    bb.put(val("CR2032"), 62.0, 36.0, anchor="tl")
    # DS3231 right beside the CR2032 holder, VBAT/SDA/SCL pins facing it
    bb.put(val("DS3231MZ"), 84.0, 43.0, rot=180, anchor="tl")
    bb.put(val("RS-485"), W, 58.0, rot=270, anchor="tr")
    bz = (110.0, 80.0) if VARIANT == "gw-lan" else (86.0, 28.0)   # gw-lan: core is crowded
    bb.put(val("5V magnetic buzzer"), bz[0], bz[1], anchor="tl")
    # uplink connectors before the core packing so it flows around them
    if VARIANT == "gw-lan":
        bb.put(val("LAN"), W, 24.0, rot=90, anchor="tr")
    if VARIANT == "hub-c":
        bb.put(val("LTE MODULE"), W - 3.0, 26.0, rot=0, anchor="tr")

    ldo = [r for r in block("3.3 V rail") if r.startswith("U")][0]
    bb.put(ldo, 64.0, 24.0, rot=0, anchor="tl")
    if VARIANT != "hub-w":
        bb.put(val("100u/10V"), 53.5, 23.5, rot=0, anchor="tl")   # LDO output bulk cap, beside the regulator
    pack("ESP32-WROOM", 40, 22, 62, 30)
    # uplink block first: its big parts need the free space right of the core
    x0 = CORE_W + 1
    if VARIANT == "hub-l":
        pack("LoRa", x0, 24, W - 2, 56)
    if VARIANT == "gw-lan":
        pack("LoRa", x0 - 14, 56, W - 20, H - 2)
        pack("Ethernet", x0, 24, W - 22, 56)
    if VARIANT == "hub-c":
        pack("4G LTE", x0, 24, W - 6, H - 2)
    # CH340C turned so UD+/UD- (pins 5/6) face the USB-B jack; DTR/RTS face the auto-reset pair
    bb.put(val("CH340C"), CORE_W - 20.0, 3.0, rot=180, anchor="tl")
    pack("USB programming", 72, 3, W - 20, 26)
    pack("Reset and boot", 20, 12, 40, 20)
    pack("WS2813", 20, 12, 40, 22)
    pack("Inputs", 14, 22, 40, 44)
    pack("Supply monitoring", 30, 22, 44, 36)
    pack("5 V buck", 14, 44, 44, 74)
    pack("5 V bus", 14, 44, 44, 74)
    pack("18650 charger", 44, 50, 64, 74)
    pack("18650 cell", 44, 58, 64, 74)
    pack("Power path", 44, 40, 62, 52)
    pack("3.3 V rail", 44, 24, 84, 40)
    pack("RTC", 62, 36, 86, 58)
    pack("Buzzer", bz[0] - 2, bz[1], bz[0] + 18, min(H - 2, bz[1] + 18))
    pack("RS-485", 84, 44, W - 14, 74)


def finish(bb, route):
    bb.netclasses(NETCLASSES, ASSIGN)
    esp = bb.fps[[r for r, p in bb.part_of.items() if p.lib_id == "RF_Module:ESP32-WROOM-32E"][0]]
    x0, y0, x1, _ = bb.bbox(esp)
    z = bb.zone(None, pcbnew.B_Cu, [(x0 - 1, 0), (x1 + 1, 0), (x1 + 1, 1.0), (x0 - 1, 1.0)], keepout=True,
                name="antenna keepout")
    ls = pcbnew.LSET()
    ls.AddLayer(pcbnew.F_Cu)
    ls.AddLayer(pcbnew.B_Cu)
    z.SetLayerSet(ls)
    z.SetDoNotAllowTracks(True)
    z.SetDoNotAllowVias(True)
    bb.text(c.title.split(" (")[0] + " rev A", 45, H - 23.5, size=1.5)
    bb.save()
    pcbgen.write_project_netclasses(os.path.join(KICAD, c.name + ".kicad_pro"), NETCLASSES, ASSIGN)
    ov = bb.overlaps()
    print("footprints:", len(bb.fps), "overlapping pairs:", len(ov))
    for a, b in ov[:30]:
        print("  overlap", a, b)
    if route:
        do_route(bb, route)
    fill_and_drc(PCB)


def gnd_stitch(board):
    """Give every SMD ground pad a short stub and a via to the ground pours, so the autorouter
    does not have to route GND as traces (it cost ~18 % of all copper and blocked signal routes)."""
    gnd = board.GetNetsByName()["GND"]
    others = [q for q in board.GetPads() if q.GetNetname() != "GND"]
    edge = board.GetBoardEdgesBoundingBox()
    vias = []
    V_R, CLR, TW = 0.6, 0.5, 0.6

    def clear(pt, r):
        v = pcbnew.VECTOR2I(pcbgen.MM(pt[0]), pcbgen.MM(pt[1]))
        for q in others:
            if q.GetEffectivePolygon().Collide(v, pcbgen.MM(r)):
                return False
        return True

    def fits(c, pad_xy):
        x, y = c
        if not (pcbnew.ToMM(edge.GetLeft()) + 1.2 < x < pcbnew.ToMM(edge.GetRight()) - 1.2 and
                pcbnew.ToMM(edge.GetTop()) + 2.5 < y < pcbnew.ToMM(edge.GetBottom()) - 1.2):
            return False
        if any((x - vx) ** 2 + (y - vy) ** 2 < (2 * V_R + CLR + 0.1) ** 2 for vx, vy in vias):
            return False
        if not clear(c, V_R + CLR + 0.1):
            return False
        n = 8   # the stub from the pad to the via
        return all(clear((pad_xy[0] + (x - pad_xy[0]) * k / n, pad_xy[1] + (y - pad_xy[1]) * k / n), TW / 2 + CLR + 0.1)
                   for k in range(1, n))

    added = 0
    for fp in board.GetFootprints():
        fc = fp.GetPosition()
        for p in fp.Pads():
            if p.GetNetname() != "GND" or p.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
                continue
            pc = (pcbnew.ToMM(p.GetPosition().x), pcbnew.ToMM(p.GetPosition().y))
            sx, sy = pcbnew.ToMM(p.GetBoundingBox().GetWidth()) / 2, pcbnew.ToMM(p.GetBoundingBox().GetHeight()) / 2
            if min(sx, sy) >= 1.0:   # large pad (exposed pad, TO-263 tab): via in the pad
                cands = [pc]
            else:
                ox, oy = pc[0] - pcbnew.ToMM(fc.x), pc[1] - pcbnew.ToMM(fc.y)
                dirs = [(1, 0), (-1, 0), (0, 1), (0, -1), (0.7071, 0.7071), (0.7071, -0.7071), (-0.7071, 0.7071),
                        (-0.7071, -0.7071)]
                dirs.sort(key=lambda d: -(d[0] * ox + d[1] * oy))   # away from the part first
                cands = [(pc[0] + d[0] * (abs(d[0]) * sx + abs(d[1]) * sy + extra),
                          pc[1] + d[1] * (abs(d[0]) * sx + abs(d[1]) * sy + extra))
                         for extra in (1.0, 1.5, 2.2) for d in dirs]
            for cnd in cands:
                if cnd == pc or fits(cnd, pc):
                    if cnd != pc:
                        t = pcbnew.PCB_TRACK(board)
                        t.SetStart(p.GetPosition())
                        t.SetEnd(pcbnew.VECTOR2I(pcbgen.MM(cnd[0]), pcbgen.MM(cnd[1])))
                        t.SetWidth(pcbgen.MM(TW))
                        t.SetLayer(pcbnew.F_Cu)
                        t.SetNet(gnd)
                        t.SetLocked(True)
                        board.Add(t)
                    v = pcbnew.PCB_VIA(board)
                    v.SetPosition(pcbnew.VECTOR2I(pcbgen.MM(cnd[0]), pcbgen.MM(cnd[1])))
                    v.SetWidth(pcbgen.MM(1.2))
                    v.SetDrill(pcbgen.MM(0.6))
                    v.SetViaType(pcbnew.VIATYPE_THROUGH)
                    v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
                    v.SetNet(gnd)
                    v.SetLocked(True)
                    board.Add(v)
                    vias.append(cnd)
                    added += 1
                    break
    return added


def dsn_without_gnd(path):
    """Leave GND out of the autorouter's connection list (pours + stitching vias connect it)."""
    txt = open(path).read()
    txt2 = re.sub(r"\(net GND\s*\(pins[^)]*\)", "(net GND (pins)", txt, count=1)
    open(path, "w").write(txt2)
    return txt2 != txt


def run_freerouting(dsn, ses, rdir):
    """Single-threaded Freerouting is deterministic, but it saves the *last* pass, not the best one.
    Run once, find the pass with the fewest unrouted nets, then re-run stopping at that pass."""
    def run(passes, tag):
        if os.path.exists(ses):
            os.remove(ses)
        cmd = [JAVA, "-Djava.awt.headless=true", "-jar", JAR, "-de", dsn, "-do", ses,
               "-mp", str(passes), "-mt", "1"]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=int(os.environ.get("FR_TIMEOUT", "7200")))
        log = r.stdout + r.stderr
        open(os.path.join(rdir, "freerouting%s.log" % tag), "w").write(log[-40000:])
        return [(int(m.group(1)), int(m.group(2))) for m in
                re.finditer(r"Auto-routing pass #(\d+) .*?\((\d+) unrouted", log)]
    passes = int(os.environ.get("FR_PASSES", "20"))
    hist = run(passes, "")
    if not hist:
        return
    best_pass, best = min(hist, key=lambda pu: (pu[1], pu[0]))
    print("freerouting: best pass #%d with %d unrouted (last pass: %d unrouted)" % (best_pass, best, hist[-1][1]))
    if best < hist[-1][1]:
        run(best_pass, "_best")


def do_route(bb, route):
    rdir = os.path.join(OUT, "route")
    os.makedirs(rdir, exist_ok=True)
    dsn = os.path.join(rdir, c.name + ".dsn")
    ses = os.path.join(rdir, c.name + ".ses")
    if route != "import":
        board = pcbgen.load(PCB)
        if TWO_LAYER and STITCH:
            print("GND stitching vias: %d" % gnd_stitch(board))
            board.Save(PCB)
            board = pcbgen.load(PCB)
        pcbnew.ExportSpecctraDSN(board, dsn + ".kicad")
        if TWO_LAYER:
            pcbgen.dsn_single_layer(dsn + ".kicad", dsn, top_trace_cost=float(os.environ.get("FR_TOP_COST", "1.5")),
                                    via_cost=int(os.environ.get("FR_VIA_COST", "40")), strip_top=False)
            if STITCH:
                print("GND left to the pours: %s" % dsn_without_gnd(dsn))
        else:
            pcbgen.dsn_single_layer(dsn + ".kicad", dsn)
        run_freerouting(dsn, ses, rdir)
    board = pcbgen.load(PCB)
    nt, nv = pcbgen.import_ses(board, ses)
    print("imported %d track segments, %d vias" % (nt, nv))
    for t in board.GetTracks():
        if t.GetClass() == "PCB_TRACK" and t.GetWidth() < pcbgen.MM(0.5) and t.GetLength() < pcbgen.MM(0.3):
            t.SetWidth(pcbgen.MM(0.5))
    if TWO_LAYER:
        import finish_router
        done, left = finish_router.finish(board, track_w=0.5, via_d=1.2, via_drill=0.6, log=lambda *_: None,
                                          width_of=width_of)
        print("finishing router: %d routed, still open: %s" % (done, [n.split("/")[-1] for n in left]))
        # rip-up stages; each result is kept only when it leaves fewer open nets (rip-up can make things worse)
        power = tuple({str(n).split("/")[-1] for n in board.GetNetsByName().keys() if width_of(str(n)) > 0.5})
        snap = os.path.join(rdir, "best.kicad_pcb")
        for name, protect, iters in (("signal nets only", ("GND",) + power, 150),
                                     ("incl. power nets", ("GND",), 60)):
            if not left or os.environ.get("RIPUP", "1") == "0":
                break
            board.Save(snap)
            got = finish_router.rip_and_reroute(board, protected_names=protect, track_w=0.5, via_d=1.2,
                                                via_drill=0.6, max_iter=iters, log=lambda *_: None,
                                                width_of=width_of)
            print("rip-up (%s): still open: %s" % (name, [n.split("/")[-1] for n in got]))
            if len(got) < len(left):
                left = got
            else:
                board = pcbgen.load(snap)
                print("  -> no better, kept the previous result")
        for ext in (".kicad_pcb", ".kicad_pro", ".kicad_prl"):
            if os.path.exists(snap[:-10] + ext):
                os.remove(snap[:-10] + ext)
        print("open connections: %s" % [n.split("/")[-1] for n in left])
    else:
        jumpers = pcbgen.jumperize(board, drill=0.8, pad=1.8)
        print("wire jumpers: %d" % len(jumpers))
        with open(os.path.join(OUT, "jumpers.txt"), "w") as f:
            for i, (a, b, chain) in enumerate(jumpers, 1):
                f.write("W%d  %s  %.1f mm\n" % (i, chain[0].GetNetname().split("/")[-1],
                                                 ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5 / 1000.0))
    tmp = pcbgen.BoardBuilder.__new__(pcbgen.BoardBuilder)
    tmp.board, tmp.ox, tmp.oy = board, bb.ox, bb.oy
    tmp.nets = {n.GetNetname(): n for n in board.GetNetInfo().NetsByName().values()}
    for layer in ((pcbnew.F_Cu, pcbnew.B_Cu) if TWO_LAYER else (pcbnew.B_Cu,)):
        z = tmp.zone("GND", layer, [(0, 0), (W, 0), (W, H), (0, H)], clearance=0.6, min_width=0.6, name="GND pour")
        z.SetThermalReliefSpokeWidth(pcbgen.MM(0.8))
    board.Save(PCB)


def fill_and_drc(path):
    board = pcbgen.load(path)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(path)
    pcbgen.write_project_netclasses(os.path.join(KICAD, c.name + ".kicad_pro"), NETCLASSES, ASSIGN)
    board = pcbgen.load(path)
    rpt = os.path.join(OUT, "drc.rpt")
    pcbnew.WriteDRCReport(board, rpt, pcbnew.EDA_UNITS_MILLIMETRES, True)
    txt = open(rpt).read()
    for key in ("violations", "unconnected pads"):
        m = re.search(r"\*\* Found (\d+) (?:DRC )?%s" % key, txt)
        print("DRC %s: %s" % (key, m.group(1) if m else "?"))
    cats = {}
    for m in re.finditer(r"^\[([a-z_]+)\]", txt, re.M):
        cats[m.group(1)] = cats.get(m.group(1), 0) + 1
    print("   ", {k: v for k, v in sorted(cats.items()) if not k.startswith("silk")})


if __name__ == "__main__":
    main(route="import" if "--import-ses" in sys.argv else "--route" in sys.argv)
