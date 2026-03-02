#!/bin/bash
set -e
cd "$(dirname "$0")"

# Activate conda environment (do NOT use system/Homebrew Python)
eval "$(conda shell.bash hook)"
conda activate agentview

if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  python -m venv .venv
fi

source .venv/bin/activate
pip install -q -r requirements.txt
python -m playwright install chromium --with-deps 2>/dev/null || python -m playwright install chromium

echo ""
echo "AgentLens running at http://localhost:7001"
echo "API: GET /parse?url=https://example.com"
echo "     POST /parse  {url, max_tokens, include_links, include_actions}"
echo "     GET /agent-manifest?url=..."
echo ""
uvicorn main:app --host 0.0.0.0 --port 7001 --reload
