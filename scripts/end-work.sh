#!/bin/bash
# END WORK SCRIPT - Universal (Mac & Windows/Git Bash)
# Auto-detects OS (macOS/Windows) and commits/pushes changes
# Works on macOS and Windows (Git Bash / WSL)

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

# Function to load project directory
load_config() {
    if [ -f "$CONFIG_FILE" ]; then
        cat "$CONFIG_FILE"
    else
        echo ""
    fi
}

# Get project directory
PROJECT_DIR=$(load_config)

if [ -z "$PROJECT_DIR" ] || [ ! -d "$PROJECT_DIR" ]; then
    echo -e "${RED}❌ Error: Project directory not configured${NC}"
    echo -e "${YELLOW}Please run 'start-work' first to set up the project directory${NC}"
    exit 1
fi

cd "$PROJECT_DIR"

echo -e "${BLUE}🛑 Ending work session...${NC}"
echo ""
echo -e "${BLUE}📂 Working Directory: $PROJECT_DIR${NC}"
echo ""

# Check current status
echo -e "${BLUE}📊 Current changes:${NC}"
git status
echo ""

# Ask user if they want to commit
read -p "Do you want to commit and push changes? (y/n) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}⏭️  Skipped. Changes not pushed.${NC}"
    echo ""
    echo -e "${YELLOW}💡 Tip: Don't forget to push your changes before switching to another machine!${NC}"
    exit 0
fi

echo ""

# Check if there are any changes
if git diff-index --quiet HEAD --; then
    echo -e "${YELLOW}ℹ️  No changes to commit${NC}"
    exit 0
fi

# Ask for commit message
echo -e "${YELLOW}📝 Enter a commit message (or press Enter for auto message):${NC}"
read commit_message

# Use auto message if empty
if [ -z "$commit_message" ]; then
    commit_message="Update: $(date '+%Y-%m-%d %H:%M')"
fi

echo ""

# Add all changes
echo -e "${BLUE}➕ Adding all changes...${NC}"
git add .
echo -e "${GREEN}✅ Changes added${NC}"
echo ""

# Commit
echo -e "${BLUE}💾 Committing with message: '$commit_message'${NC}"
git commit -m "$commit_message"
COMMIT_STATUS=$?
echo ""

if [ $COMMIT_STATUS -ne 0 ]; then
    echo -e "${RED}❌ Commit failed${NC}"
    exit 1
fi

# Push to GitHub
echo -e "${BLUE}📤 Pushing to GitHub...${NC}"
git push origin main
PUSH_STATUS=$?

echo ""

if [ $PUSH_STATUS -eq 0 ]; then
    echo -e "${GREEN}✅ Success! All changes pushed to GitHub${NC}"
    echo ""
    echo -e "${BLUE}📊 Latest commits:${NC}"
    git log --oneline -3
    echo ""
    echo -e "${GREEN}✅ All set! You're done for today.${NC}"
    echo ""
    echo -e "${YELLOW}💡 Tip: Don't forget to pull on the other machine before starting work${NC}"
else
    echo -e "${RED}❌ Push failed. Please check your connection and try again${NC}"
    echo ""
    echo -e "${YELLOW}⚠️  Your changes are committed locally but not pushed to GitHub${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}👋 Good job! See you next time${NC}"
