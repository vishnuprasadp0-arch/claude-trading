from __future__ import annotations

import os
from pathlib import Path

import dash_bootstrap_components as dbc
from dash import dcc, html, page_container

from trading_bot.dashboard.dash_app.server import app
from trading_bot.dashboard.dash_app.components.sidebar import sidebar

# Import pages so Dash registers them
import trading_bot.dashboard.dash_app.pages.home          # noqa: F401
import trading_bot.dashboard.dash_app.pages.backtest      # noqa: F401
import trading_bot.dashboard.dash_app.pages.paper         # noqa: F401
import trading_bot.dashboard.dash_app.pages.data_library  # noqa: F401


def _right_panel() -> html.Div:
    """Persistent right panel — content swapped by page callbacks."""
    return html.Div(
        id="right-panel",
        className="right-panel",
        children=[
            html.Div("Portfolio", className="right-panel-header"),
            html.Div(id="right-panel-body", className="right-panel-body", children=[
                html.Div("Select a strategy and run a backtest to see live signals here.",
                         style={"color": "#9CA3AF", "fontSize": "13px"}),
            ]),
        ],
    )


app.layout = html.Div(
    className="app-wrapper",
    children=[
        # URL routing
        dcc.Location(id="url", refresh=False),

        # Left sidebar (fixed)
        sidebar(),

        # Main content area
        html.Div(
            className="main-content",
            children=[
                # Top bar
                html.Div(
                    className="top-bar",
                    children=[
                        html.Div(
                            className="top-bar-search",
                            children=[
                                dbc.Input(
                                    placeholder="Search by symbol…",
                                    type="text",
                                    id="global-search",
                                    debounce=True,
                                    style={"borderRadius": "20px", "fontSize": "13px",
                                           "border": "1px solid #E5E7EB", "paddingLeft": "36px"},
                                ),
                            ],
                        ),
                        html.Div(style={"flex": "1"}),
                        dbc.Badge(
                            [html.I(className="bi bi-shield-check me-1"), "Paper Trading"],
                            color="info", pill=True,
                            style={"fontSize": "12px", "padding": "6px 12px"},
                        ),
                    ],
                ),
                # Page content
                page_container,
            ],
        ),

        # Right panel (fixed)
        _right_panel(),

        # Global stores
        dcc.Store(id="strategy-store", storage_type="session"),
        dcc.Store(id="paper-signals-global", storage_type="memory"),
    ],
)


if __name__ == "__main__":
    port = int(os.getenv("DASH_PORT", 8050))
    debug = os.getenv("DASH_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
