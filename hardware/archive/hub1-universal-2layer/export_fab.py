#!/usr/bin/env python3
"""Export fabrication files (Gerber + Excellon drill + zip) for the HUB-1 board."""
import os
import shutil
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.join(HERE, "kicad", "agrinode_hub.kicad_pcb")
FAB = os.path.join(HERE, "outputs", "fab")
LAYERS = "F.Cu,B.Cu,F.Mask,B.Mask,F.Silkscreen,B.Silkscreen,Edge.Cuts"


def main():
    shutil.rmtree(FAB, ignore_errors=True)
    os.makedirs(FAB)
    subprocess.run(["kicad-cli", "pcb", "export", "gerbers", PCB, "-o", FAB + "/", "-l", LAYERS,
                    "--subtract-soldermask"], check=True, capture_output=True)
    subprocess.run(["kicad-cli", "pcb", "export", "drill", PCB, "-o", FAB + "/", "--excellon-separate-th",
                    "--generate-map", "--map-format", "pdf"], check=True, capture_output=True)
    zipbase = os.path.join(HERE, "outputs", "agrinode_hub_gerbers")
    shutil.make_archive(zipbase, "zip", FAB)
    print("\n".join(sorted(os.listdir(FAB))))
    print("zip:", zipbase + ".zip")


if __name__ == "__main__":
    main()
