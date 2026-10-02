import argparse, json, os, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://game.battlecode.au"
API = SITE + "/api/v1/"
MAPS = {"Schooltime": 9, "Portals": 20, "Slithery Fight": 21, "Queen Of Spades": 7, "Default": 4, "Trophy": 11,
        "Prisoners Dilemma": 17, "Autarky": 19, "Devil": 13, "Trauma": 15}
last = [0.0]


def fetch(url, auth=False, raw=False):
    wait = 1.2 - (time.time() - last[0])
    if wait > 0:
        time.sleep(wait)
    headers = {"User-Agent": "Mozilla/5.0"}
    if auth:
        headers["Authorization"] = "Bearer " + os.environ["BC_API_KEY"]
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as r:
                last[0] = time.time()
                body = r.read()
                return body if raw else json.loads(body)
        except urllib.error.HTTPError as e:
            last[0] = time.time()
            if e.code == 429:
                time.sleep(int(e.headers.get("Retry-After", "30")))
                continue
            if e.code == 404:
                return None
            raise
        except OSError:
            last[0] = time.time()
            time.sleep(5)
    return None


def devalue(arr, i=0):
    v = arr[i]
    if isinstance(v, dict):
        return {k: devalue(arr, j) if isinstance(j, int) and j >= 0 else j for k, j in v.items()}
    if isinstance(v, list):
        return [devalue(arr, j) if isinstance(j, int) and j >= 0 else j for j in v]
    return v


def games(team, map_id, page=1):
    d = fetch(f"{SITE}/games/__data.json?teams={team}&maps={map_id}&page={page}")
    if not d:
        return []
    node = [n for n in d["nodes"] if n and n.get("type") == "data"][-1]
    return devalue(node["data"])["matches"]


def leaderboard():
    if os.environ.get("BC_API_KEY"):
        return fetch(API + "leaderboard", auth=True)
    board, page, pages = [], 1, 1
    while page <= pages:
        d = fetch(f"{SITE}/leaderboard/__data.json?page={page}")
        v = devalue([n for n in d["nodes"] if n and n.get("type") == "data"][-1]["data"])
        board += v["teams"]
        pages = v["pages"]
        page += 1
    return board


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--teams", nargs="*", type=int, default=[])
    ap.add_argument("--per-map", type=int, default=4)
    ap.add_argument("--pages", type=int, default=1)
    ap.add_argument("--unranked", action="store_true", help="also keep unranked and challenge games")
    ap.add_argument("--since", default="2026-10-01T00:00:00")
    ap.add_argument("--out", default=str(ROOT / "notes" / "2026-10-02-research" / "manifest.jsonl"))
    ap.add_argument("--replays", default=str(ROOT / "replays" / "ladder"))
    args = ap.parse_args()
    board = leaderboard()
    elo = {t["id"]: t["elo"] for t in board}
    names = {t["id"]: t["name"] for t in board}
    teams = [t["id"] for t in board[:args.top]] + [t for t in args.teams if t not in [x["id"] for x in board[:args.top]]]
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    have = set()
    if out.exists():
        have = {json.loads(line)["id"] for line in open(out, encoding="utf-8")}
    rdir = Path(args.replays)
    rdir.mkdir(parents=True, exist_ok=True)
    for team in teams:
        got_team = 0
        for name, mid in MAPS.items():
            kept = 0
            for m in (m for page in range(1, args.pages + 1) for m in games(team, mid, page)):
                at = m["at"][1] if isinstance(m["at"], list) else m["at"]
                if kept >= args.per_map or at < args.since:
                    break
                if not (m["status"] == "completed" and m["hasReplay"]) or m["tournament"]:
                    continue
                if not args.unranked and (not m["ranked"] or m["challenge"]):
                    continue
                kept += 1
                if m["id"] in have:
                    continue
                path = rdir / f"{m['id']}.replay.gz"
                if not path.exists():
                    blob = fetch(f"{SITE}/api/matches/{m['id']}/replay", raw=True)
                    if not blob:
                        continue
                    path.write_bytes(blob)
                row = {"id": m["id"], "at": at, "map": m["mapName"], "winner": m["winner"], "focus": team, "ranked": m["ranked"] and not m["challenge"],
                       "a": dict(m["a"], elo_now=elo.get(m["a"]["id"])), "b": dict(m["b"], elo_now=elo.get(m["b"]["id"]))}
                with open(out, "a", encoding="utf-8") as f:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
                have.add(m["id"])
                got_team += 1
        print(f"team {team} {names.get(team, '?')} (elo {elo.get(team)}): {got_team} new games", flush=True)


if __name__ == "__main__":
    main()
