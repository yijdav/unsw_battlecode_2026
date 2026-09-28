import sys, os, struct, collections, json, tarfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rp import Msg, unpack, read_result
def analyse(data):
    m = Msg(unpack(data))
    r = m.root()
    mp = m.text(m.struct_ptr(r, 0))
    W = H = 0
    team = {}
    nid = 0
    for line in mp.splitlines():
        if line.startswith('MAP '):
            _, W, H = line.split()[:3]; W = int(W); H = int(H)
        elif line.startswith('DRAGON '):
            team[nid] = int(line.split()[1]); nid += 1
    bots = (m.text(m.struct_ptr(r, 1)), m.text(m.struct_ptr(r, 2)))
    ev = m.struct_ptr(r, 3)
    seg, st, n, dw, pw = m.composite(ev)
    stride = (dw + pw) * 8
    S = m.segs[seg]
    rnd = 0
    first = {}
    texts = collections.defaultdict(collections.Counter)
    maxid = nid
    for i in range(n):
        base = (st * 8) + i * stride
        which = struct.unpack_from('<H', S, base)[0]
        if which not in (0, 7, 10):
            continue
        p = m.ptr(seg, st + i * (dw + pw) + dw)
        if p is None:
            continue
        if which == 0:
            rnd = m.i32(p, 0)
        elif which == 10:
            team[m.i32(p, 4)] = m.u16(p, 8)
        else:
            did = m.i32(p, 0)
            t = team.get(did, -1)
            txt = m.text(m.struct_ptr(p, 0))
            texts[t][txt] += 1
            if txt in ('F', 'feed') and t not in first:
                first[t] = rnd
    res = read_result(data)
    return dict(bots=bots, W=W, H=H, N=W * H, first_feed={bots[k]: first.get(k) for k in (0, 1)} if bots[0] != bots[1] else {'A': first.get(0), 'B': first.get(1)},
                texts={bots[k] if bots[0] != bots[1] else 'AB'[k]: dict(texts[k]) for k in (0, 1)}, winner=res['winner'], rounds=res['rounds'], map=res['mapname'], seed=res['seed'])
if __name__ == '__main__':
    out = open(sys.argv[1], 'w')
    srcs = sys.argv[2:]
    def emit(name, data):
        try:
            d = analyse(data)
        except Exception as e:
            d = {'error': f'{type(e).__name__}: {e}'}
        d['file'] = os.path.basename(name)
        out.write(json.dumps(d) + '\n'); out.flush()
    if srcs == ['-']:
        with tarfile.open(fileobj=sys.stdin.buffer, mode='r|') as tar:
            for ti in tar:
                if ti.isfile() and ti.name.endswith('.replay'):
                    emit(ti.name, tar.extractfile(ti).read())
    else:
        for s in srcs:
            fs = sorted(os.path.join(s, f) for f in os.listdir(s) if f.endswith('.replay')) if os.path.isdir(s) else [s]
            for f in fs:
                emit(f, open(f, 'rb').read())
