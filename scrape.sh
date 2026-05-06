#!/bin/bash
# Trading Bot — One-Click Strategy Scraper

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

CHANNEL="https://www.youtube.com/@synthicator-in"

# Activate venv
if [ ! -f ".venv/bin/activate" ]; then
    echo "ERROR: .venv not found. Run: bash setup.sh"
    exit 1
fi
source .venv/bin/activate

# Quick .env guard
if [ ! -f ".env" ]; then
    echo "ERROR: .env not found. Run: bash setup.sh"
    exit 1
fi
source .env

if [ -z "$OPENAI_API_KEY" ] || [ "$OPENAI_API_KEY" = "sk-..." ]; then
    echo "ERROR: OPENAI_API_KEY not set in .env. Run: bash setup.sh"
    exit 1
fi

if [ ! -f "$EXCEL_PATH" ]; then
    echo "ERROR: SwingPlanner.xlsx not found at: $EXCEL_PATH"
    echo "Check EXCEL_PATH in .env"
    exit 1
fi

echo ""
echo "=== Synthicator Strategy Scraper ==="
echo "Channel : $CHANNEL"
echo "Excel   : $EXCEL_PATH"
echo ""

LIMIT="${1:-15}"
echo "Listing up to $LIMIT videos. Pass a number to show more: bash scrape.sh 30"
echo ""

python3 main.py scrape --channel "$CHANNEL" --limit "$LIMIT"
