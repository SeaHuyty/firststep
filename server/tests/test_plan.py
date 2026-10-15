import itertools

import pytest

from app.domain.catalog import PRODUCTS, group_of
from app.domain.plan import allocate_pct, analyse, apply_targets, limits, project, valid_pct
from app.domain.schemas import BUCKETS, Profile

PROFILES = [
    Profile(amount=10000, goal="wealth", horizon=h, emergency=e, debt=d, risk=r)
    for h, e, d, r in itertools.product([1, 3, 7, 12], ["none", "insufficient", "enough"], ["none", "some", "significant"], [1, 2, 3])
]


def find(**kw) -> Profile:
    return next(p for p in PROFILES if all(getattr(p, k) == v for k, v in kw.items()))


def test_default_matches_known_values():
    # Same numbers the TypeScript prototype produced for these inputs.
    p = Profile(amount=10000, goal="wealth", horizon=7, emergency="insufficient", debt="none", risk=2)
    assert allocate_pct(p) == {"emergency": 20, "stocks": 32, "single": 8, "bonds": 23, "cash": 12, "alt": 5}


def test_default_sums_to_100_and_is_inside_limits_for_every_combination():
    assert len(PROFILES) == 108
    for p in PROFILES:
        pct = allocate_pct(p)
        assert sum(pct.values()) == 100
        assert all(v >= 0 for v in pct.values())
        assert valid_pct(p, pct)


def test_more_risk_means_more_stocks():
    def stocks(risk):
        return allocate_pct(find(horizon=7, emergency="enough", debt="none", risk=risk))["stocks"]

    assert stocks(1) < stocks(2) < stocks(3)


def test_missing_emergency_savings_means_bigger_emergency_fund():
    def em(e):
        return allocate_pct(find(horizon=7, emergency=e, debt="none", risk=2))["emergency"]

    assert em("none") > em("insufficient") > em("enough")


@pytest.mark.parametrize("target", [-10, 0, 17, 50, 100, 250])
def test_any_targets_stay_valid_and_sum_to_100(target):
    for p in PROFILES:
        for bucket in BUCKETS:
            pct, _ = apply_targets(p, allocate_pct(p), {bucket: target})
            assert valid_pct(p, pct)


def test_caps_stocks_and_never_cuts_emergency_fund_below_minimum():
    p = Profile(amount=10000, goal="wealth", horizon=1, emergency="none", debt="none", risk=1)
    more, notes = apply_targets(p, allocate_pct(p), {"stocks": 90})
    assert more["stocks"] == limits(p)["max"]["stocks"]
    assert notes
    less, _ = apply_targets(p, allocate_pct(p), {"emergency": 0})
    assert less["emergency"] == allocate_pct(p)["emergency"]


def test_increase_is_funded_from_untargeted_buckets_and_targets_stay_exact():
    p = find(risk=3, horizon=12, emergency="enough", debt="none")
    cur = allocate_pct(p)
    pct, _ = apply_targets(p, cur, {"stocks": cur["stocks"] - 5, "bonds": cur["bonds"] + 5})
    assert pct["stocks"] == cur["stocks"] - 5
    assert pct["bonds"] == cur["bonds"] + 5
    assert pct["cash"] == cur["cash"]


def test_valid_pct_rejects_bad_sum_and_out_of_limit():
    p = find(risk=1, horizon=7, emergency="enough", debt="none")
    good = allocate_pct(p)
    assert valid_pct(p, good)
    assert not valid_pct(p, {**good, "stocks": good["stocks"] + 1})  # sum != 100
    assert not valid_pct(p, {"emergency": 0, "stocks": 100, "single": 0, "bonds": 0, "cash": 0, "alt": 0})


def test_analyse_score_range_and_ordering():
    for p in PROFILES:
        assert 0 <= analyse(p)["score"] <= 100
    weak = analyse(find(emergency="none", debt="significant", horizon=1, risk=1))["score"]
    strong = analyse(find(emergency="enough", debt="none", horizon=12, risk=1))["score"]
    assert strong > weak


def test_projection_orders_scenarios_and_starts_at_deposit():
    low, base, high = project(10000, 100, 10, 2)
    assert low[0] == 10000 and len(low) == 11
    assert low[-1] <= base[-1] <= high[-1]


def test_projection_is_linear_at_zero_return():
    low, _, _ = project(1000, 100, 2, 2)  # moderate pessimistic rate is 0%
    assert low[-1] == 1000 + 100 * 24


def test_catalog_tickers_unique_and_map_to_group():
    tickers = [p.ticker for items in PRODUCTS.values() for p in items]
    assert len(set(tickers)) == len(tickers)
    assert all(group_of(t) is not None for t in tickers)
