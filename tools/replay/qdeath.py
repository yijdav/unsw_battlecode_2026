import gzip, json, sys
from collections import Counter, deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import decode as D


def owner(body, team, cell):
    for o, b in body.items():
        if cell in b:
            return o, list(b).index(cell)
    return None, None


def trace(path, side, keep=8):
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
    me = 0 if side == 'A' else 1
    queen = min(d for d, t, _ in board.dragons if t == me)
    fqueen = min(d for d, t, _ in board.dragons if t != me)
    start = body[queen][0]
    hist = deque(maxlen=keep)
    ind = {}
    splits = []
    out = {'map': board.name, 'queen': queen, 'start': start, 'death': None, 'splits': splits}
    rnd = 0
    cur = None
    dirs = []
    done = 0
    maxd = 0
    partner = {}
    for ev in msg.structs(msg.sptr(root, 3)):
        which = msg.u16(ev, 0)
        p = msg.sptr(ev, 0)
        if which == 0:
            rnd = msg.i32(p, 0)
            q = body.get(queen)
            if q:
                h = q[0]
                maxd = max(maxd, abs(h[0] - start[0]) + abs(h[1] - start[1]))
            cur = None
            ind = {}
        elif which == 1:
            cur = msg.i32(p, 0)
            dirs = []
            done = 0
            partner = {}
        elif which == 4:
            did = msg.i32(p, 0)
            act = msg.sptr(p, 0)
            dirs = msg.u16s(msg.sptr(act, 0)) if act and msg.u16(act, 0) == 0 else []
        elif which == 7:
            did = msg.i32(p, 0)
            ind[did] = msg.text(msg.sptr(p, 0))
            if did == queen and body.get(queen):
                hist.append((rnd, len(body[queen]), body[queen][0], ind[did], len(dirs)))
        elif which == 9:
            did = msg.i32(p, 0)
            head = msg.point(msg.sptr(p, 0))
            tail = msg.point(msg.sptr(p, 1))
            b = body.get(did)
            if b is None:
                continue
            if did == cur:
                done += 1
            b.appendleft(head)
            while len(b) > 1 and b[-1] != tail:
                b.pop()
        elif which == 10:
            par = msg.i32(p, 0)
            child = msg.i32(p, 4)
            team[child] = msg.u16(p, 8)
            body[par] = deque(msg.point(q) for q in msg.structs(msg.sptr(p, 0)))
            body[child] = deque(msg.point(q) for q in msg.structs(msg.sptr(p, 1)))
            if par == queen:
                splits.append((rnd, len(body[par]), len(body[child])))
        elif which == 11:
            did = msg.i32(p, 0)
            reason = msg.u16(p, 4)
            if reason == 3 and cur is not None and did != cur:
                partner[cur] = (did, len(body.get(did, ())))
            if did == queen and out['death'] is None:
                b = body.get(did, deque())
                h = b[0] if b else None
                nb = []
                if h is not None:
                    for d in range(4):
                        n, via = board.step(h, d)
                        if n is None:
                            nb.append('kelp')
                            continue
                        o, idx = owner(body, team, n)
                        if o is None:
                            nb.append('free')
                        elif o == queen:
                            nb.append(f'self{idx}')
                        else:
                            ob = body[o]
                            nb.append(('mate' if team[o] == me else 'foe') + (':H' if idx == 0 else f':{idx}') + f':{o}:{len(ob)}')
                near = []
                for o, ob in body.items():
                    if o == queen or not ob or h is None:
                        continue
                    dd = abs(ob[0][0] - h[0]) + abs(ob[0][1] - h[1])
                    if dd <= 4:
                        near.append(('m' if team[o] == me else 'f', o, len(ob), dd, ind.get(o)))
                killer = None
                if reason == 3:
                    if did == cur and h is not None:
                        o = partner.get(cur)
                        if o is not None:
                            killer = {'by': 'self_move', 'id': o[0], 'team': 'mate' if team[o[0]] == me else 'foe', 'len': o[1], 'ind': ind.get(o[0])}
                    elif cur is not None and cur != did and cur in team:
                        killer = {'by': 'mate_move' if team[cur] == me else 'foe_move', 'id': cur, 'len': len(body.get(cur, ())), 'ind': ind.get(cur), 'steps': len(dirs)}
                out['death'] = {'round': rnd, 'reason': D.REASONS[reason] if reason < len(D.REASONS) else str(reason),
                                'len': len(b), 'head': h, 'nb': nb, 'near': sorted(near, key=lambda x: x[3]), 'killer': killer,
                                'ind': ind.get(queen), 'hist': list(hist), 'dirs': len(dirs), 'cur': cur,
                                'since_split': rnd - splits[-1][0] if splits else None}
            body.pop(did, None)
    out['maxd'] = maxd
    q = body.get(queen)
    out['alive_end'] = q is not None
    out['len_end'] = len(q) if q else 0
    return out


def category(d):
    if d is None:
        return 'alive'
    if d['ind'] == 'feed':
        return 'feed'
    if d['reason'] == 'novalid':
        own = any(x.startswith('mate') for x in d['nb'])
        foe = any(x.startswith('foe') for x in d['nb'])
        return 'boxed_' + ('own' if own else 'foe' if foe else 'self')
    if d['reason'] == 'head':
        k = d['killer'] or {}
        if k.get('by') == 'foe_move':
            return 'rammed'
        if k.get('by') == 'self_move':
            return 'moved_into_' + k.get('team', '?')
        if k.get('by') == 'mate_move':
            return 'rammed_by_mate'
        return 'head_other'
    return d['reason']


def one(job):
    p, side, extra = job
    try:
        t = trace(p, side)
    except Exception as e:
        return None
    t.update(extra)
    t['cat'] = category(t['death'])
    return t


if __name__ == '__main__':
    from multiprocessing import Pool
    rows = json.load(open(sys.argv[1]))
    root = Path(sys.argv[2])
    me = sys.argv[3]
    sys.path.insert(0, str(root / 'tools'))
    from arena_dump import replay_path
    jobs = []
    for i, bot, opp, mp, side, res, rounds, how, seed in rows:
        if bot != me:
            continue
        a, b = (bot, opp) if side == 'A' else (opp, bot)
        p = root / replay_path(root / 'maps' / (mp + '.map'), a, b, seed)
        if p.exists():
            jobs.append((str(p), side, {'opp': opp, 'mapf': mp, 'side': side, 'seed': seed, 'res': res, 'how': how}))
    with Pool(8) as pool, open(sys.argv[4], 'w') as out:
        for t in pool.imap(one, jobs, chunksize=2):
            if t is not None:
                out.write(json.dumps(t) + '\n')
