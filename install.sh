#!/usr/bin/env bash
# Manual install: link the mockup-canvas skill into Claude Code and/or Codex.
# Usage: ./install.sh [--claude] [--codex] [--dry-run]
# With neither --claude nor --codex, both are installed.
# Anything already at a target that is not this link is moved to
# ~/.mockup-canvas/backup/<timestamp>/ first. Safe to run again.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_SRC="$REPO_DIR/skills/mockup-canvas"
DATA_DIR="${MOCKUP_CANVAS_HOME:-$HOME/.mockup-canvas}"
BACKUP_DIR="$DATA_DIR/backup/$(date +%Y%m%d_%H%M%S)"
DO_CLAUDE=false
DO_CODEX=false
DRY_RUN=false

for arg in "$@"; do
  case "$arg" in
    --claude) DO_CLAUDE=true ;;
    --codex) DO_CODEX=true ;;
    --dry-run) DRY_RUN=true ;;
    -h|--help) sed -n '2,6p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done
if ! $DO_CLAUDE && ! $DO_CODEX; then DO_CLAUDE=true; DO_CODEX=true; fi

run() {
  if $DRY_RUN; then printf '[dry-run]'; printf ' %q' "$@"; printf '\n'; else "$@"; fi
}

link_skill() {
  local dst="$1" tool="$2"
  if [ -L "$dst" ] && [ "$(readlink "$dst")" = "$SKILL_SRC" ]; then
    echo "OK (already linked): $dst"
    return
  fi
  if [ -e "$dst" ] || [ -L "$dst" ]; then
    if $DRY_RUN; then echo "Would back up: $dst -> $BACKUP_DIR/$tool/"; else echo "Backup: $dst -> $BACKUP_DIR/$tool/"; fi
    run mkdir -p "$BACKUP_DIR/$tool"
    run mv "$dst" "$BACKUP_DIR/$tool/"
  fi
  run mkdir -p "$(dirname "$dst")"
  run ln -s "$SKILL_SRC" "$dst"
  if $DRY_RUN; then echo "Would link: $dst -> $SKILL_SRC"; else echo "Linked: $dst -> $SKILL_SRC"; fi
}

if $DO_CLAUDE; then link_skill "$HOME/.claude/skills/mockup-canvas" claude; fi
if $DO_CODEX; then link_skill "$HOME/.codex/skills/mockup-canvas" codex; fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "Warning: python3 not found. mockup-canvas needs Python 3." >&2
fi
echo "Done. User data folder: $DATA_DIR"
