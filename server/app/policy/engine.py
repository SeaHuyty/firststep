"""The guardian: deterministic checks the LLM cannot talk its way past.

Every check reads its threshold from data/rules.yaml and returns a
Decision naming the rule ID, in words a beginner can act on (copy
patterns from docs/standards/onboarding-ux.md section 5). Following
OWASP LLM06 "complete mediation", authorization lives here, never in
the model's judgement.
"""

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.core.reference import Reference
from app.core.types import ClientClass, Money, Stage
from app.engine.monitor import needs_cooling_off
from app.engine.readiness import Readiness
from app.engine.suitability import concentration_violations, unsuitable_lines
from app.policy.tokens import TokenSigner


@dataclass(frozen=True, slots=True)
class Decision:
    """Allowed, or refused with the rule that refused it."""

    allowed: bool
    rule_id: str | None = None
    message: str = ""


ALLOW = Decision(True)


def _usd(amount: float | Decimal) -> str:
    return f"${amount:,.0f}"


class Policy:
    """All checks, bound to one rule book and product shelf."""

    def __init__(self, ref: Reference, signer: TokenSigner) -> None:
        """Keep the rules, products and the token signer."""
        self.rules = ref.rules
        self.products = ref.products
        self.signer = signer
        self._lang = [
            (rule.id, re.compile("|".join(rule.patterns), re.IGNORECASE))
            for rule in ref.rules.lang.rules
        ]

    def stage(self, tool: str, stage: Stage) -> Decision:
        """STAGE-01: the tool must be allowed in the current stage."""
        if tool in self.rules.stage_01.allowed.get(stage, ()):
            return ALLOW
        return Decision(False, "STAGE-01", f"{tool} isn't available at the {stage} step.")

    def readiness(self, result: Readiness) -> Decision:
        """READY-01 and READY-02: no investing before the basics."""
        if result.ready:
            return ALLOW
        if "READY-02" in result.failed_rule_ids:
            worst = max(result.high_apr_debts, key=lambda d: d.apr_pct)
            return Decision(
                False,
                "READY-02",
                f"Your {worst.kind.replace('_', ' ')} charges {worst.apr_pct:g}% a year. "
                "Paying it off first is a surer return than investing.",
            )
        need = self.rules.ready_01.min_emergency_months
        return Decision(
            False,
            "READY-01",
            f"Your savings cover {result.emergency_months:.1f} months of costs. "
            f"Let's build at least {need:g} months first.",
        )

    def suitability(self, weights: Mapping[str, float], client: ClientClass) -> Decision:
        """SUIT-01: every product rated at or below the client class."""
        found = unsuitable_lines(
            weights, self.products, client, self.rules.suit_01.max_rating_for_class
        )
        if not found:
            return ALLOW
        product = self.products[found[0].subject]
        return Decision(
            False,
            "SUIT-01",
            f"{product.name} is rated {product.risk_rating}, above your {client} level, "
            "so I can't include it.",
        )

    def concentration(self, weights: Mapping[str, float], client: ClientClass) -> Decision:
        """CONC-01: no single product or equity class may dominate."""
        rule = self.rules.conc_01
        found = concentration_violations(
            weights,
            self.products,
            client,
            max_product_pct=rule.max_product_pct,
            max_equity_class_pct=rule.max_equity_class_pct,
            exempt=rule.exempt_classes,
        )
        if not found:
            return ALLOW
        v = found[0]
        name = self.products[v.subject].name if v.subject in self.products else v.subject
        return Decision(
            False,
            "CONC-01",
            f"{name} would be {v.value_pct:.0f}% of your plan; the limit is "
            f"{v.limit_pct:.0f}% so one bad result can't sink everything.",
        )

    def allocation(self, weights: Mapping[str, float], client: ClientClass) -> Decision:
        """SUIT-01 then CONC-01 on a proposed mix."""
        first = self.suitability(weights, client)
        return first if not first.allowed else self.concentration(weights, client)

    def order_limits(self, amounts: Sequence[Money], spent_today: Money) -> Decision:
        """LIM-01: per-order and per-day ceilings in the sandbox."""
        rule = self.rules.lim_01
        biggest = max(amounts, default=Decimal(0))
        if biggest > Decimal(str(rule.max_order_usd)):
            return Decision(
                False,
                "LIM-01",
                f"That order is above the {_usd(rule.max_order_usd)} per-order limit. "
                "Try a smaller amount or split it into two orders.",
            )
        if spent_today + sum(amounts, Decimal(0)) > Decimal(str(rule.max_daily_usd)):
            return Decision(
                False,
                "LIM-01",
                f"That would pass the {_usd(rule.max_daily_usd)} daily limit. "
                "You can place the rest tomorrow.",
            )
        return ALLOW

    def confirmation(
        self,
        token: str | None,
        *,
        proposal_id: str,
        contents_sha256: str,
        now: datetime,
        nonce_used: Callable[[str], bool],
    ) -> Decision:
        """CONF-01: a valid, unexpired, unused token for this plan."""
        problem = self._token_problem(token, proposal_id, contents_sha256, now, nonce_used)
        if problem is None:
            return ALLOW
        return Decision(False, "CONF-01", f"{problem} Press Confirm to go ahead.")

    def _token_problem(
        self,
        token: str | None,
        proposal_id: str,
        contents_sha256: str,
        now: datetime,
        nonce_used: Callable[[str], bool],
    ) -> str | None:
        claims = self.signer.read(token) if token else None
        if claims is None:
            return "This order needs your confirmation."
        checks = (
            (
                (claims.proposal_id, claims.content_hash) != (proposal_id, contents_sha256),
                "This confirmation was for a different plan.",
            ),
            (now >= claims.expires_at, "This confirmation has expired."),
            (nonce_used(claims.nonce), "This confirmation was already used."),
        )
        return next((why for broken, why in checks if broken), None)

    def cooling_off(self, sell_usd: Money, portfolio_usd: Money, drawdown_pct: float) -> Decision:
        """COOL-01: a big sale in a big drop waits, then asks again."""
        rule = self.rules.cool_01
        if not needs_cooling_off(
            sell_usd=sell_usd,
            portfolio_usd=portfolio_usd,
            drawdown=drawdown_pct,
            drawdown_pct_limit=rule.drawdown_pct,
            sell_share_pct_limit=rule.sell_share_pct,
        ):
            return ALLOW
        return Decision(
            False,
            "COOL-01",
            f"This fund is {drawdown_pct:.0f}% below its high. Selling now locks in the drop, "
            f"so big sales wait {rule.cooling_off_hours:g} hours. I'll ask you again then.",
        )

    def language(self, text: str) -> list[str]:
        """LANG-*: return the IDs of every rule the reply breaks."""
        return [rule_id for rule_id, pattern in self._lang if pattern.search(text)]
