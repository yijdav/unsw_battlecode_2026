import argparse, json
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("runs")
ap.add_argument("base")
ap.add_argument("out")
ap.add_argument("--part", nargs=2, action="append", default=[], metavar=("GAMES", "MAPS"))
ap.add_argument("--bot", required=True)
args = ap.parse_args()
runs = Path(args.runs)
base = [json.loads(x) for x in open(runs / args.base)]
take = {}
for games, maps in args.part:
    ms = set(maps.split(","))
    for line in open(runs / games):
        r = json.loads(line)
        if r["map"] in ms:
            take[(r["opp"], r["map"], r["seed"], r["side"])] = r
out, used, same, diff = [], 0, 0, 0
for b in base:
    k = (b["opp"], b["map"], b["seed"], b["side"])
    if k in take:
        r = dict(take[k], bot=args.bot, i=b["i"])
        used += 1
        if (r["res"], r["rounds"], r["how"]) == (b["res"], b["rounds"], b["how"]):
            same += 1
        else:
            diff += 1
    else:
        r = dict(b, bot=args.bot)
    out.append(r)
with open(runs / args.out, "w") as f:
    for r in out:
        f.write(json.dumps(r) + "\n")
print(f"{len(out)} rows: {used} from candidate runs ({same} identical to base, {diff} different), {len(out) - used} filled from base")
