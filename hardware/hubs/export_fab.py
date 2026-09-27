#!/usr/bin/env python3
"""Fabrication files for one hub variant: Gerber + Excellon drill + zip.

    python3 export_fab.py <variant>
"""
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LAYERS = "F.Cu,B.Cu,F.Mask,B.Mask,F.Silkscreen,B.Silkscreen,Edge.Cuts"


def main(variant):
    kicad = os.path.join(HERE, variant, "kicad")
    pcb = os.path.join(kicad, [f for f in os.listdir(kicad) if f.endswith(".kicad_pcb")][0])
    fab = os.path.join(HERE, variant, "outputs", "fab")
    shutil.rmtree(fab, ignore_errors=True)
    os.makedirs(fab)
    subprocess.run(["kicad-cli", "pcb", "export", "gerbers", pcb, "-o", fab + "/", "-l", LAYERS,
                    "--subtract-soldermask"], check=True, capture_output=True)
    subprocess.run(["kicad-cli", "pcb", "export", "drill", pcb, "-o", fab + "/", "--excellon-separate-th",
                    "--generate-map", "--map-format", "pdf"], check=True, capture_output=True)
    zipbase = os.path.join(HERE, variant, "outputs", os.path.basename(pcb)[:-10] + "_gerbers")
    shutil.make_archive(zipbase, "zip", fab)
    print("\n".join(sorted(os.listdir(fab))))
    print("zip:", zipbase + ".zip")


if __name__ == "__main__":
    main(sys.argv[1])
