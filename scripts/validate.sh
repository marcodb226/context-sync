#!/usr/bin/env bash
# scripts/validate.sh — canonical "validate everything" entry point.
#
# Runs all declared quality gates in sequence.  Exits non-zero on the first
# failure so CI feedback is immediate.
#
# Usage:
#   scripts/validate.sh          # from repo root
#   bash scripts/validate.sh     # explicit shell invocation

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

echo "==> Ruff lint"
.venv/bin/ruff check src/ tests/

echo "==> Ruff format check"
.venv/bin/ruff format --check src/ tests/

echo "==> Pyright"
.venv/bin/pyright

echo "==> Pytest (with coverage)"
.venv/bin/pytest --cov --cov-report=term-missing

echo "==> All gates passed."
