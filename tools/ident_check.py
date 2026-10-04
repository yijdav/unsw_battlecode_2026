import json, sys

base = {}
for line in open(sys.argv[1]):
    r = json.loads(line)
    base[(r["opp"], r["map"], r["seed"], r["side"])] = r
same = diff = 0
for line in open(sys.argv[2]):
    r = json.loads(line)
    b = base.get((r["opp"], r["map"], r["seed"], r["side"]))
    if b is None:
        continue
    keys = ("res", "rounds", "how", "ours", "theirs")
    strip = lambda v: {k: x for k, x in v.items() if not k.startswith("cpu")} if isinstance(v, dict) else v
    if all(strip(r.get(k)) == strip(b.get(k)) for k in keys):
        same += 1
    else:
        diff += 1
        print("DIFF", r["opp"], r["map"], r["seed"], r["side"], [k for k in keys if strip(r.get(k)) != strip(b.get(k))])
print(f"identical {same}, different {diff}")
