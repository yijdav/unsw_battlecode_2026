import argparse, base64, io, json, os, re, shlex, subprocess, sys, tarfile, threading, uuid
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SSH_BASE = ["-o", "BatchMode=yes", "-o", "ConnectTimeout=10"]
SSH_MUX = ["-o", "ControlMaster=auto", "-o", f"ControlPath={Path.home()}/.ssh/cm-bc-%C", "-o", "ControlPersist=600"]
SSH_OPTS = SSH_BASE + SSH_MUX

RUNNER = r'''
import json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
jobs, bots, j, sandbox = json.loads(PAYLOAD)
env = dict(os.environ, PATH=os.path.expanduser("~/.local/bin") + ":" + os.environ.get("PATH", ""))
def cmd(args):
    return ["nice", "-n", "10", "unswbc", "run", *args] + (["--sandbox"] if sandbox else [])
for b in bots:
    subprocess.run(cmd(["maps/arena.map", b, b, "--no-replay", "--seed", "1"]), capture_output=True, text=True, env=env)
def play(job):
    i, mp, a, b, seed, out = job
    r = subprocess.run(cmd([mp, a, b, "--seed", str(seed), "-o", out, "--no-logs"]), capture_output=True, text=True, env=env, errors="replace")
    return i, r.stdout[-1500:] + ("" if "wins after" in r.stdout or "draw after" in r.stdout else "\nSTDERR " + r.stderr[-800:])
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


class Remote:
    def __init__(self, spec, default_j):
        self.wsl = spec.startswith("wsl:")
        spec = spec[4:] if self.wsl else spec
        self.j = default_j
        m = re.match(r"^(.*):(\d+)$", spec)
        if m:
            spec, self.j = m.group(1), int(m.group(2))
        self.user, _, self.host = spec.rpartition("@")
        self.name = spec
        self.mux = not self.wsl
        self.reported = False

    def argv(self, command, mux=None):
        b64 = base64.b64encode(command.encode()).decode()
        remote = f"wsl --exec /usr/local/bin/bcrun {b64}" if self.wsl else f'bash -lc "$(echo {b64} | base64 -d)"'
        login = ["-l", self.user] if self.user else []
        opts = SSH_BASE + (SSH_MUX if (self.mux if mux is None else mux) else [])
        return ["ssh", *opts, *login, self.host, remote]


def ssh(host, command, **kw):
    kw.setdefault("capture_output", True)
    if kw.get("text"):
        kw.setdefault("errors", "replace")
    r = subprocess.run(host.argv(command), **kw)
    if r.returncode == 255 and host.mux:
        r = subprocess.run(host.argv(command, mux=False), **kw)
    return r


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
    r = ssh(host, f"mkdir -p {ws}/replays/arena && tar -x -C {ws}", input=buf.getvalue())
    return r.returncode == 0


def fetch(host, ws):
    r = ssh(host, f"cd {ws} && tar -c replays && cd && rm -rf {ws}")
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
    ap.add_argument("--remote", default=os.environ.get("ARENA_REMOTE"), help="comma-separated [wsl:]user@host[:jobs]")
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
    remotes = []
    for spec in filter(None, (args.remote or "").split(",")):
        r = Remote(spec.strip(), args.remote_j)
        if r.j <= 0:
            continue
        r.ws = f"bc/runs/{uuid.uuid4().hex[:12]}"
        if sync(r, r.ws, bots):
            remotes.append(r)
        else:
            print(f"remote {r.name} unreachable, skipping it", file=sys.stderr)
    workers = [None, *remotes]
    weights = [args.j, *[r.j for r in remotes]]
    credit = [0.0] * len(workers)
    owner = {}
    for i in range(len(jobs)):
        for k, w in enumerate(weights):
            credit[k] += w
        k = max(range(len(workers)), key=lambda k: credit[k])
        credit[k] -= sum(weights)
        owner[i] = workers[k]
    remote_ids = {i for i, w in owner.items() if w is not None}

    results = {}
    lock = threading.Lock()

    def record(i, outcome):
        opp, mp, a, b, seed, side = jobs[i]
        winner, rounds, how = outcome
        res = winner if winner in ("draw", "error") else ("win" if winner == side else "loss")
        with lock:
            results[i] = (opp, f"{mp.parent.name}/{mp.stem}", side, res, rounds, how)

    def run_remote(r):
        spec = [[i, str(jobs[i][1].relative_to(ROOT)), jobs[i][2], jobs[i][3], jobs[i][4],
                 str(replay_path(jobs[i][1], jobs[i][2], jobs[i][3], jobs[i][4]))] for i in sorted(remote_ids) if owner[i] is r]
        payload = json.dumps([spec, bots, r.j, args.sandbox])
        command = f"cd {r.ws} && python3 -"
        for mux in ([True, False] if r.mux else [False]):
            got = 0
            proc = subprocess.Popen(r.argv(command, mux=mux), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, text=True, errors="replace")
            proc.stdin.write(f"PAYLOAD = {payload!r}\n" + RUNNER)
            proc.stdin.close()
            for line in proc.stdout:
                try:
                    i, text = json.loads(line)
                except ValueError:
                    continue
                outcome = parse(text)
                if outcome[0] == "error" and not r.reported:
                    r.reported = True
                    print(f"{r.host}: a game failed: {text.strip()[-600:]}", file=sys.stderr)
                record(i, outcome)
                got += 1
            err = proc.stderr.read()
            proc.wait()
            if got:
                break
            print(f"{r.host}: no results (exit {proc.returncode}): {err.strip()[-600:]}", file=sys.stderr)
            if proc.returncode != 255:
                break
        fetch(r, r.ws)

    threads = [threading.Thread(target=run_remote, args=(r,)) for r in remotes]
    for t in threads:
        t.start()

    for b in bots:
        warm(b, args.sandbox)

    def run_local(i):
        opp, mp, a, b, seed, side = jobs[i]
        record(i, play(mp, a, b, seed, args.sandbox))

    with ThreadPoolExecutor(max(args.j, 1)) as pool:
        list(pool.map(run_local, [i for i in range(len(jobs)) if i not in remote_ids]))
    for t in threads:
        t.join()

    tally = defaultdict(lambda: defaultdict(int))
    losses = []
    for i in range(len(jobs)):
        if i not in results:
            results[i] = (jobs[i][0], f"{jobs[i][1].parent.name}/{jobs[i][1].stem}", jobs[i][5], "error", -1, "no result")
        opp, mp, side, res, rounds, how = results[i]
        tally[opp][res] += 1
        if res != "win":
            where = f" on {owner[i].host}" if owner[i] is not None else ""
            losses.append(f"  {res:4s} vs {opp:10s} {mp:28s} as {side}  r{rounds} ({how}){where}")
    for opp, t in tally.items():
        n = t["win"] + t["draw"] + t["loss"]
        err = f"  {t['error']} failed to run" if t["error"] else ""
        print(f"{args.bot} vs {opp}: {t['win']}W {t['draw']}D {t['loss']}L  ({t['win'] / max(n, 1):.0%} wins of {n}){err}")
    for r in remotes:
        print(f"({sum(1 for w in owner.values() if w is r)} of {len(jobs)} games ran on {r.host})")
    print("\n".join(sorted(losses)))


if __name__ == "__main__":
    sys.exit(main())
