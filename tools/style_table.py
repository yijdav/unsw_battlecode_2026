import argparse, json, os
from collections import defaultdict
from statistics import median

CUT = 306
US = int(os.environ.get("BC_TEAM_ID", "0"))


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def med(xs):
    xs = [x for x in xs if x is not None]
    return median(xs) if xs else None


def snap(r, k, key):
    s = r["snap"].get(str(k)) or r["snap"].get(k)
    return s.get(key) if s else None


def metrics(rows):
    out = {"n": len(rows), "win": mean([float(r["win"]) for r in rows])}
    for k in (50, 100, 200):
        out[f"count r{k}"] = mean([snap(r, k, "count") for r in rows])
    for k in (100, 200, 300):
        out[f"total r{k}"] = mean([snap(r, k, "total") for r in rows])
    for k in (200, 300, 450):
        out[f"longest r{k}"] = mean([snap(r, k, "longest") for r in rows])
    out["champ share r300"] = mean([snap(r, 300, "champ_share") for r in rows])
    out["champ share r450"] = mean([snap(r, 450, "champ_share") for r in rows])
    out["second r450"] = mean([snap(r, 450, "second") for r in rows])
    out["dragons>=10 r200"] = mean([snap(r, 200, "ge10") for r in rows])
    out["pearls r<100"] = mean([r["eaten_r100"] for r in rows])
    out["pearls total"] = mean([r["eaten"] for r in rows])
    out["enemy corpse %"] = mean([r["eaten_enemy_corpse"] / r["eaten"] if r["eaten"] else None for r in rows])
    out["own corpse %"] = mean([r["eaten_own_corpse"] / r["eaten"] if r["eaten"] else None for r in rows])
    for i, ph in enumerate(("early", "mid", "late")):
        out[f"sprint % {ph}"] = mean([r["sprints"][i] / r["moves"][i] if r["moves"][i] else None for r in rows])
    out["sprint len"] = mean([sum(r["sprint_steps"]) / sum(r["sprints"]) if sum(r["sprints"]) else None for r in rows])
    out["splits"] = mean([len(r["split_round"]) for r in rows])
    out["first split"] = mean([min(r["split_round"]) if r["split_round"] else None for r in rows])
    out["split at len (med)"] = med([x for r in rows for x in r["split_len"]])
    out["child len (med)"] = med([x for r in rows for x in r["split_child"]])
    for i, ph in enumerate(("early", "mid", "late")):
        out[f"head kills {ph}"] = mean([r["kills_head"][i] for r in rows])
    out["body kills"] = mean([sum(r["kills_body"]) for r in rows])
    out["kill victim len"] = mean([x for r in rows for x in r["kill_len"]])
    out["head trade: own len"] = mean([x for r in rows for x in r["trade_len"]])
    out["split strikes"] = mean([len(r["strikes"]) for r in rows])
    out["strike victim len"] = mean([s["victim"] for r in rows for s in r["strikes"]])
    out["strike striker len"] = mean([s["striker"] for r in rows for s in r["strikes"]])
    out["big strikes (victim>=8)"] = mean([sum(1 for s in r["strikes"] if s["victim"] >= 8) for r in rows])
    out["head losses"] = mean([r["deaths"].get("head", 0) for r in rows])
    out["body deaths"] = mean([r["deaths"].get("body", 0) for r in rows])
    out["novalid deaths"] = mean([r["deaths"].get("novalid", 0) for r in rows])
    out["novalid next to friend %"] = mean([r["novalid_near_friend"] / r["deaths"]["novalid"] if r["deaths"].get("novalid") else None for r in rows])
    out["own collisions"] = mean([r["own_coll"] for r in rows])
    out["crossings"] = mean([r["crossings"] for r in rows])
    for k in (50, 200, 400):
        out[f"head gap r{k}"] = mean([(r["head_gap"].get(str(k)) or r["head_gap"].get(k)) for r in rows])
    for k in (200, 400):
        out[f"king gap r{k}"] = mean([(r.get("king_gap", {}).get(str(k)) or r.get("king_gap", {}).get(k)) for r in rows])
    for a, b in ((0, 2), (2, 4), (4, 6), (6, 8), (8, 10)):
        out[f"novalid r{a * 50}-{b * 50}"] = mean([sum(r["novalid_at"][a:b]) if "novalid_at" in r else None for r in rows])
    out["final longest"] = mean([(r["final"] or {}).get("longest") for r in rows])
    out["final count"] = mean([(r["final"] or {}).get("count") for r in rows])
    return out


def fmt(v):
    if v is None:
        return "-"
    if isinstance(v, int):
        return str(v)
    return f"{v:.2f}" if abs(v) < 1 else f"{v:.1f}"


def table(groups, order, title):
    cols = [g for g in order if groups.get(g)]
    m = {g: metrics(groups[g]) for g in cols}
    keys = list(next(iter(m.values())).keys())
    lines = [f"## {title}", "", "| metric | " + " | ".join(cols) + " |", "|---|" + "---|" * len(cols)]
    for k in keys:
        lines.append(f"| {k} | " + " | ".join(fmt(m[g][k]) for g in cols) + " |")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", required=True)
    ap.add_argument("--cut", nargs="+", required=True)
    ap.add_argument("--new-from", default="2026-10-02T02:00")
    ap.add_argument("--out", required=True)
    ap.add_argument("--top-elo", type=int, default=1880)
    args = ap.parse_args()
    rows, seen = [], set()
    for f in [args.top, *args.cut]:
        for line in open(f, encoding="utf-8"):
            r = json.loads(line)
            if (r["game"], r["team"]) in seen:
                continue
            seen.add((r["game"], r["team"]))
            rows.append(r)
    g = defaultdict(list)
    per_map = defaultdict(lambda: defaultdict(list))
    for r in rows:
        if r["team"] == CUT:
            key = "Cutlery new" if r["at"] >= args.new_from else "Cutlery old"
        elif r["opp"] == CUT and r["at"] >= args.new_from:
            key = "vs Cutlery new"
        elif r["team"] == US:
            key = "us (bot)"
        elif (r["elo"] or 0) >= args.top_elo and r["opp"] != CUT:
            key = "other top"
        else:
            continue
        g[key].append(r)
        per_map[r["map"]][key].append(r)
    order = ["Cutlery new", "Cutlery old", "vs Cutlery new", "other top", "us (bot)"]
    text = [f"# Cutlery play style (new build = games from {args.new_from}Z)", "",
            "Counts are per team per game; % are fractions. Head kills: enemy died head-on against this team's head. "
            "Split strike: a kill by a dragon split off at most 3 rounds earlier.", "",
            table(g, order, "All maps")]
    for mp in sorted(per_map):
        text.append(table(per_map[mp], order, mp))
    open(args.out, "w", encoding="utf-8").write("\n".join(text))
    print("\n".join(text)[:12000])


if __name__ == "__main__":
    main()
