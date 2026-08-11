"""Test suite for the transversal risk state machine."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.risk.models import PositionRiskState, RiskManagementConfig, MarketSnapshot
from app.risk.state_machine import (
    STATE_START,
    STATE_BREAKEVEN,
    STATE_TRAILING,
    compute_risk_from_price,
    effective_price,
    compute_trailing_sl,
    evaluate,
)

CONFIG = RiskManagementConfig()


def buy_state(state=STATE_START, **kw):
    d = dict(position_id=1, user_id="u", entry_price=1.0500,
             sl_original=1.0450, tp_fixed=1.0600, is_buy=True, state=state)
    d.update(kw)
    return PositionRiskState(**d)


def sell_state(state=STATE_START, **kw):
    d = dict(position_id=2, user_id="u", entry_price=1.0500,
             sl_original=1.0550, tp_fixed=1.0400, is_buy=False, state=state)
    d.update(kw)
    return PositionRiskState(**d)


def snap(rate, high=None, low=None, atr=None, ask=None, bid=None):
    return MarketSnapshot(current_rate=rate, candle_high=high, candle_low=low,
                          atr=atr, ask=ask, bid=bid)


def test_risk_uses_original_sl():
    s = buy_state(STATE_BREAKEVEN, sl_current=1.0501)
    assert round(compute_risk_from_price(s, 1.0575), 4) == 1.5
    assert round(compute_risk_from_price(s, 1.0600), 4) == 2.0


def test_effective_price_uses_high():
    s = buy_state()
    assert effective_price(s, snap(1.0525, high=1.0575)) == 1.0575


def test_state_start_to_breakeven():
    s = buy_state()
    d = evaluate(s, snap(1.0550, ask=1.0551, bid=1.0549), CONFIG)
    assert d is not None
    assert d.new_state == STATE_BREAKEVEN
    assert round(d.new_stop_loss, 4) == 1.0502


def test_state_breakeven_to_trailing():
    s = buy_state(STATE_BREAKEVEN, sl_current=1.0502, spread_real=0.0002)
    d = evaluate(s, snap(1.0575, atr=0.0008), CONFIG)
    assert d is not None
    assert d.new_state == STATE_TRAILING
    assert d.remove_take_profit is True
    assert d.new_stop_loss == 1.0550


def test_trailing_never_retrocedes():
    s = buy_state(STATE_TRAILING, sl_current=1.0560, highest_price=1.0580)
    assert round(compute_trailing_sl(s, snap(1.0580, atr=0.002), CONFIG), 4) == 1.0560


def test_atr_none_keeps_hito2():
    s = buy_state(STATE_TRAILING, sl_current=1.0550, highest_price=1.0600)
    assert round(compute_trailing_sl(s, snap(1.0600, atr=None), CONFIG), 4) == 1.0550


def test_sell_symmetry():
    s = sell_state(STATE_BREAKEVEN, sl_current=1.0498, spread_real=0.0002)
    d = evaluate(s, snap(1.0425, atr=0.0008), CONFIG)
    assert d is not None
    assert d.new_state == STATE_TRAILING
    assert round(d.new_stop_loss, 4) == 1.0450


def test_trailing_improves_sell():
    s = sell_state(STATE_TRAILING, sl_current=1.0450, lowest_price=1.0420)
    assert round(compute_trailing_sl(s, snap(1.0420, atr=0.0008), CONFIG), 5) == 1.04296


def test_min_spacing_no_decision():
    cfg = RiskManagementConfig(min_sl_update_spacing_pips=1.0)
    s = buy_state(STATE_TRAILING, sl_current=1.0565, highest_price=1.0570)
    assert evaluate(s, snap(1.0570, atr=0.0004), cfg) is None


if __name__ == "__main__":
    tests = [
        test_risk_uses_original_sl,
        test_effective_price_uses_high,
        test_state_start_to_breakeven,
        test_state_breakeven_to_trailing,
        test_trailing_never_retrocedes,
        test_atr_none_keeps_hito2,
        test_sell_symmetry,
        test_trailing_improves_sell,
        test_min_spacing_no_decision,
    ]
    passed = 0
    for i, t in enumerate(tests, 1):
        print(f"[{i}/{len(tests)}] {t.__name__}...")
        t()
        passed += 1
        print()
    print(f"All {passed}/{len(tests)} tests passed!")