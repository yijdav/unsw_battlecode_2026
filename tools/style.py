import argparse, gzip, json, sys
from collections import deque
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools" / "replay"))
from decode import Board, Msg, unpack, GZIP, REASONS

SNAPS = (25, 50, 100, 150, 200, 250, 300, 350, 400, 450)
STRIKE = 3


def ph(r):
    return 0 if r < 100 else 1 if r < 300 else 2


def side():
    return {"moves": [0, 0, 0], "sprints": [0, 0, 0], "sprint_steps": [0, 0, 0], "split_len": [], "split_child": [], "split_round": [],
            "eaten": 0, "eaten_spawn": 0, "eaten_own_corpse": 0, "eaten_enemy_corpse": 0, "eaten_r100": 0,
            "deaths": {r: 0 for r in REASONS}, "kills_head": [0, 0, 0], "kills_body": [0, 0, 0], "kill_len": [], "trade_len": [],
            "lost_head_len": [], "strikes": [], "own_coll": 0, "novalid_near_friend": 0, "snap": {}, "head_gap": {}, "king_gap": {}, "novalid_at": [0] * 10, "crossings": 0}


def wrapd(a, b, m):
    d = abs(a - b)
    return min(d, m - d)


def analyse(path):
    data = open(path, "rb").read()
    if data[:2] == GZIP:
        data = gzip.decompress(data)
    msg = Msg(unpack(data))
    root = msg.ptr(0, 0)
    board = Board(msg.text(msg.sptr(root, 0)))
    W, H = board.W, board.H
    team, body, born = {}, {}, {}
    for did, t, b in board.dragons:
        team[did] = t
        body[did] = deque(b)
    st = [side(), side()]
    rnd, cur, dirs, done = 0, None, [], 0
    dead = {}

    def dist(a, b):
        return wrapd(a[0], b[0], W) + wrapd(a[1], b[1], H)

    for ev in msg.structs(msg.sptr(root, 3)):
        which = msg.u16(ev, 0)
        p = msg.sptr(ev, 0)
        if which == 0:
            rnd = msg.i32(p, 0)
            if rnd in SNAPS:
                for t in (0, 1):
                    ls = sorted((len(b) for d, b in body.items() if team[d] == t), reverse=True)
                    tot = sum(ls)
                    st[t]["snap"][rnd] = {"count": len(ls), "total": tot, "longest": ls[0] if ls else 0, "second": ls[1] if len(ls) > 1 else 0,
                                          "ge10": sum(1 for x in ls if x >= 10), "le3": sum(1 for x in ls if x <= 3),
                                          "champ_share": ls[0] / tot if tot else 0}
                    mine = [b[0] for d, b in body.items() if team[d] == t and b]
                    theirs = [b[0] for d, b in body.items() if team[d] != t and b]
                    if mine and theirs:
                        gaps = sorted(min(dist(h, e) for e in theirs) for h in mine)
                        st[t]["head_gap"][rnd] = gaps[len(gaps) // 2]
                        king = max((b for d, b in body.items() if team[d] == t and b), key=len)
                        st[t]["king_gap"][rnd] = min(dist(king[0], e) for e in theirs)
            cur = None
        elif which == 1:
            cur = msg.i32(p, 0)
            dirs, done = [], 0
        elif which == 4:
            did = msg.i32(p, 0)
            act = msg.sptr(p, 0)
            if act and msg.u16(act, 0) == 0 and did in team:
                dirs = msg.u16s(msg.sptr(act, 0))
                t = team[did]
                st[t]["moves"][ph(rnd)] += 1
                if len(dirs) >= 2:
                    st[t]["sprints"][ph(rnd)] += 1
                    st[t]["sprint_steps"][ph(rnd)] += len(dirs)
        elif which == 3:
            if not msg.bit(p, 0) and cur in team:
                t = team[cur]
                cell = msg.point(msg.sptr(p, 0))
                st[t]["eaten"] += 1
                if rnd < 100:
                    st[t]["eaten_r100"] += 1
                src = dead.get(cell)
                if src and rnd - src[0] <= 40:
                    st[t]["eaten_own_corpse" if src[1] == t else "eaten_enemy_corpse"] += 1
                else:
                    st[t]["eaten_spawn"] += 1
        elif which == 9:
            did = msg.i32(p, 0)
            head, tail = msg.point(msg.sptr(p, 0)), msg.point(msg.sptr(p, 1))
            b = body.get(did)
            if b is None:
                continue
            if did == cur and done < len(dirs):
                _, via = board.step(b[0], dirs[done])
                done += 1
                if via:
                    st[team[did]]["crossings"] += 1
            b.appendleft(head)
            while len(b) > 1 and b[-1] != tail:
                b.pop()
        elif which == 10:
            par, child = msg.i32(p, 0), msg.i32(p, 4)
            team[child] = msg.u16(p, 8)
            t = team[child]
            before = len(body.get(par, ()))
            body[par] = deque(msg.point(q) for q in msg.structs(msg.sptr(p, 0)))
            body[child] = deque(msg.point(q) for q in msg.structs(msg.sptr(p, 1)))
            born[child] = (rnd, before)
            st[t]["split_len"].append(before)
            st[t]["split_child"].append(len(body[child]))
            st[t]["split_round"].append(rnd)
        elif which == 11:
            did, reason = msg.i32(p, 0), msg.u16(p, 4)
            if did not in team:
                continue
            t = team[did]
            b = body.get(did, ())
            rname = REASONS[reason] if reason < len(REASONS) else str(reason)
            st[t]["deaths"][rname] = st[t]["deaths"].get(rname, 0) + 1
            killer = None
            if reason in (2, 3):
                if did == cur and done < len(dirs) and b:
                    target, _ = board.step(b[0], dirs[done])
                    for o, ob in body.items():
                        if o != did and target in ob:
                            killer = o
                            break
                elif cur is not None and cur != did and reason == 3:
                    killer = cur
            if killer is not None and killer in team:
                kt = team[killer]
                if kt == t:
                    st[t]["own_coll"] += 1
                else:
                    st[kt]["kills_head" if reason == 3 else "kills_body"][ph(rnd)] += 1
                    st[kt]["kill_len"].append(len(b))
                    klen = len(body.get(killer, ()))
                    if reason == 3:
                        st[kt]["trade_len"].append(klen)
                        st[t]["lost_head_len"].append(len(b))
                    if killer in born and rnd - born[killer][0] <= STRIKE:
                        st[kt]["strikes"].append({"round": rnd, "head": reason == 3, "striker": klen, "parent": born[killer][1], "victim": len(b)})
            if reason == 4:
                st[t]["novalid_at"][min(rnd // 50, 9)] += 1
            if reason == 4 and b:
                if any(team[o] == t and o != did and ob and dist(ob[0], b[0]) <= 1 for o, ob in body.items()):
                    st[t]["novalid_near_friend"] += 1
            for c in b:
                dead[c] = (rnd, t)
            body.pop(did, None)
    res = msg.sptr(root, 4)
    winner, final = "unfinished", [None, None]
    if res:
        winner = ("A", "B")[msg.u16(res, 6)] if msg.u16(res, 4) == 1 else "draw"
        for t in (0, 1):
            s = msg.sptr(res, t)
            if s:
                final[t] = {"count": msg.i32(s, 0), "longest": msg.i32(s, 4)}
    for t in (0, 1):
        st[t]["final"] = final[t]
    return {"map": board.name, "rounds": rnd, "winner": winner, "A": st[0], "B": st[1]}


def job(a):
    gid, path = a
    try:
        return gid, analyse(path)
    except Exception as e:
        return gid, {"error": repr(e)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest", nargs="+")
    ap.add_argument("--replays", default=str(ROOT / "replays" / "ladder"))
    ap.add_argument("--out", required=True)
    ap.add_argument("-j", type=int, default=12)
    args = ap.parse_args()
    metas = {}
    for mf in args.manifest:
        for line in open(mf, encoding="utf-8"):
            m = json.loads(line)
            metas[m["id"]] = m
    jobs = [(g, str(Path(args.replays) / f"{g}.replay.gz")) for g in metas if (Path(args.replays) / f"{g}.replay.gz").exists()]
    with Pool(args.j) as pool:
        got = pool.map(job, jobs, chunksize=2)
    n_err = 0
    with open(args.out, "w", encoding="utf-8") as f:
        for gid, d in got:
            if "error" in d:
                n_err += 1
                print(gid, d["error"])
                continue
            m = metas[gid]
            for s, k, o in (("A", "a", "b"), ("B", "b", "a")):
                f.write(json.dumps({"game": gid, "at": m["at"], "map": m["map"], "ranked": m.get("ranked", True), "team": m[k]["id"],
                                    "name": m[k]["name"], "elo": m[k].get("elo"), "opp": m[o]["id"], "opp_name": m[o]["name"],
                                    "opp_elo": m[o].get("elo"), "win": m["winner"] == k, "draw": m["winner"] not in ("a", "b"),
                                    "rounds": d["rounds"], **d[s]}, ensure_ascii=False) + "\n")
    print(f"{len(got)} games, {n_err} errors -> {args.out}")


if __name__ == "__main__":
    main()
