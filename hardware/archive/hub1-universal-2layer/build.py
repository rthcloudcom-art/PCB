#!/usr/bin/env python3
"""Regenerate the AgriNode MC-1 KiCad project from design/main_controller.py.

Steps: design checks -> schematic -> KiCad netlist export -> netlist comparison
-> BOM -> PDF/SVG plots. PCB generation lives in pcb.py (run separately so a
hand-edited layout is never overwritten by accident).
"""
import csv
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "design"))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "tools", "kigen"))

import schgen  # noqa: E402
from circuit import NC  # noqa: E402
from hub import c  # noqa: E402
from sexp import find, find_all, parse  # noqa: E402

KICAD = os.path.join(HERE, "kicad")
OUT = os.path.join(HERE, "outputs")

NOTES = [
    "AgriNode HUB-1 - universal gateway hub (single-sided PCB)",
    "Variants by assembly option: HUB-W (Wi-Fi), HUB-L (+LORA), HUB-C (+CELL), GW-LAN (+LORA +ETH); BUZ optional",
    "ESP32-WROOM-32E | LoRa Ra-02 433 MHz | SIM800C 2G | ENC28J60 10BASE-T | I2C expansion header",
    "Power: 12 V jack/terminal, solar 6-24 V, USB-B 5 V, 18650 cell with TP4056 charger + NTC, power path, MIC29302 3.3 V",
    "6x PL9823 addressable RGB status LEDs, RESET and BOOT/PAIR buttons, buzzer",
    "Source of truth: design/hub.py - regenerate with build.py",
]


def write_project():
    pro = {
        "meta": {"filename": c.name + ".kicad_pro", "version": 1},
        "board": {"design_settings": {"defaults": {}, "rules": {}}},
        "net_settings": {"classes": [
            {"name": "Default", "clearance": 0.2, "track_width": 0.25, "via_diameter": 0.6, "via_drill": 0.3,
             "diff_pair_width": 0.2, "diff_pair_gap": 0.25, "bus_width": 12, "line_style": 0, "wire_width": 6,
             "microvia_diameter": 0.3, "microvia_drill": 0.1, "pcb_color": "rgba(0, 0, 0, 0.000)",
             "schematic_color": "rgba(0, 0, 0, 0.000)"}],
            "meta": {"version": 3}},
        "schematic": {"legacy_lib_dir": "", "legacy_lib_list": []},
        "sheets": [[schgen.stable_uuid(c.name, "root"), ""]] + [
            [schgen.stable_uuid(c.name, "sheet", s.name), s.title] for s in c.sheets],
        "text_variables": {},
    }
    path = os.path.join(KICAD, c.name + ".kicad_pro")
    if os.path.exists(path):  # keep net classes written by pcb.py
        old = json.load(open(path))
        if old.get("net_settings", {}).get("netclass_patterns"):
            pro["net_settings"] = old["net_settings"]
    with open(path, "w") as f:
        json.dump(pro, f, indent=2)


def compare_netlist(path):
    """Check KiCad's own connectivity against the design intent."""
    tree = parse(open(path, encoding="utf-8").read())
    got = {}
    for net in find_all(find(tree, "nets"), "net"):
        name = find(net, "name")[1]
        nodes = frozenset((find(n, "ref")[1], find(n, "pin")[1]) for n in find_all(net, "node"))
        got[nodes] = name
    want = {}
    for net, pins in c.netlist().items():
        want[frozenset(x for x in pins if not x[0].startswith("#"))] = net
    # KiCad also lists single unconnected pins as nets; ignore those
    got = {k: v for k, v in got.items() if not (len(k) == 1 and v.startswith("unconnected-"))}
    missing = [want[k] for k in want if k not in got]
    extra = [got[k] for k in got if k not in want]
    return missing, extra


VARIANTS = {
    "HUB-W": set(),
    "HUB-L": {"LORA"},
    "HUB-C": {"CELL"},
    "GW-LAN": {"LORA", "ETH"},
}
EXTRAS = {"BUZ"}


def write_lib_tables():
    lib = "${KIPRJMOD}/../../lib/agrinode"
    open(os.path.join(KICAD, "sym-lib-table"), "w").write(
        '(sym_lib_table\n  (lib (name "agrinode")(type "KiCad")(uri "%s.kicad_sym")(options "")(descr "AgriNode parts"))\n)\n' % lib)
    open(os.path.join(KICAD, "fp-lib-table"), "w").write(
        '(fp_lib_table\n  (lib (name "agrinode")(type "KiCad")(uri "%s.pretty")(options "")(descr "AgriNode coarse-process footprints"))\n)\n' % lib)


def write_variant_boms():
    """One BOM per variant (all optional extras fitted) so each hub type can be ordered separately."""
    for name, opts in VARIANTS.items():
        fitted = opts | EXTRAS
        rows = {}
        for p in c.parts:
            if not p.bom or p.ref.startswith("#"):
                continue
            opt = getattr(p, "option", None)
            if opt and opt not in fitted:
                continue
            if "fit if no NTC" in p.value:
                continue
            rows.setdefault((p.value, p.footprint.split(":")[-1]), []).append(p.ref)
        with open(os.path.join(OUT, "bom_%s.csv" % name), "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["Qty", "Value", "Footprint", "References"])
            for (val, fp), refs in sorted(rows.items()):
                w.writerow([len(refs), val, fp, " ".join(sorted(refs))])


def write_bom():
    rows = {}
    for p in c.parts:
        if not p.bom or p.ref.startswith("#"):
            continue
        key = (p.value, p.footprint, p.lib_id, getattr(p, "option", None) or "CORE")
        rows.setdefault(key, []).append(p.ref)

    def refkey(r):
        head = r.rstrip("0123456789")
        return head, int(r[len(head):] or 0)

    with open(os.path.join(OUT, "bom.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Qty", "Value", "Footprint", "Symbol", "Option", "References"])
        for (val, fp, lib, opt), refs in sorted(rows.items(), key=lambda kv: refkey(sorted(kv[1], key=refkey)[0])):
            refs = sorted(refs, key=refkey)
            w.writerow([len(refs), val, fp.split(":")[-1], lib, opt, " ".join(refs)])
    return sum(len(v) for v in rows.values()), len(rows)


def main():
    os.makedirs(KICAD, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)
    papers = schgen.write(c, KICAD, NOTES)
    write_project()
    write_lib_tables()
    print("schematic sheets:", papers)
    root = os.path.join(KICAD, c.name + ".kicad_sch")
    net = os.path.join(OUT, c.name + ".net")
    subprocess.run(["kicad-cli", "sch", "export", "netlist", root, "-o", net], check=True, capture_output=True)
    missing, extra = compare_netlist(net)
    if missing or extra:
        print("NETLIST MISMATCH\n missing:", missing, "\n extra:", extra)
        sys.exit(1)
    print("netlist check: KiCad connectivity matches design (%d nets)" % len(c.netlist()))
    n, lines = write_bom()
    print("BOM: %d parts, %d lines" % (n, lines))
    write_variant_boms()
    subprocess.run(["kicad-cli", "sch", "export", "pdf", root, "-o", os.path.join(OUT, c.name + "_schematic.pdf")],
                   check=True, capture_output=True)
    print("PDF written")


if __name__ == "__main__":
    main()
