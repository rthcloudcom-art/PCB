#!/usr/bin/env python3
"""Build agrinode.kicad_sym (parts missing from the stock KiCad library)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tools", "kigen"))
from sexp import Sym, dump  # noqa: E402

F = [Sym("effects"), [Sym("font"), [Sym("size"), 1.27, 1.27]]]
FH = [Sym("effects"), [Sym("font"), [Sym("size"), 1.27, 1.27]], Sym("hide")]


def prop(k, v, x, y, hide=False):
    return [Sym("property"), k, v, [Sym("at"), x, y, 0], FH if hide else F]


def pin(etype, num, name, x, y, ang, hidden=False):
    p = [Sym("pin"), Sym(etype), Sym("line"), [Sym("at"), x, y, ang], [Sym("length"), 2.54]]
    if hidden:
        p.append(Sym("hide"))
    p += [[Sym("name"), name, F], [Sym("number"), num, F]]
    return p


def symbol(name, ref, fp, desc, w, h, pins, datasheet=""):
    body = [Sym("rectangle"), [Sym("start"), -w, h], [Sym("end"), w, -h],
            [Sym("stroke"), [Sym("width"), 0.254], [Sym("type"), Sym("default")]],
            [Sym("fill"), [Sym("type"), Sym("background")]]]
    return [Sym("symbol"), name, [Sym("in_bom"), Sym("yes")], [Sym("on_board"), Sym("yes")],
            prop("Reference", ref, 0, h + 1.27), prop("Value", name, 0, -h - 1.27),
            prop("Footprint", fp, 0, -h - 3.81, True), prop("Datasheet", datasheet, 0, 0, True),
            prop("ki_description", desc, 0, 0, True),
            [Sym("symbol"), name + "_0_1", body],
            [Sym("symbol"), name + "_1_1"] + pins]


lib = [Sym("kicad_symbol_lib"), [Sym("version"), 20220914], [Sym("generator"), Sym("kigen")],
       symbol("TP4056", "U", "agrinode:ESOP-8_TP4056_Coarse",
              "1 A linear Li-ion charger, ESOP-8 (NanJing Top Power)", 7.62, 7.62, [
                  pin("power_in", "4", "VCC", -10.16, 5.08, 0),
                  pin("input", "8", "CE", -10.16, 2.54, 0),
                  pin("input", "1", "TEMP", -10.16, -2.54, 0),
                  pin("passive", "2", "PROG", -10.16, -5.08, 0),
                  pin("power_out", "5", "BAT", 10.16, 5.08, 180),
                  pin("open_collector", "7", "~{CHRG}", 10.16, 0, 180),
                  pin("open_collector", "6", "~{STDBY}", 10.16, -2.54, 180),
                  pin("power_in", "3", "GND", 0, -10.16, 90),
                  pin("passive", "9", "GND", 0, -10.16, 90, hidden=True),
              ]),
       symbol("PL9823", "D", "agrinode:LED_PL9823_D5.0mm_Coarse",
              "Addressable RGB LED, 5 mm THT (WS2812 protocol). Check lead order of the supplier", 5.08, 5.08, [
                  pin("input", "1", "DIN", -7.62, 0, 0),
                  pin("power_in", "2", "VDD", 0, 7.62, 270),
                  pin("power_in", "3", "GND", 0, -7.62, 90),
                  pin("output", "4", "DOUT", 7.62, 0, 180),
              ]),
       ]
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agrinode.kicad_sym")
open(out, "w").write(dump(lib) + "\n")
print("wrote", out)
