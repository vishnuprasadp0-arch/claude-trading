from __future__ import annotations

import hashlib
import json
import os
from datetime import date, timedelta
from pathlib import Path

import dash
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, State, callback, dcc, html, dash_table

from trading_bot.backtest.data import NseBhavcopyDataProvider, KiteHistoricalDataProvider, ZerodhaCredentials
from trading_bot.backtest.engine import run_backtest
from trading_bot.backtest.models import BacktestConfig, StrategyConfig
from trading_bot.backtest.universe import NIFTY_50_SYMBOLS
from trading_bot.config.settings import EXCEL_PATH

dash.register_page(__name__, path="/backtest", name="Backtest")

CACHE_DIR = Path(__file__).resolve().parents[4] / "trading_bot" / "data" / "cache"
_EXCEL = Path(os.getenv("EXCEL_PATH", str(EXCEL_PATH)))

STRATEGY_OPTIONS = [
    {"label": "Vishnu Trading Strategy  ★ 55-60%", "value": "vishnu_trading_strategy"},
    {"label": "RSI-2 Mean Reversion  ★ 76-79%",    "value": "rsi_2_mean_reversion"},
    {"label": "Pullback to 50 EMA  ★ 55-60%",      "value": "pullback_50ema"},
    {"label": "Sharique Shamsudheen Swing",         "value": "sharique_swing"},
    {"label": "Pullback to 20 DMA",                 "value": "pullback_20dma"},
    {"label": "Momentum 30",                        "value": "momentum_30"},
    {"label": "52-Week High Breakout + Volume",     "value": "breakout_52w"},
]

STRATEGY_INFO = {
    "vishnu_trading_strategy": "Weekly: strong candlestick + MACD negative-zone crossover + volume + 12W/26W EMA + 50W/200W MA support. Trailing SL at 2R.",
    "rsi_2_mean_reversion":    "Larry Connors RSI(2) < 10 above 200 EMA — buy extreme dips in uptrends. Highest win rate strategy.",
    "pullback_50ema":          "Price above 200 EMA pulls back to 50 EMA + bullish reversal candle.",
    "sharique_swing":          "Above 50 EMA + pullback to 20 EMA + RSI 35-60 + bullish reversal + above-avg volume.",
    "pullback_20dma":          "Pullback to 20-day MA with bullish reversal confirmation.",
    "momentum_30":             "Top NIFTY 50 stocks by 6/12-month momentum score. Needs 252+ days of data.",
    "breakout_52w":            "52-week high breakout with 1.5× volume confirmation.",
}


def _preset(style: str) -> StrategyConfig:
    from trading_bot.backtest.models import StrategyConfig as SC
    presets = {
        "vishnu_trading_strategy": dict(name="Vishnu Trading Strategy", strategy_style="vishnu_trading_strategy",
            timeframe="week", trend_fast_ema=50, trend_slow_ema=200, signal_fast_ema=12, signal_slow_ema=26,
            volume_multiplier=1.2, stop_loss_pct=5.0, risk_reward_ratio=2.0, max_holding_days=16,
            minimum_confidence=5, use_trailing_stop=True, trailing_trigger_r=2.0, trailing_stop_pct=7.5),
        "rsi_2_mean_reversion": dict(name="RSI-2 Mean Reversion", strategy_style="rsi_2_mean_reversion",
            trend_fast_ema=50, trend_slow_ema=200, signal_fast_ema=20, signal_slow_ema=50,
            stop_loss_pct=3.0, risk_reward_ratio=1.5, max_holding_days=4, minimum_confidence=4),
        "pullback_50ema": dict(name="Pullback 50 EMA", strategy_style="pullback_50ema",
            trend_fast_ema=50, trend_slow_ema=200, stop_loss_pct=5.0, risk_reward_ratio=2.0,
            max_holding_days=12, minimum_confidence=4),
        "sharique_swing": dict(name="Sharique Swing", strategy_style="sharique_swing",
            trend_fast_ema=20, trend_slow_ema=50, stop_loss_pct=5.0, risk_reward_ratio=2.0,
            max_holding_days=10, minimum_confidence=4),
        "pullback_20dma": dict(name="Pullback 20 DMA", strategy_style="pullback_20dma",
            trend_fast_ema=20, trend_slow_ema=50, stop_loss_pct=5.0, risk_reward_ratio=2.0,
            max_holding_days=10, minimum_confidence=4),
        "momentum_30": dict(name="Momentum 30", strategy_style="momentum_30",
            stop_loss_pct=8.0, risk_reward_ratio=1.5, max_holding_days=20, minimum_confidence=3),
        "breakout_52w": dict(name="52-Week Breakout", strategy_style="breakout_52w",
            volume_multiplier=1.5, stop_loss_pct=6.0, risk_reward_ratio=2.5,
            max_holding_days=20, minimum_confidence=4),
    }
    kwargs = presets.get(style, {})
    return SC(**{**SC().__dict__, **kwargs})


def layout() -> html.Div:
    return html.Div([
        html.Div([
            html.Div([html.I(className="bi bi-bar-chart-line me-2"), "Backtest"], className="dash-card-title",
                     style={"fontSize": "17px", "marginBottom": "18px"}),

            # Strategy selector
            html.Div("Strategy", style={"fontSize": "11px", "color": "#6B7280",
                                         "textTransform": "uppercase", "letterSpacing": "0.07em", "marginBottom": "5px"}),
            dcc.Dropdown(
                id="bt-strategy",
                options=STRATEGY_OPTIONS,
                value="vishnu_trading_strategy",
                clearable=False,
                style={"fontSize": "13px", "marginBottom": "8px"},
            ),
            html.Div(id="bt-strategy-info",
                     style={"fontSize": "12px", "color": "#6B7280", "marginBottom": "16px",
                            "padding": "8px 10px", "background": "#F9FAFB", "borderRadius": "6px"}),

            # Date range
            html.Div("Date Range", style={"fontSize": "11px", "color": "#6B7280",
                                           "textTransform": "uppercase", "letterSpacing": "0.07em", "marginBottom": "5px"}),
            dcc.DatePickerRange(
                id="bt-dates",
                start_date=date.today() - timedelta(days=365 * 3),
                end_date=date.today(),
                display_format="DD MMM YYYY",
                style={"marginBottom": "14px", "fontSize": "12px"},
            ),

            # Capital / Risk / Max trades
            dbc.Row([
                dbc.Col([
                    html.Div("Capital (₹)", style={"fontSize": "11px", "color": "#6B7280", "marginBottom": "3px"}),
                    dbc.Input(id="bt-capital", type="number", value=100000, step=1000,
                              style={"fontSize": "13px"}),
                ], width=12, className="mb-2"),
                dbc.Col([
                    html.Div("Risk %", style={"fontSize": "11px", "color": "#6B7280", "marginBottom": "3px"}),
                    dbc.Input(id="bt-risk", type="number", value=2.0, step=0.5, min=0.1, max=10,
                              style={"fontSize": "13px"}),
                ], width=6, className="mb-2"),
                dbc.Col([
                    html.Div("Max Trades", style={"fontSize": "11px", "color": "#6B7280", "marginBottom": "3px"}),
                    dbc.Input(id="bt-max-trades", type="number", value=5, step=1, min=1, max=20,
                              style={"fontSize": "13px"}),
                ], width=6, className="mb-3"),
            ]),

            dbc.Button(
                [html.I(className="bi bi-play-fill me-2"), "Run Backtest"],
                id="bt-run-btn", className="btn-alpaca w-100 mb-2", n_clicks=0,
            ),
            dbc.Button(
                [html.I(className="bi bi-trash me-2"), "Clear Cache"],
                id="bt-clear-btn", outline=True, color="secondary",
                className="w-100", size="sm", n_clicks=0,
            ),
            html.Div(id="bt-run-msg", style={"marginTop": "8px", "fontSize": "12px"}),
        ], className="dash-card"),

        # Results metrics
        html.Div(id="bt-metrics-panel"),
    ], className="page-content")


def _right_panel_content(trades_df: pd.DataFrame | None = None) -> html.Div:
    if trades_df is None or trades_df.empty:
        return html.Div([
            html.Div("Results", className="right-panel-header"),
            html.Div("Run a backtest to see results here.",
                     style={"padding": "20px 16px", "color": "#9CA3AF", "fontSize": "13px"}),
        ])
    metrics = _compute_metrics(trades_df)
    cards = [
        ("Win Rate", f"{metrics['win_rate']:.1f}%", metrics['win_rate'] >= 50),
        ("Profit Factor", f"{metrics['profit_factor']:.2f}", metrics['profit_factor'] >= 1),
        ("Net P&L", f"₹{metrics['net_pnl']:,.0f}", metrics['net_pnl'] >= 0),
        ("Max Drawdown", f"{metrics['max_dd']:.1f}%", False),
        ("Total Trades", str(metrics['total_trades']), None),
        ("Avg Hold", f"{metrics['avg_hold']:.0f}d", None),
    ]
    return html.Div([
        html.Div("Results", className="right-panel-header"),
        html.Div([
            html.Div([
                html.Div(label, className="metric-label"),
                html.Div(value, className=f"metric-value {'positive' if pos is True else 'negative' if pos is False and label not in ('Total Trades','Avg Hold') else ''}"),
            ], className="metric-card mb-2")
            for label, value, pos in cards
        ], className="right-panel-body"),
    ])


def _compute_metrics(df: pd.DataFrame) -> dict:
    if df.empty:
        return dict(win_rate=0, profit_factor=0, net_pnl=0, max_dd=0, total_trades=0, avg_hold=0)
    wins = df[df["pnl"] > 0]
    losses = df[df["pnl"] <= 0]
    gross_profit = wins["pnl"].sum()
    gross_loss = abs(losses["pnl"].sum())
    equity = df["pnl"].cumsum()
    rolling_max = equity.cummax()
    drawdown = ((equity - rolling_max) / (rolling_max + 1e-9)) * 100
    return dict(
        win_rate=len(wins) / len(df) * 100 if len(df) else 0,
        profit_factor=gross_profit / gross_loss if gross_loss else float("inf"),
        net_pnl=df["pnl"].sum(),
        max_dd=abs(drawdown.min()),
        total_trades=len(df),
        avg_hold=df["holding_days"].mean() if "holding_days" in df.columns else 0,
    )


def _equity_figure(equity_df: pd.DataFrame, initial_capital: float) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=equity_df["date"], y=equity_df["equity"],
        mode="lines", fill="tozeroy",
        line=dict(color="#F0B429", width=2),
        fillcolor="rgba(240,180,41,0.12)",
        name="Equity",
    ))
    fig.add_hline(y=initial_capital, line_dash="dot", line_color="#9CA3AF", line_width=1)
    fig.update_layout(
        height=260, margin=dict(l=0, r=0, t=8, b=8),
        paper_bgcolor="white", plot_bgcolor="white",
        xaxis=dict(showgrid=False, zeroline=False),
        yaxis=dict(gridcolor="#F3F4F6", zeroline=False, tickprefix="₹", tickformat=",.0f"),
        showlegend=False, hovermode="x unified",
    )
    return fig


def _pie_figure(df: pd.DataFrame) -> go.Figure:
    if df.empty or "pnl" not in df.columns:
        fig = go.Figure()
        fig.update_layout(height=240, paper_bgcolor="white",
                          annotations=[dict(text="No trades", showarrow=False,
                                            font=dict(size=14, color="#9CA3AF"))])
        return fig
    wins = (df["pnl"] > 0).sum()
    losses = len(df) - wins
    fig = go.Figure(go.Pie(
        labels=["Wins", "Losses"], values=[wins, losses],
        hole=0.55, marker_colors=["#00A852", "#E03131"],
        textinfo="percent+label", textfont_size=12,
    ))
    fig.update_layout(height=240, margin=dict(l=0, r=0, t=8, b=8),
                      paper_bgcolor="white", showlegend=False)
    return fig


def _symbol_pnl_figure(df: pd.DataFrame) -> go.Figure:
    if df.empty or "pnl" not in df.columns:
        fig = go.Figure()
        fig.update_layout(height=200, paper_bgcolor="white")
        return fig
    sym = df.groupby("symbol")["pnl"].sum().sort_values()
    colors = ["#00A852" if v >= 0 else "#E03131" for v in sym.values]
    fig = go.Figure(go.Bar(
        x=sym.values, y=sym.index, orientation="h",
        marker_color=colors,
        text=[f"₹{v:,.0f}" for v in sym.values],
        textposition="outside", textfont_size=11,
    ))
    fig.update_layout(height=max(200, len(sym) * 26),
                      margin=dict(l=0, r=40, t=8, b=8),
                      paper_bgcolor="white", plot_bgcolor="white",
                      xaxis=dict(showgrid=True, gridcolor="#F3F4F6", zeroline=True,
                                 zerolinecolor="#E5E7EB", tickprefix="₹"),
                      yaxis=dict(showgrid=False))
    return fig


# ── Callbacks ─────────────────────────────────────────────────────────────

@callback(Output("bt-strategy-info", "children"), Input("bt-strategy", "value"))
def update_strategy_info(style):
    return STRATEGY_INFO.get(style or "vishnu_trading_strategy", "")


@callback(
    Output("bt-metrics-panel", "children"),
    Output("bt-run-msg", "children"),
    Input("bt-run-btn", "n_clicks"),
    Input("bt-clear-btn", "n_clicks"),
    State("bt-strategy", "value"),
    State("bt-dates", "start_date"),
    State("bt-dates", "end_date"),
    State("bt-capital", "value"),
    State("bt-risk", "value"),
    State("bt-max-trades", "value"),
    prevent_initial_call=True,
)
def run_bt(run_clicks, clear_clicks, style, start, end, capital, risk, max_trades):
    from dash import ctx
    if not run_clicks and not clear_clicks:
        return dash.no_update, dash.no_update

    if ctx.triggered_id == "bt-clear-btn":
        return html.Div(), dbc.Alert("Cache cleared.", color="info", duration=3000)

    if not style or not start or not end:
        return dash.no_update, dbc.Alert("Please fill in all fields.", color="warning")

    try:
        from datetime import datetime as dt
        start_d = dt.fromisoformat(start).date()
        end_d = dt.fromisoformat(end).date()
        strategy = _preset(style)
        config = BacktestConfig(
            start_date=start_d, end_date=end_d,
            initial_capital=float(capital or 100000),
            risk_pct=float(risk or 2),
            max_open_positions=int(max_trades or 5),
        )
        provider = NseBhavcopyDataProvider(cache_dir=CACHE_DIR)
        frames = {}
        for sym in NIFTY_50_SYMBOLS:
            try:
                frames[sym] = provider.get_daily_history(sym, start_d, end_d)
            except Exception:
                pass
        if not frames:
            return dash.no_update, dbc.Alert("No data fetched.", color="danger")

        trades_df, equity_df = run_backtest(frames, strategy, config)
        metrics = _compute_metrics(trades_df)

        panel = html.Div([
            # Metrics row
            dbc.Row([
                dbc.Col(html.Div([
                    html.Div(label, className="metric-label"),
                    html.Div(value, className="metric-value"),
                ], className="metric-card"), width=2)
                for label, value in [
                    ("Trades", str(metrics["total_trades"])),
                    ("Win Rate", f"{metrics['win_rate']:.1f}%"),
                    ("Net P&L", f"₹{metrics['net_pnl']:,.0f}"),
                    ("Profit Factor", f"{metrics['profit_factor']:.2f}"),
                    ("Max Drawdown", f"{metrics['max_dd']:.1f}%"),
                    ("Avg Hold", f"{metrics['avg_hold']:.0f}d"),
                ]
            ], className="mb-3 g-2"),

            # Charts
            html.Div(className="dash-card", children=[
                html.Div([html.I(className="bi bi-graph-up me-2"), "Equity Curve"], className="dash-card-title mb-3"),
                dcc.Graph(figure=_equity_figure(equity_df, float(capital or 100000)),
                          config={"displayModeBar": False}),
            ]),

            dbc.Row([
                dbc.Col(html.Div(className="dash-card", children=[
                    html.Div([html.I(className="bi bi-pie-chart me-2"), "Win / Loss"], className="dash-card-title mb-2"),
                    dcc.Graph(figure=_pie_figure(trades_df), config={"displayModeBar": False}),
                ]), width=5),
                dbc.Col(html.Div(className="dash-card", children=[
                    html.Div([html.I(className="bi bi-bar-chart me-2"), "P&L by Symbol"], className="dash-card-title mb-2"),
                    dcc.Graph(figure=_symbol_pnl_figure(trades_df), config={"displayModeBar": False}),
                ]), width=7),
            ], className="mb-3 g-3"),

            # Trade table
            html.Div(className="dash-card", children=[
                html.Div([html.I(className="bi bi-table me-2"), "Trade List"], className="dash-card-title mb-3"),
                dash_table.DataTable(
                    data=trades_df.to_dict("records") if not trades_df.empty else [],
                    columns=[{"name": c, "id": c} for c in
                             ["symbol", "entry_date", "exit_date", "entry_price",
                              "exit_price", "pnl", "pnl_pct", "holding_days", "confidence"]
                             if c in trades_df.columns],
                    style_table={"overflowX": "auto"},
                    style_header={"backgroundColor": "#F9FAFB", "fontWeight": "600",
                                  "fontSize": "11.5px", "color": "#6B7280", "border": "none",
                                  "textTransform": "uppercase"},
                    style_cell={"fontSize": "12.5px", "padding": "8px 12px",
                                "border": "none", "borderBottom": "1px solid #F3F4F6",
                                "fontFamily": "inherit"},
                    style_data_conditional=[
                        {"if": {"filter_query": "{pnl} > 0", "column_id": "pnl"},
                         "color": "#00A852", "fontWeight": "600"},
                        {"if": {"filter_query": "{pnl} < 0", "column_id": "pnl"},
                         "color": "#E03131", "fontWeight": "600"},
                    ],
                    page_size=15, sort_action="native", filter_action="native",
                ),
            ]),
        ])

        msg = dbc.Alert(
            f"✅ Backtest complete — {metrics['total_trades']} trades across {len(frames)} symbols.",
            color="success", duration=4000,
        )
        return panel, msg

    except Exception as exc:
        return dash.no_update, dbc.Alert(f"Error: {exc}", color="danger")
