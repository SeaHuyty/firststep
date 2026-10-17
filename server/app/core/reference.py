"""Load the read-only reference data in data/ into frozen models.

Every file is validated once at start-up, so a typo in a rule or a
portfolio fails loudly instead of reaching a user. The engine never
reads files itself; callers pass it values from these models.
"""

import csv
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.types import AssetClass, ClientClassField, RiskRatingField, Stage


class Frozen(BaseModel):
    """Base for reference models: immutable, no unknown keys."""

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)


# --- rules.yaml


class RuleInfo(Frozen):
    """Fields every rule carries for the docs and the UI."""

    title: str
    description: str
    cites: tuple[str, ...] = ()


class SuitabilityRule(RuleInfo):
    """SUIT-01."""

    max_rating_for_class: dict[ClientClassField, RiskRatingField]


class EmergencyRule(RuleInfo):
    """READY-01."""

    min_emergency_months: float = Field(gt=0)


class DebtRule(RuleInfo):
    """READY-02."""

    max_apr_pct: float = Field(gt=0)


class HorizonCap(Frozen):
    """One HOR-01 band: goals under `under_years` cap the class."""

    under_years: float = Field(gt=0)
    max_class: ClientClassField


class HorizonRule(RuleInfo):
    """HOR-01."""

    caps: tuple[HorizonCap, ...]


class ConcentrationRule(RuleInfo):
    """CONC-01."""

    max_product_pct: float = Field(gt=0, le=100)
    max_equity_class_pct: float = Field(gt=0, le=100)
    exempt_classes: tuple[ClientClassField, ...] = ()


class LimitRule(RuleInfo):
    """LIM-01."""

    max_order_usd: float = Field(gt=0)
    max_daily_usd: float = Field(gt=0)


class ConfirmRule(RuleInfo):
    """CONF-01."""

    token_ttl_minutes: float = Field(gt=0)


class CoolingOffRule(RuleInfo):
    """COOL-01."""

    drawdown_pct: float = Field(gt=0)
    sell_share_pct: float = Field(gt=0)
    cooling_off_hours: float = Field(gt=0)


class DriftRule(RuleInfo):
    """DRIFT-01."""

    max_drift_pts: float = Field(gt=0)


class StageRule(RuleInfo):
    """STAGE-01."""

    allowed: dict[Stage, tuple[str, ...]]


class TierTable(RuleInfo):
    """Permission tier per tool."""

    tier_of: dict[str, Literal[0, 1, 2, 3]]


class LangRule(Frozen):
    """One LANG-* output-filter rule."""

    id: str = Field(pattern=r"^LANG-\d{2}$")
    title: str
    patterns: tuple[str, ...]


class LangPolicy(RuleInfo):
    """All LANG-* rules."""

    rules: tuple[LangRule, ...]


class RuleBook(Frozen):
    """Every guardrail in data/rules.yaml, keyed by rule ID."""

    version: int
    suit_01: SuitabilityRule = Field(alias="SUIT-01")
    ready_01: EmergencyRule = Field(alias="READY-01")
    ready_02: DebtRule = Field(alias="READY-02")
    hor_01: HorizonRule = Field(alias="HOR-01")
    conc_01: ConcentrationRule = Field(alias="CONC-01")
    lim_01: LimitRule = Field(alias="LIM-01")
    conf_01: ConfirmRule = Field(alias="CONF-01")
    cool_01: CoolingOffRule = Field(alias="COOL-01")
    drift_01: DriftRule = Field(alias="DRIFT-01")
    stage_01: StageRule = Field(alias="STAGE-01")
    tiers: TierTable = Field(alias="TIERS")
    lang: LangPolicy = Field(alias="LANG")

    @model_validator(mode="after")
    def _stage_tools_have_tiers(self) -> "RuleBook":
        unknown = {t for tools in self.stage_01.allowed.values() for t in tools} - set(
            self.tiers.tier_of
        )
        if unknown:
            raise ValueError(f"STAGE-01 lists tools without a tier: {sorted(unknown)}")
        return self


# --- products.csv, portfolios.yaml


class Product(Frozen):
    """One fictional fund on the shelf."""

    id: str
    name: str
    asset_class: AssetClass
    risk_rating: RiskRatingField
    ter_pct: float = Field(ge=0, le=5)
    min_investment_usd: float = Field(ge=0)
    liquidity_days: int = Field(ge=0)
    description: str


class ModelPortfolio(Frozen):
    """Target weights for one client class, percent per product."""

    label: str
    summary: str
    weights: dict[str, float]

    @model_validator(mode="after")
    def _sums_to_100(self) -> "ModelPortfolio":
        total = sum(self.weights.values())
        if abs(total - 100) > 1e-9:
            raise ValueError(f"weights sum to {total}, not 100")
        return self


# --- questionnaire.yaml


class Option(Frozen):
    """One quick-reply chip."""

    label: str
    value: Any  # number, string or list, depending on the question kind
    score: int | None = Field(default=None, ge=1, le=5)


class Question(Frozen):
    """One question Sprout asks."""

    id: str
    stage: Stage
    field: str
    kind: Literal["number", "money", "choice", "debts"]
    prompt: str
    why: str
    scale: Literal["tolerance", "capacity"] | None = None
    min: float | None = None
    max: float | None = None
    options: tuple[Option, ...] = ()


class AgeBand(Frozen):
    """Capacity score for ages below `under`."""

    under: int
    score: int = Field(ge=1, le=5)


class Questionnaire(Frozen):
    """The full question list and the age bands for capacity."""

    version: int
    questions: tuple[Question, ...]
    capacity_by_age: tuple[AgeBand, ...]


# --- glossary.yaml, personas.yaml


class Source(Frozen):
    """A citable public page."""

    title: str
    publisher: str
    url: str


class Term(Frozen):
    """One glossary entry."""

    term: str
    text: str
    source: str


class Glossary(Frozen):
    """Fixed definitions for the explain tool."""

    version: int
    sources: dict[str, Source]
    terms: dict[str, Term]

    @model_validator(mode="after")
    def _sources_exist(self) -> "Glossary":
        missing = {t.source for t in self.terms.values()} - set(self.sources)
        if missing:
            raise ValueError(f"unknown glossary sources: {sorted(missing)}")
        return self


class Debt(Frozen):
    """One debt the client owes."""

    kind: str
    balance_usd: float = Field(ge=0)
    apr_pct: float = Field(ge=0, le=100)


class PersonaGoal(Frozen):
    """A demo persona's investing goal."""

    name: str
    target_usd: float
    horizon_years: float
    lump_sum_usd: float
    monthly_usd: float


class Persona(Frozen):
    """A scripted demo person."""

    name: str
    tagline: str
    sim_start: str = Field(pattern=r"^\d{4}-\d{2}$")
    answers: dict[str, Any]
    goal: PersonaGoal | None = None
    opening_line: str


class Personas(Frozen):
    """All demo personas."""

    version: int
    personas: dict[str, Persona]


# --- returns.csv


class Returns(Frozen):
    """Monthly total returns per asset class, aligned by month."""

    months: tuple[str, ...]
    series: dict[AssetClass, tuple[float, ...]]

    def index_of(self, month: str) -> int:
        """Return the position of a "YYYY-MM" month."""
        return self.months.index(month)


# --- everything


class Reference(Frozen):
    """All reference data, validated together."""

    rules: RuleBook
    products: dict[str, Product]
    portfolios: dict[ClientClassField, ModelPortfolio]
    questionnaire: Questionnaire
    glossary: Glossary
    personas: Personas
    returns: Returns

    @model_validator(mode="after")
    def _portfolios_use_known_products(self) -> "Reference":
        for cls, portfolio in self.portfolios.items():
            unknown = set(portfolio.weights) - set(self.products)
            if unknown:
                raise ValueError(f"{cls} portfolio uses unknown products: {sorted(unknown)}")
        return self


def _yaml(path: Path) -> Any:  # noqa: ANN401 (YAML is untyped until validated)
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def _products(path: Path) -> dict[str, Product]:
    with path.open(encoding="utf-8", newline="") as f:
        return {row["id"]: Product.model_validate(row) for row in csv.DictReader(f)}


def _returns(path: Path) -> Returns:
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    return Returns(
        months=tuple(r["month"] for r in rows),
        series={a: tuple(float(r[a.value]) for r in rows) for a in AssetClass},
    )


@lru_cache
def load_reference(data_dir: Path) -> Reference:
    """Return every data file in data_dir, validated and frozen."""
    return Reference(
        rules=RuleBook.model_validate(_yaml(data_dir / "rules.yaml")),
        products=_products(data_dir / "products.csv"),
        portfolios=_yaml(data_dir / "portfolios.yaml")["portfolios"],
        questionnaire=Questionnaire.model_validate(_yaml(data_dir / "questionnaire.yaml")),
        glossary=Glossary.model_validate(_yaml(data_dir / "glossary.yaml")),
        personas=Personas.model_validate(_yaml(data_dir / "personas.yaml")),
        returns=_returns(data_dir / "returns.csv"),
    )
