import random, sys, os
from collections import deque

REGIMES = ["tiny", "narrow", "huge_sparse", "maze", "portals6", "starving",
           "strip", "flagship", "nosym", "centre", "private", "flagship_maze"]


class M:
    def __init__(s, W, H, sym):
        s.W, s.H, s.sym = W, H, sym
        s.kelp = set()
        s.portals = {}
        s.tiles = {}
        s.dragons = []

    def mt(s, x, y):
        W, H = s.W, s.H
        if s.sym == 'y': return (W - 1 - x, y)
        if s.sym == 'x': return (x, H - 1 - y)
        return (W - 1 - x, H - 1 - y)

    def me(s, e):
        k, x, y = e; W, H = s.W, s.H
        if k == 'v':
            if s.sym == 'y': return ('v', (W - x) % W, y)
            if s.sym == 'x': return ('v', x, H - 1 - y)
            return ('v', (W - x) % W, H - 1 - y)
        if s.sym == 'y': return ('h', W - 1 - x, y)
        if s.sym == 'x': return ('h', x, (H - y) % H)
        return ('h', W - 1 - x, (H - y) % H)

    def add_kelp(s, e):
        e = (e[0], e[1] % s.W, e[2] % s.H)
        if e in s.portals: return
        s.kelp.add(e); s.kelp.add(s.me(e))

    def edge(s, x, y, d):
        W, H = s.W, s.H
        if d == 'N': return ('h', x, y)
        if d == 'S': return ('h', x, (y + 1) % H)
        if d == 'W': return ('v', x, y)
        return ('v', (x + 1) % W, y)

    def step(s, x, y, d):
        W, H = s.W, s.H
        if d == 'N': return (x, (y - 1) % H)
        if d == 'S': return (x, (y + 1) % H)
        if d == 'W': return ((x - 1) % W, y)
        return ((x + 1) % W, y)

    def neighbours(s, p):
        for d in 'NESW':
            e = s.edge(p[0], p[1], d)
            if e in s.kelp: continue
            if e in s.portals:
                continue
            yield s.step(p[0], p[1], d)

    def component(s, start):
        seen = {start}; q = deque([start])
        while q:
            p = q.popleft()
            for n in s.neighbours(p):
                if n not in seen: seen.add(n); q.append(n)
        return seen

    def largest(s):
        left = {(x, y) for x in range(s.W) for y in range(s.H)}; best = set()
        while left:
            c = s.component(next(iter(left))); left -= c
            if len(c) > len(best): best = c
        return best

    def write(s, path, name, with_sym=True):
        W, H = s.W, s.H
        out = [f"MAP {W} {H}"]
        if with_sym: out.append(f"SYMMETRY {s.sym}")
        out.append(f"MAP_NAME {name}")
        out.append(f"TILE_COUNT {W * H}")
        for y in range(H):
            for x in range(W):
                lo, hi = s.tiles.get((x, y), (0, 0))
                out.append(f"TILE {x} {y} {lo} {hi}")
        edges = []
        for e in s.kelp: edges.append((s.idx(e), 1, -1))
        for e, pid in s.portals.items(): edges.append((s.idx(e), 2, pid))
        edges.sort()
        out.append(f"EDGE_COUNT {len(edges)}")
        for i, k, p in edges: out.append(f"EDGE {i} {k} {p}")
        out.append(f"DRAGON_COUNT {len(s.dragons)}")
        for team, body in s.dragons:
            out.append(f"DRAGON {team} {len(body)} " + " ".join(f"{x} {y}" for x, y in body))
        open(path, "w").write("\n".join(out) + "\n")

    def idx(s, e):
        k, x, y = e
        row = 2 * y if k == 'h' else 2 * y + 1
        return row * (s.W + 1) + x


def own_half(m, p):
    x, y = p; W, H = m.W, m.H
    if m.sym == 'y': return x < W // 2 - 2
    if m.sym == 'x': return y < H // 2 - 2
    return x < W // 2 - 2 if W >= H else y < H // 2 - 2


def kelp_scattered(m, r, n):
    for _ in range(n):
        x, y = r.randrange(m.W), r.randrange(m.H); k = r.choice('vh'); L = r.randint(2, 5)
        for i in range(L):
            m.add_kelp((k, x, y + i) if k == 'v' else (k, x + i, y))


def kelp_rooms(m, r, cell):
    for y in range(0, m.H, cell):
        for x in range(m.W):
            if r.random() > 0.25: m.add_kelp(('h', x, y))
    for x in range(0, m.W, cell):
        for y in range(m.H):
            if r.random() > 0.25: m.add_kelp(('v', x, y))


def kelp_maze(m, r, cell):
    cw, ch = max(2, m.W // cell), max(2, m.H // cell)

    walls = set()
    for cy in range(ch):
        for cx in range(cw):
            walls.add(('v', cx, cy)); walls.add(('h', cx, cy))
    seen = {(0, 0)}; stack = [(0, 0)]
    while stack:
        cx, cy = stack[-1]
        opts = []
        for dx, dy, w in ((1, 0, ('v', (cx + 1) % cw, cy)), (-1, 0, ('v', cx, cy)), (0, 1, ('h', cx, (cy + 1) % ch)), (0, -1, ('h', cx, cy))):
            n = ((cx + dx) % cw, (cy + dy) % ch)
            if n not in seen: opts.append((n, w))
        if not opts: stack.pop(); continue
        n, w = r.choice(opts); walls.discard(w); seen.add(n); stack.append(n)

    for w in list(walls):
        if r.random() < 0.2: walls.discard(w)
    for k, cx, cy in walls:
        if k == 'v':
            for i in range(cell): m.add_kelp(('v', cx * cell, cy * cell + i))
        else:
            for i in range(cell): m.add_kelp(('h', cx * cell + i, cy * cell))


def add_portals(m, r, n):
    pid = 0; tries = 0
    while pid < n and tries < 500:
        tries += 1
        k = r.choice('vh')
        a = (k, r.randrange(1, m.W), r.randrange(1, m.H))
        b = (k, r.randrange(1, m.W), r.randrange(1, m.H))
        ma, mb = m.me(a), m.me(b)
        es = {a, b, ma, mb}
        if len(es) != 4: continue
        if any(e in m.kelp or e in m.portals for e in es): continue
        m.portals[a] = pid; m.portals[b] = pid
        m.portals[ma] = pid + 1; m.portals[mb] = pid + 1
        pid += 2


def food(m, r, layout, playable):
    W, H = m.W, m.H
    cx, cy = (W - 1) / 2, (H - 1) / 2
    for (x, y) in playable:
        mx, my = m.mt(x, y)
        if (mx, my) in m.tiles: m.tiles[(x, y)] = m.tiles[(mx, my)]; continue
        rng = (0, 0)
        if layout == 'uniform':
            if r.random() < 0.5: rng = (20, 60)
        elif layout == 'sparse':
            if r.random() < 0.12: rng = (30, 90)
        elif layout == 'starving':
            if r.random() < 0.03: rng = (60, 160)
        elif layout == 'strip':
            if m.sym == 'y':
                if abs(x - cx) <= 0.6: rng = (4, 16)
            else:
                if abs(y - cy) <= 0.6: rng = (4, 16)
        elif layout == 'centre':
            if abs(x - cx) + abs(y - cy) <= min(W, H) / 4: rng = (5, 25)
        elif layout == 'private':

            dist = abs(x - cx) if m.sym == 'y' else abs(y - cy) if m.sym == 'x' else max(abs(x - cx) / W, abs(y - cy) / H) * min(W, H)
            if dist > min(W, H) / 4 and r.random() < 0.3: rng = (10, 30)
        elif layout == 'fountains':
            if r.random() < 0.01: rng = (1, 3)
            elif r.random() < 0.1: rng = (40, 100)
        m.tiles[(x, y)] = rng


def place_dragons(m, r, playable, lengths):
    occ = set()
    for L in lengths:
        ok = False
        for _ in range(400):
            cand = [p for p in playable if own_half(m, p) and p not in occ]
            if not cand: return False
            head = r.choice(cand); body = [head]; good = True
            while len(body) < L:
                p = body[-1]; opts = []
                for d in 'NESW':
                    e = m.edge(p[0], p[1], d)
                    if e in m.kelp or e in m.portals: continue
                    q = m.step(p[0], p[1], d)
                    if q in occ or q in body or q not in playable or not own_half(m, q): continue
                    if any(abs(q[0] - o[0]) + abs(q[1] - o[1]) <= 1 for o in occ): continue
                    opts.append(q)
                if not opts: good = False; break
                body.append(r.choice(opts))
            if not good: continue

            hx, hy = head; exits = 0
            for d in 'NESW':
                e = m.edge(hx, hy, d)
                if e in m.kelp or e in m.portals: continue
                q = m.step(hx, hy, d)
                if q not in body and q not in occ: exits += 1
            if exits < 2: continue
            if any(abs(b[0] - o[0]) + abs(b[1] - o[1]) <= 1 for b in body for o in occ): continue
            for b in body: occ.add(b)
            m.dragons.append((0, body)); m.dragons.append((1, [m.mt(*b) for b in body]))
            ok = True; break
        if not ok: return False

    for t, b in m.dragons:
        if t != 0: continue
        for t2, b2 in m.dragons:
            if t2 != 1: continue
            for p in b:
                for q in b2:
                    dx = min(abs(p[0] - q[0]), m.W - abs(p[0] - q[0])); dy = min(abs(p[1] - q[1]), m.H - abs(p[1] - q[1]))
                    if dx + dy < 4: return False
    return True


def generate(r, regime):
    while True:
        sym = r.choice(['x', 'y', 'xy'])
        style = r.choice(['open', 'scattered', 'rooms', 'divider'])
        foodl = r.choice(['uniform', 'sparse', 'centre', 'private', 'fountains'])
        nport = r.choice([0, 0, 1, 2, 3])
        lengths = [r.randint(2, 5) for _ in range(r.randint(1, 5))]
        if regime == 'tiny':
            W, H = r.randint(10, 13), r.randint(10, 12); lengths = [3] * r.randint(1, 2)
        elif regime == 'narrow':
            if r.random() < 0.5: W, H, sym = r.randint(40, 64), r.randint(10, 12), 'y'
            else: W, H, sym = r.randint(10, 12), r.randint(40, 64), 'x'
        elif regime == 'huge_sparse':
            W, H = 64, r.choice([48, 64]); foodl = 'sparse'
        elif regime == 'maze':
            W, H = r.choice([24, 30, 36]), r.choice([24, 30]); style = 'maze'
        elif regime == 'portals6':
            W, H = r.randint(24, 40), r.randint(16, 32); style = r.choice(['rooms', 'scattered']); nport = 6
        elif regime == 'starving':
            W, H = r.randint(24, 48), r.randint(20, 40); foodl = 'starving'
        elif regime == 'strip':
            W, H = r.randint(24, 48), r.randint(16, 32); foodl = 'strip'; sym = r.choice(['x', 'y'])
        elif regime == 'flagship':
            W, H = r.randint(24, 48), r.randint(20, 40); lengths = [r.randint(12, 22)] + [r.randint(2, 3) for _ in range(r.randint(1, 3))]
        elif regime == 'flagship_maze':
            W, H = r.choice([30, 36]), r.choice([24, 30]); style = 'maze'; lengths = [r.randint(10, 16), 2, 3]
        elif regime == 'nosym':
            W, H = r.randint(16, 48), r.randint(16, 48)
        elif regime == 'centre':
            W, H = r.randint(20, 48), r.randint(20, 40); foodl = 'centre'
        elif regime == 'private':
            W, H = r.randint(20, 48), r.randint(20, 40); foodl = 'private'
        m = M(W, H, sym)
        dense = style == 'maze'
        if style == 'scattered': kelp_scattered(m, r, W * H // 30)
        elif style == 'rooms': kelp_rooms(m, r, r.choice([6, 8]))
        elif style == 'maze': kelp_maze(m, r, r.choice([2, 3]))
        elif style == 'divider':
            if sym == 'y':
                x = W // 2
                for y in range(H):
                    if r.random() < 0.8: m.add_kelp(('v', x, y))
            else:
                y = H // 2
                for x in range(W):
                    if r.random() < 0.8: m.add_kelp(('h', x, y))
        add_portals(m, r, min(nport, W * H // 80))
        comp = m.largest()
        playable = comp | {m.mt(*p) for p in comp}
        if len(playable) < (0.35 if dense else 0.6) * W * H: continue
        if not place_dragons(m, r, playable, lengths): continue
        food(m, r, foodl, playable)
        if sum(1 for v in m.tiles.values() if v[1] > 0) == 0: continue
        return m, dict(W=W, H=H, sym=sym, style=style, food=foodl, portals=len(m.portals) // 2, lengths=lengths)


if __name__ == '__main__':
    n, seed, outdir = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
    os.makedirs(outdir, exist_ok=True)
    r = random.Random(seed)
    regs = os.environ.get('REGIMES', '').split(',') if os.environ.get('REGIMES') else REGIMES
    for i in range(n):
        regime = regs[i % len(regs)]
        m, info = generate(r, regime)
        name = f"g{seed}_{i:02d}_{regime}"
        m.write(os.path.join(outdir, name + ".map"), name, with_sym=(regime != 'nosym'))
        print(name, info)

