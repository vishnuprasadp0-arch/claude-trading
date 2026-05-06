from __future__ import annotations

import argparse
import os
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from dotenv import load_dotenv
from kiteconnect import KiteConnect


DEFAULT_REDIRECT_URI = "http://127.0.0.1:8787/callback"
ENV_PATH = Path(__file__).resolve().parents[2] / ".env"


class _CallbackState:
    def __init__(self) -> None:
        self.request_token: str | None = None
        self.error: str | None = None
        self.event = threading.Event()


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Generate a Zerodha access token")
    parser.add_argument("--api-key", default=os.getenv("ZERODHA_API_KEY", ""))
    parser.add_argument("--api-secret", default=os.getenv("ZERODHA_API_SECRET", ""))
    parser.add_argument("--redirect-uri", default=os.getenv("ZERODHA_REDIRECT_URI", DEFAULT_REDIRECT_URI))
    parser.add_argument("--no-browser", action="store_true", help="Print the login URL instead of opening a browser")
    parser.add_argument("--write-env", action="store_true", help="Write the new access token into .env")
    args = parser.parse_args()

    if not args.api_key or not args.api_secret:
        print("ZERODHA_API_KEY and ZERODHA_API_SECRET are required.")
        return 1

    parsed = urlparse(args.redirect_uri)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"} or not parsed.port:
        print("Use a local HTTP redirect URI such as http://127.0.0.1:8787/callback")
        return 1

    state = _CallbackState()
    server = _start_callback_server(parsed.hostname, parsed.port, parsed.path, state)
    kite = KiteConnect(api_key=args.api_key)
    login_url = kite.login_url()

    print(f"Redirect URI expected by this helper: {args.redirect_uri}")
    print("Configure the same Redirect URL in the Zerodha developer console before continuing.")
    print("")

    if args.no_browser:
        print("Open this URL in your browser and complete the login:")
        print(login_url)
    else:
        opened = webbrowser.open(login_url)
        if opened:
            print("Opened Zerodha login in your browser.")
        else:
            print("Browser did not open automatically. Open this URL manually:")
            print(login_url)

    print("Waiting for Zerodha callback on the local redirect URI...")
    state.event.wait()
    server.shutdown()
    server.server_close()

    if state.error:
        print(f"Login failed: {state.error}")
        return 1
    if not state.request_token:
        print("No request token received.")
        return 1

    session = kite.generate_session(state.request_token, api_secret=args.api_secret)
    access_token = session["access_token"]
    print("")
    print("Access token generated successfully:")
    print(access_token)

    if args.write_env:
        _write_env_value("ZERODHA_ACCESS_TOKEN", access_token)
        _write_env_value("ZERODHA_REDIRECT_URI", args.redirect_uri)
        print(f"Updated {ENV_PATH}")

    return 0


def _start_callback_server(host: str, port: int, expected_path: str, state: _CallbackState) -> HTTPServer:
    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path != expected_path:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"Not found")
                return

            params = parse_qs(parsed.query)
            request_token = _first(params, "request_token")
            status = _first(params, "status")
            error = _first(params, "message") or _first(params, "error_type")

            if request_token:
                state.request_token = request_token
            else:
                state.error = error or f"Missing request_token, status={status or 'unknown'}"

            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            if state.request_token:
                body = "<h2>Zerodha login complete.</h2><p>You can return to the terminal.</p>"
            else:
                body = "<h2>Zerodha login failed.</h2><p>Check the terminal for details.</p>"
            self.wfile.write(body.encode("utf-8"))
            state.event.set()

        def log_message(self, _format: str, *_args) -> None:
            return

    server = HTTPServer((host, port), CallbackHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def _first(params: dict[str, list[str]], key: str) -> str | None:
    values = params.get(key)
    if not values:
        return None
    return values[0]


def _write_env_value(key: str, value: str) -> None:
    lines: list[str] = []
    if ENV_PATH.exists():
        lines = ENV_PATH.read_text().splitlines()

    replaced = False
    for index, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[index] = f"{key}={value}"
            replaced = True
            break

    if not replaced:
        lines.append(f"{key}={value}")

    ENV_PATH.write_text("\n".join(lines) + "\n")
