import argparse, base64, json, random, shlex, subprocess, sys, time, uuid
from pathlib import Path

WT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WT / "tools"))
from arena_dump import Remote, sync, ssh, parse, BOOT

RUNNER = r'''
import json, os, subprocess, sys, threading, time
bots, j, sandbox, cache = json.loads(sys.stdin.readline())
env = dict(os.environ, PATH=os.path.expanduser("~/.local/bin") + ":" + os.environ.get("PATH", ""), UNSWBC_NO_UPDATE="1")
def cmd(args):
    return ["nice", "-n", "10", "unswbc", "run", *args] + (["--sandbox"] if sandbox else [])
for b in bots:
    subprocess.run(["flock", os.path.expanduser(f"~/bc/cache/{cache[b]}.lock")] + cmd(["maps/arena.map", b, b, "--no-replay", "--seed", "1"]), stdin=subprocess.DEVNULL, capture_output=True, text=True, env=env)
print(json.dumps(["ready"]), flush=True)
lock_in, lock_out = threading.Lock(), threading.Lock()
def worker():
    while True:
        with lock_in:
            line = sys.stdin.readline()
        if not line.strip():
            return
        i, mp, a, b, seed = json.loads(line)
        t0 = time.time()
        r = subprocess.run(cmd([mp, a, b, "--seed", str(seed), "--no-replay", "--no-logs"]), stdin=subprocess.DEVNULL, capture_output=True, text=True, env=env, errors="replace")
        out = r.stdout
        res = next((ln for ln in out.splitlines() if "wins after" in ln or "draw after" in ln), out[-300:] + r.stderr[-300:])
        with lock_out:
            print(json.dumps([i, res, out.count("ran out of time"), round(time.time() - t0, 1), os.getloadavg()[0]]), flush=True)
threads = [threading.Thread(target=worker) for _ in range(j)]
for t in threads:
    t.start()
for t in threads:
    t.join()
'''


def load(path):
    return [json.loads(x) for x in open(path)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cand", required=True)
    ap.add_argument("--base", required=True)
    ap.add_argument("--cname", required=True)
    ap.add_argument("--bname", required=True)
    ap.add_argument("--remote", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--gained", type=int, default=80)
    ap.add_argument("--random", type=int, default=80)
    ap.add_argument("--seed", type=int, default=20261005)
    ap.add_argument("--keys")
    args = ap.parse_args()
    cand, base = load(args.cand), load(args.base)
    key = lambda r: (r["opp"], r["map"], r["seed"], r["side"])
    bmap = {key(r): r for r in base}
    score = {"win": 1.0, "draw": 0.5, "loss": 0.0}
    out = Path(args.out)
    if args.keys:
        picks = [(tuple(k[:4]), k[4]) for k in json.load(open(args.keys))]
    else:
        gained = [key(r) for r in cand if key(r) in bmap and r["res"] in score and bmap[key(r)]["res"] in score and score[r["res"]] > score[bmap[key(r)]["res"]]]
        rng = random.Random(args.seed)
        g = rng.sample(sorted(gained), min(args.gained, len(gained)))
        rest = sorted(set(key(r) for r in cand) - set(g))
        o = rng.sample(rest, args.random)
        picks = [(k, "gained") for k in g] + [(k, "random") for k in o]
    done = {}
    if out.exists():
        for line in open(out):
            v = json.loads(line)
            done[(tuple(v["key"]), v["who"])] = v
    cmap = {key(r): r for r in cand}
    jobs = []
    for k, tag in picks:
        for who, bot, rows in (("cand", args.cname, cmap), ("base", args.bname, bmap)):
            if (k, who) in done:
                continue
            opp, mp, seed, side = k
            a, b = (bot, opp) if side == "A" else (opp, bot)
            jobs.append({"key": list(k), "tag": tag, "who": who, "bot": bot, "a": a, "b": b, "map": f"maps/{mp}.map", "seed": seed,
                         "rec": [rows[k]["res"], rows[k]["rounds"], rows[k]["how"]]})
    print(f"{len(picks)} fixtures, {len(jobs)} games to play", flush=True)
    if not jobs:
        return
    bots = sorted({args.cname, args.bname, *(j["key"][0] for j in jobs)})
    r = Remote(args.remote, 4)
    r.ws = f"bc/runs/{uuid.uuid4().hex[:12]}"
    if not sync(r, r.ws, bots, None, False):
        sys.exit("sync failed")
    header = json.dumps([bots, r.j, True, r.cache])
    proc = subprocess.Popen(r.argv(f"cd {r.ws} && python3 -c {shlex.quote(BOOT)}", mux=False), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, errors="replace", bufsize=1)
    proc.stdin.write(base64.b64encode(RUNNER.encode()).decode() + "\n" + header + "\n")
    proc.stdin.flush()
    nxt = 0
    left = len(jobs)

    def feed():
        nonlocal nxt
        if nxt < len(jobs):
            j = jobs[nxt]
            proc.stdin.write(json.dumps([nxt, j["map"], j["a"], j["b"], j["seed"]]) + "\n")
            proc.stdin.flush()
            nxt += 1
            if nxt == len(jobs):
                proc.stdin.close()

    try:
        for line in proc.stdout:
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            if msg == ["ready"]:
                for _ in range(r.j):
                    feed()
                continue
            i, text, tmo, secs, la = msg
            j = jobs[i]
            winner, rounds, how = parse(text)
            side = j["key"][3]
            res = winner if winner in ("draw", "error") else ("win" if winner == side else "loss")
            v = {"key": j["key"], "tag": j["tag"], "who": j["who"], "res": res, "rounds": rounds, "how": how, "timeouts": tmo,
                 "secs": secs, "load": la, "rec": j["rec"], "same": [res, rounds, how] == j["rec"]}
            with open(out, "a") as f:
                f.write(json.dumps(v) + "\n")
            left -= 1
            if left % 20 == 0:
                print(f"{left} left", flush=True)
            feed()
    finally:
        print(proc.stderr.read()[-800:], flush=True)
        proc.wait()
        ssh(r, f"rm -rf {r.ws}")


if __name__ == "__main__":
    main()
