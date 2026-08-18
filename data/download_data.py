#!/usr/bin/env python3
"""Download the raw single-cell data from NCBI GEO.

    python data/download_data.py              # fetch both cohorts (~0.9 GB)
    python data/download_data.py --check      # verify what is already present
    python data/download_data.py --cohort main

The matrices are far too large to commit, so they are pulled from the original
public repositories. Downloads resume if interrupted and are size-verified against
the Content-Length GEO reports.

The CZ CELLxGENE atlas used for the marker-recovery sub-study is not downloadable
without a browser session; see README.md in this directory.
"""
from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent

FILES = {
    "main": dict(
        accession="GSE171213",
        url="https://ftp.ncbi.nlm.nih.gov/geo/series/GSE171nnn/GSE171213/suppl/"
            "GSE171213_AllSample.counts.tsv.gz",
        name="GSE171213_AllSample.counts.tsv.gz",
        size=90_617_204,
        note="Main cohort, 12 donors. analysis/disease_01_build.py reads this.",
    ),
    "external": dict(
        accession="GSE164241",
        url="https://ftp.ncbi.nlm.nih.gov/geo/series/GSE164nnn/GSE164241/suppl/"
            "GSE164241_RAW.tar",
        name="GSE164241_RAW.tar",
        size=796_436_480,
        note="External cohort, 18 samples. Untar into data/GSE164241/ before "
             "running analysis/disease_ext_01_build.py.",
    ),
}


def _human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def check():
    ok = True
    for key, f in FILES.items():
        p = HERE / f["name"]
        if not p.exists():
            print(f"  MISSING   {f['name']}  ({_human(f['size'])})")
            ok = False
        elif p.stat().st_size != f["size"]:
            print(f"  PARTIAL   {f['name']}  {_human(p.stat().st_size)} of {_human(f['size'])}")
            ok = False
        else:
            print(f"  OK        {f['name']}  {_human(f['size'])}")
    return ok


def fetch(f):
    dest = HERE / f["name"]
    if dest.exists() and dest.stat().st_size == f["size"]:
        print(f"  already complete: {f['name']}")
        return True

    have = dest.stat().st_size if dest.exists() else 0
    if have > f["size"]:
        print(f"  {f['name']} is larger than expected; removing and refetching")
        dest.unlink()
        have = 0

    req = urllib.request.Request(f["url"], headers={"User-Agent": "mosaic-omega/1.0"})
    if have:
        req.add_header("Range", f"bytes={have}-")
        print(f"  resuming {f['name']} at {_human(have)}")

    try:
        with urllib.request.urlopen(req, timeout=60) as r, open(dest, "ab" if have else "wb") as out:
            total, done, last = f["size"], have, -1
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                out.write(chunk)
                done += len(chunk)
                pct = int(done * 100 / total)
                if pct != last:
                    print(f"\r  {f['name']}  {pct:3d}%  {_human(done)} / {_human(total)}",
                          end="", flush=True)
                    last = pct
        print()
    except Exception as exc:                                  # noqa: BLE001
        print(f"\n  FAILED {f['name']}: {exc}\n  re-run to resume", file=sys.stderr)
        return False

    got = dest.stat().st_size
    if got != f["size"]:
        print(f"  SIZE MISMATCH {f['name']}: got {got}, expected {f['size']}", file=sys.stderr)
        return False
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="report what is present, download nothing")
    ap.add_argument("--cohort", choices=sorted(FILES), help="fetch only one cohort")
    args = ap.parse_args()

    if args.check:
        return 0 if check() else 1

    targets = [FILES[args.cohort]] if args.cohort else list(FILES.values())
    total = sum(f["size"] for f in targets)
    print(f"Downloading {len(targets)} file(s), {_human(total)} total, into {HERE}\n")

    failed = [f["name"] for f in targets if not fetch(f)]
    print()
    if failed:
        print("failed: " + ", ".join(failed))
        return 1

    print("All downloads complete and size-verified.")
    if not args.cohort or args.cohort == "external":
        print(f"\nNext: untar the external cohort ->\n"
              f"  tar -xf {HERE / 'GSE164241_RAW.tar'} -C {HERE / 'GSE164241'}")
    print("\nThen: python reproduce.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
