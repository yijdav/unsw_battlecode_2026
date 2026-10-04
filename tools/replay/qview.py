import gzip, sys
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import decode as D


def states(path, rounds):
    raw = open(path, 'rb').read()
    if raw[:2] == D.GZIP:
        raw = gzip.decompress(raw)
    msg = D.Msg(D.unpack(raw))
    root = msg.ptr(0, 0)
    board = D.Board(msg.text(msg.sptr(root, 0)))
    team, body = {}, {}
    for did, t, b in board.dragons:
        team[did] = t
        body[did] = deque(b)
    pearls = set()
    out = {}
    rnd = -1
    ind = {}
    for ev in msg.structs(msg.sptr(root, 3)):
        which = msg.u16(ev, 0)
        p = msg.sptr(ev, 0)
        if which == 0:
            rnd = msg.i32(p, 0)
            if rnd in rounds:
                out[rnd] = ({d: list(b) for d, b in body.items()}, dict(team), set(pearls), dict(ind))
            ind = {}
        elif which == 3:
            c = msg.point(msg.sptr(p, 0))
            if msg.bit(p, 0):
                pearls.add(c)
            else:
                pearls.discard(c)
        elif which == 7:
            ind[msg.i32(p, 0)] = msg.text(msg.sptr(p, 0))
        elif which == 9:
            did = msg.i32(p, 0)
            head = msg.point(msg.sptr(p, 0))
            tail = msg.point(msg.sptr(p, 1))
            b = body.get(did)
            if b is None:
                continue
            b.appendleft(head)
            while len(b) > 1 and b[-1] != tail:
                b.pop()
        elif which == 10:
            par = msg.i32(p, 0)
            child = msg.i32(p, 4)
            team[child] = msg.u16(p, 8)
            body[par] = deque(msg.point(q) for q in msg.structs(msg.sptr(p, 0)))
            body[child] = deque(msg.point(q) for q in msg.structs(msg.sptr(p, 1)))
        elif which == 11:
            body.pop(msg.i32(p, 0), None)
    return board, out


def render(board, st, me, cx, cy, rad):
    body, team, pearls, ind = st
    occ = {}
    for d, b in body.items():
        for k, c in enumerate(b):
            occ[c] = (d, k)
    lines = []
    W, H = board.W, board.H
    xs = [(cx + dx) % W for dx in range(-rad, rad + 1)]
    ys = [(cy + dy) % H for dy in range(-rad, rad + 1)]
    lines.append('    ' + ''.join(f'{x % 100:<2d}' for x in xs))
    for y in ys:
        top = '    '
        row = f'{y:3d} '
        for x in xs:
            top += ('--' if board.canon(board.side_edge((x, y), 0)) in board.kelp else ('==' if board.canon(board.side_edge((x, y), 0)) in board.port else '  '))
            c = (x, y)
            if c in occ:
                d, k = occ[c]
                mine = team[d] == me
                if d < 2:
                    ch = ('Q' if mine else 'K') if k == 0 else ('q' if mine else 'k')
                else:
                    ch = ('H' if mine else 'E') if k == 0 else ('o' if mine else 'x')
            else:
                ch = '*' if c in pearls else '.'
            e = board.canon(board.side_edge(c, 1))
            row += ch + ('|' if e in board.kelp else (':' if e in board.port else ' '))
        lines.append(top)
        lines.append(row)
    return '\n'.join(lines)


if __name__ == '__main__':
    path, side, r0, r1 = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
    rad = int(sys.argv[5]) if len(sys.argv) > 5 else 6
    me = 0 if side == 'A' else 1
    board, out = states(path, set(range(r0, r1 + 1)))
    queen = min(d for d, t, _ in board.dragons if t == me)
    for r in range(r0, r1 + 1):
        if r not in out:
            continue
        body = out[r][0]
        q = body.get(queen)
        if q:
            cx, cy = q[0]
        elif len(sys.argv) > 7:
            cx, cy = int(sys.argv[6]), int(sys.argv[7])
        else:
            continue
        info = ' '.join(f'{d}:{len(b)}{"*" if out[r][1][d] == me else ""}' for d, b in sorted(body.items()) if b and abs(b[0][0] - cx) + abs(b[0][1] - cy) <= rad)
        print(f'round {r} (state before the round) queen {queen} len {len(q) if q else 0} at {q[0] if q else None} prev ind {out[r][3].get(queen)} | {info}')
        print(render(board, out[r], me, cx, cy, rad))
