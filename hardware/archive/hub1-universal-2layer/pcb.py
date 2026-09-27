#!/usr/bin/env python3
"""AgriNode HUB-1 single-sided PCB: placement, rules, routing, wire jumpers.

    python3 pcb.py              # placement + rules + ground pour, no routing
    python3 pcb.py --route      # + Freerouting on the bottom layer, top runs -> wire jumpers
    python3 pcb.py --import-ses # rebuild and reuse outputs/route/agrinode_hub.ses
    python3 pcb.py --continue   # keep the routed copper and let Freerouting finish the rest

Copper is on the bottom (B.Cu) only. SMD parts sit on the bottom, THT parts on top.
Every top-layer track the router needs is replaced by an insulated wire jumper (W1, W2 ...).
Run build.py first.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "design"))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "tools", "kigen"))
os.environ.setdefault("KICAD7_FOOTPRINT_DIR", "/usr/share/kicad/footprints")
os.environ.setdefault("KICAD7_SYMBOL_DIR", "/usr/share/kicad/symbols")

import pcbnew  # noqa: E402

import pcbgen  # noqa: E402
from hub import c  # noqa: E402

KICAD = os.path.join(HERE, "kicad")
OUT = os.path.join(HERE, "outputs")
PCB = os.path.join(KICAD, c.name + ".kicad_pcb")
JAR = os.environ.get("FREEROUTING_JAR", "/tmp/claude-0/fr/freerouting.jar")
JAVA = os.environ.get("FREEROUTING_JAVA", "/usr/lib/jvm/java-25-openjdk-amd64/bin/java")

W, H = 150.0, 118.0
# The universal hub is too dense for one copper layer (trial: 72 wire jumpers and 78 connections
# still unrouted), so it is a 2-layer board. Set HUB_LAYERS=1 to rerun the single-sided attempt.
TWO_LAYER = os.environ.get("HUB_LAYERS", "2") == "2"

NETCLASSES = {
    "Default": dict(track=0.5, clearance=0.5, via=1.2, drill=0.6),
    # 0.8 mm: must still fit into 1.0 mm SOIC/TO-263 pads (the router cannot neck down)
    "Power": dict(track=0.8, clearance=0.5, via=1.2, drill=0.6),
    "Supply": dict(track=0.7, clearance=0.5, via=1.2, drill=0.6),
}
ASSIGN = [  # GND and VMODEM stay at 0.6 mm (narrow module pads); the ground pour carries the current
    ("*VIN_BUCK", "Power"), ("*BUCK_SW", "Power"), ("*V5_BUCK", "Power"), ("*V5", "Power"),
    ("*VSYS", "Power"), ("*VBAT", "Power"), ("*BATT_*", "Power"),
    ("*VDC_*", "Power"), ("*VSOL_*", "Power"), ("*VUSB_*", "Power"),
    ("+3V3", "Supply"),
]


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
    ds.m_MinThroughDrill = pcbgen.MM(0.6)
    bb.add_footprints(pin_net)
    if not TWO_LAYER:
        pcbgen.flip_smd_to_bottom(bb)          # single-sided: SMD on the copper side
    bb.outline(W, H)

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
        over = bb.pack_free(refs, x0, y0, x1, y1, gap=0.8)
        if over:
            print("  region overflow in '%s': %s" % (prefix, over))

    place(bb, val, block, pack)
    finish(bb, route)


def place(bb, val, block, pack):
    holes = sorted(r for r in bb.fps if r.startswith("H"))
    for r, (x, y) in zip(holes, ((4, 4), (W - 4, 32), (5, 88), (W - 4, 100))):
        bb.put(r, x, y, anchor="cc")

    # --- top edge: status LEDs, buttons, ESP32 (bottom side, antenna on the board edge)
    esp = [r for r in block("ESP32-WROOM") if r.startswith("U")][0]
    fp = bb.fps[esp]
    fp._fab_bbox = True
    fp.SetOrientationDegrees(180 if fp.IsFlipped() else 0)  # antenna towards the top board edge
    fp.SetPosition(pcbgen.V(bb.ox + 70.0, bb.oy + 15.8))   # module top flush with the board edge
    fp._placed = True
    leds = sorted([r for r in block("Addressable RGB") if bb.part_of[r].lib_id == "agrinode:PL9823"],
                  key=lambda r: bb.part_of[r].value)
    for i, r in enumerate(leds):
        bb.put(r, 12.0 + i * 7.5, 11.5, rot=90, anchor="cc")
    bb.put(val("RESET"), 8.0, 17.5, anchor="tl")
    bb.put(val("BOOT / PAIR"), 19.0, 17.5, anchor="tl")
    bb.put(val("PROG"), 81.0, 6.0, rot=0, anchor="tl")      # next to TXD0/RXD0/IO0 on the ESP32 right side

    # --- left edge: power inputs (openings to the left)
    bb.put(val("USB 5V"), 0.0, 26.0, rot=90, anchor="tl")
    bb.put(val("DC 12V 5.5/2.1"), 0.0, 44.0, rot=0, anchor="tl")
    bb.put(val("DC IN 7-24V"), 0.0, 58.5, rot=90, anchor="tl")
    bb.put(val("SOLAR 6-24V"), 0.0, 71.0, rot=90, anchor="tl")

    # --- bottom: 18650 cell (THT holder on top), SIM holder and GSM antenna
    bb.put(val("18650 Li-ion (protected)"), 2.0, H - 1.0, rot=0, anchor="bl")
    bb.put(val("micro SIM"), 90.0, H - 1.0, rot=90, anchor="bl")
    bb.put(val("GSM ANT SMA"), W + 4.0, H - 8.0, rot=180, anchor="cr")
    bb.put(val("5V magnetic buzzer"), 82.0, 62.0, anchor="tl")

    # --- right edge: LAN, RS-485
    bb.put(val("LAN"), W, 2.0, rot=90, anchor="tr")

    # --- functional clusters (SMD parts land on the bottom side)
    pack("Inputs", 18, 29, 47.5, 47)
    pack("5 V buck", 17, 47.5, 47, 85.5)
    pack("5 V bus", 17, 86, 47, 90)
    pack("Supply monitoring", 17, 89.8, 47, 96)
    pack("Addressable RGB", 47, 17.5, 61, 38)
    pack("Reset, boot", 30, 17.5, 47, 28.5)
    pack("ESP32-WROOM", 62, 27, 79, 34)
    pack("3.3 V rail", 48, 38.5, 79, 54)
    pack("Power path", 48, 54, 79, 64.5)
    pack("18650 charger", 48, 65, 78, 80)
    pack("18650 cell", 48, 81, 78, 96)
    pack("LoRa", 80, 36, 106, 58)
    pack("I2C expansion", 108, 40, W - 14, 52)
    pack("Buzzer", 80, 76, 100, 96)
    pack("Ethernet", 86, 7, W - 13, 36)
    cell = block("Cellular")
    u_sim = [r for r in cell if bb.part_of[r].value == "SIM800C"][0]
    u_ldo = [r for r in cell if bb.part_of[r].value == "MIC29302WU"][0]
    c_big = [r for r in cell if bb.part_of[r].value.startswith("1000u")][0]
    bb.put(u_sim, 108.0, 58.0, anchor="tl")
    bb.put(u_ldo, W - 16.0, 57.0, rot=90, anchor="tl")
    bb.put(c_big, 108.0, 80.0, anchor="tl")
    pack("Cellular", 104, 78, W - 1, 99)


def finish(bb, route):
    bb.netclasses(NETCLASSES, ASSIGN)
    # antenna keep-out (all copper) above the ESP32 PCB antenna
    esp = bb.fps[[r for r, p in bb.part_of.items() if p.lib_id == "RF_Module:ESP32-WROOM-32E"][0]]
    x0, y0, x1, _ = bb.bbox(esp)
    z = bb.zone(None, pcbnew.B_Cu, [(x0 - 1, 0), (x1 + 1, 0), (x1 + 1, 5.5), (x0 - 1, 5.5)], keepout=True,
                name="antenna keepout")
    ls = pcbnew.LSET()
    ls.AddLayer(pcbnew.F_Cu)
    ls.AddLayer(pcbnew.B_Cu)
    z.SetLayerSet(ls)
    z.SetDoNotAllowTracks(True)
    z.SetDoNotAllowVias(True)
    bb.text("AgriNode HUB-1 rev A", W / 2, H - 2.0, size=1.6)
    bb.save()
    pcbgen.write_project_netclasses(os.path.join(KICAD, c.name + ".kicad_pro"), NETCLASSES, ASSIGN)
    ov = bb.overlaps()
    print("footprints:", len(bb.fps), "overlapping pairs:", len(ov))
    for a, b in ov[:40]:
        print("  overlap", a, b)
    if route:
        do_route(bb, route)
    fill_and_drc(PCB)


def do_route(bb, route):
    rdir = os.path.join(OUT, "route")
    os.makedirs(rdir, exist_ok=True)
    dsn = os.path.join(rdir, c.name + ".dsn")
    ses = os.path.join(rdir, c.name + ".ses")
    if route == "continue":  # keep the current copper, route what is left
        board = pcbgen.load(PCB)
        for z in list(board.Zones()):
            if not z.GetIsRuleArea():
                board.Remove(z)
        pcbnew.ExportSpecctraDSN(board, dsn + ".kicad")
        pcbgen.dsn_single_layer(dsn + ".kicad", dsn, top_trace_cost=1.5, via_cost=60, strip_top=False)
        run_freerouting(dsn, ses, rdir)
        board = pcbgen.load(PCB)
        for t in list(board.GetTracks()):
            board.Remove(t)
        for z in list(board.Zones()):
            if not z.GetIsRuleArea():
                board.Remove(z)
    elif route != "import":
        board = pcbgen.load(PCB)
        pcbnew.ExportSpecctraDSN(board, dsn + ".kicad")
        if TWO_LAYER:
            pcbgen.dsn_single_layer(dsn + ".kicad", dsn, top_trace_cost=float(os.environ.get("FR_TOP_COST", "1.5")),
                                    via_cost=int(os.environ.get("FR_VIA_COST", "60")), strip_top=False)
        else:
            pcbgen.dsn_single_layer(dsn + ".kicad", dsn)
        run_freerouting(dsn, ses, rdir)
    if route != "continue":
        board = pcbgen.load(PCB)
    nt, nv = pcbgen.import_ses(board, ses)
    # the router leaves tiny sub-width stubs inside narrow module pads; bring them to the minimum width
    for t in board.GetTracks():
        if t.GetClass() == "PCB_TRACK" and t.GetWidth() < pcbgen.MM(0.5) and t.GetLength() < pcbgen.MM(0.3):
            t.SetWidth(pcbgen.MM(0.5))
    print("imported %d track segments, %d vias" % (nt, nv))
    if not TWO_LAYER:
        jumpers = pcbgen.jumperize(board)
        print("wire jumpers: %d" % len(jumpers))
    else:
        import finish_router
        done, left = finish_router.finish(board, track_w=0.5, log=lambda *_: None)
        print("finishing router: %d more connections routed, still open: %s"
              % (done, [n.split("/")[-1] for n in left]))
    # ground pour on the copper side
    tmp = pcbgen.BoardBuilder.__new__(pcbgen.BoardBuilder)
    tmp.board, tmp.ox, tmp.oy = board, bb.ox, bb.oy
    tmp.nets = {n.GetNetname(): n for n in board.GetNetInfo().NetsByName().values()}
    for layer in ((pcbnew.F_Cu, pcbnew.B_Cu) if TWO_LAYER else (pcbnew.B_Cu,)):
        z = tmp.zone("GND", layer, [(0, 0), (W, 0), (W, H), (0, H)], clearance=0.6, min_width=0.6, name="GND pour")
        z.SetThermalReliefSpokeWidth(pcbgen.MM(0.8))
    board.Save(PCB)
    pcbgen.write_project_netclasses(os.path.join(KICAD, c.name + ".kicad_pro"), NETCLASSES, ASSIGN)


def run_freerouting(dsn, ses, rdir):
    import subprocess
    if os.path.exists(ses):
        os.remove(ses)
    cmd = [JAVA, "-Djava.awt.headless=true", "-jar", JAR, "-de", dsn, "-do", ses,
           "-mp", os.environ.get("FR_PASSES", "20"), "-mt", "4"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=int(os.environ.get("FR_TIMEOUT", "7200")))
    open(os.path.join(rdir, "freerouting.log"), "w").write(r.stdout[-20000:] + r.stderr[-20000:])


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


if __name__ == "__main__":
    if "--continue" in sys.argv:
        c.annotate()
        bb = pcbgen.BoardBuilder.__new__(pcbgen.BoardBuilder)
        bb.ox, bb.oy = 50.0, 50.0
        do_route(bb, "continue")
        fill_and_drc(PCB)
    else:
        main(route="import" if "--import-ses" in sys.argv else "--route" in sys.argv)
