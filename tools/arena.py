import argparse, re, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def play(map_path, a, b, seed, sandbox):
    out = ROOT / "replays" / "arena" / f"{a}-vs-{b}-{map_path.parent.name}_{map_path.stem}-{seed}.replay"
    cmd = ["unswbc", "run", str(map_path), a, b, "--seed", str(seed), "-o", str(out), "--no-logs"]
    if sandbox:
        cmd.append("--sandbox")
    text = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True).stdout
    m = re.search(r"team (A|B) wins after (\d+) rounds \(([^)]*)\)", text)
    if m:
        return m.group(1), int(m.group(2)), m.group(3), text
    m = re.search(r"draw after (\d+) rounds", text)
    return ("draw", int(m.group(1)) if m else -1, "draw", text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bot")
    ap.add_argument("opponents", nargs="+")
    ap.add_argument("--maps", nargs="*", default=["maps/ladder", "maps"])
    ap.add_argument("--seeds", type=int, default=1)
    ap.add_argument("-j", type=int, default=8)
    ap.add_argument("--sandbox", action="store_true")
    args = ap.parse_args()

    maps = []
    for m in args.maps:
        p = ROOT / m
        maps += sorted(p.glob("*.map")) if p.is_dir() else [p]
    (ROOT / "replays" / "arena").mkdir(parents=True, exist_ok=True)

    jobs = []
    for opp in args.opponents:
        for mp in maps:
            for seed in range(1, args.seeds + 1):
                jobs.append((opp, mp, args.bot, opp, seed, "A"))
                jobs.append((opp, mp, opp, args.bot, seed, "B"))

    def run(job):
        opp, mp, a, b, seed, side = job
        winner, rounds, how, _ = play(mp, a, b, seed, args.sandbox)
        res = "draw" if winner == "draw" else ("win" if winner == side else "loss")
        return opp, f"{mp.parent.name}/{mp.stem}", side, res, rounds, how

    tally = defaultdict(lambda: defaultdict(int))
    losses = []
    with ThreadPoolExecutor(args.j) as pool:
        for opp, mp, side, res, rounds, how in pool.map(run, jobs):
            tally[opp][res] += 1
            if res != "win":
                losses.append(f"  {res:4s} vs {opp:10s} {mp:28s} as {side}  r{rounds} ({how})")
    for opp, t in tally.items():
        n = sum(t.values())
        print(f"{args.bot} vs {opp}: {t['win']}W {t['draw']}D {t['loss']}L  ({t['win'] / n:.0%} wins of {n})")
    print("\n".join(sorted(losses)))


if __name__ == "__main__":
    sys.exit(main())
