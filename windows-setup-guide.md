# Windows Setup Guide - claude-trading Project

Complete step-by-step guide to set up the claude-trading project on your Windows machine.

---

## Prerequisites

Before starting, make sure you have:

- ✅ **Git for Windows** - Download from https://git-scm.com/download/win
- ✅ **Python** - Download from https://www.python.org/downloads/ (make sure to check "Add Python to PATH")
- ✅ **Git Bash** - Installed with Git for Windows

### Verify Installation

Open **Git Bash** and run:

```bash
git --version
python --version
python -m pip --version
```

All three should show version numbers.

---

## Step 1: Clone the Repository

### Open Git Bash

1. Right-click on your Desktop or Documents folder
2. Select **"Git Bash Here"**

Or open **Git Bash** from Start Menu

### Navigate to Where You Want the Project

```bash
# Navigate to Documents
cd ~/Documents

# Or create a Projects folder
mkdir Projects
cd Projects
```

### Clone the Repository

```bash
git clone https://github.com/vishnuprasadp0-arch/claude-trading.git
cd claude-trading
```

You should see output like:
```
Cloning into 'claude-trading'...
remote: Enumerating objects: 1174, done.
...
```

---

## Step 2: Set Up Virtual Environment

### Create Virtual Environment

```bash
python -m venv venv
```

### Activate Virtual Environment

```bash
source venv/Scripts/activate
```

You should see `(venv)` at the start of your prompt, like:
```
(venv) C:\Users\YourUsername\Documents\Projects\claude-trading $
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

This may take a few minutes. You'll see lots of lines like:
```
Collecting numpy==1.24.3
Downloading numpy-1.24.3-cp311-cp311-win_amd64.whl
...
Successfully installed numpy-1.24.3
```

---

## Step 3: Set Up Local Environment File

### Create .env File

```bash
# Create a new .env file
touch .env

# Open it in your text editor (Notepad)
notepad .env
```

### Add Your Configuration

Add your secrets (never commit this file):

```
GROQ_API_KEY=your_actual_key_here
DATABASE_URL=your_database_url
OTHER_SECRET=your_secret_here
```

Save and close.

**Important:** This file is in `.gitignore` and will NOT be pushed to GitHub.

---

## Step 4: Make Scripts Executable

The scripts are already in `scripts/` folder. Make them executable:

```bash
chmod +x scripts/start-work.sh
chmod +x scripts/end-work.sh
```

Verify they exist:

```bash
ls -la scripts/
```

You should see:
```
start-work.sh
end-work.sh
```

---

## Step 5: Set Up Aliases in Git Bash

### Open or Create ~/.bashrc

```bash
# Open in Notepad
notepad ~/.bashrc
```

If the file is empty, that's fine. Add these lines at the end:

```bash
# Aliases for work automation
alias start-work="bash ~/Documents/Projects/claude-trading/scripts/start-work.sh"
alias end-work="bash ~/Documents/Projects/claude-trading/scripts/end-work.sh"
```

**Important:** Replace the path with your actual project path!

Examples of correct paths:
```bash
# If project is in Documents
alias start-work="bash ~/Documents/claude-trading/scripts/start-work.sh"

# If project is in C:\Users\YourUsername\Projects
alias start-work="bash ~/Projects/claude-trading/scripts/start-work.sh"

# To find your path, run this in Git Bash:
pwd
```

Save and close the file.

### Reload Git Bash Configuration

Close Git Bash completely and reopen it, OR run:

```bash
source ~/.bashrc
```

Test that aliases work:

```bash
start-work
```

Should show a welcome message.

---

## Step 6: PyCharm Setup (Optional)

If you use PyCharm:

### Open Project in PyCharm

1. Open PyCharm
2. File → Open
3. Navigate to your project folder: `C:\Users\YourUsername\Documents\Projects\claude-trading`
4. Click Open

### Configure Python Interpreter

1. File → Settings (or PyCharm → Preferences on Mac)
2. Search for "Python Interpreter" or go to Project → Python Interpreter
3. Click the gear icon → Add
4. Select "Existing Environment"
5. Navigate to your venv:
   - `C:\Users\YourUsername\Documents\Projects\claude-trading\venv\Scripts\python.exe`
6. Click OK

Now PyCharm will use your virtual environment and show you autocomplete and type hints!

---

## Step 7: First Time - Pull Latest Changes

Before starting work, pull the latest changes:

```bash
git pull origin main
```

You should see:
```
Already up to date.
```

---

## Daily Workflow on Windows

### When You Open Your Laptop

Open **Git Bash** and run:

```bash
start-work
```

This will:
1. 🪟 Detect Windows
2. 📥 Pull latest changes from GitHub
3. 🔧 Activate virtual environment automatically
4. 📦 Ask if you want to install dependencies
5. 📊 Show Git status
6. ✅ You're ready to code!

Example output:
```
🪟 Detected: Windows (Git Bash/WSL)

✅ Project Directory: C:\Users\YourUsername\Documents\Projects\claude-trading

🚀 Starting work session...

📥 Pulling latest changes from GitHub...
Already up to date.

🔧 Activating virtual environment (Windows)...

Install/update dependencies from requirements.txt? (y/n) n

✅ All set! You're ready to work

📊 Current Git Status:
On branch main
nothing to commit, working tree clean

💡 Tips:
   • Your virtual environment is already activated
   • Type 'deactivate' to exit virtual environment when done
   • Run 'end-work' before closing your laptop

📂 Working Directory: C:\Users\YourUsername\Documents\Projects\claude-trading
🐍 Python Version: Python 3.11.5
```

### Start Coding

Now you can:
- Open PyCharm and start coding
- Or use VS Code or any other editor
- Your virtual environment is already activated
- All dependencies are installed

### Before You Close Your Laptop

When you're done working, run:

```bash
end-work
```

This will:
1. 📊 Show all changes you made
2. 🗨️ Ask for a commit message
3. ➕ Add all changes to Git
4. 💾 Commit the changes
5. 📤 Push to GitHub
6. 📊 Show your latest commits
7. ✅ Done!

Example:
```
🪟 Detected: Windows (Git Bash/WSL)

🛑 Ending work session...

📂 Working Directory: C:\Users\YourUsername\Documents\Projects\claude-trading

📊 Current changes:
On branch main
Changes not staged for commit:
  modified:   trading_bot.py
  new file:   new_strategy.py

Do you want to commit and push changes? (y/n) y

📝 Enter a commit message (or press Enter for auto message):
Added new trading strategy

➕ Adding all changes...
✅ Changes added

💾 Committing with message: 'Added new trading strategy'

📤 Pushing to GitHub...

✅ Success! All changes pushed to GitHub

📊 Latest commits:
abc1234 Added new trading strategy
def5678 Initial commit

✅ All set! You're done for today.

👋 Good job! See you next time
```

---

## Switching Between Machines

### Before Closing Windows

```bash
end-work
```

This pushes all changes to GitHub.

### On Mac (Next Time)

```bash
start-work
```

This automatically pulls your changes from Windows!

### Before Closing Mac

```bash
end-work
```

This pushes changes to GitHub.

### On Windows (Next Time)

```bash
start-work
```

This automatically pulls your changes from Mac!

✅ Everything stays in sync!

---

## Common Tasks

### Check What Changed

```bash
git status
```

Shows modified, new, or deleted files.

### See Your Recent Commits

```bash
git log --oneline -5
```

Shows your last 5 commits.

### View Changes Before Committing

```bash
git diff
```

Shows exactly what changed in each file.

### Undo Changes (Before Committing)

```bash
# Undo changes in one file
git restore filename.py

# Undo all changes
git restore .
```

### Update Dependencies

If you installed new packages:

```bash
pip freeze > requirements.txt
git add requirements.txt
git commit -m "Update dependencies"
git push origin main
```

### Deactivate Virtual Environment

When you're done coding:

```bash
deactivate
```

The `(venv)` will disappear from your prompt.

---

## Troubleshooting

### "Command not found: start-work"

Make sure you:
1. Edited ~/.bashrc correctly
2. Saved the file
3. Closed and reopened Git Bash
4. Used the correct project path

To find your project path:
```bash
pwd
```

### "Python not found"

Install Python from: https://www.python.org/downloads/

**Important:** Check "Add Python to PATH" during installation

### "Git not found"

Install Git Bash from: https://git-scm.com/download/win

### Virtual Environment Won't Activate

Delete and recreate it:

```bash
rmdir /s venv
python -m venv venv
source venv/Scripts/activate
pip install -r requirements.txt
```

### Can't Find Python Packages After Pull

Reinstall dependencies:

```bash
source venv/Scripts/activate
pip install -r requirements.txt
```

### Git Push Rejected

Pull first:

```bash
git pull origin main
```

Then try pushing again:

```bash
git push origin main
```

### Permission Denied on Scripts

Make them executable:

```bash
chmod +x scripts/start-work.sh
chmod +x scripts/end-work.sh
```

### PyCharm Can't Find Modules

Make sure Python interpreter is set correctly:
1. File → Settings → Project → Python Interpreter
2. Select the venv interpreter
3. PyCharm should index the packages

---

## Useful Git Commands

```bash
# Check current status
git status

# View recent commits
git log --oneline -5

# See what changed in a file
git diff filename.py

# See all changes
git diff

# Undo changes
git restore .

# View current branch
git branch

# Switch to a branch
git checkout branch-name

# Create a new branch
git checkout -b feature/my-feature
```

---

## Pro Tips

1. **Always run `start-work` before coding** - ensures you have latest changes

2. **Always run `end-work` before switching machines** - ensures changes are pushed

3. **Use meaningful commit messages:**
   ```
   ✅ "Add new trading strategy with RSI indicator"
   ❌ "update"
   ❌ "fix"
   ```

4. **Don't work on both machines at the same time** - can cause conflicts

5. **Keep `.env` file local only** - never push secrets to GitHub

6. **Update requirements.txt when installing new packages:**
   ```bash
   pip freeze > requirements.txt
   ```

7. **Test code before committing** - run your tests first

---

## Project Structure

After setup, your project should look like:

```
claude-trading/
├── .git/                 (hidden - git repository)
├── .gitignore            (git ignores .env, .start-work-config, venv/)
├── .env                  (NOT in git - your local secrets)
├── venv/                 (NOT in git - your virtual environment)
├── scripts/
│   ├── start-work.sh     (Run this when you open your laptop)
│   └── end-work.sh       (Run this before closing your laptop)
├── requirements.txt      (List of Python packages)
├── README.md             (Project documentation)
├── src/
│   └── trading_bot.py    (Your code)
└── ... (other files)
```

---

## Quick Reference Checklist

- [ ] Git for Windows installed
- [ ] Python installed (with PATH)
- [ ] Repository cloned
- [ ] Virtual environment created and activated
- [ ] Dependencies installed
- [ ] .env file created with your secrets
- [ ] Scripts made executable (chmod +x)
- [ ] Aliases added to ~/.bashrc
- [ ] Git Bash reloaded
- [ ] start-work works
- [ ] PyCharm configured (optional)

---

## Next Steps

1. ✅ Complete setup following steps 1-7
2. ✅ Run `start-work` to verify everything works
3. ✅ Open project in PyCharm or your editor
4. ✅ Start coding!
5. ✅ When done, run `end-work`
6. ✅ Switch to Mac and run `start-work` there

---

## Need Help?

**Check the troubleshooting section above first!**

If issues persist:
1. Check that all prerequisites are installed
2. Verify file paths are correct
3. Make sure virtual environment is activated
4. Check Git status: `git status`
5. View Git logs: `git log --oneline`

Good luck! 🚀 Happy coding!
