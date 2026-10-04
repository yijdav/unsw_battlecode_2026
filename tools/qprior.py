import argparse
from pathlib import Path
from mapbook import Map, edges_string

ROOT = Path(__file__).resolve().parent.parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--maps", default=str(ROOT / "maps" / "ladder17"))
    ap.add_argument("--out", default=str(ROOT / "bot" / "qprior.hpp"))
    args = ap.parse_args()
    seen = {}
    for p in sorted(Path(args.maps).glob("*.map")):
        m = Map(p)
        key = (m.W, m.H, edges_string(m), tuple(m.ports))
        seen.setdefault(key, []).append(p.stem)
    out = ["#pragma once",
           "struct QPrior { int w, h; char const* edges; std::vector<std::array<int, 3>> ports; };",
           "std::vector<QPrior> const QPRIORS = {"]
    for (w, h, edges, ports), names in seen.items():
        out.append("    {%d, %d, \"%s\"," % (w, h, edges))
        out.append("     {%s}}," % ", ".join("{%d, %d, %d}" % t for t in ports))
        print(w, h, len(ports), " ".join(names))
    out.append("};")
    Path(args.out).write_text("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
