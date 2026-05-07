from __future__ import annotations

import os
from pathlib import Path

import dash_bootstrap_components as dbc
from dash import html
import openpyxl

from trading_bot.config.settings import EXCEL_PATH


def _read_capital() -> str:
    path = Path(os.getenv("EXCEL_PATH", str(EXCEL_PATH)))
    try:
        wb = openpyxl.load_workbook(path, data_only=True)
        val = wb["System"]["B3"].value
        return f"₹{float(val or 100000):,.0f}"
    except Exception:
        return "₹1,00,000"


def sidebar() -> html.Div:
    capital = _read_capital()
    return html.Div(
        className="sidebar",
        children=[
            # Logo
            html.Div(
                className="sidebar-logo",
                children=[
                    html.Div("ST", className="sidebar-logo-icon"),
                    html.Div([
                        html.Div("Swing Trader", className="sidebar-logo-text"),
                        html.Div("Paper · NSE", className="sidebar-logo-sub"),
                    ]),
                ],
            ),

            # Navigation
            html.Div(
                className="sidebar-nav",
                children=[
                    html.Div("Trading", className="sidebar-section-label"),
                    dbc.NavLink(
                        [html.I(className="bi bi-house"), " Home"],
                        href="/", active="exact", className="nav-link",
                    ),
                    dbc.NavLink(
                        [html.I(className="bi bi-play-circle"), " Backtest"],
                        href="/backtest", active="exact", className="nav-link",
                    ),
                    dbc.NavLink(
                        [html.I(className="bi bi-clipboard-data"), " Paper Trading"],
                        href="/paper", active="exact", className="nav-link",
                    ),
                    html.Div("Data", className="sidebar-section-label"),
                    dbc.NavLink(
                        [html.I(className="bi bi-database"), " Data Library"],
                        href="/data", active="exact", className="nav-link",
                    ),
                ],
            ),

            # Footer
            html.Div(
                className="sidebar-footer",
                children=[
                    html.Div("Capital", style={"fontSize": "10px", "color": "#9CA3AF", "textTransform": "uppercase", "letterSpacing": "0.06em"}),
                    html.Div(capital, style={"fontWeight": "700", "fontSize": "14px", "color": "#1A1A2E"}),
                ],
            ),
        ],
    )
