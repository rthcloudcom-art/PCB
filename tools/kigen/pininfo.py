import sys
import symlib
for lid in sys.argv[1:]:
    s = symlib.get(lid)
    print("==", lid, "fp:", s.prop("Footprint"), "units:", sorted(s.units), "power" if s.is_power else "")
    for p in sorted(s.pins, key=lambda p: (p.unit, int(p.number) if p.number.isdigit() else 999, p.number)):
        print("  u%d %4s %-14s %-13s (%g,%g) a%d%s" % (p.unit, p.number, p.name, p.etype, p.x, p.y, p.angle, " HIDDEN" if p.hidden else ""))
