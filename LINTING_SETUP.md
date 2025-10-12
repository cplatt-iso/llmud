# Python Linting Setup Complete! ✅

## What's Been Configured

### VS Code Settings (`.vscode/settings.json`)
- ✅ Python interpreter set to your venv: `./venv/bin/python`
- ✅ **Pylint** enabled (comprehensive linting)
- ✅ **Pylance** type checking enabled (basic mode)
- ✅ Linting runs on save
- ✅ Auto-save enabled (1 second delay)
- ✅ Line length ruler at 120 characters

### Installed Linting Tools
```bash
# In your venv/bin/:
✅ pylint     # Main linter
✅ flake8     # Style guide enforcement (disabled by default)
✅ mypy       # Static type checker
✅ black      # Code formatter
✅ autopep8   # Auto-formatter
```

## How to Use

### Automatic Linting
- Linting runs automatically when you save a Python file
- Look for squiggly underlines in your code
- Hover over underlined code to see the issue
- Problems panel (Ctrl+Shift+M) shows all issues

### Manual Linting
Run from terminal:
```bash
# Lint a specific file
venv/bin/pylint backend/app/main.py

# Lint entire backend
venv/bin/pylint backend/app/

# Type check with mypy
venv/bin/mypy backend/app/

# Format code with black
venv/bin/black backend/app/
```

### VS Code Commands
- **Ctrl+Shift+P** → "Python: Run Linting"
- **Ctrl+Shift+P** → "Python: Enable Linting"
- **Ctrl+Shift+P** → "Python: Select Linter"

### Disabled Pylint Warnings
These common warnings are disabled in the settings:
- `C0111` - missing-docstring (not every function needs docs)
- `C0103` - invalid-name (allows single letter vars)
- `W0212` - protected-access (allows `_private` access)
- `R0903` - too-few-public-methods
- `R0913` - too-many-arguments
- `R0914` - too-many-locals
- `R0915` - too-many-statements

## Customizing

### Enable Flake8 Instead of Pylint
In `.vscode/settings.json`:
```json
"python.linting.pylintEnabled": false,
"python.linting.flake8Enabled": true,
```

### Adjust Pylint Severity
Add to `.vscode/settings.json`:
```json
"python.linting.pylintArgs": [
  "--disable=C,R",  // Disable all convention and refactoring warnings
  "--max-line-length=120"
]
```

### Enable Type Checking
Change in `.vscode/settings.json`:
```json
"python.analysis.typeCheckingMode": "strict",  // or "basic", "off"
```

## Troubleshooting

### Linting Not Working?
1. Check Python interpreter: Look at bottom left of VS Code
2. Should show: `Python 3.12.3 ('venv': venv)`
3. If not, press it and select: `./venv/bin/python`

### Too Many Warnings?
Add specific codes to disable in settings:
```json
"python.linting.pylintArgs": [
  "--disable=C0111,W0212,YOUR_CODE_HERE"
]
```

### Performance Issues?
Change diagnostic mode:
```json
"python.analysis.diagnosticMode": "openFilesOnly",
```

## Backend-Specific Configuration

You might want to create `backend/.pylintrc` for backend-specific rules:
```ini
[MASTER]
ignore=migrations,__pycache__,venv

[FORMAT]
max-line-length=120

[MESSAGES CONTROL]
disable=C0111,C0103,W0212,R0903
```

## Recommended Extensions
Check `.vscode/extensions.json` for recommended VS Code extensions.
You'll be prompted to install them when you open the workspace.

Happy coding! 🐍
