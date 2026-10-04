import argparse, json, sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools" / "replay"))
from gate import DECIDED, DEATHS, SCORE, decided_of, fmt, mean, median, pct, sign_p, wdl


def load(path):
    return [json.loads(line) for line in open(path)] if path.exists() else []


def corrected(rows, verify, who):
    out = []
    for r in rows:
        k = (r["opp"], r["map"], r["seed"], r["side"])
        v = verify.get(k)
        out.append(dict(r, res=v[who]) if v else r)
    return out


def score(rows):
    rows = [r for r in rows if r["res"] in SCORE]
    return 100 * mean([SCORE[r["res"]] for r in rows]) if rows else None


def table(head, rows):
    return ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)] + ["| " + " | ".join(fmt(c) for c in r) + " |" for r in rows]


def group(mp):
    return mp.split("/")[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True)
    ap.add_argument("--base", default="v_capri")
    ap.add_argument("--cand", default="v_live")
    ap.add_argument("--sets", nargs="*", default=["main", "fresh", "holdout"])
    args = ap.parse_args()
    runs = ROOT / args.runs
    bots = {args.base: {}, args.cand: {}}
    paired = {}
    for fset in args.sets:
        verify = {tuple(v["key"]): v for v in load(runs / f"{args.cand}_{fset}_verify.jsonl")}
        b = corrected(load(runs / f"base_{args.base}_{fset}_games.jsonl"), verify, "base")
        c = corrected(load(runs / f"{args.cand}_{fset}_games.jsonl"), verify, "cand")
        bots[args.base][fset], bots[args.cand][fset] = b, c
        bmap = {(r["opp"], r["map"], r["seed"], r["side"]): r for r in b}
        pairs = [(r, bmap[k]) for r in c for k in [(r["opp"], r["map"], r["seed"], r["side"])]
                 if k in bmap and "error" not in (r["res"], bmap[k]["res"])]
        paired[fset] = (pairs, len(verify))
    names = list(bots)
    out = []

    out += ["## Paired: %s against %s (same fixtures, flipped fixtures replayed, majority of three)" % (args.cand, args.base), ""]
    rows = []
    for fset, (pairs, nv) in paired.items():
        for label, sel in [("all", pairs)] + [(o, [p for p in pairs if p[0]["opp"] == o]) for o in sorted({p[0]["opp"] for p in pairs})]:
            g = sum(1 for r, x in sel if SCORE[r["res"]] > SCORE[x["res"]])
            l = sum(1 for r, x in sel if SCORE[r["res"]] < SCORE[x["res"]])
            rows.append([fset, label, len(sel), g, l, f"{sign_p(g, l):.3g}", score([r for r, _ in sel]), score([x for _, x in sel])])
    out += table(["set", "subset", "fixtures", "gained", "lost", "sign p", f"{args.cand} %", f"{args.base} %"], rows) + [""]

    out += ["## Score per ladder map (main + fresh: ladder seeds 1-6, both sides, 6 opponents)", ""]
    rows = []
    allrows = {n: [r for fs in bots[n].values() for r in fs] for n in names}
    ladder = sorted({r["map"] for n in names for r in allrows[n] if r["map"].startswith("ladder/")})
    for mp in ladder:
        row = [mp.split("/")[1]]
        for n in names:
            sel = [r for r in allrows[n] if r["map"] == mp]
            row += [score(sel)]
        for n in names:
            sel = [r for r in allrows[n] if r["map"] == mp]
            row += [pct([r["ours"].get("queen_alive_end") for r in sel if "ours" in r])]
        for n in names:
            sel = [r for r in allrows[n] if r["map"] == mp]
            row += [median([r["ours"].get("queen_death_round") for r in sel if "ours" in r])]
        sel = [r for r in allrows[names[0]] if r["map"] == mp]
        row += [len(sel), " ".join(f"{k[0].upper()}{sum(1 for r in sel if decided_of(r) == k)}" for k in DECIDED if any(decided_of(r) == k for r in sel))]
        rows.append(row)
    for g in ("generated", "portal_heavy", "holdout"):
        row = [g + " (all)"]
        for n in names:
            row += [score([r for r in allrows[n] if group(r["map"]) == g])]
        for n in names:
            row += [pct([r["ours"].get("queen_alive_end") for r in allrows[n] if group(r["map"]) == g and "ours" in r])]
        for n in names:
            row += [median([r["ours"].get("queen_death_round") for r in allrows[n] if group(r["map"]) == g and "ours" in r])]
        sel = [r for r in allrows[names[0]] if group(r["map"]) == g]
        row += [len(sel), " ".join(f"{k[0].upper()}{sum(1 for r in sel if decided_of(r) == k)}" for k in DECIDED if any(decided_of(r) == k for r in sel))]
        if sel:
            rows.append(row)
    head = ["map"] + [f"{n} %" for n in names] + [f"{n} queen alive end %" for n in names] + [f"{n} queen death r (median)" for n in names] + ["games per bot", f"{names[0]} decided by"]
    out += table(head, rows) + ["", "Decided-by letters: E elimination, Q queen, L longest, T total, D draw.", ""]

    out += ["## Score per opponent", ""]
    rows = []
    opps = sorted({r["opp"] for n in names for r in allrows[n]})
    for o in opps:
        row = [o]
        for n in names:
            for fset in args.sets:
                row.append(score([r for r in bots[n].get(fset, []) if r["opp"] == o]))
            row.append(score([r for r in allrows[n] if r["opp"] == o]))
        rows.append(row)
    head = ["opponent"] + [f"{n} {s}" for n in names for s in args.sets + ["all"]]
    out += table(head, rows) + [""]

    out += ["## Decided by (W-D-L, all sets)", ""]
    rows = []
    for k in DECIDED + ["error"]:
        row = [k]
        for n in names:
            for fset in args.sets:
                row.append(wdl([r["res"] for r in bots[n].get(fset, []) if decided_of(r) == k]))
        if any(c != "0-0-0" for c in row[1:]):
            rows.append(row)
    out += table(["decided by"] + [f"{n} {s}" for n in names for s in args.sets], rows) + [""]

    out += ["## Queen survival (all sets)", ""]
    rows = []
    teams = {(n, who): [r[who] for r in allrows[n] if who in r] for n in names for who in ("ours", "theirs")}
    metrics = [("games", lambda t: len(t)), ("queen alive at end %", lambda t: pct([q.get("queen_alive_end") for q in t]))]
    for rr in (100, 200, 300, 400):
        metrics.append((f"queen alive at r{rr} %", lambda t, rr=rr: pct([None if q.get(f"queen_len_r{rr}") is None else int(q[f"queen_len_r{rr}"] > 0) for q in t])))
    metrics += [("queen death round, median", lambda t: median([q.get("queen_death_round") for q in t])),
                ("queen death round, mean", lambda t: mean([q.get("queen_death_round") for q in t])),
                ("queen dead by r50 %", lambda t: pct([int(q.get("queen_death_round") is not None and q["queen_death_round"] < 50) for q in t])),
                ("queen dead by r100 %", lambda t: pct([int(q.get("queen_death_round") is not None and q["queen_death_round"] < 100) for q in t]))]
    for reason in DEATHS:
        metrics.append((f"queen died: {reason} %", lambda t, reason=reason: pct([int(q.get("queen_death_reason") == reason) for q in t])))
    metrics += [("queen killed by an enemy moving into it %", lambda t: pct([int(q.get("queen_death_by") == "enemy_move") for q in t])),
                ("queen killed by an ally moving into it %", lambda t: pct([int(q.get("queen_death_by") == "ally_move") for q in t])),
                ("queen moved head-on into a head %", lambda t: pct([int(q.get("queen_death_by") == "self_move" and q.get("queen_death_reason") == "head") for q in t])),
                ("head-on killer length, median", lambda t: median([q.get("queen_killer_len") for q in t])),
                ("killed the enemy queen by moving into it %", lambda t: pct([min(1, q.get("enemy_queen_killed") or 0) for q in t])),
                ("queen is the longest at end %", lambda t: pct([q.get("queen_is_longest_end") for q in t])),
                ("queen length at end, mean", lambda t: mean([q.get("queen_len_end") for q in t])),
                ("queen splits, mean", lambda t: mean([q.get("queen_splits") for q in t]))]
    for label, fn in metrics:
        rows.append([label] + [fn(teams[(n, who)]) for who in ("ours", "theirs") for n in names])
    out += table(["metric"] + [f"{n} {who}" for who in ("ours", "theirs") for n in names], rows) + [""]

    out += ["## How our queen dies, per ladder map (% of games)", ""]
    rows = []
    kinds = [("alive", lambda q: q.get("queen_alive_end") == 1),
             ("enemy rammed it", lambda q: q.get("queen_death_by") == "enemy_move"),
             ("it rammed a head", lambda q: q.get("queen_death_by") == "self_move" and q.get("queen_death_reason") == "head"),
             ("ally rammed it", lambda q: q.get("queen_death_by") == "ally_move"),
             ("no valid action", lambda q: q.get("queen_death_reason") == "novalid"),
             ("wall/self/body", lambda q: q.get("queen_death_reason") in ("wall", "self", "body"))]
    for mp in ladder + ["generated", "portal_heavy", "holdout"]:
        row = [mp.split("/")[-1]]
        for n in names:
            sel = [r["ours"] for r in allrows[n] if (r["map"] == mp or group(r["map"]) == mp) and "ours" in r]
            row += [pct([int(fn(q)) for q in sel]) for _, fn in kinds] + [median([q.get("queen_death_round") for q in sel])]
        if any(c is not None for c in row[1:]):
            rows.append(row)
    out += table(["map"] + [f"{n} {k}" for n in names for k in [k for k, _ in kinds] + ["median death r"]], rows) + [""]

    out += ["## Queen survival per opponent (ours / theirs alive at end %, median death round ours)", ""]
    rows = []
    for o in opps:
        row = [o]
        for n in names:
            sel = [r for r in allrows[n] if r["opp"] == o and "ours" in r]
            row += [pct([r["ours"].get("queen_alive_end") for r in sel]), pct([r["theirs"].get("queen_alive_end") for r in sel]),
                    median([r["ours"].get("queen_death_round") for r in sel])]
        rows.append(row)
    out += table(["opponent"] + [f"{n} {c}" for n in names for c in ("ours alive %", "theirs alive %", "ours death r")], rows) + [""]

    out += ["## CPU (sandbox points per dragon turn, per-game peak of the tested bot)", ""]
    rows = []
    for n in names:
        for fset in args.sets:
            peaks = sorted(r["cpu_peak"] for r in bots[n].get(fset, []) if r.get("cpu_peak"))
            if peaks:
                rows.append([n, fset, len(peaks), peaks[-1] / 1e6, peaks[len(peaks) // 2] / 1e6, peaks[int(0.99 * (len(peaks) - 1))] / 1e6,
                             max(((r["cpu_peak"] or 0, r["map"]) for r in bots[n][fset]))[1]])
    out += table(["bot", "set", "games with CPU", "max M", "median M", "p99 M", "map of the max"], rows) + [""]
    rows = []
    for mp in ladder:
        rows.append([mp.split("/")[1]] + [max((r.get("cpu_peak") or 0 for r in allrows[n] if r["map"] == mp), default=0) / 1e6 for n in names])
    out += ["Peak CPU per ladder map (M points):", ""] + table(["map"] + names, rows) + [""]
    print("\n".join(out))


if __name__ == "__main__":
    main()
