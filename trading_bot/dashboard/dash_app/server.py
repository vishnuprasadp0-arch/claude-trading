from __future__ import annotations

import dash
import dash_bootstrap_components as dbc
from flask_caching import Cache

app = dash.Dash(
    __name__,
    use_pages=True,
    external_stylesheets=[dbc.themes.FLATLY, dbc.icons.BOOTSTRAP],
    suppress_callback_exceptions=True,
    title="Swing Trading Dashboard",
    update_title=None,
)
server = app.server

cache = Cache(server, config={"CACHE_TYPE": "SimpleCache", "CACHE_DEFAULT_TIMEOUT": 3600})
