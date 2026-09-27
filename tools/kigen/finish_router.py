"""Small grid maze router (A*, two layers) to finish the last connections an autorouter left open.

It rasterises every copper item (except zones, which are refilled afterwards) at GRID mm,
inflates other-net copper by clearance + half the track width, and searches a path between
the islands of each unfinished net, allowing layer changes through vias.
"""
import heapq
import math

import numpy as np
import pcbnew

GRID = 0.1  # mm per cell
MARGIN = 0.08  # extra clearance: covers rasterisation error (half a cell diagonal) and diagonal steps
LAYERS = (pcbnew.F_Cu, pcbnew.B_Cu)


def mm(v):
    return pcbnew.ToMM(v)


class Grid:
    def __init__(self, board, clearance, track_w, via_d, edge_clear):
        bb = board.GetBoardEdgesBoundingBox()
        self.x0, self.y0 = mm(bb.GetX()), mm(bb.GetY())
        self.nx = int(mm(bb.GetWidth()) / GRID) + 1
        self.ny = int(mm(bb.GetHeight()) / GRID) + 1
        self.clearance, self.track_w, self.via_d = clearance, track_w, via_d
        self.edge_clear = edge_clear
        self.board = board
        self.xs = self.x0 + np.arange(self.nx) * GRID
        self.ys = self.y0 + np.arange(self.ny) * GRID

    def cell(self, x, y):
        return int(round((x - self.x0) / GRID)), int(round((y - self.y0) / GRID))

    def pos(self, i, j):
        return self.x0 + i * GRID, self.y0 + j * GRID

    # ---------------------------------------------------------- rasterising
    def _window(self, x0, y0, x1, y1):
        i0 = max(0, int((x0 - self.x0) / GRID) - 1)
        i1 = min(self.nx, int((x1 - self.x0) / GRID) + 2)
        j0 = max(0, int((y0 - self.y0) / GRID) - 1)
        j1 = min(self.ny, int((y1 - self.y0) / GRID) + 2)
        return i0, i1, j0, j1

    def paint_segment(self, arr, a, b, r):
        i0, i1, j0, j1 = self._window(min(a[0], b[0]) - r, min(a[1], b[1]) - r, max(a[0], b[0]) + r,
                                      max(a[1], b[1]) + r)
        if i0 >= i1 or j0 >= j1:
            return
        X, Y = np.meshgrid(self.xs[i0:i1], self.ys[j0:j1], indexing="ij")
        dx, dy = b[0] - a[0], b[1] - a[1]
        L2 = dx * dx + dy * dy
        if L2 == 0:
            d2 = (X - a[0]) ** 2 + (Y - a[1]) ** 2
        else:
            t = np.clip(((X - a[0]) * dx + (Y - a[1]) * dy) / L2, 0, 1)
            d2 = (X - a[0] - t * dx) ** 2 + (Y - a[1] - t * dy) ** 2
        arr[i0:i1, j0:j1] |= d2 <= r * r

    def paint_poly(self, arr, pts, r):
        """Polygon (list of (x,y)) grown by r: inside test OR distance to an edge <= r."""
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        i0, i1, j0, j1 = self._window(min(xs) - r, min(ys) - r, max(xs) + r, max(ys) + r)
        if i0 >= i1 or j0 >= j1:
            return
        X, Y = np.meshgrid(self.xs[i0:i1], self.ys[j0:j1], indexing="ij")
        inside = np.zeros(X.shape, bool)
        n = len(pts)
        for k in range(n):
            (xa, ya), (xb, yb) = pts[k], pts[(k + 1) % n]
            cond = ((ya > Y) != (yb > Y)) & (X < (xb - xa) * (Y - ya) / ((yb - ya) + 1e-12) + xa)
            inside ^= cond
        arr[i0:i1, j0:j1] |= inside
        for k in range(n):
            self.paint_segment(arr, pts[k], pts[(k + 1) % n], r)

    def pad_poly(self, pad):
        ps = pad.GetEffectivePolygon()
        ol = ps.COutline(0)
        return [(mm(ol.CPoint(i).x), mm(ol.CPoint(i).y)) for i in range(ol.PointCount())]

    def paint_item(self, arr_by_layer, item, r):
        cls = item.GetClass()
        if cls == "PCB_TRACK":
            a = (mm(item.GetStart().x), mm(item.GetStart().y))
            b = (mm(item.GetEnd().x), mm(item.GetEnd().y))
            lay = item.GetLayer()
            if lay in arr_by_layer:
                self.paint_segment(arr_by_layer[lay], a, b, mm(item.GetWidth()) / 2 + r)
        elif cls == "PCB_VIA":
            c = (mm(item.GetPosition().x), mm(item.GetPosition().y))
            for lay in LAYERS:
                self.paint_segment(arr_by_layer[lay], c, c, mm(item.GetWidth()) / 2 + r)
        elif cls == "PAD":
            pts = self.pad_poly(item)
            for lay in LAYERS:
                if item.IsOnLayer(lay):
                    self.paint_poly(arr_by_layer[lay], pts, r)
            if item.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH):
                c = (mm(item.GetPosition().x), mm(item.GetPosition().y))
                d = mm(item.GetDrillSize().x)
                for lay in LAYERS:  # a hole blocks both layers
                    self.paint_segment(arr_by_layer[lay], c, c, d / 2 + r)

    def copper_items(self):
        for t in self.board.GetTracks():
            yield t
        for p in self.board.GetPads():
            yield p

    def obstacles(self, netcode, extra=()):
        r = self.clearance + self.track_w / 2 + MARGIN
        obs = {lay: np.zeros((self.nx, self.ny), bool) for lay in LAYERS}
        for it in list(self.copper_items()) + list(extra):
            if it.GetNetCode() == netcode and it.GetNetCode() != 0:
                continue
            self.paint_item(obs, it, r)
        # board edge and rule-area keepouts
        e = self.edge_clear + self.track_w / 2 + 0.05
        m = int(math.ceil(e / GRID))
        for lay in LAYERS:
            obs[lay][:m, :] = obs[lay][-m:, :] = True
            obs[lay][:, :m] = obs[lay][:, -m:] = True
        for z in _rule_areas(self.board):
            if z.GetDoNotAllowTracks() or z.GetDoNotAllowVias():
                ol = z.Outline().COutline(0)
                pts = [(mm(ol.CPoint(i).x), mm(ol.CPoint(i).y)) for i in range(ol.PointCount())]
                for lay in LAYERS:
                    if z.IsOnLayer(lay):
                        self.paint_poly(obs[lay], pts, self.track_w / 2)
        return obs

    def own_copper(self, items):
        own = {lay: np.zeros((self.nx, self.ny), bool) for lay in LAYERS}
        for it in items:
            self.paint_item(own, it, 0.0)
        return own


def _rule_areas(board):
    out = [z for z in board.Zones() if z.GetIsRuleArea()]
    for fp in board.GetFootprints():
        out += [z for z in fp.Zones() if z.GetIsRuleArea()]
    return out


def islands(board, netcode):
    """Group a net's pads/tracks/vias into electrically connected islands (geometric test)."""
    items = [t for t in board.GetTracks() if t.GetNetCode() == netcode] + \
            [p for p in board.GetPads() if p.GetNetCode() == netcode]
    n = len(items)
    parent = list(range(n))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def layers(it):
        if it.GetClass() == "PCB_VIA":
            return set(LAYERS)
        if it.GetClass() == "PCB_TRACK":
            return {it.GetLayer()}
        return {l for l in LAYERS if it.IsOnLayer(l)}

    def shape(it):
        if it.GetClass() == "PAD":
            return it.GetEffectivePolygon()
        return None

    def touch(a, b):
        if not (layers(a) & layers(b)):
            return False
        return a.GetEffectiveShape().Collide(b.GetEffectiveShape(), pcbnew.FromMM(0.005))
    for i in range(n):
        for j in range(i + 1, n):
            if find(i) != find(j) and touch(items[i], items[j]):
                parent[find(i)] = find(j)
    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(items[i])
    return list(groups.values())


def astar(grid, obs, src, dst, via_ok, via_cost):
    """src/dst: dict layer -> bool array. Returns list of (layer, i, j)."""
    L = {LAYERS[0]: 0, LAYERS[1]: 1}
    free = [~obs[LAYERS[0]], ~obs[LAYERS[1]]]
    tgt = [dst[LAYERS[0]], dst[LAYERS[1]]]
    ti = np.argwhere(tgt[0] | tgt[1])
    if len(ti) == 0:
        return None
    tcx, tcy = ti[:, 0].mean(), ti[:, 1].mean()
    heap, came, gbest = [], {}, {}
    for lay in LAYERS:
        for i, j in np.argwhere(src[lay]):
            s = (L[lay], int(i), int(j))
            gbest[s] = 0.0
            heapq.heappush(heap, (math.hypot(i - tcx, j - tcy) * 0.5, 0.0, s))
    dirs = [(1, 0, 1), (-1, 0, 1), (0, 1, 1), (0, -1, 1), (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414),
            (-1, -1, 1.414)]
    nx, ny = grid.nx, grid.ny
    expanded = 0
    while heap:
        f, g, s = heapq.heappop(heap)
        if g > gbest.get(s, 1e18):
            continue
        l, i, j = s
        if tgt[l][i, j] and g > 0:
            path = [s]
            while s in came:
                s = came[s]
                path.append(s)
            return [(LAYERS[p[0]], p[1], p[2]) for p in reversed(path)]
        expanded += 1
        if expanded > 3_000_000:
            return None
        nbrs = []
        for di, dj, c in dirs:
            a, b = i + di, j + dj
            if 0 <= a < nx and 0 <= b < ny and (free[l][a, b] or tgt[l][a, b]):
                nbrs.append(((l, a, b), c))
        if via_ok[i, j]:
            nbrs.append(((1 - l, i, j), via_cost))
        for t, c in nbrs:
            ng = g + c
            if ng < gbest.get(t, 1e18):
                gbest[t] = ng
                came[t] = s
                h = math.hypot(t[1] - tcx, t[2] - tcy) * 0.5
                heapq.heappush(heap, (ng + h, ng, t))
    return None


def finish(board, clearance=0.5, track_w=0.6, via_d=1.2, via_drill=0.6, edge_clear=0.5, log=print, width_of=None):
    """width_of(netname) -> track width in mm (defaults to track_w for every net)."""
    board.BuildConnectivity()
    grids = {}
    nets = {}
    for p in board.GetPads():
        if p.GetNetCode() > 0:
            nets.setdefault(p.GetNetCode(), p.GetNet())
    done, failed = 0, []
    for code, net in sorted(nets.items(), key=lambda kv: kv[1].GetNetname()):
        if net.GetNetname() == "GND":
            continue  # handled by the ground pours
        w = width_of(net.GetNetname()) if width_of else track_w
        grid = grids.setdefault(w, Grid(board, clearance, w, via_d, edge_clear))
        while True:
            groups = islands(board, code)
            groups = [g for g in groups if any(it.GetClass() == "PAD" for it in g)]
            if len(groups) < 2:
                break
            obs = grid.obstacles(code)
            # via allowed where a via disc fits on both layers (obstacles already grown by track_w/2 + clearance)
            vr = max(0.0, via_d / 2 - w / 2) + GRID / 2
            k = int(math.ceil(vr / GRID))
            both = obs[LAYERS[0]] | obs[LAYERS[1]]
            via_ok = ~both.copy()
            if k > 0:
                pad_ = np.pad(both, k, constant_values=True)
                acc = np.zeros_like(both)
                for di in range(-k, k + 1):
                    for dj in range(-k, k + 1):
                        if di * di + dj * dj <= k * k:
                            acc |= pad_[k + di:k + di + grid.nx, k + dj:k + dj + grid.ny]
                via_ok = ~acc
            src = grid.own_copper(groups[0])
            dst = grid.own_copper([it for g in groups[1:] for it in g])
            path = astar(grid, obs, src, dst, via_ok, via_cost=25)
            if not path:
                failed.append(net.GetNetname())
                log("  no path for %s" % net.GetNetname())
                break
            add_path(board, grid, path, net, w, via_d, via_drill)
            done += 1
            log("  routed %s (%d cells)" % (net.GetNetname(), len(path)))
    return done, failed


def add_path(board, grid, path, net, track_w, via_d, via_drill):
    # split into same-layer runs; simplify collinear points
    runs, cur = [], [path[0]]
    for p in path[1:]:
        if p[0] != cur[-1][0]:
            runs.append(cur)
            v = pcbnew.PCB_VIA(board)
            x, y = grid.pos(p[1], p[2])
            v.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y)))
            v.SetWidth(pcbnew.FromMM(via_d))
            v.SetDrill(pcbnew.FromMM(via_drill))
            v.SetViaType(pcbnew.VIATYPE_THROUGH)
            v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
            v.SetNet(net)
            board.Add(v)
            cur = [p]
        else:
            cur.append(p)
    runs.append(cur)
    for run in runs:
        pts = [run[0]]
        for k in range(1, len(run) - 1):
            a, b, c = pts[-1], run[k], run[k + 1]
            if (b[1] - a[1]) * (c[2] - b[2]) != (b[2] - a[2]) * (c[1] - b[1]):
                pts.append(b)
        if len(run) > 1:
            pts.append(run[-1])
        for a, b in zip(pts, pts[1:]):
            t = pcbnew.PCB_TRACK(board)
            xa, ya = grid.pos(a[1], a[2])
            xb, yb = grid.pos(b[1], b[2])
            t.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(xa), pcbnew.FromMM(ya)))
            t.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(xb), pcbnew.FromMM(yb)))
            t.SetWidth(pcbnew.FromMM(track_w))
            t.SetLayer(a[0])
            t.SetNet(net)
            board.Add(t)


# ---------------------------------------------------------------- rip-up and reroute
_GRAVEYARD = []

def _obstacles_split(grid, code, protected, taboo=()):
    """hard: pads, holes, edges, keepouts and protected nets; soft: rippable signal tracks/vias."""
    r = grid.clearance + grid.track_w / 2 + MARGIN
    hard = {lay: np.zeros((grid.nx, grid.ny), bool) for lay in LAYERS}
    soft = {lay: np.zeros((grid.nx, grid.ny), bool) for lay in LAYERS}
    for it in grid.copper_items():
        if it.GetNetCode() == code and code != 0:
            continue
        rippable = it.GetClass() in ("PCB_TRACK", "PCB_VIA") and it.GetNetCode() not in protected \
            and it.GetNetCode() not in taboo
        grid.paint_item(soft if rippable else hard, it, r)
    e = grid.edge_clear + grid.track_w / 2 + 0.05
    m = int(math.ceil(e / GRID))
    for lay in LAYERS:
        hard[lay][:m, :] = hard[lay][-m:, :] = True
        hard[lay][:, :m] = hard[lay][:, -m:] = True
    for z in _rule_areas(grid.board):
        if z.GetDoNotAllowTracks() or z.GetDoNotAllowVias():
            ol = z.Outline().COutline(0)
            pts = [(mm(ol.CPoint(i).x), mm(ol.CPoint(i).y)) for i in range(ol.PointCount())]
            for lay in LAYERS:
                if z.IsOnLayer(lay):
                    grid.paint_poly(hard[lay], pts, grid.track_w / 2)
    return hard, soft


def _astar_soft(grid, hard, soft, src, dst, via_ok, via_cost, soft_cost):
    L = {LAYERS[0]: 0, LAYERS[1]: 1}
    hardl = [hard[LAYERS[0]], hard[LAYERS[1]]]
    softl = [soft[LAYERS[0]], soft[LAYERS[1]]]
    tgt = [dst[LAYERS[0]], dst[LAYERS[1]]]
    ti = np.argwhere(tgt[0] | tgt[1])
    tcx, tcy = ti[:, 0].mean(), ti[:, 1].mean()
    heap, came, gbest = [], {}, {}
    for lay in LAYERS:
        for i, j in np.argwhere(src[lay]):
            s = (L[lay], int(i), int(j))
            gbest[s] = 0.0
            heapq.heappush(heap, (0.0, 0.0, s))
    dirs = [(1, 0, 1), (-1, 0, 1), (0, 1, 1), (0, -1, 1), (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414),
            (-1, -1, 1.414)]
    expanded = 0
    while heap:
        f, g, s = heapq.heappop(heap)
        if g > gbest.get(s, 1e18):
            continue
        l, i, j = s
        if tgt[l][i, j] and g > 0:
            path = [s]
            while s in came:
                s = came[s]
                path.append(s)
            return [(LAYERS[p[0]], p[1], p[2]) for p in reversed(path)]
        expanded += 1
        if expanded > 4_000_000:
            return None
        cand = []
        for di, dj, c in dirs:
            a, b = i + di, j + dj
            if 0 <= a < grid.nx and 0 <= b < grid.ny:
                if tgt[l][a, b]:
                    cand.append(((l, a, b), c))
                elif not hardl[l][a, b]:
                    cand.append(((l, a, b), c + (soft_cost if softl[l][a, b] else 0)))
        if via_ok[i, j]:
            cand.append(((1 - l, i, j), via_cost))
        for t, c in cand:
            ng = g + c
            if ng < gbest.get(t, 1e18):
                gbest[t] = ng
                came[t] = s
                heapq.heappush(heap, (ng + math.hypot(t[1] - tcx, t[2] - tcy) * 0.5, ng, t))
    return None


def _via_ok(grid, both, via_d):
    vr = max(0.0, via_d / 2 - grid.track_w / 2) + GRID / 2
    k = int(math.ceil(vr / GRID))
    if k == 0:
        return ~both
    padded = np.pad(both, k, constant_values=True)
    acc = np.zeros_like(both)
    for di in range(-k, k + 1):
        for dj in range(-k, k + 1):
            if di * di + dj * dj <= k * k:
                acc |= padded[k + di:k + di + grid.nx, k + dj:k + dj + grid.ny]
    return ~acc


def _blocking_items(grid, path, code, protected, taboo=()):
    """Tracks and vias of other (rippable) nets that the path would violate."""
    r = grid.clearance + grid.track_w / 2 + MARGIN
    pts = np.array([grid.pos(p[1], p[2]) for p in path])
    lays = np.array([p[0] for p in path])
    hit = []
    for t in grid.board.GetTracks():
        n = t.GetNetCode()
        if n == code or n in protected or n in taboo:
            continue
        if t.GetClass() == "PCB_VIA":
            c = np.array([mm(t.GetPosition().x), mm(t.GetPosition().y)])
            if (np.hypot(*(pts - c).T) < r + mm(t.GetWidth()) / 2).any():
                hit.append(t)
            continue
        sel = lays == t.GetLayer()
        if not sel.any():
            continue
        a = np.array([mm(t.GetStart().x), mm(t.GetStart().y)])
        b = np.array([mm(t.GetEnd().x), mm(t.GetEnd().y)])
        ab = b - a
        L2 = (ab ** 2).sum()
        P = pts[sel]
        tt = np.clip(((P - a) @ ab) / L2, 0, 1) if L2 > 0 else np.zeros(len(P))
        if (np.hypot(*(P - (a + np.outer(tt, ab))).T) < r + mm(t.GetWidth()) / 2).any():
            hit.append(t)
    return hit


def _blocking_nets(grid, path, code, protected, taboo=()):
    r = grid.clearance + grid.track_w / 2
    pts = np.array([grid.pos(p[1], p[2]) for p in path])
    lays = np.array([p[0] for p in path])
    hit = set()
    for t in grid.board.GetTracks():
        n = t.GetNetCode()
        if n == code or n in protected or n in hit or n in taboo:
            continue
        if t.GetClass() == "PCB_VIA":
            c = np.array([mm(t.GetPosition().x), mm(t.GetPosition().y)])
            d = np.hypot(*(pts - c).T)
            if (d < r + mm(t.GetWidth()) / 2).any():
                hit.add(n)
            continue
        sel = lays == t.GetLayer()
        if not sel.any():
            continue
        a = np.array([mm(t.GetStart().x), mm(t.GetStart().y)])
        b = np.array([mm(t.GetEnd().x), mm(t.GetEnd().y)])
        ab = b - a
        L2 = (ab ** 2).sum()
        P = pts[sel]
        tt = np.clip(((P - a) @ ab) / L2, 0, 1) if L2 > 0 else np.zeros(len(P))
        d = np.hypot(*(P - (a + np.outer(tt, ab))).T)
        if (d < r + mm(t.GetWidth()) / 2).any():
            hit.add(n)
    return hit


def _route_net(board, grid, code, net, track_w, via_d, via_drill):
    """Connect all islands of a net with hard obstacles only. True when complete."""
    while True:
        groups = [g for g in islands(board, code) if any(it.GetClass() == "PAD" for it in g)]
        if len(groups) < 2:
            return True
        obs = grid.obstacles(code)
        via_ok = _via_ok(grid, obs[LAYERS[0]] | obs[LAYERS[1]], via_d)
        src = grid.own_copper(groups[0])
        dst = grid.own_copper([it for g in groups[1:] for it in g])
        path = astar(grid, obs, src, dst, via_ok, via_cost=25)
        if not path:
            return False
        add_path(board, grid, path, net, track_w, via_d, via_drill)


def rip_and_reroute(board, protected_names=("GND",), protected_prefix=(), clearance=0.5, track_w=0.6,
                    via_d=1.2, via_drill=0.6, edge_clear=0.5, max_iter=80, log=print, width_of=None, local=True):
    """Finish all open nets, ripping up blocking signal nets when needed.

    width_of(netname) -> track width in mm for re-routed nets (defaults to track_w)."""
    grids = {}

    def grid_for(net):
        w = width_of(net.GetNetname()) if width_of else track_w
        return grids.setdefault(w, Grid(board, clearance, w, via_d, edge_clear)), w
    nets = {}
    for p in board.GetPads():
        if p.GetNetCode() > 0:
            nets.setdefault(p.GetNetCode(), p.GetNet())
    protected = {c for c, n in nets.items()
                 if n.GetNetname().split("/")[-1] in protected_names
                 or any(n.GetNetname().split("/")[-1].startswith(pfx) for pfx in protected_prefix)}
    todo = [c for c in nets if c not in protected and
            len([g for g in islands(board, c) if any(it.GetClass() == "PAD" for it in g)]) > 1]
    history = {}
    ripped_by = {}  # victim -> set of nets that ripped it (the victim may not rip them back)
    it = 0
    while todo and it < max_iter:
        it += 1
        code = todo.pop(0)
        net = nets[code]
        grid, w = grid_for(net)
        if _route_net(board, grid, code, net, w, via_d, via_drill):
            log("  [%d] routed %s" % (it, net.GetNetname()))
            continue
        # needs rip-up: find a path through rippable tracks, preferring rarely ripped nets
        groups = [g for g in islands(board, code) if any(x.GetClass() == "PAD" for x in g)]
        taboo = ripped_by.get(code, set())
        hard, soft = _obstacles_split(grid, code, protected, taboo)
        via_ok = _via_ok(grid, hard[LAYERS[0]] | hard[LAYERS[1]] | soft[LAYERS[0]] | soft[LAYERS[1]], via_d)
        src = grid.own_copper(groups[0])
        dst = grid.own_copper([x for g in groups[1:] for x in g])
        path = _astar_soft(grid, hard, soft, src, dst, via_ok, via_cost=25, soft_cost=40)
        if not path:
            log("  [%d] impossible even with rip-up: %s" % (it, net.GetNetname()))
            continue
        if local:   # remove only the blocking segments; the victim keeps the rest and needs a short detour
            items = _blocking_items(grid, path, code, protected, taboo)
            victims = {t.GetNetCode() for t in items}
        else:
            victims = _blocking_nets(grid, path, code, protected, taboo)
            items = [t for t in board.GetTracks() if t.GetNetCode() in victims]
        for v in victims:
            history[v] = history.get(v, 0) + 1
            ripped_by.setdefault(v, set()).add(code)
        for t in items:
            board.Remove(t)
            _GRAVEYARD.append(t)  # keep the Python wrapper alive: SWIG would otherwise free it twice
        add_path(board, grid, path, net, w, via_d, via_drill)
        log("  [%d] %s routed after ripping %s" % (it, net.GetNetname(),
                                                   [nets[v].GetNetname().split("/")[-1] for v in victims]))
        todo = [code] + [v for v in victims if v not in todo] + todo  # finish own islands first
    # local rip-up leaves copper fragments without a pad: remove them
    for c in history:
        for g in islands(board, c):
            if not any(x.GetClass() == "PAD" for x in g):
                for t in g:
                    if t.GetClass() in ("PCB_TRACK", "PCB_VIA"):
                        board.Remove(t)
                        _GRAVEYARD.append(t)
    left = [nets[c].GetNetname() for c in nets if c not in protected and
            len([g for g in islands(board, c) if any(x.GetClass() == "PAD" for x in g)]) > 1]
    return left
