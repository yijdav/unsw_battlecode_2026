import argparse, io, json, os, re, subprocess, sys, tarfile, threading, uuid
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SSH_OPTS = ["-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "-o", "ControlMaster=auto",
            "-o", f"ControlPath={Path.home()}/.ssh/cm-bc-%C", "-o", "ControlPersist=600"]

RUNNER = r'''
import json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
jobs, bots, j, sandbox = json.loads(sys.argv[1])
env = dict(os.environ, PATH=os.path.expanduser("~/.local/bin") + ":" + os.environ.get("PATH", ""))
def cmd(args):
    return ["nice", "-n", "10", "unswbc", "run", *args] + (["--sandbox"] if sandbox else [])
for b in bots:
    subprocess.run(cmd(["maps/arena.map", b, b, "--no-replay", "--seed", "1"]), capture_output=True, text=True, env=env)
def play(job):
    i, mp, a, b, seed, out = job
    text = subprocess.run(cmd([mp, a, b, "--seed", str(seed), "-o", out, "--no-logs"]), capture_output=True, text=True, env=env).stdout
    return i, text
with ThreadPoolExecutor(j) as pool:
    for i, text in pool.map(play, jobs):
        print(json.dumps([i, text[-2000:]]), flush=True)
'''


def safe(name):
    return name.replace("/", "_")


def replay_path(map_path, a, b, seed):
    return Path("replays") / "arena" / f"{safe(a)}-vs-{safe(b)}-{map_path.parent.name}_{map_path.stem}-{seed}.replay"


def parse(text):
    m = re.search(r"team (A|B) wins after (\d+) rounds \(([^)]*)\)", text)
    if m:
        return m.group(1), int(m.group(2)), m.group(3)
    m = re.search(r"draw after (\d+) rounds", text)
    if m:
        return "draw", int(m.group(1)), "draw"
    return "error", -1, "error"


def play(map_path, a, b, seed, sandbox):
    out = ROOT / replay_path(map_path, a, b, seed)
    cmd = ["unswbc", "run", str(map_path), a, b, "--seed", str(seed), "-o", str(out), "--no-logs"]
    if sandbox:
        cmd.append("--sandbox")
    return parse(subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True).stdout)


def warm(bot, sandbox):
    cmd = ["unswbc", "run", str(ROOT / "maps" / "arena.map"), bot, bot, "--no-replay", "--seed", "1"]
    if sandbox:
        cmd.append("--sandbox")
    subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)


def ssh(host, command, **kw):
    return subprocess.run(["ssh", *SSH_OPTS, host, f"bash -lc {json.dumps(command)}"], **kw)


def sync(host, ws, bots):
    buf = io.BytesIO()
    skip = {".unswbc-build", "replays", "__pycache__", ".git"}
    with tarfile.open(fileobj=buf, mode="w") as tar:
        for top in [*dict.fromkeys(bots), "maps"]:
            src = ROOT / top
            for path in [src, *sorted(src.rglob("*"))]:
                if skip & set(path.relative_to(ROOT).parts):
                    continue
                tar.add(path, arcname=str(path.relative_to(ROOT)), recursive=False)
    r = ssh(host, f"mkdir -p {ws}/replays/arena && tar -x -C {ws}", input=buf.getvalue(), capture_output=True)
    return r.returncode == 0


def fetch(host, ws):
    r = ssh(host, f"cd {ws} && tar -c replays && cd && rm -rf {ws}", capture_output=True)
    if r.returncode == 0 and r.stdout:
        with tarfile.open(fileobj=io.BytesIO(r.stdout)) as tar:
            tar.extractall(ROOT, filter="data")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bot")
    ap.add_argument("opponents", nargs="+")
    ap.add_argument("--maps", nargs="*", default=["maps/ladder", "maps"])
    ap.add_argument("--seeds", type=int, default=1)
    ap.add_argument("-j", type=int, default=8)
    ap.add_argument("--sandbox", action="store_true")
    ap.add_argument("--remote", default=os.environ.get("ARENA_REMOTE"))
    ap.add_argument("--remote-j", type=int, default=int(os.environ.get("ARENA_REMOTE_J", "8")))
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

    bots = list(dict.fromkeys([args.bot, *args.opponents]))
    remote_ids = set()
    ws = None
    if args.remote and args.remote_j > 0:
        ws = f"bc/runs/{uuid.uuid4().hex[:12]}"
        if sync(args.remote, ws, bots):
            share = args.remote_j / (args.remote_j + args.j)
            remote_ids = {i for i in range(len(jobs)) if int((i + 1) * share) > int(i * share)}
        else:
            print(f"remote {args.remote} unreachable, running everything locally", file=sys.stderr)
            ws = None

    results = {}
    lock = threading.Lock()

    def record(i, outcome):
        opp, mp, a, b, seed, side = jobs[i]
        winner, rounds, how = outcome
        res = winner if winner in ("draw", "error") else ("win" if winner == side else "loss")
        with lock:
            results[i] = (opp, f"{mp.parent.name}/{mp.stem}", side, res, rounds, how)

    def run_remote():
        spec = [[i, str(jobs[i][1].relative_to(ROOT)), jobs[i][2], jobs[i][3], jobs[i][4],
                 str(replay_path(jobs[i][1], jobs[i][2], jobs[i][3], jobs[i][4]))] for i in sorted(remote_ids)]
        payload = json.dumps([spec, bots, args.remote_j, args.sandbox])
        remote_cmd = f"cd {ws} && python3 - {json.dumps(payload)}"
        proc = subprocess.Popen(["ssh", *SSH_OPTS, args.remote, f"bash -lc {json.dumps(remote_cmd)}"],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        proc.stdin.write(RUNNER)
        proc.stdin.close()
        for line in proc.stdout:
            try:
                i, text = json.loads(line)
            except ValueError:
                continue
            record(i, parse(text))
        proc.wait()
        fetch(args.remote, ws)

    remote_thread = threading.Thread(target=run_remote) if remote_ids else None
    if remote_thread:
        remote_thread.start()

    for b in bots:
        warm(b, args.sandbox)

    def run_local(i):
        opp, mp, a, b, seed, side = jobs[i]
        record(i, play(mp, a, b, seed, args.sandbox))

    with ThreadPoolExecutor(args.j) as pool:
        list(pool.map(run_local, [i for i in range(len(jobs)) if i not in remote_ids]))
    if remote_thread:
        remote_thread.join()

    tally = defaultdict(lambda: defaultdict(int))
    losses = []
    for i in range(len(jobs)):
        if i not in results:
            results[i] = (jobs[i][0], f"{jobs[i][1].parent.name}/{jobs[i][1].stem}", jobs[i][5], "error", -1, "no result")
        opp, mp, side, res, rounds, how = results[i]
        tally[opp][res] += 1
        if res != "win":
            where = " remote" if i in remote_ids else ""
            losses.append(f"  {res:4s} vs {opp:10s} {mp:28s} as {side}  r{rounds} ({how}){where}")
    for opp, t in tally.items():
        n = t["win"] + t["draw"] + t["loss"]
        err = f"  {t['error']} failed to run" if t["error"] else ""
        print(f"{args.bot} vs {opp}: {t['win']}W {t['draw']}D {t['loss']}L  ({t['win'] / max(n, 1):.0%} wins of {n}){err}")
    if remote_ids:
        print(f"({len(remote_ids)} of {len(jobs)} games ran on {args.remote})")
    print("\n".join(sorted(losses)))


if __name__ == "__main__":
    sys.exit(main())
