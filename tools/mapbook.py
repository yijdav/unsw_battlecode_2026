import argparse, sys
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ORDER = [("portals", 2), ("schooltime", 128), ("trophy", 512), ("prisoners_dilemma", 1024), ("devil", 2048),
         ("queen_of_spades", 4096), ("default", 8192), ("trauma", 1), ("autarky", 4), ("slithery_fight", 256)]
FOUNT_MAX = {"queen_of_spades": 50}
DX = [0, 1, 0, -1]
DY = [-1, 0, 1, 0]


def load(p):
    W = H = 0
    tiles, edges, dr, sym, name = {}, {}, [], None, ""
    for line in open(p):
        t = line.split()
        if not t:
            continue
        if t[0] == "MAP":
            W, H = int(t[1]), int(t[2])
        elif t[0] == "SYMMETRY":
            sym = t[1]
        elif t[0] == "MAP_NAME":
            name = " ".join(t[1:])
        elif t[0] == "TILE":
            tiles[(int(t[1]), int(t[2]))] = (int(t[3]), int(t[4]))
        elif t[0] == "EDGE":
            edges[int(t[1])] = (int(t[2]), int(t[3]))
        elif t[0] in ("DRAGON", "SNAKE"):
            n = int(t[2])
            dr.append((int(t[1]), [(int(t[3 + 2 * i]), int(t[4 + 2 * i])) for i in range(n)]))
    return W, H, tiles, edges, dr, sym, name


class Map:
    def __init__(self, p, fount_max=2):
        self.W, self.H, self.tiles, self.edges, self.dr, self.sym, self.name = load(p)
        W, H = self.W, self.H
        self.N = N = W * H
        self.en = [0] * N
        self.ew = [0] * N
        pid_n, pid_w = {}, {}
        for i, (k, pid) in self.edges.items():
            r = i // (W + 1)
            x = i % (W + 1)
            if r % 2 == 0:
                y = (r // 2) % H
                if x == W:
                    continue
                c = y * W + x % W
                if k > self.en[c]:
                    self.en[c] = k
                if k == 2:
                    pid_n[c] = pid
            else:
                y = r // 2
                c = y * W + x % W
                if k > self.ew[c]:
                    self.ew[c] = k
                if k == 2:
                    pid_w[c] = pid
        self.ports = sorted([(p, c, 1) for c, p in pid_n.items()] + [(p, c, 0) for c, p in pid_w.items()])
        self.partner_n = [-1] * N
        self.partner_w = [-1] * N
        by = {}
        for p, c, north in self.ports:
            by.setdefault((p, north), []).append(c)
        for (p, north), cs in by.items():
            if len(cs) == 2:
                arr = self.partner_n if north else self.partner_w
                arr[cs[0]], arr[cs[1]] = cs[1], cs[0]
        self.founts = sorted(y * W + x for (x, y), (a, b) in self.tiles.items() if 0 < b <= fount_max)

    def cell(self, x, y):
        return (y % self.H) * self.W + (x % self.W)

    def adj(self, c, d):
        return self.cell(c % self.W + DX[d], c // self.W + DY[d])

    def step(self, c, d, portals=True):
        north = d in (0, 2)
        key = self.adj(c, 2) if d == 2 else self.adj(c, 1) if d == 1 else c
        kind = (self.en if north else self.ew)[key]
        if kind == 1:
            return -1
        if kind == 0:
            return self.adj(c, d)
        if not portals:
            return -1
        p = (self.partner_n if north else self.partner_w)[key]
        if p < 0:
            return -1
        return self.adj(p, d) if d in (0, 3) else p

    def bfs(self, srcs, portals=True, limit=None):
        dist = [-1] * self.N
        q = deque()
        for s in srcs:
            dist[s] = 0
            q.append(s)
        while q:
            c = q.popleft()
            if limit is not None and dist[c] >= limit:
                continue
            for d in range(4):
                n = self.step(c, d, portals)
                if n >= 0 and dist[n] < 0:
                    dist[n] = dist[c] + 1
                    q.append(n)
        return dist

    def rates(self):
        r = [0.0] * self.N
        for (x, y), (a, b) in self.tiles.items():
            if b > 0:
                r[self.cell(x, y)] = 2.0 / (a + b)
        return r

    def regions(self, radius, sep, keep, cap):
        rate = self.rates()
        win = []
        for c in range(self.N):
            d = self.bfs([c], portals=False, limit=radius)
            win.append(sum(rate[q] for q in range(self.N) if 0 <= d[q] <= radius))
        order = sorted(range(self.N), key=lambda c: (-win[c], c))
        chosen = []
        for c in order:
            if not win[c] or (chosen and win[c] < keep * win[chosen[0]]) or len(chosen) >= cap:
                break
            dc = self.bfs([c], portals=True, limit=sep)
            if all(not (0 <= dc[o] <= sep) for o in chosen):
                chosen.append(c)
        return [(c, win[c]) for c in chosen]


def edges_string(m):
    return "".join("%d%d" % (m.en[c], m.ew[c]) for c in range(m.N))


def gaps_string(m):
    out = []
    for c in range(m.N):
        a, b = m.tiles.get((c % m.W, c // m.W), (0, 0))
        out.append("%d,%d" % (a, b))
    return ";".join(out)


ALPHA = [chr(c) for c in range(35, 126) if chr(c) not in "?\\"]


def field_string(dist):
    return "".join(ALPHA[min(d, len(ALPHA) - 1)] if d >= 0 else "~" for d in dist)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--maps", default=str(ROOT / "maps" / "ladder"))
    ap.add_argument("--out", default=str(ROOT / "bot" / "mapbook.hpp"))
    ap.add_argument("--radius", type=int, default=2)
    ap.add_argument("--sep", type=int, default=6)
    ap.add_argument("--keep", type=float, default=0.25)
    ap.add_argument("--regions", type=int, default=8)
    ap.add_argument("--check", help="main.cpp whose inline PRIORS must match the generated ones")
    args = ap.parse_args()
    maps = [(n, bit, Map(Path(args.maps) / f"{n}.map", FOUNT_MAX.get(n, 2))) for n, bit in ORDER]
    sym_code = {"y": 0, "x": 1, "xy": 2}
    out = ["#pragma once",
           "struct PriorMap { int w, h, bit; char const* edges; std::vector<std::array<int, 3>> ports; std::vector<int> founts; };",
           "std::vector<PriorMap> const PRIORS = {"]
    prior_lines = []
    for n, bit, m in maps:
        lines = ["    {%d, %d, %d, \"%s\"," % (m.W, m.H, bit, edges_string(m)),
                 "     {%s}," % ", ".join("{%d, %d, %d}" % t for t in m.ports),
                 "     {%s}}," % ", ".join(str(f) for f in m.founts)]
        prior_lines.append(lines)
        out += lines
    out += ["};", "",
            "struct BookRegion { int cell; double rate; char const* dist; };",
            "struct BookMap { int bit, sym; char const* gaps; std::vector<BookRegion> regions; };",
            "std::vector<BookMap> const BOOK = {"]
    summary = []
    for n, bit, m in maps:
        regs = m.regions(args.radius, args.sep, args.keep, args.regions)
        out.append("    {%d, %d, \"%s\"," % (bit, sym_code.get(m.sym, -1), gaps_string(m)))
        out.append("     {")
        for c, r in regs:
            out.append("      {%d, %.4f, \"%s\"}," % (c, r, field_string(m.bfs([c]))))
        out.append("     }},")
        summary.append(f"{m.name:18s} bit {bit:5d} sym {m.sym} regions " +
                       ", ".join(f"({c % m.W},{c // m.W}) {r:.2f}/round" for c, r in regs))
    out.append("};")
    Path(args.out).write_text("\n".join(out) + "\n")
    print("\n".join(summary))
    if args.check:
        src = Path(args.check).read_text()
        i = src.find("std::vector<PriorMap> const PRIORS = {")
        if i < 0:
            sys.exit("no inline PRIORS in " + args.check)
        inline = src[i:src.find("\n};", i)].splitlines()[1:]
        gen = [line for lines in prior_lines[:7] for line in lines]
        print("inline PRIORS identical to generated (first 7 maps):", inline == gen)
        if inline != gen:
            for a, b in zip(inline, gen):
                if a != b:
                    print("first difference:\n  inline:", a[:160], "\n  gen:   ", b[:160])
                    break
            sys.exit(1)


if __name__ == "__main__":
    main()
