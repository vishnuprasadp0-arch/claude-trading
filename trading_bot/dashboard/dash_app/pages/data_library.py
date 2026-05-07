from __future__ import annotations

from pathlib import Path

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, State, callback, dcc, html

from trading_bot.backtest.data import NseBhavcopyDataProvider
from trading_bot.backtest.universe import NIFTY_50_SYMBOLS

dash.register_page(__name__, path="/data", name="Data Library")

CACHE_DIR = Path(__file__).resolve().parents[4] / "trading_bot" / "data" / "cache"


def _provider() -> NseBhavcopyDataProvider:
    return NseBhavcopyDataProvider(cache_dir=CACHE_DIR)


def _coverage_card() -> html.Div:
    try:
        stats = _provider().get_coverage_stats(years=5)
        pct = stats["coverage_pct"]
        bar_color = "#00A852" if pct >= 99 else ("#F0B429" if pct >= 60 else "#E03131")
        status_icon = "🟢" if pct >= 99 else ("🟡" if pct >= 60 else "🔴")
        idx = _provider().get_symbol_index_stats(NIFTY_50_SYMBOLS)
    except Exception:
        return html.Div("Could not load coverage stats.", style={"color": "#E03131"})

    return html.Div([
        # Coverage header
        dbc.Row([
            dbc.Col([
                html.Div(f"{status_icon} {stats['cached'] + stats['holidays']:,} / {stats['expected']:,} days",
                         style={"fontSize": "18px", "fontWeight": "700", "color": "#1A1A2E"}),
                html.Div(f"{stats['cached']:,} trading days · {stats['holidays']:,} confirmed holidays",
                         style={"fontSize": "12px", "color": "#6B7280", "marginTop": "2px"}),
            ], width=8),
            dbc.Col(html.Div(f"{pct:.0f}%", style={"fontSize": "28px", "fontWeight": "700",
                                                     "color": bar_color, "textAlign": "right"}), width=4),
        ], className="mb-3"),

        # Progress bar
        dbc.Progress(value=min(int(pct), 100), color="success" if pct >= 99 else "warning" if pct >= 60 else "danger",
                     style={"height": "8px", "borderRadius": "4px", "marginBottom": "10px"}),

        # Date range
        html.Div(
            f"Coverage: {stats['start']} → {stats['end']}" if stats.get("earliest") else "",
            style={"fontSize": "12px", "color": "#9CA3AF", "marginBottom": "12px"},
        ),

        # Missing dates
        html.Div([
            dbc.Button(
                f"▼ {len(stats['missing'])} missing dates" if stats["missing"] else "✅ All dates accounted for",
                id="missing-toggle", size="sm", outline=True, color="secondary",
                style={"fontSize": "12px"},
            ),
            dbc.Collapse(
                html.Div(
                    ", ".join(str(d) for d in stats["missing"][:50]) +
                    (f" ... and {len(stats['missing']) - 50} more" if len(stats["missing"]) > 50 else ""),
                    style={"fontSize": "11.5px", "color": "#6B7280", "marginTop": "8px",
                           "padding": "8px", "background": "#F9FAFB", "borderRadius": "4px"},
                ),
                id="missing-collapse", is_open=False,
            ),
        ], className="mb-3") if stats["missing"] else html.Div(style={"marginBottom": "8px"}),

        # Download button
        dbc.Button(
            [html.I(className="bi bi-download me-2"), "Download Missing Data"],
            id="download-btn", className="btn-alpaca me-2", n_clicks=0,
        ) if stats["missing"] else html.Div(),
    ])


def _symbol_index_card() -> html.Div:
    try:
        idx = _provider().get_symbol_index_stats(NIFTY_50_SYMBOLS)
    except Exception:
        return html.Div("Could not load index stats.", style={"color": "#E03131"})

    all_built = idx["built"] == idx["total"] and idx["unpivoted_dates"] == 0
    return html.Div([
        dbc.Row([
            dbc.Col([
                html.Div(
                    "⚡ All symbols indexed" if all_built else f"📊 {idx['built']} / {idx['total']} symbols built",
                    style={"fontSize": "15px", "fontWeight": "600",
                           "color": "#00A852" if all_built else "#F0B429"},
                ),
                html.Div(
                    "Ready for instant backtests" if all_built else
                    f"{idx['unpivoted_dates']} dates not yet indexed",
                    style={"fontSize": "12px", "color": "#6B7280", "marginTop": "2px"},
                ),
            ], width=8),
            dbc.Col(
                dbc.Button(
                    [html.I(className="bi bi-tools me-2"), "Build Index"],
                    id="pivot-btn", className="btn-alpaca", n_clicks=0,
                ) if not all_built else html.Div(),
                width=4, style={"textAlign": "right"},
            ),
        ]),
    ])


def layout() -> html.Div:
    return html.Div([
        html.Div([html.I(className="bi bi-database me-2"), "Data Library"],
                 className="dash-card-title",
                 style={"fontSize": "17px", "marginBottom": "18px"}),

        # NSE Bhavcopy coverage
        html.Div(className="dash-card", children=[
            html.Div(className="dash-card-header", children=[
                html.Div([html.I(className="bi bi-calendar-check me-2"), "NSE Bhavcopy Coverage (5 Years)"],
                         className="dash-card-title"),
                dbc.Button([html.I(className="bi bi-arrow-clockwise")],
                           id="coverage-refresh-btn", size="sm", outline=True,
                           color="secondary", n_clicks=0),
            ]),
            html.Div(id="coverage-content", children=_coverage_card()),
            dcc.Loading(html.Div(id="download-progress"), type="circle"),
        ]),

        # Symbol Index
        html.Div(className="dash-card", children=[
            html.Div(className="dash-card-header", children=[
                html.Div([html.I(className="bi bi-lightning me-2"), "Symbol Index"],
                         className="dash-card-title"),
            ]),
            html.Div(id="index-content", children=_symbol_index_card()),
            dcc.Loading(html.Div(id="pivot-progress"), type="circle"),
        ]),

        # Log viewer
        html.Div(className="dash-card", children=[
            html.Div(className="dash-card-header", children=[
                html.Div([html.I(className="bi bi-terminal me-2"), "Recent Logs"],
                         className="dash-card-title"),
                dbc.Button([html.I(className="bi bi-arrow-clockwise")],
                           id="log-refresh-btn", size="sm", outline=True,
                           color="secondary", n_clicks=0),
            ]),
            dcc.Pre(id="log-content", style={
                "fontSize": "11.5px", "color": "#374151",
                "background": "#F9FAFB", "borderRadius": "6px",
                "padding": "12px", "maxHeight": "300px", "overflowY": "auto",
                "margin": "0",
            }),
            dcc.Interval(id="log-interval", interval=10_000, n_intervals=0),
        ]),
    ], className="page-content")


# ── Callbacks ─────────────────────────────────────────────────────────────

@callback(
    Output("missing-collapse", "is_open"),
    Input("missing-toggle", "n_clicks"),
    State("missing-collapse", "is_open"),
    prevent_initial_call=True,
)
def toggle_missing(n, is_open):
    return not is_open


@callback(
    Output("coverage-content", "children", allow_duplicate=True),
    Output("index-content", "children", allow_duplicate=True),
    Input("coverage-refresh-btn", "n_clicks"),
    prevent_initial_call=True,
)
def refresh_coverage(_):
    return _coverage_card(), _symbol_index_card()


@callback(
    Output("download-progress", "children"),
    Output("coverage-content", "children", allow_duplicate=True),
    Input("download-btn", "n_clicks"),
    prevent_initial_call=True,
)
def download_missing(n_clicks):
    if not n_clicks:
        return dash.no_update, dash.no_update
    try:
        provider = _provider()
        stats = provider.get_coverage_stats(years=5)
        if not stats["missing"]:
            return dbc.Alert("Nothing to download.", color="info", duration=3000), dash.no_update
        downloaded, skipped = provider.download_bulk(stats["missing"])
        if downloaded > 0:
            provider.pivot_bhavcopy_to_symbols(NIFTY_50_SYMBOLS)
        msg = dbc.Alert(
            f"✅ Done — {downloaded} files downloaded, {skipped} holidays/timeouts skipped.",
            color="success", duration=5000,
        )
        return msg, _coverage_card()
    except Exception as exc:
        return dbc.Alert(f"Download failed: {exc}", color="danger"), dash.no_update


@callback(
    Output("pivot-progress", "children"),
    Output("index-content", "children", allow_duplicate=True),
    Input("pivot-btn", "n_clicks"),
    prevent_initial_call=True,
)
def build_index(n_clicks):
    if not n_clicks:
        return dash.no_update, dash.no_update
    try:
        provider = _provider()
        processed = provider.pivot_bhavcopy_to_symbols(NIFTY_50_SYMBOLS)
        msg = dbc.Alert(f"⚡ Symbol index built — {processed} dates processed.", color="success", duration=4000)
        return msg, _symbol_index_card()
    except Exception as exc:
        return dbc.Alert(f"Pivot failed: {exc}", color="danger"), dash.no_update


@callback(
    Output("log-content", "children"),
    Input("log-interval", "n_intervals"),
    Input("log-refresh-btn", "n_clicks"),
)
def update_logs(_, __):
    try:
        from trading_bot.utils.logging import _LOG_FILE
        log_path = Path(_LOG_FILE)
        if not log_path.exists():
            return "No log file found."
        lines = log_path.read_text().splitlines()[-60:]
        return "\n".join(lines)
    except Exception:
        return "Could not read log file."
