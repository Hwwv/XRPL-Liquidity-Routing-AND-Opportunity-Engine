#!/usr/bin/env bash
# Environment setup for XRPL Liquidity Routing & Opportunity Engine.
# Run from project root: ./setup.sh

set -e
cd "$(dirname "$0")"

echo "Creating virtual environment..."
python3 -m venv .venv

echo "Activating .venv..."
# shellcheck source=/dev/null
source .venv/bin/activate

echo "Upgrading pip..."
pip install --upgrade pip

echo "Installing dependencies from requirements.txt..."
pip install -r requirements.txt

echo "Running tests..."
python -m unittest discover -s xrpl_router/tests -v

echo ""
echo "Setup complete. Activate the environment with:"
echo "  source .venv/bin/activate"
echo "Then run:"
echo "  python -m xrpl_router.cli route --from XRP --to USD --amount 100 --mock"
echo "  streamlit run app.py"
