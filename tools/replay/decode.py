import gzip, json, struct, sys
from collections import deque

BITS = [[b for b in range(8) if t >> b & 1] for t in range(256)]
DIRS = {0: (0, -1), 1: (1, 0), 2: (0, 1), 3: (-1, 0)}
REASONS = ['wall', 'self', 'body', 'head', 'novalid']
SNAPS = (25, 50, 100, 200, 300, 400)
QUEEN_SNAPS = (100, 200, 300, 400)
ZONES = (25, 50, 100)
GZIP = bytes([31, 139])


def unpack(data):
    out = bytearray()
    i, n = 0, len(data)
    zero = bytes(8)
    while i < n:
        tag = data[i]
        i += 1
        if tag == 0:
            out += zero * (data[i] + 1)
            i += 1
        elif tag == 0xFF:
            out += data[i:i + 8]
            cnt = data[i + 8]
            i += 9
            out += data[i:i + 8 * cnt]
            i += 8 * cnt
        else:
            w = bytearray(8)
            for b in BITS[tag]:
                w[b] = data[i]
                i += 1
            out += w
    return bytes(out)


class Msg:
    def __init__(self, raw):
        nseg = struct.unpack_from('<I', raw, 0)[0] + 1
        sizes = struct.unpack_from(f'<{nseg}I', raw, 4)
        off = 4 + 4 * nseg
        off += (-off) % 8
        self.segs = []
        for s in sizes:
            self.segs.append(raw[off:off + s * 8])
            off += s * 8

    def word(self, seg, idx):
        return struct.unpack_from('<Q', self.segs[seg], idx * 8)[0]

    def ptr(self, seg, idx):
        w = self.word(seg, idx)
        if w == 0:
            return None
        if w & 3 == 2:
            land = (w >> 2) & 1
            off = (w >> 3) & ((1 << 29) - 1)
            sid = w >> 32
            if not land:
                return self.ptr(sid, off)
            w2 = self.word(sid, off)
            tag = self.word(sid, off + 1)
            return self._decode(tag, w2 >> 32, (w2 >> 3) & ((1 << 29) - 1), True)
        return self._decode(w, seg, idx, False)

    def _decode(self, w, seg, idx, direct):
        o = (w >> 2) & 0x3FFFFFFF
        if o & 0x20000000:
            o -= 0x40000000
        start = idx if direct else idx + 1 + o
        if w & 3 == 0:
            return ('s', seg, start, (w >> 32) & 0xFFFF, w >> 48)
        return ('l', seg, start, (w >> 32) & 7, w >> 35)

    def sptr(self, s, i):
        _, seg, start, dw, pw = s
        if i >= pw:
            return None
        return self.ptr(seg, start + dw + i)

    def u16(self, s, off):
        _, seg, start, dw, _ = s
        return struct.unpack_from('<H', self.segs[seg], start * 8 + off)[0] if off + 2 <= dw * 8 else 0

    def i32(self, s, off):
        _, seg, start, dw, _ = s
        return struct.unpack_from('<i', self.segs[seg], start * 8 + off)[0] if off + 4 <= dw * 8 else 0

    def u64(self, s, off):
        _, seg, start, dw, _ = s
        return struct.unpack_from('<Q', self.segs[seg], start * 8 + off)[0] if off + 8 <= dw * 8 else 0

    def bit(self, s, b):
        _, seg, start, dw, _ = s
        if b >= dw * 64:
            return False
        return bool(self.segs[seg][start * 8 + b // 8] >> (b % 8) & 1)

    def text(self, p):
        if p is None:
            return ''
        _, seg, start, _, cnt = p
        return self.segs[seg][start * 8:start * 8 + cnt].rstrip(b'\0').decode('utf-8', 'replace')

    def structs(self, p):
        if p is None:
            return []
        _, seg, start, es, cnt = p
        if es != 7:
            return []
        tag = self.word(seg, start)
        n = (tag >> 2) & 0x3FFFFFFF
        dw = (tag >> 32) & 0xFFFF
        pw = tag >> 48
        return [('s', seg, start + 1 + k * (dw + pw), dw, pw) for k in range(n)]

    def u16s(self, p):
        if p is None:
            return []
        _, seg, start, es, cnt = p
        return list(struct.unpack_from(f'<{cnt}H', self.segs[seg], start * 8)) if es == 3 else []

    def point(self, p):
        return (self.i32(p, 0), self.i32(p, 4)) if p else None


class Board:
    def __init__(self, text):
        self.W = self.H = 0
        self.sym = None
        self.name = ''
        self.gaps = {}
        self.kelp = set()
        self.port = {}
        self.dragons = []
        pairs = {}
        for line in text.splitlines():
            t = line.split()
            if not t:
                continue
            if t[0] == 'MAP':
                self.W, self.H = int(t[1]), int(t[2])
            elif t[0] == 'SYMMETRY':
                self.sym = t[1]
            elif t[0] == 'MAP_NAME':
                self.name = ' '.join(t[1:])
            elif t[0] == 'TILE':
                self.gaps[(int(t[1]), int(t[2]))] = (int(t[3]), int(t[4]))
            elif t[0] == 'EDGE':
                e = self.edge_of(int(t[1]))
                if int(t[2]) == 1:
                    self.kelp.add(self.canon(e))
                elif int(t[2]) == 2:
                    pairs.setdefault(int(t[3]), []).append(e)
            elif t[0] in ('DRAGON', 'SNAKE'):
                n = int(t[2])
                body = [(int(t[3 + 2 * k]), int(t[4 + 2 * k])) for k in range(n)]
                self.dragons.append((len(self.dragons), int(t[1]), body))
        for pid, v in pairs.items():
            if len(v) == 2:
                a, b = v
                self.port[self.canon(a)] = (pid, b)
                self.port[self.canon(b)] = (pid, a)

    def edge_of(self, idx):
        r, x = divmod(idx, self.W + 1)
        return ('H', x, r // 2) if r % 2 == 0 else ('V', x, r // 2)

    def canon(self, e):
        k, x, y = e
        return (k, x % self.W, y % self.H)

    def side_edge(self, c, d):
        x, y = c
        if d == 0:
            return ('H', x, y)
        if d == 2:
            return ('H', x, y + 1)
        if d == 3:
            return ('V', x, y)
        return ('V', x + 1, y)

    def step(self, c, d):
        e = self.canon(self.side_edge(c, d))
        if e in self.kelp:
            return None, False
        if e in self.port:
            k, px, py = self.port[e][1]
            if k == 'V' and d in (1, 3):
                nx, ny = (px if d == 1 else px - 1), py
            elif k == 'H' and d in (0, 2):
                nx, ny = px, (py if d == 2 else py - 1)
            else:
                nx, ny = px, py
            return (nx % self.W, ny % self.H), True
        dx, dy = DIRS[d]
        return ((c[0] + dx) % self.W, (c[1] + dy) % self.H), False

    def portal_only_cells(self):
        seen = set()
        q = deque()
        for _, _, body in self.dragons:
            for c in body:
                if c not in seen:
                    seen.add(c)
                    q.append(c)
        while q:
            c = q.popleft()
            for d in range(4):
                n, via = self.step(c, d)
                if n is not None and not via and n not in seen:
                    seen.add(n)
                    q.append(n)
        return {(x, y) for x in range(self.W) for y in range(self.H)} - seen

    def tube_cells(self):
        cells = [(x, y) for x in range(self.W) for y in range(self.H)]
        nbr = {}
        for c in cells:
            nbr[c] = [n for n, via in (self.step(c, d) for d in range(4)) if n is not None and not via]
        out = set()
        for c in cells:
            if len(nbr[c]) != 1:
                continue
            tube, prev, cur = [c], None, c
            while True:
                nxt = [n for n in nbr[cur] if n != prev]
                if len(nxt) != 1 or len(nbr[nxt[0]]) != 2:
                    break
                prev, cur = cur, nxt[0]
                tube.append(cur)
            if len(tube) >= 2 and any(0 < self.gaps.get(t, (0, 0))[1] <= 2 for t in tube):
                out.update(tube)
        return out


def team_stats():
    return {'alive_r100': None, 'pearls_r100': 0, 'behind_portal_pearls_r100': 0, 'first_cross': None,
            'crossings_r100': 0, 'own_coll_deaths': 0, 'own_coll_portal': 0, 'champ_feed_deaths': 0,
            'small_head_deaths_by_enemy': 0, 'tube_deaths': 0, 'deaths': {r: 0 for r in REASONS}, 'longest_feed_start': None,
            'cpu_peak': 0, 'cpu_p99': 0, 'final_longest': None, 'final_count': None,
            'snap': {}, 'zone': {}, 'splits': [0, 0, 0], 'rams': [0, 0, 0], 'pearls_spawn': 0, 'pearls_drop': 0,
            'champ_own_drop': [0] * 10, 'queen_id': None, 'queen_alive_end': None, 'queen_len_end': None,
            'queen_death_round': None, 'queen_death_reason': None, 'queen_death_by': None, 'queen_killer_len': None,
            'queen_splits': 0, 'queen_is_longest_end': None, **{f'queen_len_r{r}': None for r in QUEEN_SNAPS},
            'enemy_queen_killed': 0, 'final_total': None, 'final_queen': None}


def decided(winner, end_reason, a, b):
    if winner == 'unfinished':
        return None
    if winner == 'draw':
        return 'draw'
    if end_reason == 0:
        return 'elimination'
    for name, x, y in zip(('queen', 'longest', 'total'), a, b):
        if x != y:
            return name
    return 'length'


def decode(path):
    data = open(path, 'rb').read()
    if data[:2] == GZIP:
        data = gzip.decompress(data)
    msg = Msg(unpack(data))
    root = msg.ptr(0, 0)
    board = Board(msg.text(msg.sptr(root, 0)))
    W, H = board.W, board.H
    feed_start = 261 if W * H >= 2048 else 383
    behind = board.portal_only_cells()
    tubes = board.tube_cells()
    team = {}
    body = {}
    for did, t, b in board.dragons:
        team[did] = t
        body[did] = deque(b)
    st = [team_stats(), team_stats()]
    queen = {}
    for did, t, b in board.dragons:
        if t in (0, 1) and (t not in queen or did < queen[t]):
            queen[t] = did
    for t in queen:
        st[t]['queen_id'] = queen[t]
    partner = {}
    gone = {}
    cpu = [[], []]
    rnd = 0
    longest_id = [None, None]
    dead_cells = {}
    centre = (W // 2, H // 2)
    radius = max(2, min(W, H) // 4)
    cur = None
    dirs = []
    done = 0
    for ev in msg.structs(msg.sptr(root, 3)):
        which = msg.u16(ev, 0)
        p = msg.sptr(ev, 0)
        if which == 0:
            rnd = msg.i32(p, 0)
            best = [(-1, None), (-1, None)]
            for did, b in body.items():
                if len(b) > best[team[did]][0]:
                    best[team[did]] = (len(b), did)
            longest_id = [best[0][1], best[1][1]]
            if rnd in SNAPS:
                for t in (0, 1):
                    mine = [len(b) for d, b in body.items() if team[d] == t]
                    st[t]['snap'][rnd] = {'count': len(mine), 'total': sum(mine), 'longest': max(mine, default=0)}
            if rnd in ZONES:
                for t in (0, 1):
                    z = {'centre': 0, 'behind': 0, 'other': 0}
                    for d, b in body.items():
                        if team[d] != t or not b:
                            continue
                        hx, hy = b[0]
                        dx = min(abs(hx - centre[0]), W - abs(hx - centre[0]))
                        dy = min(abs(hy - centre[1]), H - abs(hy - centre[1]))
                        z['centre' if max(dx, dy) <= radius else 'behind' if b[0] in behind else 'other'] += 1
                    st[t]['zone'][rnd] = z
            if rnd in QUEEN_SNAPS:
                for t in queen:
                    st[t][f'queen_len_r{rnd}'] = len(body.get(queen[t], ()))
            for t in (0, 1):
                if rnd == 100:
                    st[t]['alive_r100'] = sum(1 for d in body if team[d] == t)
                if rnd == feed_start:
                    st[t]['longest_feed_start'] = max(best[t][0], 0)
            cur = None
        elif which == 1:
            cur = msg.i32(p, 0)
            dirs = []
            done = 0
            partner = {}
        elif which == 3:
            if not msg.bit(p, 0) and cur is not None and cur in team:
                t = team[cur]
                cell = msg.point(msg.sptr(p, 0))
                src = dead_cells.get(cell)
                if src and rnd - src[0] <= 40:
                    st[t]['pearls_drop'] += 1
                    if src[1] == t and cur == longest_id[t]:
                        st[t]['champ_own_drop'][min(rnd // 50, 9)] += 1
                else:
                    st[t]['pearls_spawn'] += 1
                if rnd < 100:
                    st[t]['pearls_r100'] += 1
                    if cell in behind:
                        st[t]['behind_portal_pearls_r100'] += 1
        elif which == 4:
            did = msg.i32(p, 0)
            act = msg.sptr(p, 0)
            dirs = msg.u16s(msg.sptr(act, 0)) if act and msg.u16(act, 0) == 0 else []
            usage = msg.sptr(p, 1)
            if usage and did in team:
                cpu[team[did]].append(msg.u64(usage, 0))
        elif which == 9:
            did = msg.i32(p, 0)
            head = msg.point(msg.sptr(p, 0))
            tail = msg.point(msg.sptr(p, 1))
            b = body.get(did)
            if b is None:
                continue
            if did == cur and done < len(dirs):
                _, via = board.step(b[0], dirs[done])
                done += 1
                if via:
                    t = team[did]
                    if st[t]['first_cross'] is None:
                        st[t]['first_cross'] = rnd
                    if rnd < 100:
                        st[t]['crossings_r100'] += 1
            b.appendleft(head)
            while len(b) > 1 and b[-1] != tail:
                b.pop()
        elif which == 10:
            par = msg.i32(p, 0)
            child = msg.i32(p, 4)
            team[child] = msg.u16(p, 8)
            st[team[child]]['splits'][0 if rnd < 100 else 1 if rnd < 300 else 2] += 1
            if par == queen.get(team.get(par)):
                st[team[par]]['queen_splits'] += 1
            body[par] = deque(msg.point(q) for q in msg.structs(msg.sptr(p, 0)))
            body[child] = deque(msg.point(q) for q in msg.structs(msg.sptr(p, 1)))
        elif which == 11:
            did = msg.i32(p, 0)
            reason = msg.u16(p, 4)
            if did not in team:
                continue
            t = team[did]
            b = body.get(did, ())
            st[t]['deaths'][REASONS[reason] if reason < len(REASONS) else str(reason)] += 1
            if b and b[0] in tubes:
                st[t]['tube_deaths'] += 1
            killer = None
            via = False
            if reason in (2, 3):
                if did == cur and done < len(dirs) and b:
                    target, via = board.step(b[0], dirs[done])
                    for o, ob in body.items():
                        if o != did and target in ob:
                            killer = o
                            break
                elif cur is not None and cur != did and reason == 3:
                    killer = cur
            if reason == 3 and did == cur and killer is not None and killer in team and team[killer] != t:
                st[t]['rams'][0 if rnd < 100 else 1 if rnd < 300 else 2] += 1
            for c in b:
                dead_cells[c] = (rnd, t)
            if killer is not None and killer in team:
                if team[killer] == t:
                    st[t]['own_coll_deaths'] += 1
                    if via:
                        st[t]['own_coll_portal'] += 1
                elif reason == 3 and len(b) <= 3:
                    st[t]['small_head_deaths_by_enemy'] += 1
            if rnd >= feed_start and did == longest_id[t] and len(b) >= 10:
                st[t]['champ_feed_deaths'] += 1
            if reason == 3 and cur is not None and did != cur:
                partner[cur] = (did, len(b))
            if did == queen.get(t):
                q = st[t]
                q['queen_death_round'] = rnd
                q['queen_death_reason'] = REASONS[reason] if reason < len(REASONS) else str(reason)
                if did == cur:
                    q['queen_death_by'] = 'self_move'
                    if reason == 3:
                        other = partner.get(did)
                        if other is None and done < len(dirs) and b:
                            target, _ = board.step(b[0], dirs[done])
                            other = next(((o, len(ob)) for o, ob in body.items() if o != did and ob and ob[0] == target), None)
                        if other is not None:
                            q['queen_killer_len'] = other[1]
                elif cur is not None and cur in team:
                    q['queen_death_by'] = 'ally_move' if team[cur] == t else 'enemy_move'
                    q['queen_killer_len'] = len(body[cur]) if cur in body else gone.get(cur)
                    if team[cur] != t:
                        st[team[cur]]['enemy_queen_killed'] += 1
            gone[did] = len(b)
            body.pop(did, None)
    for t in (0, 1):
        c = sorted(cpu[t])
        st[t]['cpu_peak'] = c[-1] if c else 0
        st[t]['cpu_p99'] = c[int(0.99 * (len(c) - 1))] if c else 0
    for t in queen:
        q = st[t]
        mine = [len(b) for d, b in body.items() if team[d] == t]
        qb = body.get(queen[t])
        q['queen_alive_end'] = int(qb is not None)
        q['queen_len_end'] = len(qb) if qb is not None else 0
        q['queen_is_longest_end'] = int(qb is not None and len(qb) >= max(mine, default=0))
    res = msg.sptr(root, 4)
    winner = 'unfinished'
    end_reason = None
    if res:
        winner = ('A', 'B')[msg.u16(res, 6)] if msg.u16(res, 4) == 1 else 'draw'
        end_reason = msg.u16(res, 2)
        for t in (0, 1):
            s = msg.sptr(res, t)
            if s:
                st[t]['final_count'] = msg.i32(s, 0)
                st[t]['final_longest'] = msg.i32(s, 4)
                st[t]['final_total'] = msg.i32(s, 8)
                st[t]['final_queen'] = msg.i32(s, 12)
    stand = [(st[t]['final_queen'] or 0, st[t]['final_longest'] or 0, st[t]['final_total'] or 0) for t in (0, 1)]
    return {'map': board.name, 'W': W, 'H': H, 'rounds': rnd, 'winner': winner,
            'botA': msg.text(msg.sptr(root, 1)), 'botB': msg.text(msg.sptr(root, 2)), 'A': st[0], 'B': st[1],
            'end_reason': end_reason, 'decided_by': decided(winner, end_reason, *stand)}


if __name__ == '__main__':
    for f in sys.argv[1:]:
        print(json.dumps({'file': f, **decode(f)}))
