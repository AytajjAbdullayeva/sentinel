# sentinel

Sentinel is a security analysis platform for Solidity and DeFi protocols. It scans smart contracts, maps how an attacker could move from an entry point to a sensitive operation, and tests supported attack scenarios on a local Ethereum Virtual Machine (EVM). Findings are available through a React dashboard, a FastAPI backend, and a command-line interface.
Features
- Contract analysis — Compile Solidity with solc and extract findings and code relationships with Slither.
- Attack-path exploration — Build an attack graph and trace candidate paths back to the code and analysis evidence that support them.
- Local EVM simulation — Reproduce supported scenarios on Anvil. Transaction receipts and balance changes show whether a simulated path succeeded.
- Risk scoring and reporting — Compute scores from available evidence using versioned rules. Reports mark missing inputs as unknown, and optional AI explanations reference evidence from the analysis.
- Web dashboard and API — Review scan findings and interactive attack graphs. The API uses JWT authentication and viewer, analyst, and admin roles.
- CI checks — Compare changed contracts against a saved baseline and flag new or more severe findings that meet the configured threshold.
Run locally
You need Python 3.11+, Node.js and npm for the dashboard, and the Solidity compiler version required by the contracts you scan. Install Foundry and make sure anvil is on your PATH to run EVM simulations.
1. Install the backend
Run these commands from the repository root in Bash:
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
solc-select install 0.8.24
solc-select use 0.8.24
In Git Bash on Windows, activate the environment with source .venv/Scripts/activate.
2. Start the API
export SENTINEL_JWT_SECRET="$(python -c 'import secrets; print(secrets.token_hex(32))')"
python scripts/serve_api.py
The API runs on port 8000. Interactive API docs are available at localhost:8000/docs.
3. Start the dashboard
Open a second terminal from the repository root:
cd web
npm ci
npm run dev
Open localhost:5173. For the local demo, sign in as admin, analyst, or viewer with the default demo password sentinel-demo. Set SENTINEL_DEMO_PW before starting the API to override it. The demo accounts are for local development.
Scan contracts from the CLI
Run the included baseline and changed-contract examples from the repository root:
sentinel scan fixtures/contracts/ci/baseline --out baseline.json
sentinel diff --baseline baseline.json fixtures/contracts/ci/changed
The second command exits with status 1 if a new or more severe finding meets the configured threshold. This lets you use it as a CI check.
Repository layout
Path	Purpose
sentinel/	Analysis, attack graphs, simulation, scoring, API, and CLI
web/	React, Vite, and Cytoscape dashboard
fixtures/	Example contracts and analysis configurations
scripts/	Local API launcher and analysis demos
tests/	Python unit and integration tests


Run the tests with python -m pytest -q. Some integration tests require Anvil or external fixtures, which can be fetched with bash scripts/fetch_fixtures.sh.
