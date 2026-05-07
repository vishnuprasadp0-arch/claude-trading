from __future__ import annotations

from pathlib import Path

import dash
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import Input, Output, State, callback, dcc, html, dash_table

from trading_bot.paper_trading.engine import PaperTradingEngine
from trading_bot.paper_trading.runner import (
    close_position, enter_signal_trade, get_latest_prices, scan_signals,
)
from trading_bot.backtest.data import NseBhavcopyDataProvider
from trading_bot.backtest.universe import NIFTY_50_SYMBOLS
from trading_bot.dashboard.dash_app.pages.backtest import _preset, STRATEGY_OPTIONS

dash.register_page(__name__, path="/paper", name="Paper Trading")

_CACHE_DIR = Path(__file__).resolve().parents[4] / "trading_bot" / "data" / "cache"
_engine = PaperTradingEngine()


def _provider() -> NseBhavcopyDataProvider:
    return NseBhavcopyDataProvider(cache_dir=_CACHE_DIR)


# ── Layout ────────────────────────────────────────────────────────────────

def layout() -> html.Div:
    portfolio = _engine.get_portfolio()
    return html.Div([
        # Info banner
        html.Div(
            [html.I(className="bi bi-info-circle me-2"),
             "Paper Trading — simulated orders only, no real money used."],
            className="info-banner",
        ),

        # ── Account Settings ──────────────────────────────────────────
        html.Div(className="dash-card", children=[
            html.Div(className="dash-card-header", children=[
                html.Div([html.I(className="bi bi-gear me-2"), "Account Settings"],
                         className="dash-card-title"),
                dbc.Button([html.I(className="bi bi-pencil me-1"), "Edit"],
                           id="settings-edit-btn", size="sm", outline=True,
                           color="secondary", n_clicks=0),
            ]),
            html.Div(id="settings-display", children=_settings_display()),
            html.Div(id="settings-edit-form", style={"display": "none"}, children=_settings_form()),
            html.Div(id="settings-msg"),
        ]),

        # ── Portfolio Summary ─────────────────────────────────────────
        dbc.Row([
            dbc.Col(_metric("Equity", f"₹{portfolio.equity:,.2f}", None), width=3),
            dbc.Col(_metric("Cash", f"₹{portfolio.cash:,.2f}", None), width=2),
            dbc.Col(_metric("Buying Power", f"₹{portfolio.buying_power:,.2f}", None), width=2),
            dbc.Col(_metric("Realized P&L",
                            f"₹{portfolio.realized_pnl:+,.2f}",
                            portfolio.realized_pnl >= 0), width=2),
            dbc.Col(_metric("Unrealized P&L",
                            f"₹{portfolio.unrealized_pnl:+,.2f}",
                            portfolio.unrealized_pnl >= 0), width=2),
            dbc.Col(_metric("Total P&L",
                            f"₹{portfolio.total_pnl:+,.2f} ({portfolio.total_pnl_pct:+.1f}%)",
                            portfolio.total_pnl >= 0), width=1),
        ], className="mb-3 g-2"),

        # ── Equity Curve ──────────────────────────────────────────────
        html.Div(className="dash-card", children=[
            html.Div(className="dash-card-header", children=[
                html.Div([html.I(className="bi bi-graph-up me-2"), "Portfolio Equity"],
                         className="dash-card-title"),
                dbc.Button([html.I(className="bi bi-arrow-clockwise")],
                           id="paper-equity-refresh", size="sm", outline=True,
                           color="secondary", n_clicks=0),
            ]),
            dcc.Graph(id="paper-equity-chart", figure=_equity_figure(),
                      config={"displayModeBar": False}),
        ]),

        # ── Open Positions ────────────────────────────────────────────
        html.Div(className="dash-card", children=[
            html.Div(className="dash-card-header", children=[
                html.Div([html.I(className="bi bi-briefcase me-2"), "Open Positions"],
                         className="dash-card-title"),
                dbc.Button([html.I(className="bi bi-arrow-clockwise me-1"), "Refresh"],
                           id="paper-pos-refresh", size="sm", outline=True,
                           color="secondary", n_clicks=0),
            ]),
            dcc.Loading(html.Div(id="paper-positions-div", children=_positions_table()), type="circle"),
            html.Div(id="paper-close-msg"),
        ]),

        # ── Recent Orders ─────────────────────────────────────────────
        html.Div(className="dash-card", children=[
            html.Div(className="dash-card-header", children=[
                html.Div([html.I(className="bi bi-clock-history me-2"), "Recent Orders"],
                         className="dash-card-title"),
            ]),
            html.Div(id="paper-orders-div", children=_orders_table()),
        ]),

        # ── Signal Scanner ────────────────────────────────────────────
        html.Div(className="dash-card", children=[
            html.Div(className="dash-card-header", children=[
                html.Div([html.I(className="bi bi-search me-2"), "Signal Scanner"],
                         className="dash-card-title"),
            ]),
            dbc.Row([
                dbc.Col([
                    html.Div("Strategy", style={"fontSize": "11px", "color": "#6B7280",
                                                 "textTransform": "uppercase", "marginBottom": "4px"}),
                    dcc.Dropdown(id="paper-strategy", options=STRATEGY_OPTIONS,
                                 value="vishnu_trading_strategy", clearable=False,
                                 style={"fontSize": "13px"}),
                ], width=5),
                dbc.Col([
                    html.Div("Lookback Days", style={"fontSize": "11px", "color": "#6B7280",
                                                      "textTransform": "uppercase", "marginBottom": "4px"}),
                    dbc.Input(id="paper-lookback", type="number", value=300,
                              min=100, max=500, style={"fontSize": "13px"}),
                ], width=3),
                dbc.Col([
                    html.Div(" ", style={"marginBottom": "4px", "fontSize": "11px"}),
                    dbc.Button([html.I(className="bi bi-search me-2"), "Scan for Signals"],
                               id="paper-scan-btn", className="btn-alpaca w-100", n_clicks=0),
                ], width=4),
            ], className="mb-3 g-2"),

            dcc.Loading(html.Div(id="paper-signals-div"), type="circle"),
            html.Div(id="paper-enter-msg"),
        ]),

        # Stores
        dcc.Store(id="paper-signals-store"),
        dcc.Interval(id="paper-price-interval", interval=300_000, n_intervals=0),
    ], className="page-content")


# ── UI helpers ────────────────────────────────────────────────────────────

def _metric(label: str, value: str, positive: bool | None) -> html.Div:
    color = ("#00A852" if positive else "#E03131") if positive is not None else "#1A1A2E"
    return html.Div([
        html.Div(label, className="metric-label"),
        html.Div(value, className="metric-value", style={"color": color, "fontSize": "16px"}),
    ], className="metric-card")


def _settings_display() -> html.Div:
    return html.Div([
        dbc.Row([
            dbc.Col([
                html.Span("Initial Capital: ", style={"color": "#6B7280", "fontSize": "13px"}),
                html.Span(f"₹{_engine.initial_capital:,.0f}",
                          style={"fontWeight": "600", "fontSize": "13px"}),
            ], width=4),
            dbc.Col([
                html.Span("Risk %: ", style={"color": "#6B7280", "fontSize": "13px"}),
                html.Span(f"{_engine.risk_pct:.1f}%",
                          style={"fontWeight": "600", "fontSize": "13px"}),
            ], width=3),
            dbc.Col([
                html.Span("Max Positions: ", style={"color": "#6B7280", "fontSize": "13px"}),
                html.Span(str(_engine.max_open_positions),
                          style={"fontWeight": "600", "fontSize": "13px"}),
            ], width=3),
        ]),
    ])


def _settings_form() -> html.Div:
    return html.Div([
        dbc.Row([
            dbc.Col([
                html.Div("Initial Capital (₹)", style={"fontSize": "11px", "color": "#6B7280", "marginBottom": "3px"}),
                dbc.Input(id="settings-capital", type="number",
                          value=_engine.initial_capital, step=1000, style={"fontSize": "13px"}),
            ], width=4),
            dbc.Col([
                html.Div("Risk % per trade", style={"fontSize": "11px", "color": "#6B7280", "marginBottom": "3px"}),
                dbc.Input(id="settings-risk", type="number",
                          value=_engine.risk_pct, step=0.5, min=0.1, max=10,
                          style={"fontSize": "13px"}),
            ], width=3),
            dbc.Col([
                html.Div("Max Open Positions", style={"fontSize": "11px", "color": "#6B7280", "marginBottom": "3px"}),
                dbc.Input(id="settings-max-pos", type="number",
                          value=_engine.max_open_positions, step=1, min=1, max=20,
                          style={"fontSize": "13px"}),
            ], width=3),
            dbc.Col([
                html.Div(" ", style={"marginBottom": "3px", "fontSize": "11px"}),
                dbc.Button("Save", id="settings-save-btn", className="btn-alpaca w-100", n_clicks=0),
            ], width=2),
        ], className="g-2"),
        html.Div([
            dbc.Button("Reset Account", id="settings-reset-btn", color="danger",
                       outline=True, size="sm", className="mt-2", n_clicks=0),
            html.Span(" Resets all trades, positions and equity history",
                      style={"fontSize": "11px", "color": "#9CA3AF", "marginLeft": "8px"}),
        ]),
    ], className="mt-2")


def _equity_figure() -> go.Figure:
    df = _engine.get_equity_history()
    fig = go.Figure()
    if not df.empty:
        fig.add_trace(go.Scatter(
            x=df["snapshot_at"], y=df["equity"],
            mode="lines", fill="tozeroy",
            line=dict(color="#F0B429", width=2),
            fillcolor="rgba(240,180,41,0.12)",
            hovertemplate="₹%{y:,.0f}<extra></extra>",
        ))
    fig.add_hline(y=_engine.initial_capital, line_dash="dot",
                  line_color="#9CA3AF", line_width=1)
    fig.update_layout(
        height=200, margin=dict(l=0, r=0, t=8, b=8),
        paper_bgcolor="white", plot_bgcolor="white",
        xaxis=dict(showgrid=False, zeroline=False),
        yaxis=dict(gridcolor="#F3F4F6", zeroline=False,
                   tickprefix="₹", tickformat=",.0f"),
        showlegend=False, hovermode="x unified",
    )
    return fig


def _positions_table() -> html.Div:
    positions = _engine.get_positions()
    if not positions:
        return html.Div("No open positions.",
                        style={"color": "#9CA3AF", "fontSize": "13px", "padding": "10px 0"})

    rows = [{
        "Symbol": p.symbol,
        "Qty": p.qty,
        "Avg Entry": f"₹{p.avg_entry_price:,.2f}",
        "Current": f"₹{p.current_price:,.2f}",
        "Market Value": f"₹{p.market_value:,.2f}",
        "Unrealized P&L": f"₹{p.unrealized_pnl:+,.2f} ({p.unrealized_pnl_pct:+.1f}%)",
        "Stop Loss": f"₹{p.stop_loss:,.2f}" if p.stop_loss else "—",
        "Target": f"₹{p.target_price:,.2f}" if p.target_price else "—",
        "Strategy": p.strategy or "—",
        "Opened": str(p.opened_at.date()),
        "_symbol": p.symbol,
    } for p in positions]

    display_cols = [c for c in rows[0].keys() if not c.startswith("_")]
    return html.Div([
        dash_table.DataTable(
            id="positions-datatable",
            data=rows,
            columns=[{"name": c, "id": c} for c in display_cols],
            style_table={"overflowX": "auto"},
            style_header={"backgroundColor": "#F9FAFB", "fontWeight": "600",
                          "fontSize": "11px", "color": "#6B7280", "border": "none",
                          "textTransform": "uppercase"},
            style_cell={"fontSize": "12.5px", "padding": "8px 12px",
                        "border": "none", "borderBottom": "1px solid #F3F4F6",
                        "fontFamily": "inherit"},
            style_data_conditional=[
                {"if": {"filter_query": '{Unrealized P&L} contains "+"',
                        "column_id": "Unrealized P&L"},
                 "color": "#00A852", "fontWeight": "600"},
                {"if": {"filter_query": '{Unrealized P&L} contains "-"',
                        "column_id": "Unrealized P&L"},
                 "color": "#E03131", "fontWeight": "600"},
            ],
            row_selectable="single",
            selected_rows=[],
            page_size=10,
        ),
        dbc.Button("📤 Close Selected Position", id="paper-close-btn",
                   color="danger", outline=True, size="sm",
                   className="mt-2", n_clicks=0,
                   style={"display": "none" if not positions else ""}),
        dcc.Store(id="selected-position-store"),
    ])


def _orders_table() -> html.Div:
    orders = _engine.get_all_orders()[:20]
    if not orders:
        return html.Div("No orders yet.",
                        style={"color": "#9CA3AF", "fontSize": "13px", "padding": "10px 0"})
    rows = [{
        "ID": o.id,
        "Symbol": o.symbol,
        "Side": o.side,
        "Qty": o.qty,
        "Type": o.order_type,
        "Status": o.status,
        "Fill Price": f"₹{o.filled_price:,.2f}" if o.filled_price else "—",
        "Created": o.created_at.strftime("%d %b %H:%M"),
    } for o in orders]

    return dash_table.DataTable(
        data=rows,
        columns=[{"name": c, "id": c} for c in rows[0].keys()],
        style_table={"overflowX": "auto"},
        style_header={"backgroundColor": "#F9FAFB", "fontWeight": "600",
                      "fontSize": "11px", "color": "#6B7280", "border": "none",
                      "textTransform": "uppercase"},
        style_cell={"fontSize": "12.5px", "padding": "8px 12px",
                    "border": "none", "borderBottom": "1px solid #F3F4F6",
                    "fontFamily": "inherit"},
        style_data_conditional=[
            {"if": {"filter_query": '{Status} = "FILLED"', "column_id": "Status"},
             "color": "#00A852", "fontWeight": "600"},
            {"if": {"filter_query": '{Status} = "CANCELLED"', "column_id": "Status"},
             "color": "#9CA3AF"},
            {"if": {"filter_query": '{Side} = "BUY"', "column_id": "Side"},
             "color": "#00A852", "fontWeight": "600"},
            {"if": {"filter_query": '{Side} = "SELL"', "column_id": "Side"},
             "color": "#E03131", "fontWeight": "600"},
        ],
        page_size=10,
    )


def _signals_table(signals: list[dict]) -> html.Div:
    if not signals:
        return html.Div("No signals match the strategy criteria.",
                        style={"color": "#9CA3AF", "fontSize": "13px", "padding": "10px 0"})

    portfolio = _engine.get_portfolio()
    open_count = len(_engine.get_positions())
    open_slots = max(0, _engine.max_open_positions - open_count)

    rows = [{
        "Symbol": s["symbol"],
        "Date": s["signal_date"],
        "Entry ₹": f"₹{s['entry']:,.2f}",
        "SL ₹": f"₹{s['stop_loss']:,.2f}",
        "Target ₹": f"₹{s['target']:,.2f}",
        "Score": f"{s['score']}/7",
        "Confidence": s["confidence"],
        "Trend": s["market_trend"],
        "Volume": s["volume"],
    } for s in signals]

    return html.Div([
        html.Div(
            f"{'⚠️ No open slots — close a position first.' if open_slots == 0 else f'✅ {open_slots} slot(s) available · Select a signal and click Enter Trade'}",
            style={"fontSize": "12.5px",
                   "color": "#92400E" if open_slots == 0 else "#065F46",
                   "background": "#FFFBEB" if open_slots == 0 else "#ECFDF5",
                   "padding": "8px 12px", "borderRadius": "6px", "marginBottom": "10px"},
        ),
        dash_table.DataTable(
            id="signals-datatable",
            data=rows,
            columns=[{"name": c, "id": c} for c in rows[0].keys()],
            style_table={"overflowX": "auto"},
            style_header={"backgroundColor": "#F9FAFB", "fontWeight": "600",
                          "fontSize": "11px", "color": "#6B7280", "border": "none",
                          "textTransform": "uppercase"},
            style_cell={"fontSize": "12.5px", "padding": "8px 12px",
                        "border": "none", "borderBottom": "1px solid #F3F4F6",
                        "fontFamily": "inherit"},
            style_data_conditional=[
                {"if": {"filter_query": '{Confidence} = "High"', "column_id": "Confidence"},
                 "color": "#00A852", "fontWeight": "600"},
                {"if": {"filter_query": '{Confidence} = "Low"', "column_id": "Confidence"},
                 "color": "#E03131"},
            ],
            row_selectable="single",
            selected_rows=[],
            page_size=10,
        ),
        dbc.Button(
            [html.I(className="bi bi-plus-circle me-2"), "Enter Selected Trade"],
            id="paper-enter-btn", className="btn-alpaca mt-2",
            n_clicks=0,
            disabled=(open_slots == 0),
        ),
    ])


# ── Callbacks ─────────────────────────────────────────────────────────────

@callback(
    Output("settings-display", "children"),
    Output("settings-edit-form", "style"),
    Output("settings-msg", "children"),
    Input("settings-edit-btn", "n_clicks"),
    Input("settings-save-btn", "n_clicks"),
    Input("settings-reset-btn", "n_clicks"),
    State("settings-capital", "value"),
    State("settings-risk", "value"),
    State("settings-max-pos", "value"),
    prevent_initial_call=True,
)
def handle_settings(edit_clicks, save_clicks, reset_clicks, capital, risk, max_pos):
    from dash import ctx
    tid = ctx.triggered_id

    if tid == "settings-edit-btn":
        return dash.no_update, {"display": "block"}, dash.no_update

    if tid == "settings-save-btn":
        try:
            if capital:
                _engine.set_setting("initial_capital", str(float(capital)))
                _engine.set_setting("cash", str(float(capital)))
            if risk:
                _engine.set_setting("risk_pct", str(float(risk)))
            if max_pos:
                _engine.set_setting("max_open_positions", str(int(max_pos)))
            msg = dbc.Alert("Settings saved.", color="success", duration=3000)
            return _settings_display(), {"display": "none"}, msg
        except Exception as exc:
            return dash.no_update, dash.no_update, dbc.Alert(str(exc), color="danger")

    if tid == "settings-reset-btn":
        _engine.reset_account(float(capital or _engine.initial_capital))
        msg = dbc.Alert("Account reset. All trades and positions cleared.", color="warning", duration=5000)
        return _settings_display(), {"display": "none"}, msg

    return dash.no_update, dash.no_update, dash.no_update


@callback(
    Output("paper-equity-chart", "figure"),
    Input("paper-equity-refresh", "n_clicks"),
    Input("paper-price-interval", "n_intervals"),
    prevent_initial_call=False,
)
def refresh_equity(_, __):
    return _equity_figure()


@callback(
    Output("paper-positions-div", "children"),
    Output("paper-orders-div", "children"),
    Output("paper-close-msg", "children"),
    Input("paper-pos-refresh", "n_clicks"),
    Input("paper-price-interval", "n_intervals"),
    Input("paper-close-btn", "n_clicks"),
    State("positions-datatable", "selected_rows"),
    State("positions-datatable", "data"),
    prevent_initial_call=False,
)
def refresh_positions(refresh_clicks, _, close_clicks, selected_rows, table_data):
    from dash import ctx
    msg = dash.no_update

    if ctx.triggered_id == "paper-close-btn" and close_clicks and selected_rows and table_data:
        symbol = table_data[selected_rows[0]]["Symbol"]
        result = close_position(_engine, symbol, _provider())
        color = "success" if result["status"] == "ok" else "danger"
        msg = dbc.Alert(result["message"], color=color, duration=5000)

    return _positions_table(), _orders_table(), msg


@callback(
    Output("paper-signals-div", "children"),
    Output("paper-signals-store", "data"),
    Input("paper-scan-btn", "n_clicks"),
    State("paper-strategy", "value"),
    State("paper-lookback", "value"),
    prevent_initial_call=True,
)
def run_scan(n_clicks, style_val, lookback):
    if not n_clicks:
        return dash.no_update, dash.no_update
    strategy = _preset(style_val or "vishnu_trading_strategy")
    signals = scan_signals(strategy, _provider(), int(lookback or 300))
    return _signals_table(signals), signals


@callback(
    Output("paper-enter-msg", "children"),
    Output("paper-positions-div", "children", allow_duplicate=True),
    Output("paper-orders-div", "children", allow_duplicate=True),
    Input("paper-enter-btn", "n_clicks"),
    State("paper-signals-store", "data"),
    State("signals-datatable", "selected_rows"),
    State("paper-strategy", "value"),
    prevent_initial_call=True,
)
def enter_trade(n_clicks, signals, selected_rows, style_val):
    if not n_clicks or not signals or not selected_rows:
        return dash.no_update, dash.no_update, dash.no_update

    signal = signals[selected_rows[0]]
    result = enter_signal_trade(
        _engine, signal, _provider(),
        strategy_name=style_val or "vishnu_trading_strategy",
    )
    color = "success" if result["status"] == "ok" else "danger"
    msg = dbc.Alert(result["message"], color=color, duration=5000)
    return msg, _positions_table(), _orders_table()


@callback(
    Output("paper-price-interval", "disabled"),
    Input("paper-price-interval", "n_intervals"),
    prevent_initial_call=True,
)
def auto_update_prices(_):
    """Silently refresh position prices from latest Bhavcopy data."""
    try:
        positions = _engine.get_positions()
        if positions:
            symbols = [p.symbol for p in positions]
            prices = get_latest_prices(symbols, _provider())
            if prices:
                _engine.update_prices(prices)
    except Exception:
        pass
    return False
