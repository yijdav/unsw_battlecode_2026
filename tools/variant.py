#!/usr/bin/env python3
"""Copy the bot bot with some knobs changed, for head-to-head testing.

    python3 tools/variant.py v_late feed_start_small=360,feed_start_big=330
"""
import re, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
name, subs = sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else ""
dst = ROOT / name
shutil.rmtree(dst, ignore_errors=True)
shutil.copytree(ROOT / "bot", dst, ignore=shutil.ignore_patterns(".unswbc-build"))
src = (dst / "main.cpp").read_text()
for kv in filter(None, subs.split(",")):
    k, v = kv.split("=")
    src, n = re.subn(rf"(\b{k} = )[^;]+;", rf"\g<1>{v};", src, count=1)
    if not n:
        sys.exit(f"no knob {k}")
(dst / "main.cpp").write_text(src)
print("made", name, subs)
