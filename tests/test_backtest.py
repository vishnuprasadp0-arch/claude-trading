from datetime import date, timedelta
import unittest

import pandas as pd

from trading_bot.backtest.engine import run_backtest
from trading_bot.backtest.models import BacktestConfig, StrategyConfig


class BacktestEngineTests(unittest.TestCase):
    def test_backtest_generates_trade_records(self):
        start = date(2023, 1, 1)
        rows = []
        price = 100.0
        for offset in range(260):
            current = start + timedelta(days=offset)
            drift = 0.4 if offset > 180 else 0.1
            open_price = price + 0.2
            close_price = price + drift
            high_price = close_price + 1.0
            low_price = open_price - 0.8
            volume = 1000 + (offset * 10)
            rows.append({
                "date": pd.Timestamp(current),
                "open": round(open_price, 2),
                "high": round(high_price, 2),
                "low": round(low_price, 2),
                "close": round(close_price, 2),
                "volume": volume,
            })
            price = close_price

        config = StrategyConfig(
            trend_fast_ema=20,
            trend_slow_ema=50,
            signal_fast_ema=5,
            signal_slow_ema=10,
            support_window=10,
            support_threshold_pct=10.0,
            volume_multiplier=0.8,
            stop_loss_pct=3.0,
            risk_reward_ratio=1.5,
            max_holding_days=5,
            minimum_confidence=3,
            require_support_bounce=False,
            require_bullish_reversal=False,
        )
        backtest = BacktestConfig(
            start_date=start,
            end_date=start + timedelta(days=259),
            initial_capital=25000.0,
            risk_pct=2.0,
            max_open_positions=5,
        )
        trades_df, equity_df = run_backtest({"TEST": pd.DataFrame(rows)}, config, backtest)
        self.assertFalse(trades_df.empty)
        self.assertIn("symbol", trades_df.columns)
        self.assertIn("equity", equity_df.columns)


if __name__ == "__main__":
    unittest.main()
