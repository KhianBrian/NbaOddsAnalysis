#!/bin/bash
# ParlayGod Setup Script
# Run this once to get everything installed

set -e

echo ""
echo "========================================="
echo "  ParlayGod Setup"
echo "========================================="
echo ""

# Check Python version
python_version=$(python3 --version 2>&1 | cut -d" " -f2 | cut -d"." -f1-2)
echo "Python version: $python_version"

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate venv
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

# Create .env if it doesn't exist
if [ ! -f ".env" ]; then
    cp .env.template .env
    echo ""
    echo ">>> ACTION REQUIRED <<<"
    echo "A .env file was created. Open it and add your API keys:"
    echo "  - ODDS_API_KEY       (from the-odds-api.com)"
    echo "  - ANTHROPIC_API_KEY  (from console.anthropic.com)"
    echo "  - BALLDONTLIE_API_KEY (from balldontlie.io)"
    echo ""
else
    echo ".env file already exists. Skipping."
fi

echo ""
echo "========================================="
echo "  Setup complete!"
echo ""
echo "  To run ParlayGod:"
echo "  source venv/bin/activate"
echo "  python parlay_god/main.py"
echo "========================================="
echo ""
