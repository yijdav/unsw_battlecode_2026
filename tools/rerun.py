import argparse, json, os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools" / "replay"))
from gate import OPPS, SETS


def jobs_of(bot, opps, fset):
    specs, first = SETS[fset]
    maps, nseeds = [], {}
    for m in specs:
        m, _, k = m.partition(":")
        p = ROOT / m
        got = sorted(p.glob("*.map")) if p.is_dir() else [p]
        maps += got
        for g in got:
            nseeds[g] = int(k) if k else 1
    jobs = []
    for opp in opps:
        for mp in maps:
            for seed in range(first, nseeds[mp] + 1):
                for side in "AB":
                    jobs.append((bot, opp, f"{mp.parent.name}/{mp.stem}", side, seed))
    return specs, first, jobs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bot")
    ap.add_argument("fixtures")
    ap.add_argument("out")
    ap.add_argument("--set", default="main")
    ap.add_argument("--remote", required=True)
    ap.add_argument("-j", type=int, default=0)
    args = ap.parse_args()
    want = {tuple(f) for f in json.load(open(args.fixtures))}
    specs, first, jobs = jobs_of(args.bot, OPPS, args.set)
    keys = {(opp, mp, seed, side): i for i, (_, opp, mp, side, seed) in enumerate(jobs)}
    missing = [k for k in want if k not in keys]
    if missing:
        sys.exit(f"fixtures not in set {args.set}: {missing[:5]}")
    dump = Path(args.out)
    with open(str(dump) + ".partial", "w") as f:
        for i, (bot, opp, mp, side, seed) in enumerate(jobs):
            if (opp, mp, seed, side) not in want:
                f.write(json.dumps([i, bot, opp, mp, side, "win", 0, "skip", seed, "skip"]) + "\n")
    cmd = [sys.executable, str(ROOT / "tools" / "arena_dump.py"), args.bot, *OPPS, "--maps", *specs, "--first-seed", str(first),
           "--sandbox", "-j", str(args.j), "--dump", str(dump), "--resume", "--remote", args.remote]
    subprocess.run(cmd, cwd=ROOT, stdout=subprocess.DEVNULL, env=dict(os.environ, UNSWBC_NO_UPDATE="1"))
    rows = json.load(open(dump))
    got = {}
    for line in open(str(dump) + ".partial"):
        r = json.loads(line)
        if r[9] != "skip":
            got[r[0]] = r
    out = [{"key": [r[2], r[3], r[8], r[4]], "res": r[5], "rounds": r[6], "how": r[7], "host": r[9]} for i, r in sorted(got.items())]
    Path(str(dump) + ".rows.json").write_text(json.dumps(out))
    print(f"{len(out)} of {len(want)} fixtures replayed; {sum(1 for r in rows if r[5] == 'error')} errors")


if __name__ == "__main__":
    main()
