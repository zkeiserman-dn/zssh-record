#!/usr/bin/env bash
# One-time installer for zssh-record on macOS / Linux.
#   - clones (or refreshes) the repo to $ZSSH_DIR (default ~/zohar/zssh)
#   - hooks `ssh -r` into your interactive shell (zsh/bash)
#   - creates ~/zohar/ and a default ~/.zssh.conf you can edit
#
# Run from anywhere:
#   curl -fsSL https://raw.githubusercontent.com/zkeiserman-dn/zssh-record/main/install.sh | bash
# Or from a checkout:
#   ./install.sh

set -euo pipefail

ZSSH_REPO_URL="${ZSSH_REPO_URL:-https://github.com/zkeiserman-dn/zssh-record.git}"
ZSSH_DIR="${ZSSH_DIR:-$HOME/zohar/zssh}"
ZOHAR_ROOT="${ZOHAR_ROOT:-$HOME/zohar}"
CONFIG_FILE="${ZSSH_CONFIG:-$HOME/.zssh.conf}"

mkdir -p "$ZOHAR_ROOT"

if [ -d "$ZSSH_DIR/.git" ]; then
  echo "[install] refreshing $ZSSH_DIR"
  ( cd "$ZSSH_DIR" && git fetch origin main && git reset --hard origin/main )
else
  echo "[install] cloning $ZSSH_REPO_URL -> $ZSSH_DIR"
  git clone "$ZSSH_REPO_URL" "$ZSSH_DIR"
fi

chmod +x "$ZSSH_DIR/zssh.sh" "$ZSSH_DIR/install.sh" 2>/dev/null || true

# default config
if [ ! -f "$CONFIG_FILE" ]; then
  cat > "$CONFIG_FILE" <<'EOF'
# zssh-record per-user config (sourced from zssh.sh)
# Edit any of these to taste; remove a line to use the built-in default.

# SSH user for DNOS devices
# ZSSH_USER="dnroot"

# Commands tailed in side panes after SSH'ing to <target>.
# Each is run as: ssh dnroot@<target> '<cmd>'
# Replace these with whatever your DNOS image needs.
# ZSSH_WB_AGENT_CMD='request shell node-id 1 "tail -f -n 50 /var/log/dn/wb_agent.log"'
# ZSSH_WB_FE_AGENT_CMD='request shell node-id 1 "tail -f -n 50 /var/log/dn/wb_fe_agent.log"'

# Tmux pane layout: main-horizontal | tiled | even-vertical
# ZSSH_TMUX_LAYOUT="main-horizontal"

# Disable auto-update (1=on, 0=off)
# ZSSH_SELF_UPDATE=1
EOF
  echo "[install] wrote default config: $CONFIG_FILE"
fi

# hook into shell
hook_line=". \"$ZSSH_DIR/zssh-fn.sh\"   # zssh-record: enables 'ssh -r <target>'"
for rc in "$HOME/.zshrc" "$HOME/.bashrc"; do
  [ -f "$rc" ] || continue
  if ! grep -Fq "zssh-record:" "$rc"; then
    printf '\n# >>> zssh-record >>>\n%s\n# <<< zssh-record <<<\n' "$hook_line" >> "$rc"
    echo "[install] hooked into $rc"
  fi
done

# friendly tmux check
if ! command -v tmux >/dev/null 2>&1; then
  if command -v brew >/dev/null 2>&1; then
    echo "[install] tmux is missing; install with:  brew install tmux"
  else
    echo "[install] tmux is missing; install it via your package manager"
  fi
fi

cat <<EOF

[install] done.

Open a new terminal (or 'source ~/.zshrc'), then:
    ssh -r <ip-or-serial>

It will ask for an Epic and a Testing Task once and remember them.
Recordings go under: $ZOHAR_ROOT/<EPIC>/<TASK>/<timestamp>-<target>/
EOF
