import argparse, json, os, sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import gate


def pct(xs):
    xs = [x for x in xs if x is not None]
    return f"{100.0 * sum(xs) / len(xs):.1f}" if xs else "-"


def side(rows, who, key):
    return [r[who].get(key) for r in rows if who in r]


def alive_at(rows, who, rnd):
    return [None if r[who].get(f"queen_len_r{rnd}") is None else int(r[who][f"queen_len_r{rnd}"] > 0) for r in rows if who in r]


def killed_by_enemy(rows, who):
    return [int(r[who].get("queen_death_by") == "enemy_move") for r in rows if who in r]


def score(rows):
    return f"{100.0 * sum(gate.SCORE[r['res']] for r in rows) / len(rows):.1f}" if rows else "-"


def decided(rows):
    by = defaultdict(lambda: [0, 0, 0])
    for r in rows:
        k = gate.decided_of(r)
        by[k][{"win": 0, "draw": 1, "loss": 2}.get(r["res"], 1)] += 1
    return " ".join(f"{k[0].upper()}{v[0]}-{v[2]}" + (f"(d{v[1]})" if v[1] else "") for k, v in sorted(by.items(), key=lambda kv: -sum(kv[1])))


def table(rows, bot):
    lines = [f"| opponent | games | {bot} score % | decided by ({bot} W-L) | {bot} queen alive end % | opp queen alive end % | "
             f"{bot} queen alive r100 / r200 / r300 % | opp queen alive r100 / r200 / r300 % | {bot} queen killed by opp move % | opp queen killed by {bot} move % |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for o in sorted({r["opp"] for r in rows}):
        sel = [r for r in rows if r["opp"] == o]
        lines.append(f"| {o} | {len(sel)} | {score(sel)} | {decided(sel)} | {pct(side(sel, 'ours', 'queen_alive_end'))} | "
                     f"{pct(side(sel, 'theirs', 'queen_alive_end'))} | "
                     f"{' / '.join(pct(alive_at(sel, 'ours', k)) for k in (100, 200, 300))} | "
                     f"{' / '.join(pct(alive_at(sel, 'theirs', k)) for k in (100, 200, 300))} | "
                     f"{pct(killed_by_enemy(sel, 'ours'))} | {pct(killed_by_enemy(sel, 'theirs'))} |")
    return lines


def per_board(rows, bot):
    opps = sorted({r["opp"] for r in rows})
    lines = ["| board | " + " | ".join(f"{o}: {bot} % / q {bot} / q opp" for o in opps) + " |", "|---|" + "---|" * len(opps)]
    for mp in sorted({r["map"] for r in rows}):
        cells = []
        for o in opps:
            sel = [r for r in rows if r["opp"] == o and r["map"] == mp]
            cells.append(f"{score(sel)} / {pct(side(sel, 'ours', 'queen_alive_end'))} / {pct(side(sel, 'theirs', 'queen_alive_end'))}")
        lines.append(f"| {mp.split('/')[-1]} | " + " | ".join(cells) + " |")
    return lines


def deaths(rows, bot):
    lines = [f"| opponent | team | queen died: head % | novalid % | body % | self % | median death round | killer length median |", "|---|---|---|---|---|---|---|---|"]
    for o in sorted({r["opp"] for r in rows}):
        sel = [r for r in rows if r["opp"] == o]
        for who, name in (("ours", bot), ("theirs", o)):
            t = [r[who] for r in sel if who in r]
            dead = [q for q in t if q.get("queen_death_reason")]
            share = lambda k: f"{100.0 * sum(1 for q in dead if q['queen_death_reason'] == k) / len(dead):.0f}" if dead else "-"
            rounds = sorted(q["queen_death_round"] for q in dead if q.get("queen_death_round") is not None)
            kl = sorted(q["queen_killer_len"] for q in dead if q.get("queen_killer_len") is not None)
            lines.append(f"| {o} | {name} | {share('head')} | {share('novalid')} | {share('body')} | {share('self')} | "
                         f"{rounds[len(rounds) // 2] if rounds else '-'} | {kl[len(kl) // 2] if kl else '-'} |")
    return lines


def repair(runs, tag, fset):
    games = runs / f"{tag}_{fset}_games.jsonl"
    keep = runs / f"{tag}_{fset}_good.jsonl"
    partial = runs / f"{tag}_{fset}.json.partial"
    good = {}
    for path in (keep, games):
        if path.exists():
            for line in open(path):
                r = json.loads(line)
                if "error" not in r and r["res"] != "error":
                    good[r["i"]] = r
    if games.exists() and any("error" in json.loads(line) for line in open(games)):
        with open(keep, "w") as f:
            for r in good.values():
                f.write(json.dumps(r) + "\n")
        if partial.exists():
            lines = []
            for line in open(partial):
                try:
                    if json.loads(line)[0] in good:
                        lines.append(line)
                except ValueError:
                    pass
            partial.write_text("".join(lines))
        games.unlink()
    return good


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bot")
    ap.add_argument("opps", nargs="+")
    ap.add_argument("--maps", nargs="*")
    ap.add_argument("--set", default="spar")
    ap.add_argument("--first-seed", type=int, default=1)
    ap.add_argument("--runs", default="runs")
    ap.add_argument("--tag")
    ap.add_argument("-j", type=int, default=4)
    ap.add_argument("--remote", default=os.environ.get("ARENA_REMOTE"))
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--boards", action="store_true")
    ap.add_argument("--games", nargs="*", help="report from these games.jsonl files instead of playing")
    ap.add_argument("--only-maps", default="", help="keep only rows whose map starts with this prefix, e.g. ladder17/")
    args = ap.parse_args()
    if args.maps:
        gate.SETS[args.set] = (args.maps, args.first_seed)
    runs = ROOT / args.runs
    runs.mkdir(parents=True, exist_ok=True)
    tag = args.tag or f"spar_{args.bot}"
    out = runs / f"{tag}_{args.set}_games.jsonl"
    if args.games:
        rows = [json.loads(x) for g in args.games for x in open(g)]
    elif args.report_only:
        rows = [json.loads(x) for x in open(out)]
    else:
        good = repair(runs, tag, args.set) if args.resume else {}
        rows = gate.collect(args.bot, args.set, args.opps, runs, tag, args.j, args.remote, False, args.resume)
        if good:
            rows = [good.get(r["i"], r) if "error" in r else r for r in rows]
            with open(out, "w") as f:
                for r in rows:
                    f.write(json.dumps(r) + "\n")
        lost = sum(1 for r in rows if "error" in r)
        if lost:
            print(f"warning: {lost} games still lack decoded metrics; rerun with --resume to replay them", file=sys.stderr)
    rows = [r for r in rows if r["opp"] in args.opps and r["bot"] == args.bot and r["map"].startswith(args.only_maps)]
    text = [f"## {args.bot} vs {', '.join(args.opps)} ({args.set}, {len(rows)} games)", ""] + table(rows, args.bot) + [""] + deaths(rows, args.bot)
    if args.boards:
        text += ["", "### Per board", ""] + per_board(rows, args.bot)
    print("\n".join(text))


if __name__ == "__main__":
    main()
