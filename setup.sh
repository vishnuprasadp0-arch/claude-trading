#!/bin/bash
# Trading Bot — Dependency & Config Checker

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

BOLD="\033[1m"
GREEN="\033[0;32m"
RED="\033[0;31m"
YELLOW="\033[0;33m"
RESET="\033[0m"

ERRORS=0
VENV_DIR="$SCRIPT_DIR/.venv"
VENV_PYTHON="$VENV_DIR/bin/python3"
VENV_PIP="$VENV_DIR/bin/pip"

pass() { echo -e "  ${GREEN}✓${RESET} $1"; }
fail() { echo -e "  ${RED}✗${RESET} $1"; ERRORS=$((ERRORS + 1)); }
warn() { echo -e "  ${YELLOW}!${RESET} $1"; }

open_env_and_exit() {
    echo ""
    echo -e "  ${YELLOW}Opening .env for you to fix: $1${RESET}"
    open -e "$SCRIPT_DIR/.env"
    echo ""
    echo "  Save the file, then re-run:  bash setup.sh"
    echo ""
    exit 1
}

echo ""
echo -e "${BOLD}=== Trading Bot — Setup Check ===${RESET}"
echo ""

# ── Python ───────────────────────────────────────────────────────────────────
echo -e "${BOLD}Python${RESET}"
if command -v python3 &>/dev/null; then
    PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
    PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
    if [ "$PY_MAJOR" -ge 3 ] && [ "$PY_MINOR" -ge 10 ]; then
        pass "Python $PY_VERSION"
    else
        fail "Python $PY_VERSION — need 3.10+"
    fi
else
    fail "python3 not found — install from https://python.org"
    exit 1
fi

# ── Virtual environment ───────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}Virtual environment (.venv)${RESET}"
if [ ! -d "$VENV_DIR" ]; then
    warn "No .venv found — creating one..."
    if python3 -m venv "$VENV_DIR"; then
        pass "Virtual environment created at .venv/"
    else
        fail "Failed to create virtual environment"
        exit 1
    fi
else
    pass ".venv exists"
fi

# ── Dependencies ─────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}Dependencies (requirements.txt)${RESET}"
MISSING_PKGS=()
while IFS= read -r line; do
    # Skip blank lines and comment lines
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    pkg=$(echo "$line" | sed 's/[>=<].*//' | sed 's/#.*//' | xargs)
    [ -z "$pkg" ] && continue
    case "$pkg" in
        python-dotenv)          import_name="dotenv" ;;
        yt-dlp)                 import_name="yt_dlp" ;;
        youtube-transcript-api) import_name="youtube_transcript_api" ;;
        apscheduler)            import_name="apscheduler" ;;
        groq)                   import_name="groq" ;;
        *)                      import_name="$pkg" ;;
    esac
    if "$VENV_PYTHON" -c "import $import_name" &>/dev/null 2>&1; then
        pass "$pkg"
    else
        fail "$pkg  (not installed)"
        MISSING_PKGS+=("$pkg")
    fi
done < requirements.txt

if [ ${#MISSING_PKGS[@]} -gt 0 ]; then
    echo ""
    warn "Installing missing packages into .venv..."
    if "$VENV_PIP" install "${MISSING_PKGS[@]}" --quiet; then
        pass "All packages installed"
        ERRORS=$((ERRORS - ${#MISSING_PKGS[@]}))  # clear the fail counts — now fixed
    else
        fail "pip install failed — check your internet connection"
    fi
fi

# ── .env ─────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}.env file${RESET}"

if [ ! -f ".env" ]; then
    warn ".env not found — creating from .env.example"
    cp .env.example .env
    open_env_and_exit "fill in GEMINI_API_KEY and confirm EXCEL_PATH"
fi
pass ".env exists"

set -a
# shellcheck disable=SC1091
source .env
set +a

if [ -z "$GROQ_API_KEY" ] || [ "$GROQ_API_KEY" = "gsk_..." ]; then
    fail "GROQ_API_KEY is missing or still a placeholder"
    open_env_and_exit "paste your Groq API key into GROQ_API_KEY"
elif [[ "$GROQ_API_KEY" == gsk_* ]]; then
    pass "GROQ_API_KEY is set"
else
    warn "GROQ_API_KEY doesn't look like a Groq key (expected gsk_...)"
fi

if [ -z "$EXCEL_PATH" ] || [ "$EXCEL_PATH" = "/path/to/SwingPlanner.xlsx" ]; then
    fail "EXCEL_PATH is not set"
    open_env_and_exit "set EXCEL_PATH to the full path of your SwingPlanner.xlsx"
elif [ -f "$EXCEL_PATH" ]; then
    pass "EXCEL_PATH exists: $EXCEL_PATH"
else
    fail "EXCEL_PATH file not found: $EXCEL_PATH"
    open_env_and_exit "EXCEL_PATH points to a file that doesn't exist — fix the path"
fi

if [ -z "$SYMBOLS" ]; then
    warn "SYMBOLS not set — using default (RELIANCE,TCS,INFY,HDFCBANK,ICICIBANK)"
else
    SYMBOL_COUNT=$(echo "$SYMBOLS" | tr ',' '\n' | wc -l | xargs)
    pass "SYMBOLS: $SYMBOL_COUNT symbol(s)"
fi

[ -z "$GROQ_MODEL" ] && warn "GROQ_MODEL not set — defaulting to llama-3.3-70b-versatile" || pass "GROQ_MODEL: $GROQ_MODEL"

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}=== Result ===${RESET}"
if [ "$ERRORS" -eq 0 ]; then
    echo -e "  ${GREEN}All checks passed. You're ready to run the bot.${RESET}"
    echo ""
    echo "  Scrape a strategy  :  bash scrape.sh"
    echo "  One evaluation pass:  bash run.sh --once"
    echo "  Start live bot     :  bash run.sh"
    echo "  Show open trades   :  bash run.sh status"
else
    echo -e "  ${RED}$ERRORS check(s) failed. Fix the issues above and re-run: bash setup.sh${RESET}"
fi
echo ""
