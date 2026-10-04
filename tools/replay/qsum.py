import json, sys
from collections import Counter, defaultdict


def main():
    rows = [json.loads(x) for x in open(sys.argv[1])]
    verbose = len(sys.argv) > 2 and sys.argv[2] == '-v'
    n = len(rows)
    alive = sum(r['alive_end'] for r in rows)
    print(f'games {n}, queen alive at end {alive} ({100 * alive / max(1, n):.1f}%)')
    cats = Counter(r['cat'] for r in rows)
    print('categories:', dict(cats.most_common()))
    bym = defaultdict(Counter)
    for r in rows:
        bym[r['mapf'].split('/')[-1]][r['cat']] += 1
    print('\nper map:')
    for m in sorted(bym):
        c = bym[m]
        tot = sum(c.values())
        print(f'  {m:12s} n={tot:3d} alive={c["alive"]:3d} ' + ' '.join(f'{k}={v}' for k, v in c.most_common() if k != 'alive'))
    dr = [r['death']['round'] for r in rows if r['death']]
    dr.sort()
    if dr:
        print(f'\ndeath round q1/med/q3 {dr[len(dr) // 4]}/{dr[len(dr) // 2]}/{dr[3 * len(dr) // 4]}')
    ss = Counter()
    lens = Counter()
    inds = Counter()
    kinds = Counter()
    for r in rows:
        d = r['death']
        if not d:
            continue
        ss['split<=3' if d['since_split'] is not None and d['since_split'] <= 3 else 'other'] += 1
        lens[d['len']] += 1
        h = d['hist']
        inds[(r['cat'], h[-2][3] if len(h) >= 2 else None, d['ind'])] += 1
        k = d['killer']
        if k:
            kinds[(r['cat'], k.get('len'), k.get('ind'))] += 1
    print('since split:', dict(ss), ' len at death:', dict(sorted(lens.items())))
    print('\n(cat, prev ind, last ind):')
    for k, v in inds.most_common(30):
        print('  ', v, k)
    print('\n(cat, killer len, killer ind):')
    for k, v in kinds.most_common(25):
        print('  ', v, k)
    if verbose:
        for r in rows:
            d = r['death']
            if not d:
                continue
            print(json.dumps({'m': r['mapf'], 'o': r['opp'], 's': r['side'], 'seed': r['seed'], 'cat': r['cat'], 'r': d['round'], 'len': d['len'],
                              'nb': d['nb'], 'k': d['killer'], 'hist': [(h[0], h[1], h[3]) for h in d['hist']], 'near': d['near'][:5],
                              'splits': r['splits'][-3:], 'maxd': r['maxd']}))


if __name__ == '__main__':
    main()
