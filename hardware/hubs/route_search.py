#!/usr/bin/env python3
"""Try several Freerouting cost settings for one hub variant and keep the best routed board.

    python3 route_search.py <variant> [via_cost:top_cost ...]

Single-threaded Freerouting is deterministic, so a different result needs different costs.
Each trial runs `pcb.py <variant> --route`; the board with the fewest open connections (then the
fewest DRC violations) is restored at the end.
"""
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
VARIANT = sys.argv[1]
TRIALS = sys.argv[2:] or ["40:1.5", "20:1.5", "80:1.5", "40:1.0", "40:2.5", "10:1.2"]
KICAD = os.path.join(HERE, VARIANT, "kicad")
OUT = os.path.join(HERE, VARIANT, "outputs")
PCB = os.path.join(KICAD, [f for f in os.listdir(KICAD) if f.endswith(".kicad_pcb")][0])
KEEP = [PCB, os.path.join(OUT, "drc.rpt"), os.path.join(OUT, "route", os.path.basename(PCB)[:-10] + ".ses")]


HARD = ("clearance", "shorting_items", "tracks_crossing", "hole_clearance", "copper_edge_clearance",
        "track_width", "via_diameter", "annular_width", "drill_out_of_range")


def score(log):
    """(open + hard DRC errors, open, all DRC): a short or clearance error counts like an open net."""
    m = re.search(r"open connections: \[(.*)\]", log)
    opened = len([x for x in m.group(1).split(",") if x.strip()]) if m else 999
    m = re.search(r"DRC violations: (\d+)", log)
    total = int(m.group(1)) if m else 999
    rpt = open(os.path.join(OUT, "drc.rpt")).read()
    hard = sum(len(re.findall(r"^\[%s\]" % k, rpt, re.M)) for k in HARD)
    m = re.search(r"Found (\d+) unconnected", rpt)   # includes GND pour islands
    opened = max(opened, int(m.group(1)) if m else 0)
    return opened + hard, opened, hard, total


best = None
for i, trial in enumerate(TRIALS):
    via, top = trial.split(":")
    env = dict(os.environ, FR_VIA_COST=via, FR_TOP_COST=top, RIPUP="0")
    r = subprocess.run([sys.executable, os.path.join(HERE, "pcb.py"), VARIANT, "--route"], env=env,
                       capture_output=True, text=True)
    log = r.stdout + r.stderr
    s = score(log)
    print("trial %s  via %s top %s  ->  open %d, hard DRC %d, DRC %d" % (i, via, top, s[1], s[2], s[3]), flush=True)
    if best is None or s < best[0]:
        store = os.path.join(OUT, "route", "best_trial")
        shutil.rmtree(store, ignore_errors=True)
        os.makedirs(store)
        for f in KEEP:
            shutil.copy(f, store)
        best = (s, trial)
    if s[0] == 0:
        break
store = os.path.join(OUT, "route", "best_trial")
for f in KEEP:  # rip-up is skipped during the search: run `pcb.py <variant> --import-ses` on the winner
    shutil.copy(os.path.join(store, os.path.basename(f)), f)
shutil.rmtree(store, ignore_errors=True)
print("best: via:top %s -> open %d, hard DRC %d, DRC %d" % (best[1], best[0][1], best[0][2], best[0][3]))
