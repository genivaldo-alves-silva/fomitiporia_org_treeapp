#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
EXCLUDE_FILE="${SCRIPT_DIR}/rsync-exclude.txt"

REMOTE_USER="${REMOTE_USER:-ubuntu}"
REMOTE_HOST="${REMOTE_HOST:-oraclekey}"
REMOTE_BASE="${REMOTE_BASE:-/home/ubuntu/app}"
FRONTEND_TARGET="${FRONTEND_TARGET:-/opt/phylogentree/frontend/current}"

usage() {
  cat <<EOF
Usage: $0 [--all | --backend | --frontend | --deploy] [--dry-run]

Env overrides:
  REMOTE_USER, REMOTE_HOST, REMOTE_BASE, FRONTEND_TARGET

Examples:
  $0 --all
  $0 --backend
  REMOTE_HOST=1.2.3.4 $0 --frontend
EOF
}

DRY_RUN=""

if [ "$#" -eq 0 ]; then
  usage
  exit 1
fi

SYNC_ALL=false
SYNC_BACKEND=false
SYNC_FRONTEND=false
SYNC_DEPLOY=false

while [ "$#" -gt 0 ]; do
  case "$1" in
    --all)
      SYNC_ALL=true
      ;;
    --backend)
      SYNC_BACKEND=true
      ;;
    --frontend)
      SYNC_FRONTEND=true
      ;;
    --deploy)
      SYNC_DEPLOY=true
      ;;
    --dry-run)
      DRY_RUN="--dry-run"
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
  shift
done

if [ "$SYNC_ALL" = true ]; then
  SYNC_BACKEND=true
  SYNC_FRONTEND=true
  SYNC_DEPLOY=true
fi

if [ "$SYNC_BACKEND" = false ] && [ "$SYNC_FRONTEND" = false ] && [ "$SYNC_DEPLOY" = false ]; then
  echo "Select at least one target: --backend, --frontend, --deploy, or --all" >&2
  exit 1
fi

RSYNC_BASE=(rsync -avz --delete --exclude-from "$EXCLUDE_FILE" $DRY_RUN)

if [ "$SYNC_BACKEND" = true ]; then
  echo "Syncing backend..."
  "${RSYNC_BASE[@]}" \
    "${PROJECT_ROOT}/backend/" \
    "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_BASE}/backend/"
fi

if [ "$SYNC_FRONTEND" = true ]; then
  echo "Syncing frontend..."
  rsync -avz --delete $DRY_RUN \
    "${PROJECT_ROOT}/frontend/" \
    "${REMOTE_USER}@${REMOTE_HOST}:${FRONTEND_TARGET}/"
fi

if [ "$SYNC_DEPLOY" = true ]; then
  echo "Syncing deploy scripts..."
  rsync -avz --delete $DRY_RUN \
    "${PROJECT_ROOT}/deploy/" \
    "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_BASE}/deploy/"
fi
