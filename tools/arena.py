import argparse, base64, io, json, math, os, queue, re, shlex, subprocess, sys, tarfile, threading, time, uuid
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SSH_BASE = ["-o", "BatchMode=yes", "-o", "ConnectTimeout=10"]
SSH_MUX = ["-o", "ControlMaster=auto", "-o", f"ControlPath={Path.home()}/.ssh/cm-bc-%C", "-o", "ControlPersist=600"]
SSH_OPTS = SSH_BASE + SSH_MUX

RUNNER = r'''
import json, os, subprocess, sys, threading
bots, j, sandbox = json.loads(sys.stdin.readline())
env = dict(os.environ, PATH=os.path.expanduser("~/.local/bin") + ":" + os.environ.get("PATH", ""))
def cmd(args):
    return ["nice", "-n", "10", "unswbc", "run", *args] + (["--sandbox"] if sandbox else [])
for b in bots:
    subprocess.run(cmd(["maps/arena.map", b, b, "--no-replay", "--seed", "1"]), capture_output=True, text=True, env=env)
print(json.dumps(["ready"]), flush=True)
lock_in, lock_out = threading.Lock(), threading.Lock()
def worker():
    while True:
        with lock_in:
            line = sys.stdin.readline()
        if not line.strip():
            return
        i, mp, a, b, seed, out = json.loads(line)
        r = subprocess.run(cmd([mp, a, b, "--seed", str(seed), "-o", out, "--no-logs"]), capture_output=True, text=True, env=env, errors="replace")
        text = r.stdout[-1500:] + ("" if "wins after" in r.stdout or "draw after" in r.stdout else "\nSTDERR " + r.stderr[-800:])
        with lock_out:
            print(json.dumps([i, text[-2000:]]), flush=True)
threads = [threading.Thread(target=worker) for _ in range(j)]
for t in threads:
    t.start()
for t in threads:
    t.join()
'''
BOOT = "import sys,base64;exec(base64.b64decode(sys.stdin.readline()))"


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
    ap.add_argument("--baseline", help="also play this bot on the same fixtures and report paired flips")
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

    mine = [args.bot, *([args.baseline] if args.baseline else [])]
    jobs = []
    for me in mine:
        for opp in args.opponents:
            for mp in maps:
                for seed in range(1, args.seeds + 1):
                    jobs.append((me, opp, mp, me, opp, seed, "A"))
                    jobs.append((me, opp, mp, opp, me, seed, "B"))

    bots = list(dict.fromkeys([*mine, *args.opponents]))
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
    results = {}
    owner = {}
    lock = threading.Lock()
    pending = queue.Queue()
    for i in range(len(jobs)):
        pending.put(i)

    def record(i, outcome, where):
        me, opp, mp, a, b, seed, side = jobs[i]
        winner, rounds, how = outcome
        res = winner if winner in ("draw", "error") else ("win" if winner == side else "loss")
        with lock:
            results[i] = (me, opp, f"{mp.parent.name}/{mp.stem}", side, res, rounds, how, seed)
            owner[i] = where

    def job_line(i):
        me, opp, mp, a, b, seed, side = jobs[i]
        return json.dumps([i, str(mp.relative_to(ROOT)), a, b, seed, str(replay_path(mp, a, b, seed))]) + "\n"

    def run_remote(r):
        header = json.dumps([bots, r.j, args.sandbox])
        command = f"cd {r.ws} && python3 -c {shlex.quote(BOOT)}"
        for mux in ([True, False] if r.mux else [False]):
            got = 0
            given = 0
            assigned = set()
            proc = subprocess.Popen(r.argv(command, mux=mux), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, text=True, errors="replace", bufsize=1)
            closed = False

            def feed():
                nonlocal closed, given
                if closed:
                    return
                try:
                    i = pending.get_nowait()
                except queue.Empty:
                    if not assigned:
                        closed = True
                        try:
                            proc.stdin.close()
                        except OSError:
                            pass
                    return
                assigned.add(i)
                given += 1
                try:
                    proc.stdin.write(job_line(i))
                    proc.stdin.flush()
                except OSError:
                    pass

            try:
                proc.stdin.write(base64.b64encode(RUNNER.encode()).decode() + "\n" + header + "\n")
                proc.stdin.flush()
            except OSError:
                pass
            for line in proc.stdout:
                try:
                    msg = json.loads(line)
                except ValueError:
                    continue
                if msg == ["ready"]:
                    for _ in range(r.j):
                        feed()
                    continue
                i, text = msg
                if i not in assigned:
                    continue
                assigned.discard(i)
                outcome = parse(text)
                if outcome[0] == "error" and not r.reported:
                    r.reported = True
                    print(f"{r.host}: a game failed: {text.strip()[-600:]}", file=sys.stderr)
                record(i, outcome, r)
                got += 1
                feed()
            err = proc.stderr.read()
            proc.wait()
            for i in assigned:
                pending.put(i)
            if got or (given == 0 and proc.returncode == 0):
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

    def local_worker():
        while True:
            try:
                i = pending.get(timeout=0.5)
            except queue.Empty:
                with lock:
                    finished = len(results) >= len(jobs)
                if finished or not any(t.is_alive() for t in threads):
                    if pending.empty():
                        return
                continue
            me, opp, mp, a, b, seed, side = jobs[i]
            record(i, play(mp, a, b, seed, args.sandbox), None)

    local = [threading.Thread(target=local_worker) for _ in range(args.j)]
    for t in local:
        t.start()
    for t in threads:
        t.join()
    for t in local:
        t.join()
    while not pending.empty():
        i = pending.get()
        me, opp, mp, a, b, seed, side = jobs[i]
        record(i, play(mp, a, b, seed, args.sandbox), None)

    tally = defaultdict(lambda: defaultdict(int))
    losses = []
    for i in range(len(jobs)):
        if i not in results:
            me, opp, mp, a, b, seed, side = jobs[i]
            results[i] = (me, opp, f"{mp.parent.name}/{mp.stem}", side, "error", -1, "no result", seed)
        me, opp, mp, side, res, rounds, how, seed = results[i]
        tally[(me, opp)][res] += 1
        if res != "win":
            where = f" on {owner[i].host}" if owner.get(i) is not None else ""
            who = f"{me} " if args.baseline else ""
            losses.append(f"  {who}{res:4s} vs {opp:10s} {mp:28s} as {side}  r{rounds} ({how}){where}")
    for (me, opp), t in tally.items():
        n = t["win"] + t["draw"] + t["loss"]
        err = f"  {t['error']} failed to run" if t["error"] else ""
        print(f"{me} vs {opp}: {t['win']}W {t['draw']}D {t['loss']}L  ({t['win'] / max(n, 1):.0%} wins of {n}){err}")
    if args.baseline:
        score = {"win": 1.0, "draw": 0.5, "loss": 0.0}
        fixtures = defaultdict(dict)
        for me, opp, mp, side, res, rounds, how, seed in results.values():
            fixtures[(opp, mp, seed, side)][me] = res
        for opp in args.opponents:
            gained = lost = same = skipped = 0
            for (o, mp, seed, side), r in fixtures.items():
                if o != opp:
                    continue
                c, b = r.get(args.bot, "error"), r.get(args.baseline, "error")
                if "error" in (c, b):
                    skipped += 1
                elif score[c] > score[b]:
                    gained += 1
                elif score[c] < score[b]:
                    lost += 1
                else:
                    same += 1
            n = gained + lost
            k = min(gained, lost)
            p = min(1.0, 2 * sum(math.comb(n, x) for x in range(k + 1)) / 2 ** n) if n else 1.0
            print(f"paired vs {opp}: {args.bot} gained {gained}, lost {lost}, same {same}"
                  f"{f', skipped {skipped}' if skipped else ''}  (sign test p={p:.3g})")
    for r in remotes:
        print(f"({sum(1 for w in owner.values() if w is r)} of {len(jobs)} games ran on {r.host})")
    print("\n".join(sorted(losses)))


if __name__ == "__main__":
    sys.exit(main())
