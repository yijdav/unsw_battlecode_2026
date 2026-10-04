import argparse, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import gate
from arena_dump import bot_key


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--maps", nargs="+", required=True)
    ap.add_argument("--first-seed", type=int, default=1)
    ap.add_argument("--base", default="v_climb")
    ap.add_argument("--runs", required=True)
    ap.add_argument("--src-runs", default="runs")
    ap.add_argument("--opps", nargs="*", default=gate.OPPS)
    args = ap.parse_args()
    want = set()
    for m in args.maps:
        path, _, k = m.partition(":")
        p = ROOT / path
        files = sorted(p.glob("*.map")) if p.is_dir() else [p]
        for f in files:
            for seed in range(args.first_seed, int(k or 1) + 1):
                want.add((f"{f.parent.name}/{f.stem}", seed))
    pre = gate.base_prefix(args.base)
    rows = {}
    for src in ("main", "fresh", "flip"):
        g = ROOT / args.src_runs / f"{pre}_{src}_games.jsonl"
        if not g.exists():
            continue
        for line in open(g):
            r = json.loads(line)
            if (r["map"], r["seed"]) in want and r["opp"] in args.opps:
                rows[(r["opp"], r["map"], r["seed"], r["side"])] = r
    need = len(want) * len(args.opps) * 2
    if len(rows) != need:
        sys.exit(f"only {len(rows)} of {need} base fixtures cached")
    runs = ROOT / args.runs
    runs.mkdir(parents=True, exist_ok=True)
    key = json.loads(json.dumps({"base": bot_key(args.base), "opps": {o: bot_key(o) for o in args.opps},
                                 "set": (args.maps, args.first_seed), "toolkit": gate.toolkit_version()}))
    json.dump(key, open(runs / f"{pre}_{args.name}_key.json", "w"))
    with open(runs / f"{pre}_{args.name}_games.jsonl", "w") as f:
        for r in rows.values():
            f.write(json.dumps(r) + "\n")
    print(f"{args.name}: {len(rows)} base fixtures")


if __name__ == "__main__":
    main()
