"""Line-ending normalisation for shipped bundles.

Release packages must use CRLF regardless of the machine that built them. Left to
Python's defaults this is accidental: ``open(..., "w")`` with ``newline=None``
translates ``\\n`` to ``os.linesep``, so a Windows build shipped CRLF and a Linux
build shipped LF. v3.10.0 was CRLF for that reason alone, and rebuilding it on
Linux would have changed every byte-position in every file while changing no
content -- burying real diffs and breaking any consumer anchoring on ``$``.

Normalising as a final pass rather than by fixing each writer is deliberate:
Phase 120 also brings files in through ``shutil.copy2``/``copytree``, which copy
bytes verbatim and no writer flag can reach. One pass over the finished tree
covers every path a file can arrive by, including ones added later.
"""

from pathlib import Path
from typing import Iterable

# Text formats the bundle ships. Anything else (images, archives) is left alone --
# rewriting a binary would corrupt it.
TEXT_SUFFIXES = frozenset({".md", ".xml", ".json", ".txt"})

CRLF = b"\r\n"


def to_crlf(data: bytes) -> bytes:
    """Return ``data`` with every line ending as CRLF.

    Idempotent, and correct for mixed input: existing CRLF and lone CR are
    collapsed to LF first, so a second run is a no-op rather than producing CRCRLF.
    """
    normalized = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return normalized.replace(b"\n", CRLF)


def normalize_file(path: Path) -> bool:
    """Rewrite ``path`` to CRLF. Returns True when the bytes actually changed.

    Read and written as bytes so no decoding step can mangle content that is not
    valid UTF-8; the transformation is defined purely on line-ending bytes.
    """
    original = path.read_bytes()
    converted = to_crlf(original)
    if converted == original:
        return False
    path.write_bytes(converted)
    return True


def normalize_tree(root: Path, suffixes: Iterable[str] = TEXT_SUFFIXES) -> tuple[int, int]:
    """Normalise every text file under ``root``. Returns ``(changed, scanned)``.

    A missing ``root`` is not an error -- a phase may legitimately produce no
    output -- so it reports ``(0, 0)``.
    """
    wanted = {s.lower() for s in suffixes}
    changed = scanned = 0
    if not root.exists():
        return 0, 0

    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in wanted:
            continue
        scanned += 1
        if normalize_file(path):
            changed += 1
    return changed, scanned
