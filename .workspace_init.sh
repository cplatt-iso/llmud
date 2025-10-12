#!/bin/bash
# Workspace-specific bash initialization
# This file can be sourced to set up the environment

# Activate Python virtual environment
if [ -f "${BASH_SOURCE%/*}/venv/bin/activate" ]; then
    source "${BASH_SOURCE%/*}/venv/bin/activate"
    echo "✓ Virtual environment activated"
fi

# Project-specific aliases
alias dc='docker compose'
alias dcl='docker compose logs'
alias dcu='docker compose up -d'
alias dcd='docker compose down'
alias dcr='docker compose restart'

# Backend shortcuts
alias be='cd backend'
alias fe='cd frontend'

# Python shortcuts
alias py='python'
alias pip='python -m pip'

# Show current environment
echo "📁 Project: LLMUD"
echo "🐍 Python: $(python --version 2>&1)"
echo "📦 Venv: $VIRTUAL_ENV"
