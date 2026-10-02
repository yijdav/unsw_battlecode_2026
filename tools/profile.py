import argparse, json, os, sys
from collections import defaultdict
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools" / "replay"))
from decode import decode

US = int(os.environ.get("BC_TEAM_ID", "0"))


def decode_one(args):
    gid, path = args
    try:
        return gid, decode(path)
    except Exception as e:
        return gid, {"error": str(e)}


def side_row(d, side, meta, team, other):
    s = d[side]
    snap = lambda r, k: (s["snap"].get(r) or s["snap"].get(str(r)) or {}).get(k)
    zone = lambda r: s["zone"].get(r) or s["zone"].get(str(r)) or {}
    z50 = zone(50)
    n50 = sum(z50.values()) or 1
    feed = next((i * 50 for i, v in enumerate(s["champ_own_drop"]) if v >= 3), None)
    win = (meta["winner"] == "a") == (side == "A")
    return {"game": meta["id"], "map": meta["map"], "team": team["id"], "name": team["name"], "elo": team.get("elo_now") or team["elo"],
            "opp": other["id"], "opp_elo": other.get("elo_now") or other["elo"], "win": win,
            "count_r25": snap(25, "count"), "count_r50": snap(50, "count"), "count_r100": snap(100, "count"),
            "total_r100": snap(100, "total"), "total_r200": snap(200, "total"), "total_r300": snap(300, "total"),
            "longest_r200": snap(200, "longest"), "longest_r300": snap(300, "longest"), "longest_r400": snap(400, "longest"),
            "pearls_r100": s["pearls_r100"], "pearls_spawn": s["pearls_spawn"], "pearls_drop": s["pearls_drop"],
            "splits_early": s["splits"][0], "splits_mid": s["splits"][1], "splits_late": s["splits"][2],
            "rams_early": s["rams"][0], "rams_mid": s["rams"][1], "rams_late": s["rams"][2],
            "first_cross": s["first_cross"], "crossings_r100": s["crossings_r100"], "feed_proxy": feed,
            "centre_frac_r50": z50.get("centre", 0) / n50, "behind_frac_r50": z50.get("behind", 0) / n50,
            "own_coll": s["own_coll_deaths"], "deaths_head": s["deaths"]["head"], "deaths_novalid": s["deaths"]["novalid"],
            "final_longest": s["final_longest"], "final_count": s["final_count"], "rounds": d["rounds"]}


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def fmt(x):
    return "-" if x is None else (f"{x:.2f}" if isinstance(x, float) and abs(x) < 1 else f"{x:.1f}" if isinstance(x, float) else str(x))


COLS = ["win", "count_r25", "count_r50", "count_r100", "total_r100", "total_r300", "longest_r300", "longest_r400", "pearls_r100",
        "pearls_spawn", "pearls_drop", "splits_early", "splits_mid", "rams_early", "rams_mid", "first_cross", "crossings_r100",
        "feed_proxy", "centre_frac_r50", "own_coll", "deaths_head", "deaths_novalid", "final_longest"]


def table(groups, title):
    lines = [f"## {title}", "", "| map | group | n | " + " | ".join(COLS) + " |", "|" + "---|" * (len(COLS) + 3)]
    for (mp, g), rows in sorted(groups.items()):
        vals = [mean([float(r[c]) if isinstance(r[c], bool) else r[c] for r in rows]) for c in COLS]
        lines.append(f"| {mp} | {g} | {len(rows)} | " + " | ".join(fmt(v) for v in vals) + " |")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=str(ROOT / "notes" / "2026-10-02-research" / "manifest.jsonl"))
    ap.add_argument("--replays", default=str(ROOT / "replays" / "ladder"))
    ap.add_argument("--out", default=str(ROOT / "notes" / "2026-10-02-research"))
    ap.add_argument("--top-elo", type=int, default=1880)
    ap.add_argument("-j", type=int, default=12)
    args = ap.parse_args()
    metas = {}
    for line in open(args.manifest, encoding="utf-8"):
        m = json.loads(line)
        metas[m["id"]] = m
    jobs = [(gid, str(Path(args.replays) / f"{gid}.replay.gz")) for gid in metas if (Path(args.replays) / f"{gid}.replay.gz").exists()]
    with Pool(args.j) as pool:
        got = pool.map(decode_one, jobs, chunksize=2)
    rows, mismatch, errors = [], 0, 0
    for gid, d in got:
        if "error" in d:
            errors += 1
            continue
        meta = metas[gid]
        if d["winner"] in "AB" and (d["winner"] == "A") != (meta["winner"] == "a"):
            mismatch += 1
        rows.append(side_row(d, "A", meta, meta["a"], meta["b"]))
        rows.append(side_row(d, "B", meta, meta["b"], meta["a"]))
    out = Path(args.out)
    with open(out / "games_decoded.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    top = defaultdict(list)
    wl = defaultdict(list)
    for r in rows:
        if r["team"] == US:
            top[(r["map"], "us (bot)")].append(r)
        elif (r["elo"] or 0) >= args.top_elo:
            top[(r["map"], "top teams")].append(r)
        if (r["elo"] or 0) >= args.top_elo and (r["opp_elo"] or 0) >= args.top_elo:
            wl[(r["map"], "winner" if r["win"] else "loser")].append(r)
    text = [f"# Strategy profile ({len(got)} games decoded, {errors} errors, {mismatch} winner mismatches with the site)", "",
            table(top, f"Top teams (Elo >= {args.top_elo}) against us, per map"),
            table(wl, f"Winners against losers in top-against-top games (both Elo >= {args.top_elo})")]
    (out / "profile_tables.md").write_text("\n".join(text), encoding="utf-8")
    print("\n".join(text)[:3000])


if __name__ == "__main__":
    main()
