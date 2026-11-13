"""Read DeepSeek Harness session archives: concatenated zstd frames, one per record.

Why not just `import pyzstd`? Because memloom promises zero required dependencies.
We probe, in order:

1. ``pyzstd`` (pip install memloom[zstd])
2. ``compression.zstd`` (Python >= 3.14 stdlib)
3. a local ``node`` (>= 22 has ``zlib.zstdDecompressSync``)
4. the ``zstd`` / ``zstdcat`` CLI if it happens to exist

Frames must be split by magic number first: DSH appends one independent frame per
event, so a plain "decompress whole blob" call on a truncated understanding of the
format loses everything after the first frame.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

__all__ = ["ZSTD_MAGIC", "ZstdUnavailable", "split_frames", "decompress", "backend"]

ZSTD_MAGIC = b"\x28\xb5\x2f\xfd"

_NODE_SRC = r"""
const fs = require('fs'), zlib = require('zlib');
const MAGIC = Buffer.from([0x28, 0xb5, 0x2f, 0xfd]);
const data = fs.readFileSync(process.argv[1]);
const offs = [];
let i = 0;
for (;;) { const k = data.indexOf(MAGIC, i); if (k === -1) break; offs.push(k); i = k + 4; }
const out = [];
for (let k = 0; k < offs.length; k++) {
  const s = offs[k];
  const e = (k + 1 < offs.length) ? offs[k + 1] : data.length;
  try { out.push(zlib.zstdDecompressSync(data.subarray(s, e))); }
  catch (_) {}
}
process.stdout.write(Buffer.concat(out));
"""


class ZstdUnavailable(RuntimeError):
    """Raised when no zstd backend can be found on this machine."""


def split_frames(data: bytes) -> list:
    """Return the byte ranges of every zstd frame in ``data``."""
    offs, i = [], 0
    while True:
        k = data.find(ZSTD_MAGIC, i)
        if k < 0:
            break
        offs.append(k)
        i = k + 4
    return [(offs[k], offs[k + 1] if k + 1 < len(offs) else len(data)) for k in range(len(offs))]


def _try_pyzstd(ranges, data):
    import pyzstd  # type: ignore

    parts, failed = [], 0
    for a, b in ranges:
        try:
            parts.append(pyzstd.decompress(data[a:b]))
        except Exception:
            failed += 1
    return b"".join(parts), failed


def _try_stdlib(ranges, data):
    from compression import zstd  # type: ignore  # Python >= 3.14

    parts, failed = [], 0
    for a, b in ranges:
        try:
            parts.append(zstd.decompress(data[a:b]))
        except Exception:
            failed += 1
    return b"".join(parts), failed


def _try_node(path: str, ranges):
    """Decompress via ``node -e``, piped over stdout.

    Deliberately writes *nothing* to disk: session archives usually live in a directory
    the user considers read-only, and dropping temp files next to someone's transcripts
    is rude (also fatal under a sandbox).
    """
    node = shutil.which("node")
    if not node:
        raise ZstdUnavailable("node not found")
    proc = subprocess.run(
        [node, "-e", _NODE_SRC, os.path.abspath(path)],
        capture_output=True,
        timeout=180,
    )
    if proc.returncode != 0 or not proc.stdout:
        raise ZstdUnavailable(
            "node failed: " + (proc.stderr or b"").decode("utf-8", "replace")[:200]
        )
    return proc.stdout, 0


def _try_cli(path: str):
    for exe in ("zstd", "zstdcat"):
        found = shutil.which(exe)
        if not found:
            continue
        proc = subprocess.run([found, "-d", "-c", os.path.abspath(path)], capture_output=True, timeout=180)
        if proc.returncode == 0 and proc.stdout:
            return proc.stdout, 0
    raise ZstdUnavailable("no zstd CLI")


def backend() -> str:
    """Name of the backend that would be used, or '' when none exists."""
    try:
        import pyzstd  # noqa: F401

        return "pyzstd"
    except Exception:
        pass
    try:
        from compression import zstd  # noqa: F401

        return "stdlib-compression.zstd"
    except Exception:
        pass
    if shutil.which("node"):
        return "node"
    if shutil.which("zstd") or shutil.which("zstdcat"):
        return "cli"
    return ""


def decompress(path: str) -> tuple:
    """Decompress a multi-frame ``.zstd`` file. Returns ``(payload, backend)``."""
    with open(path, "rb") as f:
        data = f.read()
    ranges = split_frames(data)
    if not ranges:
        # Some writers emit a single frame with a skippable header; try whole-blob.
        ranges = [(0, len(data))]

    errors = []
    try:
        import pyzstd  # noqa: F401

        return _try_pyzstd(ranges, data)[0], "pyzstd"
    except Exception as exc:  # ImportError or decode failure
        errors.append(f"pyzstd: {exc}")

    try:
        return _try_stdlib(ranges, data)[0], "stdlib-compression.zstd"
    except Exception as exc:
        errors.append(f"stdlib: {exc}")

    try:
        return _try_node(path, ranges)[0], "node"
    except Exception as exc:
        errors.append(f"node: {exc}")

    try:
        return _try_cli(path)[0], "cli"
    except Exception as exc:
        errors.append(f"cli: {exc}")

    raise ZstdUnavailable(
        "cannot decompress .zstd on this machine. Install one of:\n"
        "  pip install 'memloom[zstd]'   (pyzstd)\n"
        "  Python >= 3.14               (stdlib compression.zstd)\n"
        "  Node >= 22                   (already present if `node -v` works)\n"
        "Detail: " + " | ".join(errors)
    )
