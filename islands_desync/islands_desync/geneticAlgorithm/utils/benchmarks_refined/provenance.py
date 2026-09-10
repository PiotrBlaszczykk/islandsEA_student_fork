"""Identify mathematical implementation separately from algorithm parameters."""
from functools import lru_cache
import hashlib
from pathlib import Path


@lru_cache(maxsize=1)
def implementation_sha256():
    root = Path(__file__).resolve().parent
    checksum = hashlib.sha256()
    # Normalize CRLF to LF so git checkout settings do not alter identity.
    for source in sorted(root.glob("*.py")):
        checksum.update(source.name.encode("utf-8") + b"\0")
        checksum.update(source.read_text(encoding="utf-8").encode("utf-8") + b"\0")
    return checksum.hexdigest()
