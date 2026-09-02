#!/usr/bin/env bash
set -e

COMMAND=$1

case "$COMMAND" in
  install)
    cd backend && python -m pip install -r requirements.txt
    ;;
  dev)
    cd backend && python -m uvicorn app.main:app --reload --port 8000
    ;;
  seed)
    cd backend && python -m app.data.seed
    ;;
  run-batch)
    cd backend && python -m app.orchestrator.runner
    ;;
  test)
    cd backend && python -m pytest -v tests/
    ;;
  *)
    echo "Usage: ./run.sh [install|dev|seed|run-batch|test]"
    exit 1
    ;;
esac
