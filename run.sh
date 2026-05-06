#!/bin/bash
# Trading Bot — Runner (activates venv automatically)
# Usage:
#   bash run.sh dashboard → start backtest dashboard
#   bash run.sh token     → generate Zerodha access token
#   bash run.sh status    → show open trades

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -f ".venv/bin/activate" ]; then
    echo "ERROR: .venv not found. Run: bash setup.sh"
    exit 1
fi
source .venv/bin/activate

if [ ! -f ".env" ]; then
    echo "ERROR: .env not found. Run: bash setup.sh"
    exit 1
fi

case "$1" in
    dashboard)
        streamlit run dashboard.py
        ;;
    token)
        python3 get_access_token.py --write-env
        ;;
    status)
        python3 main.py status
        ;;
    *)
        echo "Unsupported mode. Use: bash run.sh dashboard | token | status"
        exit 1
        ;;
esac
