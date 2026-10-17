"""One-time confirmation tokens for Tier 2 actions (CONF-01).

Only the Confirm button's request mints a token, and only the server
reads it, so the LLM never sees or produces one. A token is an HMAC-
SHA256 signature over the proposal id, the SHA-256 of the proposal's
exact contents, a random nonce and an expiry. Signatures are compared
with hmac.compare_digest (constant time, as the Python docs advise);
the nonce is recorded when used, so a token works once.
"""

import base64
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta


def content_hash(contents: object) -> str:
    """Return the SHA-256 of a proposal's canonical JSON."""
    raw = json.dumps(contents, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


@dataclass(frozen=True, slots=True)
class Claims:
    """What a token says, once its signature checks out."""

    proposal_id: str
    content_hash: str
    nonce: str
    expires_at: datetime


class TokenSigner:
    """Mints and reads tokens with one server-side secret."""

    def __init__(self, secret: bytes, ttl: timedelta) -> None:
        """Keep the secret and the time to live."""
        if len(secret) < 16:
            raise ValueError("the confirmation secret must be at least 16 bytes")
        self._secret = secret
        self._ttl = ttl

    def _sign(self, body: bytes) -> bytes:
        return hmac.new(self._secret, body, hashlib.sha256).digest()

    def mint(self, proposal_id: str, contents_sha256: str, now: datetime) -> tuple[str, Claims]:
        """Return a new token and its claims."""
        claims = Claims(proposal_id, contents_sha256, secrets.token_hex(16), now + self._ttl)
        body = json.dumps(
            {
                "p": claims.proposal_id,
                "h": claims.content_hash,
                "n": claims.nonce,
                "e": claims.expires_at.isoformat(),
            },
            separators=(",", ":"),
        ).encode()
        return f"{_b64(body)}.{_b64(self._sign(body))}", claims

    def read(self, token: str) -> Claims | None:
        """Return the claims if the signature is valid, else None."""
        try:
            body_part, sig_part = token.split(".")
            body, sig = _unb64(body_part), _unb64(sig_part)
        except ValueError:
            return None
        if not hmac.compare_digest(sig, self._sign(body)):
            return None
        data = json.loads(body)
        return Claims(data["p"], data["h"], data["n"], datetime.fromisoformat(data["e"]))
