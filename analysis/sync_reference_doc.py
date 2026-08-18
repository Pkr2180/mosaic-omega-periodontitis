"""Regenerate the embedded source blocks in ``docs/MOSAIC_OMEGA.md``.

That document is a literate reference: each ``### `path` `` heading is followed by a
fenced block holding the full source of that file. Maintained by hand, the blocks
drift out of sync with the code -- at one point 8 of 24 differed, including the test
suite, which is how the document came to claim 23 tests while 24 were shipping.

This script rewrites every block from the file it names, so the document cannot
disagree with the repository. ``tests/test_reproducibility.py`` enforces it.

    python analysis/sync_reference_doc.py           # rewrite blocks
    python analysis/sync_reference_doc.py --check    # report drift, change nothing
"""
import re
import sys

from _paths import REPO

DOC = REPO / "docs" / "MOSAIC_OMEGA.md"

# "### `path`"  ... optional prose ...  ```lang\n<body>\n```
BLOCK = re.compile(
    r"(?P<head>^### `(?P<path>[^`]+)`\n"          # heading naming a file
    r"(?P<prose>.*?)"                             # prose between heading and fence
    r"```(?P<lang>python|text|bash)\n)"           # opening fence
    r"(?P<body>.*?)"                              # the embedded source
    r"(?P<tail>^```)",                            # closing fence
    re.S | re.M,
)

LANG = {".py": "python"}


def _read(path):
    return path.read_text(encoding="utf-8").replace("\r\n", "\n").rstrip("\n")


def sync(check_only=False):
    doc = DOC.read_text(encoding="utf-8")
    drifted, missing, ok = [], [], 0

    def repl(m):
        nonlocal ok
        rel = m.group("path")
        target = REPO / rel
        if not target.exists():
            missing.append(rel)
            return m.group(0)
        real = _read(target)
        if real == m.group("body").replace("\r\n", "\n").rstrip("\n"):
            ok += 1
            return m.group(0)
        drifted.append(rel)
        lang = LANG.get(target.suffix, "text")
        head = m.group("head").replace(f'```{m.group("lang")}\n', f"```{lang}\n")
        return f"{head}{real}\n{m.group('tail')}"

    new = BLOCK.sub(repl, doc)

    print(f"{ok} block(s) already in sync")
    for r in drifted:
        print(f"  DRIFTED  {r}")
    for r in missing:
        print(f"  NO FILE  {r}")

    if check_only:
        return 1 if (drifted or missing) else 0

    if drifted:
        DOC.write_text(new, encoding="utf-8")
        print(f"\nrewrote {len(drifted)} block(s) in {DOC.relative_to(REPO).as_posix()}")
    else:
        print("\nnothing to do")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(sync(check_only="--check" in sys.argv))
