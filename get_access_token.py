#!/usr/bin/env python3
"""Generate a Zerodha access token via the local callback flow."""

from trading_bot.auth.zerodha import main


if __name__ == "__main__":
    raise SystemExit(main())
