#!/usr/bin/env python3
"""Generate the AgriNode MC-1 PCB (placement, zones, rules) and optionally
auto-route it with Freerouting.

    python3 pcb.py              # placement + zones only
    python3 pcb.py --route      # also run Freerouting and import the result
    python3 pcb.py --import-ses # rebuild and import outputs/route/agrinode_mc.ses from an earlier run

Run build.py first (it produces outputs/agrinode_mc.net which provides the
exact KiCad net names).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "design"))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "tools", "kigen"))

os.environ.setdefault("KICAD7_FOOTPRINT_DIR", "/usr/share/kicad/footprints")
os.environ.setdefault("KICAD7_SYMBOL_DIR", "/usr/share/kicad/symbols")
import pcbnew  # noqa: E402

import pcbgen  # noqa: E402
from main_controller import c  # noqa: E402

KICAD = os.path.join(HERE, "kicad")
OUT = os.path.join(HERE, "outputs")
PCB = os.path.join(KICAD, c.name + ".kicad_pcb")
JAR = os.environ.get("FREEROUTING_JAR", "/tmp/claude-0/fr/freerouting.jar")
JAVA = os.environ.get("FREEROUTING_JAVA", "/usr/lib/jvm/java-25-openjdk-amd64/bin/java")

W, H = 240.0, 180.0          # board size (mm)
HV_BOTTOM = 40.0             # relay contact area ends here (y)
HV_GAP = 4.0                 # creepage band to low-voltage area
ISO_X = 36.0                 # isolation barrier of RS-485 B (x), iso side is x < ISO_X
ISO_Y = 125.0                # iso area starts below this y


def main(route=False):
    c.annotate()
    pin_net = pcbgen.load_kicad_netlist(os.path.join(OUT, c.name + ".net"))
    bb = pcbgen.BoardBuilder(c, PCB)
    bb.add_footprints(pin_net)
    bb.outline(W, H)

    def val(v):
        hits = [r for r, p in bb.part_of.items() if p.value == v]
        assert len(hits) == 1, (v, hits)
        return hits[0]

    def block(prefix, exclude=()):
        return [r for r, t in bb.block_of.items() if t.startswith(prefix) and r not in exclude
                and not getattr(bb.fps[r], "_placed", False)]

    def pack(prefix, x0, y0, x1, y1):
        refs = block(prefix)
        # biggest parts first so ICs anchor the cluster
        refs.sort(key=lambda r: -(lambda b: (b[2] - b[0]) * (b[3] - b[1]))(bb.bbox(bb.fps[r])))
        over = bb.pack(refs, x0, y0, x1, y1)
        if over:
            print("  region overflow in '%s': %s" % (prefix, over))

    # ---------------------------------------------------------- HV relay row
    pitch = 25.0
    for i in range(1, 9):
        x = 16.0 + (i - 1) * pitch
        bb.put(val("RELAY %d" % i), x, 0.0, rot=180, anchor="tl")
        k = [r for r in block("Relay output %d " % i) if r.startswith("K")][0]
        bb.put(k, x + 1.0, 15.0, rot=90, anchor="tl")
        pack("Relay output %d " % i, x, HV_BOTTOM + HV_GAP, x + pitch - 2, HV_BOTTOM + HV_GAP + 7)
    holes = sorted(r for r in bb.fps if r.startswith("H"))
    for r, (x, y) in zip(holes, ((5, 5), (W - 5, 5), (5, H - 5), (W - 5, H - 5))):
        bb.put(r, x, y, anchor="cc")

    # ------------------------------------------------ column 1: power, RS-485
    bb.put(val("MAIN IN 9-32V"), 0.0, 48.0, rot=270, anchor="tl")
    bb.put(val("BATTERY IN 9-32V"), 0.0, 64.0, rot=270, anchor="tl")
    pack("DC inputs", 15, 53, 58, 78)
    pack("Field supply", 15, 79, 58, 88)
    pack("Mains-fail", 15, 89, 58, 98)
    bb.put(val("RS485-A EXP BUS"), 0.0, 102.0, rot=270, anchor="tl")
    bb.put(val("RS485-B FIELD"), 0.0, 130.0, rot=270, anchor="tl")
    pack("RS-485 A", 15, 101, 58, 123)
    # isolated transceiver: bus side (pins 11-20) faces the terminal
    adm = [r for r in block("RS-485 B") if bb.part_of[r].value == "ADM2587E"][0]
    bb.put(adm, ISO_X - 5.5, 130.0, rot=180, anchor="tl")
    iso_nets = {"VISO", "GND_ISO", "RS485B_A", "RS485B_B", "RS485B_TERM"}
    iso = [r for r in block("RS-485 B")
           if {pd.GetNetname().split("/")[-1] for pd in bb.fps[r].Pads()} <= iso_nets]
    iso.sort(key=lambda r: -(lambda b: (b[2] - b[0]) * (b[3] - b[1]))(bb.bbox(bb.fps[r])))
    bb.pack(iso, 15, 126, ISO_X - 7, H - 12)
    bb.pack(block("RS-485 B"), ISO_X + 7.5, 126, 49, H - 12)

    # ------------------------------------------------ column 2: expander #1, bucks
    pack("I/O expander #1", 60, 53, 108, 71)
    pack("5 V / 3.5 A buck", 60, 72, 108, 99)
    pack("3.3 V / 3 A buck", 60, 100, 91, 118)

    # ------------------------------------------------ right edge (fixed parts first)
    esp = [r for r in block("ESP32-S3") if r.startswith("U")][0]
    fp = bb.fps[esp]
    fp._fab_bbox = True
    fp.SetOrientationDegrees(270)
    fp.SetPosition(pcbgen.V(bb.ox + W - 12.8, bb.oy + 60.0))
    fp._placed = True
    bb.put(val("ETHERNET"), W, 86.0, rot=90, anchor="tr")
    bb.put(val("USB-C"), W + 1.0, 108.0, rot=90, anchor="tr")
    bb.put(val("I2C EXT"), W, 122.0, rot=90, anchor="tr")
    bb.put(val("1-WIRE"), W, 148.0, rot=90, anchor="tr")
    pack("ESP32-S3", W - 54, 50, W - 27, 75)
    pack("External watchdog", 92, 100, 108, 113)
    pack("USB-C", W - 30, 106, W - 11, 113)
    pack("USB bench", W - 32, 113, W - 14, 118)
    pack("External I2C", W - 30, 120, W - 15, 144)
    pack("1-Wire", W - 30, 146, W - 15, 164)

    # ------------------------------------------------ column 3: RTC, expander #2, modem
    pack("RTC", 110, 53, 151, 83)
    pack("Cellular modem slot", 110, 84, 125, 122)
    pack("I/O expander #2", 126, 84, 151, 100)
    bb.put(val("microSD"), 127, 101, rot=0, anchor="tl")
    pack("microSD", 144, 101, 151, 126)

    # ------------------------------------------------ column 4: LoRa, Ethernet
    pack("LoRa", 152, 50, 185, 76)
    pack("Ethernet", 152, 77, W - 32, 97)

    # ------------------------------------------------ front panel strip
    pack("Front panel", 152, 98, W - 33, 120)

    # ------------------------------------------------ bottom: field I/O
    x = 50.0
    xs = {}
    for name in ("DI 1-4", "DI 5-8", "AI 1-2", "AI 3-4", "AO 1-2", "OUT 1-2", "OUT 3-4"):
        ref = val(name)
        bb.put(ref, x, H, rot=0, anchor="bl")
        xs[name] = (x, bb.bbox(bb.fps[ref])[2])
        x = xs[name][1] + 2.0
    top = H - 48.0
    pack("Digital inputs 1-4", xs["DI 1-4"][0], top, xs["DI 1-4"][1], H - 14)
    pack("Digital inputs 5-8", xs["DI 5-8"][0], top, xs["DI 5-8"][1], H - 14)
    a0, a1 = xs["AI 1-2"][0], xs["AI 3-4"][1]
    pack("16-bit ADC", a0, top - 8, a1, top - 1)
    aw = (a1 - a0) / 2
    for i in range(1, 5):
        cx, cy = a0 + (i - 1) % 2 * aw, top + (i - 1) // 2 * 13
        pack("Analog input %d:" % i, cx, cy, cx + aw - 1, cy + 12.5)
    pack("Analog input terminals", a0, H - 14, a1, H - 13)
    pack("Analog outputs", xs["AO 1-2"][0], top - 8, xs["AO 1-2"][1], H - 14)
    o0, o1 = xs["OUT 1-2"][0], min(xs["OUT 3-4"][1], W - 32)
    ow = (o1 - o0) / 2
    for i in range(1, 5):
        cx, cy = o0 + (i - 1) % 2 * ow, top - 12 + (i - 1) // 2 * 22
        pack("MOSFET output %d " % i, cx, cy, cx + ow - 1, cy + 21.5)

    save_and_report(bb, route)


NETCLASSES = {
    "Default": dict(track=0.25, clearance=0.2),
    "Power": dict(track=0.8, clearance=0.3, via=0.8, drill=0.4),
    "Supply3V3": dict(track=0.5, clearance=0.2, via=0.8, drill=0.4),
    "Load": dict(track=1.2, clearance=0.3, via=0.8, drill=0.4),
    "Mains": dict(track=2.5, clearance=2.5, via=1.2, drill=0.6),
}
ASSIGN = [  # KiCad wildcard patterns on the full net name (local nets carry a /sheet/ prefix)
    ("*RLY?_COM", "Mains"), ("*RLY?_NO", "Mains"), ("*RLY?_NC", "Mains"),
    ("*/OUT?", "Power"), ("*VFIELD", "Power"), ("*VSYS", "Power"), ("*VIN_*_RAW", "Power"),
    ("*VIN_*_F", "Power"), ("*+5V", "Power"), ("*BUCK5_SW", "Power"), ("*VBUS_USB", "Supply3V3"),
    ("*VSENS", "Load"), ("*V_1W", "Load"), ("*V_I2C", "Load"), ("*VISO", "Load"), ("*GND_ISO", "Load"),
    ("*BUCK3_SW", "Load"), ("*RLY?_COIL", "Load"),
    ("*+3V3", "Supply3V3"), ("*+3V3A", "Supply3V3"), ("*GND", "Supply3V3"),
]


def zones(bb):
    lv_top = HV_BOTTOM + HV_GAP - 1
    iso_y0 = ISO_Y
    gap = 1.5
    main = [(0, lv_top), (W, lv_top), (W, H), (ISO_X + gap, H), (ISO_X + gap, iso_y0 - gap), (0, iso_y0 - gap)]
    iso = [(0, iso_y0 + gap), (ISO_X - gap, iso_y0 + gap), (ISO_X - gap, H), (0, H)]
    bb.zone("GND", pcbnew.In1_Cu, main, name="GND plane")
    bb.zone("+3V3", pcbnew.In2_Cu, main, name="3V3 plane")
    bb.zone("GND_ISO", pcbnew.In1_Cu, iso, name="GND_ISO plane")
    bb.zone("GND_ISO", pcbnew.In2_Cu, iso, name="GND_ISO plane in2")
    # ESP32 antenna keep-out on every copper layer
    ant = [(W - 7.5, 60 - 10), (W, 60 - 10), (W, 60 + 10), (W - 7.5, 60 + 10)]
    z = bb.zone(None, pcbnew.F_Cu, ant, keepout=True, name="antenna keepout")
    ls = pcbnew.LSET()
    for l in (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu):
        ls.AddLayer(l)
    z.SetLayerSet(ls)
    z.SetDoNotAllowTracks(True)
    z.SetDoNotAllowVias(True)
    return main, iso


def pours(bb, main, iso):
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        bb.zone("GND", layer, main, name="GND pour")
        bb.zone("GND_ISO", layer, iso, name="GND_ISO pour")


ABBR = [(r"RLY\d_COM", "C"), (r"RLY\d_(NO|NC)", r"\1"), (r"(DI\d)_IN", r"\1"), (r"DI_COM\d", "COM"),
        (r"VSENS|VFIELD", "24V"), (r"(A[IO]\d)_T", r"\1"), (r"OUT(\d)", r"Q\1"), (r"RS485._([AB])", r"\1"),
        (r"GND_ISO", "GNDi"), (r"V_1W|V_I2C", "3V3"), (r"ONEWIRE_T", "DQ"), (r"I2C_(SDA|SCL)", r"\1"),
        (r"VIN_.*_RAW", "+"), (r"GND", "GND")]


def terminal_labels(bb):
    import re
    for ref, p in bb.part_of.items():
        if not p.lib_id.startswith("Connector:Screw_Terminal"):
            continue
        fp = bb.fps[ref]
        x0, y0, x1, y1 = bb.bbox(fp)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        edge = min((cy, "t"), (H - cy, "b"), (cx, "l"), (W - cx, "r"))[1]
        for pad in fp.Pads():
            net = pad.GetNetname().split("/")[-1]
            txt = net
            for pat, rep in ABBR:
                if re.fullmatch(pat, net):
                    txt = re.sub(pat, rep, net)
                    break
            px = pcbnew.ToMM(pad.GetPosition().x) - bb.ox
            py = pcbnew.ToMM(pad.GetPosition().y) - bb.oy
            dx, dy = {"t": (0, 3.6), "b": (0, -3.6), "l": (3.6, 0), "r": (-3.6, 0)}[edge]
            bb.text(txt, px + dx, py + dy, size=1.0, angle=90 if edge in "lr" else 0)


def silk(bb):
    terminal_labels(bb)
    bb.line(0, HV_BOTTOM + HV_GAP / 2, W, HV_BOTTOM + HV_GAP / 2, width=0.3)
    bb.text("!! 250 VAC - RELAY CONTACT AREA !!", 110, HV_BOTTOM + 0.2, size=1.5)
    bb.line(ISO_X, ISO_Y, ISO_X, H, width=0.3)
    bb.line(0, ISO_Y, ISO_X, ISO_Y, width=0.3)
    bb.text("ISOLATED", ISO_X / 2 + 5, H - 3, size=1.2)
    bb.text("AgriNode MC-1  rev A", 130, H - 2.5, size=2.0)


def save_and_report(bb, route):
    bb.netclasses(NETCLASSES, ASSIGN)
    main, iso = zones(bb)
    silk(bb)
    bb.save()
    # KiCad 7 keeps net classes in the project file; write it after the board save
    pcbgen.write_project_netclasses(os.path.join(KICAD, c.name + ".kicad_pro"), NETCLASSES, ASSIGN)
    ov = bb.overlaps()
    print("footprints:", len(bb.fps), "overlapping pairs:", len(ov))
    for a, b in ov[:40]:
        print("  overlap", a, b)
    if not route:
        fill_and_drc(PCB)
        return
    os.makedirs(os.path.join(OUT, "route"), exist_ok=True)
    dsn = os.path.join(OUT, "route", c.name + ".dsn")
    ses = os.path.join(OUT, "route", c.name + ".ses")
    if route != "import":  # "import": reuse a session file from an earlier Freerouting run
        if os.path.exists(ses):
            os.remove(ses)
        log = pcbgen.freeroute(PCB, dsn, ses, JAR, JAVA, passes=int(os.environ.get("FR_PASSES", "30")),
                               timeout=int(os.environ.get("FR_TIMEOUT", "14400")))
        open(os.path.join(OUT, "route", "freerouting.log"), "w").write(log)
    board = pcbgen.load(PCB)
    nt, nv = pcbgen.import_ses(board, ses)
    print("imported %d track segments, %d vias" % (nt, nv))
    # mains relay contacts: carry them on both outer layers (thick copper, visible, no inner-layer heat)
    import re
    for t in [t for t in board.GetTracks() if re.search(r"RLY\d_(COM|NO|NC)$", t.GetNetname())]:
        if t.GetClass() != "PCB_TRACK":
            continue
        t.SetLayer(pcbnew.B_Cu)
        d = pcbnew.PCB_TRACK(board)
        d.SetStart(t.GetStart())
        d.SetEnd(t.GetEnd())
        d.SetWidth(t.GetWidth())
        d.SetNet(t.GetNet())
        d.SetLayer(pcbnew.F_Cu)
        board.Add(d)
    tmp = pcbgen.BoardBuilder.__new__(pcbgen.BoardBuilder)
    tmp.board, tmp.ox, tmp.oy, tmp.nets = board, bb.ox, bb.oy, {n.GetNetname(): n for n in board.GetNetInfo().NetsByName().values()}
    pours(tmp, main, iso)
    board.Save(PCB)
    pcbgen.write_project_netclasses(os.path.join(KICAD, c.name + ".kicad_pro"), NETCLASSES, ASSIGN)
    fill_and_drc(PCB)


def fill_and_drc(path):
    board = pcbgen.load(path)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(path)
    pcbgen.write_project_netclasses(os.path.join(KICAD, c.name + ".kicad_pro"), NETCLASSES, ASSIGN)
    board = pcbgen.load(path)  # re-resolve net classes from the rewritten project before DRC
    rpt = os.path.join(OUT, "drc.rpt")
    pcbnew.WriteDRCReport(board, rpt, pcbnew.EDA_UNITS_MILLIMETRES, True)
    txt = open(rpt).read()
    import re
    for key in ("violations", "unconnected pads", "footprint errors"):
        m = re.search(r"\*\* Found (\d+) (?:DRC )?%s" % key, txt)
        print("DRC %s: %s" % (key, m.group(1) if m else "?"))


if __name__ == "__main__":
    main(route="import" if "--import-ses" in sys.argv else "--route" in sys.argv)
