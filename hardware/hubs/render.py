#!/usr/bin/env python3
"""Render PNG views of a hub PCB:  python3 render.py <variant> [place]"""
import os
import subprocess
import sys

import cairosvg

HERE = os.path.dirname(os.path.abspath(__file__))
V = sys.argv[1]
KICAD = os.path.join(HERE, V, "kicad")
PCB = os.path.join(KICAD, [f for f in os.listdir(KICAD) if f.endswith(".kicad_pcb")][0])
OUT = os.path.join(HERE, V, "outputs")
TMP = os.environ.get("TMPDIR", "/tmp")

VIEWS = {
    "top": ("Edge.Cuts,F.Cu,F.SilkS,F.Mask", False),
    "bottom": ("Edge.Cuts,B.Cu,B.SilkS", True),
    "assembly": ("Edge.Cuts,F.Fab,F.SilkS", False),
}
if len(sys.argv) > 2 and sys.argv[2] == "place":
    VIEWS = {"placement": ("Edge.Cuts,F.Fab,F.Courtyard,F.Cu,B.Cu", False)}

for name, (layers, mirror) in VIEWS.items():
    svg = os.path.join(TMP, "%s_%s.svg" % (V, name))
    cmd = ["kicad-cli", "pcb", "export", "svg", PCB, "-o", svg, "--layers", layers,
           "--page-size-mode", "2", "--exclude-drawing-sheet"] + (["--mirror"] if mirror else [])
    subprocess.run(cmd, check=True, capture_output=True)
    png = os.path.join(OUT if name != "placement" else TMP, "pcb_%s.png" % name)
    cairosvg.svg2png(url=svg, write_to=png, output_width=2000, background_color="white")
    print(png)
