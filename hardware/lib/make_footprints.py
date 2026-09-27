#!/usr/bin/env python3
"""Build agrinode.pretty: copies of stock KiCad footprints with pads narrowed so that
every pad-to-pad gap is >= MIN_GAP (for low-precision, home/CNC single-sided PCB making)."""
import itertools
import math
import os

import pcbnew

MIN_GAP = 0.55
STOCK = "/usr/share/kicad/footprints"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agrinode.pretty")
MM = pcbnew.FromMM


def pad_gap(a, b):
    """Gap between two pads: min vertex-to-polygon distance both ways (exact for convex pads)."""
    pa, pb = a.GetEffectivePolygon(), b.GetEffectivePolygon()

    def one_way(p, q):
        ol = p.COutline(0)
        return min(q.SquaredDistance(ol.CPoint(i)) for i in range(ol.PointCount()))
    d2 = min(one_way(pa, pb), one_way(pb, pa))
    return pcbnew.ToMM(int(d2 ** 0.5))


def min_gap(fp):
    pads = [p for p in fp.Pads() if p.GetNumber() and p.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH]
    best = (99, None)
    for a, b in itertools.combinations(pads, 2):
        if a.GetNumber() == b.GetNumber():
            continue
        if not (a.IsOnLayer(pcbnew.F_Cu) and b.IsOnLayer(pcbnew.F_Cu)) and \
                not (a.IsOnLayer(pcbnew.B_Cu) and b.IsOnLayer(pcbnew.B_Cu)):
            continue
        g = pad_gap(a, b)
        if g < best[0]:
            best = (g, (a.GetNumber(), b.GetNumber()))
    return best


def narrow(fp, pads_filter, new_min_dim):
    """Shrink the smaller dimension of matching pads to new_min_dim (mm)."""
    for p in fp.Pads():
        if not pads_filter(p):
            continue
        sz = p.GetSize()
        w, h = pcbnew.ToMM(sz.x), pcbnew.ToMM(sz.y)
        if w <= h and w > new_min_dim:
            p.SetSize(pcbnew.VECTOR2I(MM(new_min_dim), sz.y))
        elif h < w and h > new_min_dim:
            p.SetSize(pcbnew.VECTOR2I(sz.x, MM(new_min_dim)))


def drop_small_holes(fp, min_drill=0.6):
    """Mark thermal-via pads (drill < min_drill) for removal after saving (see build)."""
    fp._drop_drill = min_drill


def _strip_small_holes(path, min_drill):
    import re
    txt = open(path).read()
    out = []
    for line in txt.split("\n"):
        m = re.search(r"\(pad .*thru_hole.*\(drill ([0-9.]+)\)", line)
        if m and float(m.group(1)) < min_drill:
            continue
        out.append(line)
    open(path, "w").write("\n".join(out))


def resize_pad(fp, number, w, h):
    for p in fp.Pads():
        if p.GetNumber() == number:
            p.SetSize(pcbnew.VECTOR2I(MM(w), MM(h)))


def build(lib, name, new_name, edit, descr):
    fp = pcbnew.FootprintLoad(os.path.join(STOCK, lib + ".pretty"), name)
    edit(fp)
    fp.SetFPID(pcbnew.LIB_ID("agrinode", new_name))
    fp.SetDescription(descr)
    fp.Value().SetText(new_name)
    pcbnew.FootprintSave(OUT, fp)
    if getattr(fp, "_drop_drill", None):
        path = os.path.join(OUT, new_name + ".kicad_mod")
        _strip_small_holes(path, fp._drop_drill)
        fp = pcbnew.FootprintLoad(OUT, new_name)
    g, pair = min_gap(fp)
    print("%-32s min pad gap %.2f mm %s" % (new_name, g, pair))
    assert g >= MIN_GAP - 1e-6, new_name


def main():
    if not os.path.isdir(OUT):
        pcbnew.FootprintLibCreate(OUT) if hasattr(pcbnew, "FootprintLibCreate") else os.makedirs(OUT)
    numbered = lambda p: p.GetNumber().isdigit() and int(p.GetNumber()) <= 38  # noqa: E731
    def esp(fp):
        narrow(fp, numbered, 0.70)
        drop_small_holes(fp)
    build("RF_Module", "ESP32-WROOM-32", "ESP32-WROOM-32E_Coarse", esp,
          "ESP32-WROOM-32E with castellation pads narrowed to 0.70 mm (gap >= 0.55 mm) for coarse PCB processes")
    build("RF_GSM", "SIMCom_SIM800C", "SIMCom_SIM800C_Coarse", lambda fp: narrow(fp, lambda p: True, 0.55),
          "SIM800C LCC with pads narrowed for coarse PCB processes")
    build("RF_Module", "Ai-Thinker-Ra-01-LoRa", "Ai-Thinker-Ra-02_Coarse", lambda fp: narrow(fp, lambda p: True, 0.90),
          "Ai-Thinker Ra-01/Ra-02 with pads narrowed for coarse PCB processes")

    def round_pads(fp, dia, numbers):
        for p in fp.Pads():
            if p.GetNumber() in numbers:
                p.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
                p.SetSize(pcbnew.VECTOR2I(MM(dia), MM(dia)))
    build("Connector_USB", "USB_B_OST_USB-B1HSxx_Horizontal", "USB_B_THT_Coarse",
          lambda fp: round_pads(fp, 1.44, {"1", "2", "3", "4"}),  # 0.26 mm ring on the 0.92 drill
          "USB Type-B THT receptacle (power input), signal pads reduced for coarse PCB processes")
    def led(fp):
        round_pads(fp, 1.8, {"1", "2", "3", "4"})
        pads = sorted(fp.Pads(), key=lambda p: int(p.GetNumber()))
        x0 = pads[0].GetPosition().x
        for i, p in enumerate(pads):
            pos = pcbnew.VECTOR2I(x0 + MM(2.54 * i), p.GetPosition().y)
            p.SetPosition(pos)
            p.SetPos0(pos)
            p.SetDrillSize(pcbnew.VECTOR2I(MM(0.9), MM(0.9)))
    build("LED_THT", "LED_D5.0mm-4_RGB_Wide_Pins", "LED_PL9823_D5.0mm_Coarse", led,
          "PL9823-F5 / WS2812 THT 5 mm addressable RGB LED, leads on 2.54 mm")

    def tp4056(fp):
        resize_pad(fp, "9", 1.9, 2.6)
        drop_small_holes(fp)
        for p in fp.Pads():
            if p.GetNumber() == "9":
                continue
        # keep only the solder-paste/mask copper centre pad; drop the split paste pads
    build("Package_SO", "SOIC-8-1EP_3.9x4.9mm_P1.27mm_EP2.29x3mm", "ESOP-8_TP4056_Coarse", tp4056,
          "ESOP-8 (TP4056) with reduced exposed pad for coarse PCB processes")


if __name__ == "__main__":
    main()
