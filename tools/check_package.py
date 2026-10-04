#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fnmatch
import gzip
import hashlib
import io
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time
import tomllib
import zipfile
from concurrent.futures import ThreadPoolExecutor

HERE = pathlib.Path(__file__).resolve().parent
DEFAULT_BOT = HERE.parent / "bot"
DEFAULT_REPO = HERE.parent
TOOLKIT = "unswbc==1.2.9"
JUDGE_VERSION = "1.2.9"
HELPER_SHA = "ca57d2398f309144ce98f6c899d28847672cd9914ff8be03afdbb0379e7365b7"
MAX_ZIP_BYTES = 4 * 1024 * 1024
TURN_POINTS = 100_000_000
MEMORY_BYTES = 768 * 65536
MAPS = ["maps/ladder/default.map", "maps/big_empty.map", "maps/ladder/slithery_fight.map", "maps/ladder/australia.map",
        "maps/ladder/unsw.map"]
MAX_PARALLEL_GAMES = 3
BUILD_DIR_NAME = ".unswbc-build"
LANGUAGES = {"py": "python", "python": "python", "cpp": "cpp", "c++": "cpp", "cxx": "cpp", "c": "c"}
JUDGE_UNITS = (".c", ".cc", ".cpp", ".cxx", ".c++")
TEXT_SUFFIXES = JUDGE_UNITS + (".h", ".hh", ".hpp", ".hxx", ".inc", ".ipp", ".tpp")
FORM_LANGUAGE = {"cpp": "C++", "c": "C", "python": "Python"}
UNWANTED_NAME = re.compile(r"(\.bak|\.orig|\.rej|\.swp|\.tmp|~$|\bcopy\b|backup|\bold\b|_old|\.old|scratch)", re.I)
UNWANTED_SUFFIX = {".bak", ".orig", ".rej", ".swp", ".tmp", ".log", ".replay", ".zip", ".o", ".obj", ".a",
                   ".wasm", ".cwasm", ".exe", ".pyc", ".gz", ".out", ".dSYM"}

INNER = r'''
import hashlib, json, pathlib, shutil, sys, tempfile
import unswbc
from unswbc import clangtool
from unswbc.project import Project

def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()

def emit(obj):
    print("@@JSON@@" + json.dumps(obj), flush=True)

mode = sys.argv[1]
pkg = pathlib.Path(unswbc.__file__).resolve().parent
if mode == "info":
    t = pkg / "templates"
    emit({"version": unswbc.__version__, "package": str(pkg),
          "engine_sha": sha(pkg / "unswbc_engine.wasm"), "engine_size": (pkg / "unswbc_engine.wasm").stat().st_size,
          "helper_hpp_sha": sha(t / "cpp" / "helper.hpp"), "helper_hpp_path": str(t / "cpp" / "helper.hpp"),
          "driver_flags": clangtool.DRIVER_FLAGS, "link_flags": clangtool.LINK_FLAGS})
elif mode == "collect":
    p = Project.from_dir(sys.argv[2])
    p.collect_sources()
    emit({"language": p.language, "includes": p.includes, "output_dir": str(p.output_dir), "sources": p.sources})
elif mode == "build":
    from unswbc.sandbox import Sandbox
    src = pathlib.Path(sys.argv[2]).resolve()
    out = pathlib.Path(sys.argv[3]).resolve()
    lint = sys.argv[4] == "1"
    clangtool.warm()
    home = clangtool.toolchain()
    found = clangtool.sources(src)
    steps, lints = [], []

    def step(wasm, argv, mounts, what, into):
        box = Sandbox(wasm_path=wasm, root=home / "root", mounts=mounts, cwd="/src", argv=argv,
                      environ=["TERM=dumb", "PATH=/bin", "TMPDIR=/tmp"], writable=("/out", "/tmp"),
                      needs_zygote=False, needs_meter=False, max_pages=clangtool.BUILD_PAGES)
        rc = box.run()
        said = (bytes(box.stdout) + bytes(box.stderr)).decode("utf-8", "replace").strip()
        into.append({"what": what, "rc": rc, "output": said})
        return rc == 0

    work = pathlib.Path(tempfile.mkdtemp(prefix="pkgcheck-cxx-"))
    ok = True
    try:
        (work / "out").mkdir()
        (work / "tmp").mkdir()
        mounts = {"/src": src, "/out": work / "out", "/tmp": work / "tmp"}
        objects = []
        for index, source in enumerate(found):
            language = (["-xc", "-std=c17"] if source.suffix == clangtool.C_SUFFIX
                        else ["-xc++", "-std=c++20", "-stdlib=libc++"])
            objects.append(f"/tmp/{index}.o")
            ok = step(home / "clang.wasm", ["/bin/clang-20", *clangtool.DRIVER_FLAGS, "-c", "-o", objects[-1],
                                            *language, source.as_posix()],
                      mounts, f"compile {source.as_posix()}", steps) and ok
        any_cxx = any(source.suffix in clangtool.CXX_SUFFIXES for source in found)
        if ok:
            ok = step(home / "root" / "bin" / "wasm-ld",
                      ["/bin/wasm-ld", *clangtool.LINK_FLAGS, *(["-lc++", "-lc++abi"] if any_cxx else []),
                       *objects, *clangtool.LINK_TAIL], mounts, "link", steps)
        if lint:
            for source in found:
                language = (["-xc", "-std=c17"] if source.suffix == clangtool.C_SUFFIX
                            else ["-xc++", "-std=c++20", "-stdlib=libc++"])
                step(home / "clang.wasm", ["/bin/clang-20", *clangtool.DRIVER_FLAGS, "-fsyntax-only", "-Wall",
                                           "-Wextra", *language, source.as_posix()],
                     mounts, f"lint -Wall -Wextra {source.as_posix()}", lints)
        wasm = work / "out" / "bot.wasm"
        result = {"units": [p.as_posix() for p in found], "steps": steps, "lint": lints, "ok": ok and wasm.is_file()}
        if wasm.is_file():
            out.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(wasm, out / "bot.wasm")
            result["wasm_sha"] = sha(wasm)
            result["wasm_size"] = wasm.stat().st_size
    finally:
        shutil.rmtree(work, ignore_errors=True)
    emit(result)
elif mode == "toolkit-build":
    built = clangtool.build(pathlib.Path(sys.argv[2]))
    emit({"path": str(built), "wasm_sha": sha(built)})
'''


def find_uvx() -> str:
    for candidate in (shutil.which("uvx"), "/opt/homebrew/bin/uvx", str(pathlib.Path.home() / ".local/bin/uvx"),
                      "/usr/local/bin/uvx"):
        if candidate and pathlib.Path(candidate).is_file():
            return candidate
    sys.exit("cannot find uvx (looked on PATH, /opt/homebrew/bin, ~/.local/bin, /usr/local/bin)")


def toolkit_env() -> dict:
    env = dict(os.environ)
    env.update({"UNSWBC_NO_UPDATE": "1", "UNSWBC_NO_VSCODE": "1", "NO_COLOR": "1"})
    return env


def inner(uvx: str, *args: str, timeout: float = 1800) -> tuple[dict | None, str]:
    done = subprocess.run([uvx, "--from", TOOLKIT, "python", "-c", INNER, *args], capture_output=True, text=True,
                          env=toolkit_env(), timeout=timeout)
    payload = None
    for line in done.stdout.splitlines():
        if line.startswith("@@JSON@@"):
            payload = json.loads(line[len("@@JSON@@"):])
    noise = "\n".join(l for l in (done.stdout + done.stderr).splitlines() if not l.startswith("@@JSON@@"))
    return payload, noise.strip()


def sha256(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def slug(path: pathlib.Path) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", f"{path.parent.name}-{path.name}").strip("-") or "bot"


class Findings:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.info: list[str] = []

    def error(self, text: str) -> None:
        self.errors.append(text)

    def warn(self, text: str) -> None:
        self.warnings.append(text)

    def note(self, text: str) -> None:
        self.info.append(text)


def load_project(path: pathlib.Path, f: Findings) -> dict | None:
    botfile = path / "bot.toml"
    if not botfile.exists():
        f.error("no bot.toml in the bot folder, so `unswbc submit` refuses it and the server build fails")
        return None
    try:
        table = tomllib.loads(botfile.read_text())
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as error:
        f.error(f"bot.toml is not valid TOML: {error}")
        return None
    project = table.get("project")
    if not isinstance(project, dict):
        f.error("bot.toml has no [project] table")
        return None
    name = project.get("language")
    language = LANGUAGES.get(str(name).lower()) if name is not None else None
    if language is None:
        f.error(f"bot.toml project.language is {name!r}, which the toolkit cannot build")
        return None
    includes = project.get("include")
    if not isinstance(includes, list):
        f.error("bot.toml is missing project.include")
        return None
    output = project.get("output", BUILD_DIR_NAME)
    if output != BUILD_DIR_NAME:
        f.warn(f"bot.toml sets project.output = {output!r}; files under it are left out of the zip")
    extra = sorted(set(project) - {"language", "include", "output"})
    if extra:
        f.note(f"bot.toml has keys the toolkit ignores: {', '.join(extra)}")
    return {"language": language, "language_raw": str(name), "includes": [str(p) for p in includes],
            "output_dir": path / output}


def matches(relative: pathlib.PurePath, includes: list[str]) -> bool:
    whole = relative.as_posix()
    return any(fnmatch.fnmatchcase(whole, p) or fnmatch.fnmatchcase(relative.name, p) for p in includes)


def collect(path: pathlib.Path, project: dict) -> list[str]:
    output = project["output_dir"].resolve()
    return sorted(
        str(entry.relative_to(path))
        for entry in path.rglob("*")
        if entry.is_file()
        and output not in entry.resolve().parents
        and matches(entry.relative_to(path), project["includes"])
    )


def make_zip(path: pathlib.Path, sources: list[str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(path / "bot.toml", "bot.toml")
        for source in sources:
            if source != "bot.toml":
                archive.write(path / source, source)
    return buffer.getvalue()


def strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)
    return re.sub(r"//[^\n]*", "", text)


INCLUDE = re.compile(r'^[ \t]*#[ \t]*include[ \t]*([<"])([^>"\n]+)[>"]', re.M)
HAZARDS = [
    (re.compile(r"\b__(DATE|TIME|TIMESTAMP)__\b"), "error", "uses __DATE__/__TIME__/__TIMESTAMP__, which the judge's -Werror=date-time rejects"),
    (re.compile(r"\bunitbuf\b"), "warn", "sets std::unitbuf: every write becomes its own 2.5M-point write"),
    (re.compile(r"\bsync_with_stdio\b"), "warn", "calls sync_with_stdio, which the docs say not to (it bypasses the helper's buffer)"),
    (re.compile(r"\bcin\s*\.\s*tie\s*\("), "warn", "calls cin.tie(), which the docs say not to unless you flush at ENDTURN yourself"),
    (re.compile(r"\bcerr\b"), "warn", "writes to std::cerr (unbuffered, 2.5M points per write); the docs say use std::clog"),
    (re.compile(r"\bendl\b|\bstd::flush\b|\bfflush\s*\("), "warn", "flushes outside end_turn(): each flush costs 2.5M points"),
    (re.compile(r"\bstd::thread\b|\bpthread_create\b|\bstd::async\b|\bstd::jthread\b"), "warn", "starts a thread, which the sandbox denies"),
    (re.compile(r"\bsystem\s*\(|\bfork\s*\(|\bpopen\s*\(|\bposix_spawn"), "warn", "spawns a process, which the sandbox denies"),
    (re.compile(r"\bofstream\b|\bfopen\s*\("), "note", "opens files: the judge's disk is read-only and each open costs 40,000 points"),
    (re.compile(r"\bsrand\s*\(|[^_\w.]rand\s*\(\s*\)"), "note", "uses rand()/srand(), which gives every dragon the same sequence in the judge"),
    (re.compile(r"<generator>|bits/stdc\+\+\.h"), "error", "includes a header libc++ in the judge does not have"),
]
SONAR_32 = re.compile(r"(?i)sonar.*\b(u?int32_t|unsigned\s+int|unsigned(?!\s+long)\b|uint)\b|\b(u?int32_t|unsigned\s+int)\b.*sonar")
LEGACY_SONAR = re.compile(r"\bsend_sonar\s*\(\s*[^,()]+\)")


def inspect_sources(path: pathlib.Path, entries: list[str], helper_sha: str, f: Findings, data: dict) -> None:
    present = set(entries)
    units = [e for e in entries if pathlib.PurePosixPath(e).suffix in JUDGE_UNITS
             and not any(part.startswith(".") for part in pathlib.PurePosixPath(e).parts)]
    data["judge_units"] = units
    if not units:
        f.error("the zip holds no .c/.cc/.cpp/.cxx source, so the judge has nothing to build")
    for unit in units:
        if "/" in unit:
            f.warn(f"{unit} sits in a subfolder: the judge compiles every C/C++ source in the zip, subfolders included")
    mains = []
    helper_files = []
    for entry in entries:
        suffix = pathlib.PurePosixPath(entry).suffix
        if suffix not in TEXT_SUFFIXES:
            continue
        raw = (path / entry).read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            f.warn(f"{entry} is not valid UTF-8")
            text = raw.decode("utf-8", "replace")
        clean = strip_comments(text)
        is_template_helper = pathlib.PurePosixPath(entry).name == "helper.hpp" and sha256(raw) == helper_sha
        if pathlib.PurePosixPath(entry).name == "helper.hpp":
            helper_files.append((entry, raw, text))
        if entry in units and re.search(r"\bint\s+main\s*\(", clean):
            mains.append(entry)
        base = pathlib.PurePosixPath(entry).parent
        for kind, name in INCLUDE.findall(clean):
            name = name.strip()
            candidates = ([(base / name).as_posix()] if kind == '"' else []) + [pathlib.PurePosixPath(name).as_posix()]
            normal = [os.path.normpath(c) for c in candidates]
            if any(c in present for c in normal):
                continue
            on_disk = [c for c in normal if (path / c).is_file()]
            if on_disk:
                f.error(f'{entry} includes "{name}", which is in the bot folder but NOT in the zip (bot.toml include misses it)')
            elif kind == '"':
                f.warn(f'{entry} includes "{name}", which is not in the zip; it only builds if a system header has that name')
        for pattern, level, message in HAZARDS:
            if is_template_helper and level != "error":
                continue
            hits = [i + 1 for i, line in enumerate(clean.splitlines()) if pattern.search(line)]
            if hits:
                shown = ", ".join(map(str, hits[:8])) + (" ..." if len(hits) > 8 else "")
                {"error": f.error, "warn": f.warn, "note": f.note}[level](f"{entry} line {shown}: {message}")
        if not is_template_helper:
            lines = clean.splitlines()
            s32 = [i + 1 for i, line in enumerate(lines) if SONAR_32.search(line)]
            if s32:
                f.warn(f"{entry} lines {s32[:10]}: a 32-bit type next to sonar code (protocol 3 sonar values are 64-bit)")
            legacy = [i + 1 for i, line in enumerate(lines) if LEGACY_SONAR.search(line)]
            if legacy:
                f.note(f"{entry} lines {legacy[:10]}: one-argument send_sonar (32-bit, facing direction only)")
            data.setdefault("sonar_lines", {})[entry] = [i + 1 for i, line in enumerate(lines) if "sonar" in line.lower()][:40]
    data["main_defined_in"] = mains
    if len(mains) != 1 and units:
        f.error(f"int main( is defined in {len(mains)} judge-compiled files ({', '.join(mains) or 'none'}); the link needs exactly one")
    if not helper_files:
        f.warn("no helper.hpp in the zip (fine only if the bot does not use the helper)")
    for entry, raw, text in helper_files:
        digest = sha256(raw)
        data["helper_sha"] = digest
        protocol = re.search(r"PROTOCOL_MAJOR\s*=\s*(\d+)", text)
        data["helper_protocol"] = int(protocol.group(1)) if protocol else None
        if digest == helper_sha:
            f.note(f"{entry} is byte-identical to the {JUDGE_VERSION} toolkit template: `unswbc update` would change nothing")
        else:
            f.warn(f"{entry} differs from the {JUDGE_VERSION} toolkit template (sha {digest[:12]} vs {helper_sha[:12]})")
        if data["helper_protocol"] is not None:
            f.note(f"{entry} asks for PROTOCOL {data['helper_protocol']} in end_turn()")


def check_entries(path: pathlib.Path, project: dict, entries: list[str], f: Findings, data: dict) -> None:
    for entry in entries:
        pure = pathlib.PurePosixPath(entry)
        if any(part.startswith(".") for part in pure.parts):
            f.warn(f"{entry}: hidden path in the zip")
        if BUILD_DIR_NAME in pure.parts or "replays" in pure.parts or "__pycache__" in pure.parts:
            f.error(f"{entry}: build/replay/cache output inside the zip")
        if pure.suffix in UNWANTED_SUFFIX or UNWANTED_NAME.search(pure.name):
            f.warn(f"{entry}: looks like a backup, build product or log")
        if not re.fullmatch(r"[A-Za-z0-9_./+-]+", entry):
            f.warn(f"{entry}: space or non-ASCII character in the file name")
        full = path / entry
        if full.is_symlink():
            f.note(f"{entry}: is a symlink in the folder; the zip stores the file it points to")
        if full.stat().st_mtime < 315532800:
            f.error(f"{entry}: modified before 1980, which zipfile (and so `unswbc submit`) cannot store")
    output = project["output_dir"].resolve()
    left_out = []
    for entry in sorted(path.rglob("*")):
        if not entry.is_file():
            continue
        relative = entry.relative_to(path).as_posix()
        if relative == "bot.toml" or relative in entries:
            continue
        inside_build = output in entry.resolve().parents
        left_out.append(relative + ("  (build output, excluded)" if inside_build else ""))
        if not inside_build and pathlib.PurePosixPath(relative).suffix in TEXT_SUFFIXES \
                and not any(part.startswith(".") for part in pathlib.PurePosixPath(relative).parts):
            f.warn(f"{relative}: a C/C++ file in the folder that the zip leaves out")
    data["left_out"] = left_out


def unzip_fresh(blob: bytes, dest: pathlib.Path, path: pathlib.Path, f: Findings) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        bad = archive.testzip()
        if bad:
            f.error(f"zip member {bad} fails its CRC check")
        for info in archive.infolist():
            name = info.filename
            if name.startswith("/") or ".." in pathlib.PurePosixPath(name).parts:
                f.error(f"zip member {name} escapes the folder")
                continue
            archive.extract(info, dest)
            if (dest / name).read_bytes() != (path / name).read_bytes():
                f.error(f"zip member {name} does not match the file in the bot folder")
    found = sorted(p.relative_to(dest).as_posix() for p in dest.rglob("*") if p.is_file())
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        names = sorted(archive.namelist())
    if found != names:
        f.error(f"unzipped tree {found} differs from the zip listing {names}")


HARNESS = re.compile(r"^round (\d+|\?): bot (\d+) \(team (\S+)\) (.*)$")
ANSI = re.compile(r"\x1b\[[0-9;]*m")
COMMANDS = {
    "MOVE": re.compile(r"MOVE [NESW]+"),
    "SPLIT": re.compile(r"SPLIT \d+"),
    "SONAR": re.compile(r"SONAR (?:[NESW] )?\d+"),
    "PROTOCOL": re.compile(r"PROTOCOL \d+"),
    "INDICATOR": re.compile(r"INDICATOR( .*)?"),
    "LOG": re.compile(r"LOG( .*)?"),
    "DOT": re.compile(r"DOT -?\d+ -?\d+ \d+ \d+ \d+"),
    "LINE": re.compile(r"LINE -?\d+ -?\d+ -?\d+ -?\d+ \d+ \d+ \d+"),
}


def validate_reply(lines: list[str]) -> tuple[list[str], int]:
    bad, actions = [], 0
    for line in lines:
        text = line.strip()
        if not text:
            continue
        word = text.split(" ", 1)[0]
        pattern = COMMANDS.get(word)
        if pattern is None or not pattern.fullmatch(text):
            bad.append(text)
            continue
        if word == "SONAR":
            parts = text.split()
            value = int(parts[-1])
            if value > (2**64 - 1) or (len(parts) == 2 and value > 2**32 - 1):
                bad.append(text)
        if word in ("MOVE", "SPLIT"):
            actions += 1
    return bad, actions


def play(uvx: str, map_path: pathlib.Path, bot: pathlib.Path, replay: pathlib.Path, log: pathlib.Path,
         seed: int) -> dict:
    argv = [uvx, "--from", TOOLKIT, "unswbc", "run", "--sandbox", "-v", "--seed", str(seed), "-o", str(replay),
            str(map_path), str(bot), str(bot)]
    stats = {"map": str(map_path), "seed": seed, "command": " ".join(argv[1:]), "points": {}, "memory": {},
             "turns": {}, "top_turns": [], "over_50m": 0, "over_80m": 0, "deaths": {}, "no_valid_action": [],
             "bot_errors": [], "bad_lines": [], "no_action_turns": 0, "stderr_lines": 0, "stderr_sample": [],
             "notices": [], "result": None, "summary_lines": [], "exit": None, "seconds": None,
             "replies": 0, "replies_without_protocol3": 0, "deliberate_no_action": 0, "refused_action": []}
    started = time.monotonic()
    last_reply: dict[str, tuple[int, list[str]]] = {}
    block: list[str] | None = None
    block_kind = None
    block_key = None

    def close_block() -> None:
        nonlocal block, block_kind, block_key
        if block is None:
            return
        if block_kind == "stdout":
            bad, actions = validate_reply(block)
            for text in bad:
                if len(stats["bad_lines"]) < 50:
                    stats["bad_lines"].append(f"{block_key}: {text}")
            if actions == 0:
                stats["no_action_turns"] += 1
            stats["replies"] += 1
            if not any(l.strip() == "PROTOCOL 3" for l in block):
                stats["replies_without_protocol3"] += 1
            last_reply[block_key[1]] = (actions, list(block))
        elif block_kind == "stderr":
            real = [l for l in block if l.strip()]
            stats["stderr_lines"] += len(real)
            for l in real:
                if len(stats["stderr_sample"]) < 10:
                    stats["stderr_sample"].append(f"{block_key}: {l}")
        block, block_kind, block_key = None, None, None

    with subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace",
                          env=toolkit_env(), cwd=str(log.parent)) as process, gzip.open(log, "wt") as sink:
        for raw in process.stdout:
            sink.write(raw)
            line = ANSI.sub("", raw.rstrip("\n"))
            hit = HARNESS.match(line)
            if hit:
                close_block()
                round_num, dragon, team, rest = hit.groups()
                key = (round_num, dragon, team)
                if rest == "stdout:" or rest == "stderr:":
                    block, block_kind, block_key = [], rest[:-1], key
                elif rest.startswith("points "):
                    parts = rest.split()
                    points, memory = int(parts[1]), int(parts[3])
                    stats["points"][team] = max(stats["points"].get(team, 0), points)
                    stats["memory"][team] = max(stats["memory"].get(team, 0), memory)
                    stats["turns"][team] = stats["turns"].get(team, 0) + 1
                    stats["over_50m"] += points > 50_000_000
                    stats["over_80m"] += points > 80_000_000
                    stats["top_turns"].append((points, int(round_num) if round_num.isdigit() else -1, int(dragon), team))
                    stats["top_turns"] = sorted(stats["top_turns"], reverse=True)[:5]
                elif rest.startswith("died: "):
                    reason = rest[len("died: "):]
                    stats["deaths"][reason] = stats["deaths"].get(reason, 0) + 1
                    if reason == "no valid action":
                        actions, reply = last_reply.get(dragon, (None, []))
                        shown = f"round {round_num} bot {dragon} team {team}: " + " | ".join(l for l in reply if l.strip())[:200]
                        if actions == 0:
                            stats["deliberate_no_action"] += 1
                            if len(stats["no_valid_action"]) < 3:
                                stats["no_valid_action"].append(shown)
                        else:
                            stats["refused_action"].append(shown if actions else shown + " (no reply seen)")
                else:
                    stats["bot_errors"].append(line)
                continue
            if block is not None:
                if line.startswith("running round ") or re.match(r"^(team [AB] (wins|points)|draw after|wrote replay|skipped writing)", line):
                    close_block()
                else:
                    block.append(line)
                    continue
            if line.startswith("running round "):
                continue
            if re.match(r"^team [AB] wins after|^draw after", line):
                stats["result"] = line
            elif re.match(r"^team [AB] points per turn", line):
                stats["summary_lines"].append(line)
            elif line.startswith(("loaded ", "seed ", "wrote replay", "building ", "preparing judge", "  clang", "  wasm-ld")):
                continue
            elif line.strip():
                stats["notices"].append(line)
        close_block()
        stats["exit"] = process.wait()
    stats["seconds"] = round(time.monotonic() - started, 1)
    return stats


def check_bot(path: pathlib.Path, label: str, work: pathlib.Path, uvx: str, info: dict, args) -> dict:
    f = Findings()
    data: dict = {"bot": str(path), "label": label}
    report = {"findings": f, "data": data}
    if not path.is_dir():
        f.error(f"{path} is not a folder")
        return report
    project = load_project(path, f)
    if project is None:
        return report
    data["language"] = project["language"]
    data["includes"] = project["includes"]
    if project["language"] != "cpp":
        f.warn(f"bot.toml language is {project['language']}, not C++")
    try:
        entries = collect(path, project)
    except OSError as error:
        f.error(f"cannot walk the bot folder: {error}")
        return report
    if not entries:
        f.error("no files matched project.include, so `unswbc submit` refuses it")
        return report
    real, noise = inner(uvx, "collect", str(path))
    if real is None:
        f.warn(f"could not cross-check with the real {TOOLKIT} Project.collect_sources: {noise[-300:]}")
    elif real["sources"] != entries:
        f.error(f"file list differs from {TOOLKIT} Project.collect_sources: {real['sources']} vs {entries}")
    else:
        f.note(f"file list matches {TOOLKIT} Project.collect_sources exactly")
    try:
        blob = make_zip(path, entries)
    except ValueError as error:
        f.error(f"zipping failed the way `unswbc submit` would: {error}")
        return report
    bundle = work / label
    bundle.mkdir(parents=True, exist_ok=True)
    zip_path = bundle / f"{label}.zip"
    zip_path.write_bytes(blob)
    data["zip"] = str(zip_path)
    data["zip_bytes"] = len(blob)
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        data["zip_entries"] = [{"name": i.filename, "bytes": i.file_size, "packed": i.compress_size,
                                "sha256": sha256(archive.read(i.filename))} for i in archive.infolist()]
        names = archive.namelist()
    if names[0] != "bot.toml":
        f.error("bot.toml is not the first entry of the zip")
    if len(blob) > MAX_ZIP_BYTES:
        f.error(f"zip is {len(blob):,} bytes, over the 4 MB limit ({MAX_ZIP_BYTES:,})")
    else:
        f.note(f"zip is {len(blob):,} bytes ({len(blob) / MAX_ZIP_BYTES:.2%} of the 4 MB limit), {len(names)} entries")
    check_entries(path, project, entries, f, data)
    inspect_sources(path, [n for n in names if n != "bot.toml"], info.get("helper_hpp_sha", HELPER_SHA), f, data)
    unzipped = bundle / "unzipped" / label
    unzip_fresh(blob, unzipped, path, f)
    data["unzipped"] = str(unzipped)
    if args.package_only:
        return report
    build, noise = inner(uvx, "build", str(unzipped), str(bundle / "judge-build"), "0" if args.no_lint else "1")
    if build is None:
        f.error(f"judge-clang build did not report: {noise[-800:]}")
        return report
    data["judge_build"] = build
    for step in build["steps"]:
        if step["rc"] != 0:
            f.error(f"judge clang: {step['what']} failed:\n{step['output'][:3000]}")
        elif step["output"]:
            f.warn(f"judge clang: {step['what']} printed warnings:\n{step['output'][:3000]}")
    if build.get("ok"):
        f.note(f"judge clang built {', '.join(build['units'])} into a {build['wasm_size']:,}-byte wasm "
               f"(sha {build['wasm_sha'][:12]}) with no output from compiler or linker"
               if not any(s["output"] for s in build["steps"]) else
               f"judge clang built {', '.join(build['units'])} into a {build['wasm_size']:,}-byte wasm")
    for step in build.get("lint", []):
        warnings = [l for l in step["output"].splitlines() if "warning:" in l]
        mine = [l for l in warnings if not l.startswith("./helper.hpp") and not l.startswith("helper.hpp")]
        data.setdefault("lint_counts", {})[step["what"]] = {"warnings": len(warnings), "outside_helper": len(mine)}
        if mine:
            shown = "\n".join(mine[:12]) + (f"\n... {len(mine) - 12} more" if len(mine) > 12 else "")
            f.note(f"extra lint (not the judge's flags), {step['what']}: {len(mine)} warnings outside helper.hpp\n{shown}")
        elif step["rc"] == 0:
            f.note(f"extra lint (not the judge's flags), {step['what']}: clean outside helper.hpp")
    if not build.get("ok"):
        return report
    cached, noise = inner(uvx, "toolkit-build", str(unzipped))
    if cached is None:
        f.warn(f"`unswbc run --sandbox` build step did not report: {noise[-500:]}")
    else:
        data["toolkit_wasm"] = cached
        if cached["wasm_sha"] == build["wasm_sha"]:
            f.note("the wasm `unswbc run --sandbox` plays is byte-identical to this judge-clang build")
        else:
            f.warn(f"the wasm `unswbc run --sandbox` plays ({cached['wasm_sha'][:12]}) differs from this build "
                   f"({build['wasm_sha'][:12]})")
    return report


def summarise_games(report: dict, games: list[dict]) -> None:
    f: Findings = report["findings"]
    report["data"]["games"] = games
    for game in games:
        name = pathlib.Path(game["map"]).name
        if game["exit"] != 0:
            f.error(f"{name}: unswbc run exited {game['exit']}; see {game['log']}")
        for line in game["bot_errors"][:10]:
            f.error(f"{name}: {line}")
        if game["bad_lines"]:
            f.error(f"{name}: {len(game['bad_lines'])} reply lines the protocol does not define, e.g. {game['bad_lines'][:3]}")
        for line in game["refused_action"][:10]:
            f.warn(f"{name}: died of no valid action after sending a MOVE/SPLIT the engine refused (illegal action): {line}")
        if game["deliberate_no_action"]:
            f.note(f"{name}: {game['deliberate_no_action']} deaths by no valid action where the reply held no MOVE/SPLIT "
                   f"(the bot chose not to act, not an illegal command), e.g. {game['no_valid_action'][:1]}")
        if game["replies_without_protocol3"]:
            f.warn(f"{name}: {game['replies_without_protocol3']} of {game['replies']} replies lack PROTOCOL 3")
        if game["stderr_lines"]:
            f.warn(f"{name}: {game['stderr_lines']} stderr lines (each write costs 2.5M points), e.g. {game['stderr_sample'][:2]}")
        peak = max(game["points"].values(), default=0)
        memory = max(game["memory"].values(), default=0)
        if peak > 0.8 * TURN_POINTS:
            f.error(f"{name}: peak turn {peak:,} points is within 20% of the {TURN_POINTS:,} judge limit")
        elif peak > 0.5 * TURN_POINTS:
            f.warn(f"{name}: peak turn {peak:,} points is over half the {TURN_POINTS:,} judge limit")
        if memory > 0.8 * MEMORY_BYTES:
            f.warn(f"{name}: peak memory {memory:,} bytes is near the {MEMORY_BYTES:,}-byte judge limit")
        for notice in game["notices"][:5]:
            f.note(f"{name}: {notice}")
        f.note(f"{name}: {game['result'] or 'no result line'}; peak {peak / 1e6:.2f}M points/turn "
               f"({peak / TURN_POINTS:.1%} of limit), peak memory {memory / 2**20:.1f} MiB of 48, "
               f"{sum(game['turns'].values())} dragon-turns, {game['replies']} replies all protocol-valid"
               f"{'' if not game['bad_lines'] else ' EXCEPT ' + str(len(game['bad_lines']))}, "
               f"deaths {game['deaths'] or 'none'}, {game['seconds']}s")


def render(reports: list[dict], info: dict) -> str:
    out = [f"toolkit {info.get('version')} from {info.get('package')}",
           f"engine sha {str(info.get('engine_sha'))[:16]} ({info.get('engine_size')} bytes)", ""]
    for report in reports:
        f, data = report["findings"], report["data"]
        verdict = "FAIL" if f.errors else ("PASS with warnings" if f.warnings else "PASS")
        out.append(f"=== {data['label']}: {verdict}  ({data['bot']})")
        if data.get("zip"):
            out.append(f"zip: {data['zip']}  {data['zip_bytes']:,} bytes")
            for e in data.get("zip_entries", []):
                out.append(f"  {e['name']:<24} {e['bytes']:>9,} bytes  sha256 {e['sha256'][:16]}")
        if data.get("left_out"):
            out.append("in the folder but not in the zip: " + ", ".join(data["left_out"]))
        for title, items in (("ERRORS", f.errors), ("WARNINGS", f.warnings), ("INFO", f.info)):
            if items:
                out.append(f"{title}:")
                out.extend("  - " + item.replace("\n", "\n    ") for item in items)
        for game in data.get("games", []):
            out.append(f"game {pathlib.Path(game['map']).name}: {game['result']}")
            out.extend("  " + line for line in game["summary_lines"])
            out.append(f"  top turns (points, round, bot, team): {game['top_turns'][:3]}")
            out.append(f"  replay {game['replay']}  log {game['log']}")
        out.append("")
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild the zip `unswbc submit` would upload, then build and play it "
                                                 f"the way the judge does with {TOOLKIT}. Never submits.")
    parser.add_argument("bots", nargs="*", type=pathlib.Path, default=[DEFAULT_BOT],
                        help=f"bot folders holding bot.toml (default {DEFAULT_BOT})")
    parser.add_argument("--label", action="append", default=None, help="a name per bot, in order")
    parser.add_argument("--work", type=pathlib.Path, default=HERE.parent / "replays" / "check_package",
                        help="where zips, unzipped copies, logs go")
    parser.add_argument("--repo", type=pathlib.Path, default=DEFAULT_REPO, help="repo holding maps/")
    parser.add_argument("--maps", nargs="+", default=MAPS, help="maps relative to --repo, or absolute")
    parser.add_argument("--seed", type=int, default=20260929)
    parser.add_argument("--jobs", type=int, default=MAX_PARALLEL_GAMES)
    parser.add_argument("--no-games", action="store_true")
    parser.add_argument("--no-lint", action="store_true")
    parser.add_argument("--package-only", action="store_true", help="zip and inspect only: no judge build, no games")
    args = parser.parse_args()
    uvx = find_uvx()
    info, noise = inner(uvx, "info")
    if info is None:
        print(f"cannot run {TOOLKIT} through uvx:\n{noise}", file=sys.stderr)
        return 2
    if info["version"] != JUDGE_VERSION:
        print(f"uvx gave unswbc {info['version']}, expected {JUDGE_VERSION}", file=sys.stderr)
        return 2
    labels = args.label or []
    bots = [b.expanduser().resolve() for b in args.bots]
    labels = labels + [slug(b) for b in bots[len(labels):]]
    args.work.mkdir(parents=True, exist_ok=True)
    reports = []
    for bot, label in zip(bots, labels):
        print(f"checking {label} ({bot}) ...", flush=True)
        reports.append(check_bot(bot, label, args.work, uvx, info, args))
    if not args.no_games and not args.package_only:
        jobs = []
        for report in reports:
            data = report["data"]
            if report["findings"].errors or not data.get("unzipped"):
                continue
            for index, name in enumerate(args.maps):
                map_path = pathlib.Path(name) if pathlib.Path(name).is_absolute() else args.repo / name
                if not map_path.is_file():
                    report["findings"].error(f"map not found: {map_path}")
                    continue
                games_dir = args.work / data["label"] / "games"
                games_dir.mkdir(parents=True, exist_ok=True)
                jobs.append((report, map_path, pathlib.Path(data["unzipped"]),
                             games_dir / f"{map_path.stem}.replay", games_dir / f"{map_path.stem}.log.gz"))
        print(f"playing {len(jobs)} sandbox games, {min(args.jobs, MAX_PARALLEL_GAMES)} at a time ...", flush=True)
        with ThreadPoolExecutor(max_workers=max(1, min(args.jobs, MAX_PARALLEL_GAMES))) as pool:
            futures = [(job, pool.submit(play, uvx, job[1], job[2], job[3], job[4], args.seed)) for job in jobs]
            by_report: dict[int, list] = {}
            for job, future in futures:
                game = future.result()
                game["replay"], game["log"] = str(job[3]), str(job[4])
                by_report.setdefault(id(job[0]), []).append(game)
                print(f"  {job[0]['data']['label']} {job[1].name}: {game['result']} ({game['seconds']}s)", flush=True)
        for report in reports:
            summarise_games(report, by_report.get(id(report), []))
    text = render(reports, info)
    print(text)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    (args.work / f"check-{stamp}.txt").write_text(text)
    (args.work / f"check-{stamp}.json").write_text(json.dumps(
        [{"errors": r["findings"].errors, "warnings": r["findings"].warnings, "info": r["findings"].info,
          "data": r["data"]} for r in reports], indent=1, default=str))
    print(f"saved {args.work / f'check-{stamp}.txt'}")
    return 1 if any(r["findings"].errors for r in reports) else 0


if __name__ == "__main__":
    sys.exit(main())
