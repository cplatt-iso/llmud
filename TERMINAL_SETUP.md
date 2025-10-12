# Terminal & Markdown Configuration

## ✅ What's Been Set Up

### 1. Auto-Activate Virtual Environment in Terminals

Every new terminal opened in VS Code will automatically:
- Activate the Python venv
- Show `(venv)` in the prompt
- Have access to all installed packages

**Configuration:**
- Default terminal profile: "bash (venv)"
- Automatically sources `venv/bin/activate`
- Python terminal activation: enabled

**Test it:**
1. Open a new terminal (Ctrl + `)
2. You should see `(venv)` in the prompt
3. Type `which python` - should show `/home/icculus/llmud/venv/bin/python`

### 2. Markdown Linting Disabled

Markdownlint is now completely disabled:
- No more warnings in `.md` files
- Format on save disabled for markdown
- All markdown rules turned off

**Test it:**
1. Open any `.md` file
2. No more squiggly lines or warnings
3. Problems panel won't show markdown issues

### 3. Workspace Init Script (Optional)

Created `.workspace_init.sh` with useful aliases:

**Docker shortcuts:**
```bash
dc   # docker compose
dcu  # docker compose up -d
dcd  # docker compose down
dcl  # docker compose logs
dcr  # docker compose restart
```

**Navigation:**
```bash
be   # cd backend
fe   # cd frontend
```

**Python:**
```bash
py   # python
pip  # python -m pip (safer than pip directly)
```

**To use manually:**
```bash
source .workspace_init.sh
```

## Troubleshooting

### Terminal not activating venv?

**Option 1: Reload VS Code**
- Press Ctrl+Shift+P
- Type "Developer: Reload Window"

**Option 2: Manual activation**
```bash
source venv/bin/activate
```

**Option 3: Check terminal profile**
- Click on the dropdown in terminal panel
- Select "bash (venv)"

### Want to use a different shell?

For zsh, add to settings:
```json
"terminal.integrated.defaultProfile.linux": "zsh (venv)",
"terminal.integrated.profiles.linux": {
  "zsh (venv)": {
    "path": "zsh",
    "args": ["-c", "source ${workspaceFolder}/venv/bin/activate && exec zsh"]
  }
}
```

### Still seeing Markdown warnings?

The extension might be caching. Try:
1. Restart VS Code
2. Or add to user settings (not workspace):
   ```json
   "markdownlint.run": "onSave"
   ```

## Files Modified

- ✅ `.vscode/settings.json` - Terminal profiles & markdown config
- ✅ `.workspace_init.sh` - Optional helper script with aliases

## Quick Test

Open a new terminal and you should see:
```
✓ Virtual environment activated
📁 Project: LLMUD
🐍 Python: Python 3.12.3
📦 Venv: /home/icculus/llmud/venv
(venv) user@host:~/llmud$
```

Happy coding! 🚀
