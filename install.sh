#!/usr/bin/env bash
# Manual install: link every skill in skills/ into Claude Code and/or Codex.
# Usage: ./install.sh [--claude] [--codex] [--dry-run]
# With neither --claude nor --codex, both are installed.
# Anything already at a target that is not this link is moved to
# ~/.mockup-canvas/backup/<timestamp>/ first. Safe to run again.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
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
  local src="$1" dst="$2" tool="$3"
  if [ -L "$dst" ] && [ "$(readlink "$dst")" = "$src" ]; then
    echo "OK (already linked): $dst"
    return
  fi
  if [ -e "$dst" ] || [ -L "$dst" ]; then
    if $DRY_RUN; then echo "Would back up: $dst -> $BACKUP_DIR/$tool/"; else echo "Backup: $dst -> $BACKUP_DIR/$tool/"; fi
    run mkdir -p "$BACKUP_DIR/$tool"
    run mv "$dst" "$BACKUP_DIR/$tool/"
  fi
  run mkdir -p "$(dirname "$dst")"
  run ln -s "$src" "$dst"
  if $DRY_RUN; then echo "Would link: $dst -> $src"; else echo "Linked: $dst -> $src"; fi
}

# A skill is a folder under skills/ that has a SKILL.md
for src in "$REPO_DIR"/skills/*/; do
  src="${src%/}"
  [ -f "$src/SKILL.md" ] || continue
  name="$(basename "$src")"
  if $DO_CLAUDE; then link_skill "$src" "$HOME/.claude/skills/$name" claude; fi
  if $DO_CODEX; then link_skill "$src" "$HOME/.codex/skills/$name" codex; fi
done

if ! command -v python3 >/dev/null 2>&1; then
  echo "Warning: python3 not found. mockup-canvas needs Python 3." >&2
fi
echo "Done. User data folder: $DATA_DIR"
