"""Content hashes that bind a confirmation to an exact proposal."""

import hashlib
import json


def content_hash(contents: object) -> str:
    """Return the SHA-256 of a proposal's canonical JSON."""
    raw = json.dumps(contents, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode()).hexdigest()
