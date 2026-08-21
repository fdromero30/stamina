"""Tests for dynamic pip-size calculation."""

from app.bot.pip_size import calculate_pip_size, infer_pip_size_from_candles
from app.bot.signals import Candle


def test_eurusd_5_decimals_gives_00001():
    prices = [1.15743, 1.15744, 1.15713, 1.15752]
    assert calculate_pip_size(prices) == 0.0001


def test_gold_2_decimals_gives_001():
    prices = [4406.17, 4406.71, 4399.26, 4399.76]
    assert calculate_pip_size(prices) == 0.01


def test_jpy_3_decimals_gives_001():
    prices = [151.342, 151.355, 151.320, 151.310]
    assert calculate_pip_size(prices) == 0.01


def test_insufficient_samples_falls_back_to_default():
    # Only 2 samples → not enough to trust → default 0.0001
    assert calculate_pip_size([1.15743, 1.15744]) == 0.0001


def test_empty_sample_falls_back_to_default():
    assert calculate_pip_size([]) == 0.0001


def test_infer_from_candles():
    candles = [
        Candle(open=4406.17, high=4406.71, low=4399.26, close=4399.76),
        Candle(open=4409.13, high=4409.69, low=4404.83, close=4406.24),
        Candle(open=4414.93, high=4415.32, low=4409.05, close=4409.13),
    ]
    assert infer_pip_size_from_candles(candles) == 0.01