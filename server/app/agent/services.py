"""The long-lived pieces a request needs, built once at start-up."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from app.audit.log import AuditLog, utc_now
from app.core.reference import Reference, load_reference
from app.core.settings import Settings
from app.policy.engine import Policy
from app.policy.tokens import TokenSigner
from app.store.db import Store
from app.tools.context import Prices


@dataclass(frozen=True)
class Services:
    """Reference data, prices, the store, the guardian and the clock."""

    settings: Settings
    ref: Reference
    prices: Prices
    store: Store
    policy: Policy
    clock: Callable[[], datetime] = utc_now

    def audit(self, session_id: str) -> AuditLog:
        """Return the audit log for a session."""
        return AuditLog(self.log_path(session_id), session_id, clock=self.clock)

    def log_path(self, session_id: str) -> Path:
        """Return where a session's audit log is written."""
        return self.settings.evidence_dir / "logs" / f"{session_id}.jsonl"


def build_services(settings: Settings, clock: Callable[[], datetime] = utc_now) -> Services:
    """Load and validate everything once."""
    ref = load_reference(settings.data_dir)
    signer = TokenSigner(
        settings.confirm_secret.get_secret_value().encode(),
        timedelta(minutes=ref.rules.conf_01.token_ttl_minutes),
    )
    return Services(
        settings=settings,
        ref=ref,
        prices=Prices(ref),
        store=Store(settings.db_path),
        policy=Policy(ref, signer),
        clock=clock,
    )
