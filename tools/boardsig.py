import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from mapbook import Map, edges_string

BOARDS = [("australia", 1), ("unsw", 2), ("maze", 32), ("trauma", 64)]


def main():
    out = ["#pragma once", "struct BoardSig { int w, h, bit; char const* edges; };", "BoardSig const BOARDS[] = {"]
    for name, bit in BOARDS:
        m = Map(ROOT / "maps" / "ladder17" / f"{name}.map")
        out.append('    {%d, %d, %d, "%s"},' % (m.W, m.H, bit, edges_string(m)))
    out.append("};")
    (ROOT / "bot" / "boards.hpp").write_text("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
