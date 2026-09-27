"""Tiny circuit-description DSL used to generate KiCad schematics and PCBs.

A design is a `Circuit` made of `Sheet`s; each sheet holds `Block`s of `Part`s.
Nets are plain strings. Pins are connected with `part.c(PIN=net, ...)` or
`part.c({"pin": net})` where PIN is a pin number or pin name.
"""
import re
import uuid

import symlib

NC = object()  # explicit no-connect marker

NS = uuid.UUID("6b1b1f1e-8a0f-4a51-9c43-2c1f5d0a7a11")

# nets drawn with a KiCad power symbol instead of a label
POWER_SYMBOLS = {"GND": "power:GND", "+3V3": "power:+3V3", "+5V": "power:+5V"}


def stable_uuid(*parts):
    return str(uuid.uuid5(NS, "/".join(str(p) for p in parts)))


def _norm(name):
    return re.sub(r"[~{}]", "", name)


class Part:
    def __init__(self, sheet, lib_id, prefix, value, footprint, fields=None, bom=True, dnp=False):
        self.sheet = sheet
        self.lib_id = lib_id
        self.sym = symlib.get(lib_id)
        self.prefix = prefix
        self.value = value
        self.footprint = footprint if footprint is not None else (self.sym.prop("Footprint") or "")
        self.fields = dict(fields or {})
        self.bom = bom
        self.dnp = dnp
        self.ref = None
        self.nets = {}  # pin number -> net name or NC

    def _resolve(self, key):
        key = str(key)
        nums = {p.number for p in self.sym.pins}
        if key in nums:
            return [key]
        hits = sorted({p.number for p in self.sym.pins if p.name == key})
        if not hits:
            hits = sorted({p.number for p in self.sym.pins if _norm(p.name) == _norm(key)})
        if not hits:
            raise KeyError("%s (%s): no pin %r" % (self.lib_id, self.prefix, key))
        return hits

    def c(self, mapping=None, **kw):
        items = list((mapping or {}).items()) + list(kw.items())
        for k, net in items:
            if isinstance(k, str) and k.startswith("_") and k[1:].isdigit():
                k = k[1:]
            for num in self._resolve(k):
                if num in self.nets and self.nets[num] is not net and self.nets[num] != net:
                    raise ValueError("%s pin %s already on %s" % (self.ref or self.prefix, num, self.nets[num]))
                self.nets[num] = net
        return self

    def __setitem__(self, pin, net):
        self.c({pin: net})


class Block:
    def __init__(self, sheet, title, notes="", option=None):
        self.sheet = sheet
        self.title = title
        self.notes = notes
        self.option = option  # assembly option tag (None = always fitted)
        self.parts = []


class Sheet:
    def __init__(self, circuit, name, title, paper="A3"):
        self.circuit = circuit
        self.name = name
        self.title = title
        self.paper = paper
        self.blocks = []
        self.block(title)

    @property
    def filename(self):
        return self.name + ".kicad_sch"

    def block(self, title, notes="", option=None):
        b = Block(self, title, notes, option)
        self.blocks.append(b)
        return b

    def part(self, lib_id, prefix, value=None, footprint=None, **kw):
        p = Part(self, lib_id, prefix, value if value is not None else lib_id.split(":")[1], footprint, **kw)
        opt = self.blocks[-1].option
        p.option = opt
        if opt and p.bom:
            p.fields.setdefault("Option", opt)
        self.blocks[-1].parts.append(p)
        self.circuit.parts.append(p)
        return p

    def pwr_flag(self, net):
        p = self.part("power:PWR_FLAG", "#FLG", "PWR_FLAG", "", bom=False)
        p.c({"1": net})
        return p

    @property
    def parts(self):
        return [p for b in self.blocks for p in b.parts]


class Circuit:
    def __init__(self, name, title, rev="A", company="", date=""):
        self.name = name
        self.title = title
        self.rev = rev
        self.company = company
        self.date = date
        self.sheets = []
        self.parts = []

    def sheet(self, name, title, paper="A3"):
        s = Sheet(self, name, title, paper)
        self.sheets.append(s)
        return s

    def annotate(self):
        counters = {}
        for p in self.parts:
            if p.ref is None:
                n = counters.get(p.prefix, 0) + 1
                counters[p.prefix] = n
                p.ref = "%s%d" % (p.prefix, n) if not p.prefix.startswith("#") else "%s0%d" % (p.prefix, n)

    def netlist(self):
        """net -> list of (ref, pin number)"""
        nets = {}
        for p in self.parts:
            for num, net in p.nets.items():
                if net is NC or net is None:
                    continue
                nets.setdefault(net, []).append((p.ref, num))
        return nets

    def check(self):
        """Validate connectivity rules before generating files."""
        errors = []
        for p in self.parts:
            seen = set()
            for pin in p.sym.pins:
                if pin.number in seen:
                    continue
                seen.add(pin.number)
                if pin.number not in p.nets:
                    stacked = [q for q in p.sym.pins if q.unit == pin.unit and (q.x, q.y) == (pin.x, pin.y) and q.number in p.nets]
                    if stacked:
                        p.nets[pin.number] = p.nets[stacked[0].number]
                    elif pin.etype == "no_connect" or pin.name == "NC":
                        p.nets[pin.number] = NC
                    else:
                        errors.append("%s (%s): pin %s/%s unconnected" % (p.ref, p.lib_id, pin.number, pin.name))
            if p.footprint and not p.sym.is_power:
                if not symlib.footprint_exists(p.footprint):
                    errors.append("%s: footprint %s missing" % (p.ref, p.footprint))
                else:
                    pads = symlib.footprint_pads(p.footprint)
                    for num in {q.number for q in p.sym.pins}:
                        if num not in pads and p.nets.get(num) is not NC:
                            errors.append("%s: pin %s not in footprint %s" % (p.ref, num, p.footprint))
            elif not p.sym.is_power and p.bom:
                errors.append("%s: no footprint" % p.ref)
        for net, pins in self.netlist().items():
            if len(pins) < 2:
                errors.append("net %s has a single connection %s" % (net, pins))
        if errors:
            raise SystemExit("\n".join(["Design check failed:"] + errors))
