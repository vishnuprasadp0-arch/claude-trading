#!/bin/bash
# START WORK SCRIPT - Universal (Mac & Windows/Git Bash)
# Auto-detects OS (macOS/Windows) and asks for project directory
# Works on macOS and Windows (Git Bash / WSL)

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Detect OS
if [[ "$OSTYPE" == "darwin"* ]]; then
    OS="mac"
    echo -e "${BLUE}🍎 Detected: macOS${NC}"
elif [[ "$OSTYPE" == "linux-gnu"* ]] || [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]]; then
    OS="windows"
    echo -e "${BLUE}🪟 Detected: Windows (Git Bash/WSL)${NC}"
else
    OS="unknown"
    echo -e "${YELLOW}⚠️  Unknown OS: $OSTYPE${NC}"
fi

echo ""

# Configuration file path
CONFIG_FILE="$HOME/.start-work-config"

# Function to save project directory
save_config() {
    echo "$1" > "$CONFIG_FILE"
}

# Function to load project directory
load_config() {
    if [ -f "$CONFIG_FILE" ]; then
        cat "$CONFIG_FILE"
    else
        echo ""
    fi
}

# Function to ask for project directory
ask_for_directory() {
    echo -e "${YELLOW}📁 Project Directory Setup${NC}"
    echo ""
    
    if [[ "$OS" == "mac" ]]; then
        echo "Examples:"
        echo "  ~/Documents/trading-bot"
        echo "  ~/Projects/claude-trading"
        echo "  /Users/username/trading-bot"
    else
        echo "Examples:"
        echo "  C:\\Users\\username\\Documents\\trading-bot"
        echo "  C:\\Users\\username\\Projects\\claude-trading"
        echo "  D:\\trading-bot"
    fi
    
    echo ""
    read -p "Enter your project directory path: " user_path
    
    # Expand ~ to home directory
    user_path="${user_path/#\~/$HOME}"
    
    # Check if directory exists
    if [ ! -d "$user_path" ]; then
        echo -e "${RED}❌ Directory not found: $user_path${NC}"
        echo ""
        return 1
    fi
    
    # Check if it's a git repository
    if [ ! -d "$user_path/.git" ]; then
        echo -e "${RED}❌ Not a Git repository: $user_path${NC}"
        echo ""
        return 1
    fi
    
    save_config "$user_path"
    echo "$user_path"
    return 0
}

# Get project directory
PROJECT_DIR=$(load_config)

if [ -z "$PROJECT_DIR" ] || [ ! -d "$PROJECT_DIR" ]; then
    echo -e "${YELLOW}⚙️  First time setup required${NC}"
    echo ""
    
    while ! ask_for_directory; do
        echo -e "${YELLOW}Please try again...${NC}"
        echo ""
    done
    
    PROJECT_DIR=$(load_config)
fi

echo ""
echo -e "${GREEN}✅ Project Directory: $PROJECT_DIR${NC}"
echo ""

# Change to project directory
cd "$PROJECT_DIR"

echo -e "${BLUE}🚀 Starting work session...${NC}"
echo ""

# Pull latest changes from GitHub
echo -e "${BLUE}📥 Pulling latest changes from GitHub...${NC}"
git pull origin main
PULL_STATUS=$?
echo ""

if [ $PULL_STATUS -ne 0 ]; then
    echo -e "${YELLOW}⚠️  Pull encountered an issue (but continuing anyway)${NC}"
    echo ""
fi

# Check if venv exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}⚠️  Virtual environment not found. Creating one...${NC}"
    
    # Detect Python command
    if command -v python3 &> /dev/null; then
        python3 -m venv venv
    elif command -v python &> /dev/null; then
        python -m venv venv
    else
        echo -e "${RED}❌ Python not found. Please install Python first${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✅ Virtual environment created${NC}"
    echo ""
fi

# Activate virtual environment
if [[ "$OS" == "mac" ]]; then
    echo -e "${BLUE}🔧 Activating virtual environment (macOS)...${NC}"
    source venv/bin/activate
else
    echo -e "${BLUE}🔧 Activating virtual environment (Windows)...${NC}"
    source venv/Scripts/activate
fi

echo ""

# Check if requirements.txt exists and ask to install
if [ -f "requirements.txt" ]; then
    read -p "Install/update dependencies from requirements.txt? (y/n) " -n 1 -r INSTALL_DEPS
    echo ""
    
    if [[ $INSTALL_DEPS =~ ^[Yy]$ ]]; then
        echo -e "${BLUE}📦 Installing dependencies...${NC}"
        pip install -r requirements.txt
        echo ""
    fi
fi

# Show status
echo -e "${GREEN}✅ All set! You're ready to work${NC}"
echo ""
echo -e "${BLUE}📊 Current Git Status:${NC}"
git status
echo ""

echo -e "${YELLOW}💡 Tips:${NC}"
echo "   • Your virtual environment is already activated"
echo "   • Type 'deactivate' to exit virtual environment when done"
echo "   • Run 'end-work' before closing your laptop"

echo ""
echo -e "${BLUE}📂 Working Directory: $PROJECT_DIR${NC}"
echo -e "${BLUE}🐍 Python Version: $(python --version)${NC}"

if [ -f "$CONFIG_FILE" ]; then
    echo ""
    echo -e "${YELLOW}💾 Tip: To change project directory, edit: $CONFIG_FILE${NC}"
fi
