import argparse, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True)
    ap.add_argument("--set", required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--parts", nargs="+", required=True, help="games.jsonl files with played candidate rows")
    ap.add_argument("--same-from-base", nargs="*", default=[], help="map ids (e.g. ladder17/stripes) whose fixtures are filled from the base rows")
    args = ap.parse_args()
    runs = ROOT / args.runs
    base = [json.loads(x) for x in open(runs / f"base_v_climb_{args.set}_games.jsonl")]
    played = {}
    for p in args.parts:
        for line in open(p):
            r = json.loads(line)
            played[(r["opp"], r["map"], r["seed"], r["side"])] = r
    out, filled, missing = [], 0, 0
    for b in base:
        k = (b["opp"], b["map"], b["seed"], b["side"])
        if k in played:
            out.append(played[k])
        elif b["map"] in args.same_from_base:
            out.append(dict(b, bot=args.tag, filled_from_base=True))
            filled += 1
        else:
            missing += 1
    with open(runs / f"{args.tag}_{args.set}_games.jsonl", "w") as f:
        for r in out:
            f.write(json.dumps(r) + "\n")
    print(f"{len(out)} rows: {len(out) - filled} played, {filled} filled from base, {missing} missing")


if __name__ == "__main__":
    main()
