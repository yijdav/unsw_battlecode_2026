import argparse, json, math, os, subprocess, sys, threading, time
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools" / "replay"))
from concurrent.futures import ThreadPoolExecutor
from arena_dump import bot_key, how_kind, parse, replay_path
from decode import decode

OPPS = ["v_base", "sb_bang", "sb_python_io", "sb_heartbreaker", "ai_like", "opp_nicked_arch4"]
ARCH = "opp_nicked_arch4"
L17_ONE = ["australia", "autarky", "default", "islands", "maze", "portals", "stripes", "tower", "trauma", "trophy", "unsw", "weakhold"]
L17_TWO = ["devil", "devil_f", "dilemma", "dilemma10", "qos", "qos_e", "school", "school_k", "slithery", "slithery_x"]


def ladder17(folder, first):
    return [f"maps/{folder}/{m}.map:{first + 3}" for m in L17_ONE] + [f"maps/{folder}/{m}.map:{first + 1}" for m in L17_TWO]


SETS = {
    "main": (ladder17("ladder17", 1) + ["maps/generated:2", "maps/portal_heavy:2"], 1),
    "fresh": (ladder17("ladder17", 21), 21),
    "flip": (ladder17("ladder17_flip", 1), 1),
    "holdout": (["maps/holdout:2"], 1),
    "main_old": (["maps/ladder:3", "maps/generated:2", "maps/portal_heavy:2"], 1),
    "fresh_old": (["maps/ladder:6"], 4),
    "smoke": (["maps/ladder/portals.map:1", "maps/ladder/trauma.map:1"], 1),
}
BASE_METRICS = ["alive_r100", "pearls_r100", "behind_portal_pearls_r100", "first_cross", "crossings_r100", "own_coll_deaths",
                "own_coll_portal", "champ_feed_deaths", "small_head_deaths_by_enemy", "longest_feed_start", "final_longest"]
QUEEN_METRICS = ["queen_alive_end", "queen_len_end", "queen_death_round", "queen_killer_len", "queen_splits",
                 "queen_is_longest_end", "queen_len_r100", "queen_len_r200", "queen_len_r300", "queen_len_r400",
                 "enemy_queen_killed", "final_total", "final_queen"]
METRICS = BASE_METRICS + QUEEN_METRICS
DECIDED = ["elimination", "queen", "longest", "total", "draw", "length"]
DEATHS = ["wall", "self", "body", "head", "novalid"]
SCORE = {"win": 1.0, "draw": 0.5, "loss": 0.0}


def toolkit_version():
    try:
        out = subprocess.run(["unswbc", "--version"], capture_output=True, text=True, env=dict(os.environ, UNSWBC_NO_UPDATE="1")).stdout
    except OSError:
        return None
    return out.strip().split()[-1] if out.strip() else None


def sign_p(g, l):
    n = g + l
    if not n:
        return 1.0
    return min(1.0, 2 * sum(math.comb(n, x) for x in range(min(g, l) + 1)) / 2 ** n)


def run_games(bot, opps, fset, out, j, remote, resume, deadline=0, maps=None, keep=False):
    first = SETS[fset][1]
    maps = maps or SETS[fset][0]
    for suffix in ("", ".partial", ".cpu") if not resume else ("",):
        Path(str(out) + suffix).unlink(missing_ok=True)
    cmd = [sys.executable, str(ROOT / "tools" / "arena_dump.py"), bot, *opps, "--maps", *maps, "--first-seed", str(first),
           "--sandbox", "-j", str(j), "--dump", str(out)] + (["--resume"] if resume else []) + (["--deadline", str(deadline)] if deadline else [])
    if remote:
        cmd += ["--remote", remote] + ([] if keep else ["--remote-decode"])
    subprocess.run(cmd, cwd=ROOT, check=True)
    rows = json.load(open(out))
    missing = sum(1 for r in rows if r[5] == "error")
    if missing:
        print(f"incomplete: {missing} of {len(rows)} games not played or failed; rerun with --resume", file=sys.stderr)
        sys.exit(3)
    cpu = {}
    if Path(str(out) + ".cpu").exists():
        for line in open(str(out) + ".cpu"):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            cpu[r[0]] = r[1:]
    return rows, cpu


def decode_one(args):
    path, side = args
    try:
        pre = Path(path + ".json")
        d = json.loads(pre.read_text()) if pre.exists() else decode(path)
    except Exception as e:
        return {"error": str(e)}
    other = "B" if side == "A" else "A"
    return {"ours": d[side], "theirs": d[other], "rounds_played": d["rounds"], "replay_decided_by": d.get("decided_by")}


def metrics_for(rows, j, keep):
    jobs = []
    for i, me, opp, mp, side, res, rounds, how, seed in rows:
        a, b = (me, opp) if side == "A" else (opp, me)
        p = ROOT / replay_path(ROOT / "maps" / (mp + ".map"), a, b, seed)
        jobs.append((str(p), side))
    with Pool(j) as pool:
        got = pool.map(decode_one, jobs, chunksize=4)
    if not keep:
        for p, _ in jobs:
            Path(p).unlink(missing_ok=True)
            Path(p + ".json").unlink(missing_ok=True)
    return got


def collect(bot, fset, opps, runs, tag, j, remote, keep, resume=False, dj=6):
    out = runs / f"{tag}_{fset}.json"
    games = runs / f"{tag}_{fset}_games.jsonl"
    if resume and games.exists():
        done = [json.loads(line) for line in open(games)]
        if done and all(r["res"] != "error" and "error" not in r for r in done):
            return done
    deadline = float(os.environ.get("GATE_DEADLINE", "0") or 0)
    batches = SETS[fset][0] if os.environ.get("GATE_BATCH") else [None]
    table = []
    for k, spec in enumerate(batches):
        bout = out if spec is None else runs / f"{tag}_{fset}_b{k}.json"
        bgames = Path(str(bout)[:-5] + "_games.jsonl")
        if spec is not None and resume and bgames.exists():
            table += [json.loads(line) for line in open(bgames)]
            continue
        rows, cpu = run_games(bot, opps, fset, bout, j, remote, resume, deadline, None if spec is None else [spec], keep)
        mets = metrics_for(rows, dj, keep)
        part = []
        for row, m in zip(rows, mets):
            i, me, opp, mp, side, res, rounds, how, seed = row
            c = cpu.get(i)
            peak = (c[0] if side == "A" else c[1]) if c else None
            kind = how_kind(how)
            part.append({"i": i, "bot": me, "opp": opp, "map": mp, "side": side, "seed": seed, "res": res, "rounds": rounds,
                         "how": how, "decided_by": kind if kind != "error" else m.get("replay_decided_by"), "cpu_peak": peak, **m})
        if spec is not None:
            with open(bgames, "w") as f:
                for t in part:
                    f.write(json.dumps(t) + "\n")
        table += part
    with open(runs / f"{tag}_{fset}_games.jsonl", "w") as f:
        for t in table:
            f.write(json.dumps(t) + "\n")
    return table


def base_prefix(base):
    return "base" if base == "v_base" else f"base_{base}"


def base_rows(fset, opps, runs, j, remote, keep, base, resume=False, dj=6):
    key = json.loads(json.dumps({"base": bot_key(base), "opps": {o: bot_key(o) for o in opps}, "set": SETS[fset],
                                 "toolkit": toolkit_version()}))
    pre = base_prefix(base)
    meta = runs / f"{pre}_{fset}_key.json"
    games = runs / f"{pre}_{fset}_games.jsonl"
    if meta.exists() and games.exists() and json.load(open(meta)) == key:
        return [json.loads(line) for line in open(games)]
    rows = collect(base, fset, opps, runs, pre, j, remote, keep, resume, dj)
    json.dump(key, open(meta, "w"))
    return rows


def replay_result(bot, opp, mp, side, seed):
    a, b = (bot, opp) if side == "A" else (opp, bot)
    out = subprocess.run(["unswbc", "run", str(ROOT / "maps" / (mp + ".map")), a, b, "--seed", str(seed), "--sandbox", "--no-replay"],
                         cwd=ROOT, capture_output=True, text=True, errors="replace").stdout
    winner = parse(out)[0]
    return winner if winner in ("draw", "error") else ("win" if winner == side else "loss")


def verify(cand, base, cname, bname, path, j, fset="main"):
    done = {}
    if path.exists():
        for line in open(path):
            v = json.loads(line)
            done[tuple(v["key"])] = v
    bmap = {(r["opp"], r["map"], r["seed"], r["side"]): r for r in base}
    todo = []
    for r in cand:
        k = (r["opp"], r["map"], r["seed"], r["side"])
        b = bmap.get(k)
        if b is None or "error" in (r["res"], b["res"]) or r["res"] == b["res"] or k in done:
            continue
        todo.append((k, r, b))
    deadline = float(os.environ.get("GATE_DEADLINE", "0") or 0)
    lock = threading.Lock()
    recheck_path = path.parent / f"{base_prefix(bname)}_{fset}_recheck.jsonl"
    recheck = {}
    if recheck_path.exists():
        for line in open(recheck_path):
            v = json.loads(line)
            recheck[tuple(v["key"])] = v["res"]

    def majority(bot, k, first, known=None):
        runs_ = [first]
        second = known if known is not None else replay_result(bot, k[0], k[1], k[3], k[2])
        runs_.append(second)
        if second != first:
            runs_ += [replay_result(bot, k[0], k[1], k[3], k[2]) for _ in range(2)]
        valid = [x for x in runs_ if x != "error"] or [first]
        return sorted(set(valid), key=lambda x: (-valid.count(x), x != first, x))[0], runs_, second

    def one(item):
        k, r, b = item
        if deadline and time.time() > deadline:
            return False
        cand_res, c3, _ = majority(cname, k, r["res"])
        base_res, b3, second = majority(bname, k, b["res"], recheck.get(k))
        v = {"key": list(k), "cand": cand_res, "base": base_res, "cand_runs": c3, "base_runs": b3}
        if k not in recheck and second != "error":
            with lock:
                recheck[k] = second
                with open(recheck_path, "a") as f:
                    f.write(json.dumps({"key": list(k), "res": second}) + "\n")
        with lock:
            done[k] = v
            with open(path, "a") as f:
                f.write(json.dumps(v) + "\n")
        return True

    with ThreadPoolExecutor(max(1, j)) as ex:
        finished = list(ex.map(one, todo))
    if not all(finished):
        print(f"incomplete: verified {sum(finished)} of {len(todo)} flipped fixtures before the deadline; rerun with --resume", file=sys.stderr)
        sys.exit(3)
    return done


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def fmt(x):
    return "-" if x is None else (f"{x:.1f}" if isinstance(x, float) else str(x))


def decided_of(row):
    return row.get("decided_by") or how_kind(row.get("how"))


def wdl(results):
    return f"{results.count('win')}-{results.count('draw')}-{results.count('loss')}"


def pct(xs):
    xs = [x for x in xs if x is not None]
    return 100.0 * sum(xs) / len(xs) if xs else None


def median(xs):
    xs = sorted(x for x in xs if x is not None)
    return float(xs[len(xs) // 2]) if xs else None


def queen_rows():
    rows = [("games", lambda t: len(t)),
            ("queen alive at end %", lambda t: pct([q.get("queen_alive_end") for q in t]))]
    for r in (100, 200, 300, 400):
        rows.append((f"queen alive at r{r} %", lambda t, r=r: pct([None if q.get(f"queen_len_r{r}") is None else int(q[f"queen_len_r{r}"] > 0) for q in t])))
    rows += [("queen death round, median", lambda t: median([q.get("queen_death_round") for q in t])),
             ("queen death round, mean", lambda t: mean([q.get("queen_death_round") for q in t]))]
    for reason in DEATHS:
        rows.append((f"queen died: {reason} %", lambda t, reason=reason: pct([int(q.get("queen_death_reason") == reason) for q in t if "queen_death_reason" in q])))
    rows += [("queen killed by an enemy moving into it %", lambda t: pct([int(q.get("queen_death_by") == "enemy_move") for q in t if "queen_death_by" in q])),
             ("queen killed head-on by own move %", lambda t: pct([int(q.get("queen_death_by") == "self_move" and q.get("queen_death_reason") == "head") for q in t if "queen_death_by" in q])),
             ("head-on killer length, median", lambda t: median([q.get("queen_killer_len") for q in t])),
             ("killed the enemy queen by moving into it %", lambda t: pct([min(1, q["enemy_queen_killed"]) for q in t if "enemy_queen_killed" in q])),
             ("queen is the longest at end %", lambda t: pct([q.get("queen_is_longest_end") for q in t])),
             ("queen length at end, mean", lambda t: mean([q.get("queen_len_end") for q in t])),
             ("queen splits, mean", lambda t: mean([q.get("queen_splits") for q in t if "queen_splits" in q]))]
    return rows


def report(cand, base, cname, fset, checked=None, bname="v_base"):
    checked = checked or {}
    bmap = {(r["opp"], r["map"], r["seed"], r["side"]): r for r in base}
    pairs = []
    fixed = 0
    for r in cand:
        k = (r["opp"], r["map"], r["seed"], r["side"])
        b = bmap.get(k)
        if b is None or "error" in (r["res"], b["res"]):
            continue
        if k in checked:
            v = checked[k]
            if v["cand"] != r["res"] or v["base"] != b["res"]:
                fixed += 1
            r, b = dict(r, res=v["cand"]), dict(b, res=v["base"])
        pairs.append((r, b))
    lines = [f"# Gate: {cname} vs {bname} ({fset} set, {len(pairs)} paired fixtures)", "",
             f"Flipped fixtures replayed twice per side: {len(checked)}; results corrected by the majority of three: {fixed}.", ""]

    def flips(sel):
        g = sum(1 for r, b in sel if SCORE[r["res"]] > SCORE[b["res"]])
        l = sum(1 for r, b in sel if SCORE[r["res"]] < SCORE[b["res"]])
        return g, l, len(sel) - g - l, sign_p(g, l)

    groups = [("overall", pairs), ("ladder", [p for p in pairs if p[0]["map"].split("/")[0] in ("ladder", "ladder17", "ladder17_flip")]),
              ("vs " + ARCH, [p for p in pairs if p[0]["opp"] == ARCH])]
    for o in sorted({p[0]["opp"] for p in pairs}):
        if o != ARCH:
            groups.append(("vs " + o, [p for p in pairs if p[0]["opp"] == o]))
    for s in ("generated", "portal_heavy", "holdout"):
        sel = [p for p in pairs if p[0]["map"].startswith(s + "/")]
        if sel:
            groups.append((s, sel))
    lines += ["| subset | gained | lost | same | sign p | cand score% | base score% |", "|---|---|---|---|---|---|---|"]
    summary = {}
    for name, sel in groups:
        g, l, s, p = flips(sel)
        cw = 100 * mean([SCORE[r["res"]] for r, _ in sel]) if sel else None
        bw = 100 * mean([SCORE[b["res"]] for _, b in sel]) if sel else None
        summary[name] = (g, l, p)
        lines.append(f"| {name} | {g} | {l} | {s} | {p:.3g} | {fmt(cw)} | {fmt(bw)} |")
    lines += ["", "## Per map (all opponents; maps with flips)", "", "| map | gained | lost | p |", "|---|---|---|---|"]
    for mp in sorted({p[0]["map"] for p in pairs}):
        g, l, s, p = flips([q for q in pairs if q[0]["map"] == mp])
        if g or l:
            lines.append(f"| {mp} | {g} | {l} | {p:.3g} |")
    lines += ["", "## Decided by (W-D-L)", "", "| decided by | cand W-D-L | base W-D-L |", "|---|---|---|"]
    for kind in DECIDED + ["error"]:
        c = [r["res"] for r, _ in pairs if decided_of(r) == kind]
        b = [b["res"] for _, b in pairs if decided_of(b) == kind]
        if c or b:
            lines.append(f"| {kind} | {wdl(c)} | {wdl(b)} |")
    lines += ["", "## Queen survival (ours = the tested bot, theirs = its opponents)", "",
              "| metric | base ours | cand ours | base theirs | cand theirs |", "|---|---|---|---|---|"]
    teams = [[x[who] for x in sel if who in x] for who in ("ours", "theirs") for sel in ([b for _, b in pairs], [r for r, _ in pairs])]
    for name, fn in queen_rows():
        lines.append(f"| {name} | " + " | ".join(fmt(fn(t)) for t in teams) + " |")

    lines += ["", "## Movement (multi-step moves per 100 dragon-turns by length band, steps per turn, paid steps per 100 turns)", "",
              "| team | rows | L2-4 | L5-8 | L9-12 | L13+ | steps/turn L5+ | paid/100 L5+ | pearls/game | final longest |", "|---|---|---|---|---|---|---|---|---|---|"]
    for label, sel, who in (("base ours", [b for _, b in pairs], "ours"), ("cand ours", [r for r, _ in pairs], "ours"),
                            ("base theirs", [b for _, b in pairs], "theirs"), ("cand theirs", [r for r, _ in pairs], "theirs")):
        got = [x[who] for x in sel if who in x and "mv_turns" in x[who]]
        cells = []
        for k in range(4):
            t = sum(g["mv_turns"][k] for g in got)
            cells.append(fmt(100.0 * sum(g["mv_multi"][k] for g in got) / t) if t else "-")
        t5 = sum(sum(g["mv_turns"][1:]) for g in got)
        cells.append(fmt(sum(sum(g["mv_steps"][1:]) for g in got) / t5) if t5 else "-")
        cells.append(fmt(100.0 * sum(sum(g["mv_paid"][1:]) for g in got) / t5) if t5 else "-")
        allg = [x[who] for x in sel if who in x]
        cells.append(fmt(mean([(g.get("pearls_spawn") or 0) + (g.get("pearls_drop") or 0) for g in allg])))
        cells.append(fmt(mean([g.get("final_longest") for g in allg])))
        lines.append(f"| {label} | {len(got)} | " + " | ".join(cells) + " |")

    def mrow(sel, who, keys, deaths):
        vals = [mean([r[who].get(k) for r in sel if who in r]) for k in keys]
        return vals + ([mean([r[who]["deaths"][d] for r in sel if who in r]) for d in DEATHS] if deaths else [])

    maps = sorted({p[0]["map"] for p in pairs if not p[0]["map"].startswith(("generated/", "portal_heavy/"))})
    for title, keys, deaths in (("Metrics per map", BASE_METRICS, True), ("Queen metrics per map", QUEEN_METRICS, False)):
        lines += ["", f"## {title}, means per game (base -> cand)", ""]
        lines += ["| map | side | " + " | ".join(keys) + (" | " + " | ".join("d_" + d for d in DEATHS) if deaths else "") + " |",
                  "|" + "---|" * (len(keys) + (len(DEATHS) if deaths else 0) + 2)]
        for mp in maps + ["ALL"]:
            cs = [r for r, _ in pairs if mp == "ALL" or r["map"] == mp]
            bs = [b for _, b in pairs if mp == "ALL" or b["map"] == mp]
            for who in ("ours", "theirs"):
                cells = [f"{fmt(x)}->{fmt(y)}" for x, y in zip(mrow(bs, who, keys, deaths), mrow(cs, who, keys, deaths))]
                lines.append(f"| {mp} | {who} | " + " | ".join(cells) + " |")
    cpu_c = max((r["cpu_peak"] or 0) for r in cand) if cand else 0
    cpu_b = max((r["cpu_peak"] or 0) for r in base) if base else 0
    nv_c = mean([r["ours"]["deaths"]["novalid"] for r, _ in pairs if "ours" in r])
    nv_b = mean([b["ours"]["deaths"]["novalid"] for _, b in pairs if "ours" in b])
    errs = sum(1 for r in cand if r["res"] == "error" or "error" in r)
    g, l, p = summary["overall"]
    lg, ll, _ = summary["ladder"]
    ag, al, _ = summary.get("vs " + ARCH, (0, 0, 1))
    checks = [
        ("1 overall p<0.05 and gained>lost", p < 0.05 and g > l),
        ("2 ladder not worse", lg >= ll),
        (f"3 not worse vs {ARCH}", ag >= al),
        ("5 no rise in no-valid-action deaths (at most +5%)", nv_c is not None and nv_b is not None and nv_c <= nv_b * 1.05),
        ("6 peak CPU < 50M", cpu_c < 50e6),
    ]
    lines += ["", f"Peak CPU per turn: cand {cpu_c / 1e6:.2f}M, base {cpu_b / 1e6:.2f}M. Games with errors: {errs}.",
              f"No-valid-action deaths per game (ours): base {fmt(nv_b)}, cand {fmt(nv_c)}.", "",
              "## Acceptance (item 4, the target metric, is judged from the tables)", ""]
    lines += [f"- [{'x' if ok else ' '}] {name}" for name, ok in checks]
    return "\n".join(lines) + "\n", all(ok for _, ok in checks)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("candidate")
    ap.add_argument("--tag")
    ap.add_argument("--set", default="main")
    ap.add_argument("--opps", nargs="*", default=OPPS)
    ap.add_argument("--base", default="v_base")
    ap.add_argument("--runs", default="runs")
    ap.add_argument("-j", type=int, default=8)
    ap.add_argument("--remote", default=os.environ.get("ARENA_REMOTE"))
    ap.add_argument("--keep-replays", action="store_true")
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--decode-j", type=int, default=6)
    ap.add_argument("--no-verify", action="store_true")
    ap.add_argument("--maps", nargs="*", help="custom fixture set, e.g. maps/ladder/trophy.map:40; named by --set")
    ap.add_argument("--first-seed", type=int, default=1)
    args = ap.parse_args()
    if args.maps:
        SETS[args.set] = (args.maps, args.first_seed)
    if args.set not in SETS:
        ap.error(f"unknown set {args.set}; give --maps to define it")
    runs = ROOT / args.runs
    runs.mkdir(parents=True, exist_ok=True)
    tag = args.tag or args.candidate
    if args.report_only:
        base = [json.loads(x) for x in open(runs / f"{base_prefix(args.base)}_{args.set}_games.jsonl")]
        cand = [json.loads(x) for x in open(runs / f"{tag}_{args.set}_games.jsonl")]
    else:
        base = base_rows(args.set, args.opps, runs, args.j, args.remote, args.keep_replays, args.base, args.resume, args.decode_j)
        cand = collect(args.candidate, args.set, args.opps, runs, tag, args.j, args.remote, args.keep_replays, args.resume, args.decode_j)
    checked = {} if args.no_verify else verify(cand, base, args.candidate, args.base, runs / f"{tag}_{args.set}_verify.jsonl", args.j, args.set)
    text, ok = report(cand, base, args.candidate, args.set, checked, args.base)
    (runs / f"{tag}_{args.set}_report.md").write_text(text, encoding="utf-8")
    print(text)
    print("GATE", "PASS" if ok else "FAIL", "(item 4 still to judge)")


if __name__ == "__main__":
    main()
