import argparse, base64, gzip, json, os, queue, shlex, subprocess, sys, tempfile, threading, time, uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools" / "replay"))
from arena_dump import BOOT, Remote, cpu_of, how_kind, parse, ssh, sync, warm
from decode import decode

RUNNER = r'''
import base64, gzip, json, os, resource, shutil, subprocess, sys, threading
try:
    os.setpgrp()
except OSError:
    pass
open("runner.pgid", "w").write(str(os.getpgrp()))
bots, j, sandbox, cache = json.loads(sys.stdin.readline())
_s, _h = resource.getrlimit(resource.RLIMIT_NOFILE)
for _n in (65536, 32768, 16384, 10240, 4096):
    try:
        resource.setrlimit(resource.RLIMIT_NOFILE, (_n if _h == resource.RLIM_INFINITY else min(_n, _h), _h))
        break
    except (ValueError, OSError):
        pass
env = dict(os.environ, PATH=os.path.expanduser("~/.local/bin") + ":" + os.environ.get("PATH", ""), UNSWBC_NO_UPDATE="1")
def cmd(args):
    return ["nice", "-n", "10", "unswbc", "run", *args] + (["--sandbox"] if sandbox else [])
for b in bots:
    lock = ["flock", os.path.expanduser(f"~/bc/cache/{cache[b]}.lock")] if b in cache and shutil.which("flock") else []
    subprocess.run(lock + cmd(["maps/arena.map", b, b, "--no-replay", "--seed", "1"]), stdin=subprocess.DEVNULL, capture_output=True, text=True, env=env)
print(json.dumps(["ready"]), flush=True)
lock_in, lock_out = threading.Lock(), threading.Lock()
def worker():
    while True:
        with lock_in:
            line = sys.stdin.readline()
        if not line.strip():
            return
        i, mp, a, b, seed, out = json.loads(line)
        r = subprocess.run(cmd([mp, a, b, "--seed", str(seed), "-o", out, "--no-logs"]), stdin=subprocess.DEVNULL, capture_output=True, text=True, env=env, errors="replace")
        text = r.stdout[-1500:] + ("" if "wins after" in r.stdout or "draw after" in r.stdout else "\nSTDERR " + r.stderr[-800:])
        blob = None
        if os.path.exists(out):
            with open(out, "rb") as f:
                blob = base64.b64encode(gzip.compress(f.read(), 1)).decode()
            os.remove(out)
        info = {"timeouts": r.stdout.count("ran out of time"), "load": os.getloadavg()[0]}
        with lock_out:
            print(json.dumps([i, text[-2000:], info, blob]), flush=True)
threads = [threading.Thread(target=worker) for _ in range(j)]
for t in threads:
    t.start()
for t in threads:
    t.join()
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixtures", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("-j", type=int, default=1)
    ap.add_argument("--remote", default="")
    ap.add_argument("--decode-j", type=int, default=2)
    ap.add_argument("--no-decode", action="store_true")
    args = ap.parse_args()
    jobs = [json.loads(x) for x in open(args.fixtures) if x.strip()]
    key = lambda f: (f["bot"], f["opp"], f["map"], f["seed"], f["side"])
    out = Path(args.out)
    done = set()
    if out.exists():
        for line in open(out):
            try:
                done.add(key(json.loads(line)))
            except (ValueError, KeyError):
                pass
    pending = queue.Queue()
    for i, f in enumerate(jobs):
        if key(f) not in done:
            pending.put(i)
    total = pending.qsize()
    print(f"{total} of {len(jobs)} fixtures to play", file=sys.stderr, flush=True)
    if not total:
        return
    bots = list(dict.fromkeys([f["bot"] for f in jobs] + [f["opp"] for f in jobs]))
    maps = sorted({ROOT / "maps" / (f["map"] + ".map") for f in jobs})
    lock = threading.Lock()
    tmp = Path(tempfile.mkdtemp(prefix="fx-"))
    pool = ThreadPoolExecutor(max(1, args.decode_j))
    counter = [0]
    futures = []

    def finish(i, text, info, replay, where):
        f = jobs[i]
        winner, rounds, how = parse(text)
        res = winner if winner in ("draw", "error") else ("win" if winner == f["side"] else "loss")
        cpu = cpu_of(text)
        c = cpu.get(f["side"])
        row = dict(f, res=res, rounds=rounds, how=how, decided_by=how_kind(how), cpu_peak=c[0] if c else None, host=where, **info)
        if replay is not None and replay.exists():
            if not args.no_decode:
                try:
                    d = decode(str(replay))
                    other = "B" if f["side"] == "A" else "A"
                    row.update(ours=d[f["side"]], theirs=d[other], rounds_played=d["rounds"], replay_decided_by=d.get("decided_by"))
                except Exception as e:
                    row["decode_error"] = str(e)
            replay.unlink(missing_ok=True)
        with lock:
            with open(out, "a") as fh:
                fh.write(json.dumps(row) + "\n")
            counter[0] += 1
            if counter[0] % 10 == 0 or counter[0] == total:
                print(f"{time.strftime('%H:%M:%S')} {counter[0]} of {total} done", file=sys.stderr, flush=True)

    def sides(f):
        return (f["bot"], f["opp"]) if f["side"] == "A" else (f["opp"], f["bot"])

    remotes = []
    for spec in filter(None, args.remote.split(",")):
        r = Remote(spec.strip(), 1)
        if r.j <= 0:
            continue
        r.ws = f"bc/runs/{uuid.uuid4().hex[:12]}"
        if sync(r, r.ws, bots, maps, False):
            remotes.append(r)
        else:
            print(f"remote {r.name} unreachable, skipping it", file=sys.stderr)

    def run_remote(r):
        header = json.dumps([bots, r.j, True, r.cache])
        command = f"cd {r.ws} && python3 -c {shlex.quote(BOOT)}"
        for attempt in range(3):
            assigned = set()
            got = 0
            proc = subprocess.Popen(r.argv(command, mux=False), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, text=True, errors="replace", bufsize=1)
            r.proc = proc
            closed = False

            def feed():
                nonlocal closed
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
                a, b = sides(jobs[i])
                line = json.dumps([i, "maps/" + jobs[i]["map"] + ".map", a, b, jobs[i]["seed"], f"replays/arena/fx{i}.replay"])
                try:
                    proc.stdin.write(line + "\n")
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
                i, text, info, blob = msg
                if i not in assigned:
                    continue
                assigned.discard(i)
                replay = None
                if blob:
                    replay = tmp / f"fx{i}.replay"
                    replay.write_bytes(gzip.decompress(base64.b64decode(blob)))
                futures.append(pool.submit(finish, i, text, info, replay, r.host))
                got += 1
                feed()
            err = proc.stderr.read()
            proc.wait()
            for i in assigned:
                pending.put(i)
            if not assigned and pending.empty():
                break
            print(f"{r.host}: runner ended (exit {proc.returncode}, {got} games): {err.strip()[-600:]}", file=sys.stderr)
            if got == 0 and attempt:
                break
        ssh(r, f"cd {r.ws} && kill -- -$(cat runner.pgid) 2>/dev/null; cd && rm -rf {r.ws}")

    threads = [threading.Thread(target=run_remote, args=(r,)) for r in remotes]
    for t in threads:
        t.start()
    if args.j > 0:
        for b in bots:
            warm(b, True)

    def local_worker():
        while True:
            try:
                i = pending.get(timeout=0.5)
            except queue.Empty:
                if pending.empty() and not any(t.is_alive() for t in threads):
                    return
                continue
            f = jobs[i]
            a, b = sides(f)
            replay = tmp / f"fx{i}.replay"
            r = subprocess.run(["unswbc", "run", str(ROOT / "maps" / (f["map"] + ".map")), a, b, "--seed", str(f["seed"]), "-o", str(replay),
                                "--no-logs", "--sandbox"], cwd=ROOT, capture_output=True, text=True, errors="replace",
                               env=dict(os.environ, UNSWBC_NO_UPDATE="1"))
            info = {"timeouts": r.stdout.count("ran out of time"), "load": os.getloadavg()[0]}
            futures.append(pool.submit(finish, i, r.stdout[-2000:], info, replay, "local"))

    local = [threading.Thread(target=local_worker) for _ in range(args.j)]
    for t in local:
        t.start()
    for t in threads + local:
        t.join()
    pool.shutdown(wait=True)
    for fu in futures:
        fu.result()
    left = pending.qsize()
    print(f"finished; {left} fixtures not played" if left else "finished", file=sys.stderr)


if __name__ == "__main__":
    main()
