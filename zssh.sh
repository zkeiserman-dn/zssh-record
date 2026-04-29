#!/usr/bin/env bash
# zssh - Zohar SSH session recorder for DNOS lab work
# Usage: zssh <ip-or-serial>
# Or via shell wrapper: ssh -r <ip-or-serial>
#
# Records:
#   - full interactive SSH session via `script`
#   - tail wb_agent + wb_fe_agent in side panes (configurable)
# Folder layout (sticky per epic+task):
#   ~/zohar/<EPIC>/<TASK>/<YYYYmmdd-HHMMSS>-<target>/
#       session.log           full typescript
#       session.timing        typing timestamps
#       wb_agent.log          colorized agent log
#       wb_fe_agent.log       colorized FE agent log
#       meta.json             epic, task, target, started_at

set -euo pipefail

ZSSH_DIR="${ZSSH_DIR:-$HOME/zohar/zssh}"
ZOHAR_ROOT="${ZOHAR_ROOT:-$HOME/zohar}"
STATE_FILE="$HOME/.zssh-state"
CONFIG_FILE="${ZSSH_CONFIG:-$HOME/.zssh.conf}"

# Defaults; override via $CONFIG_FILE
ZSSH_USER="${ZSSH_USER:-dnroot}"
ZSSH_WB_AGENT_CMD="${ZSSH_WB_AGENT_CMD:-request shell node-id 1 \"tail -f -n 50 /var/log/dn/wb_agent.log\"}"
ZSSH_WB_FE_AGENT_CMD="${ZSSH_WB_FE_AGENT_CMD:-request shell node-id 1 \"tail -f -n 50 /var/log/dn/wb_fe_agent.log\"}"
ZSSH_TMUX_LAYOUT="${ZSSH_TMUX_LAYOUT:-main-horizontal}"
ZSSH_SELF_UPDATE="${ZSSH_SELF_UPDATE:-1}"

# shellcheck disable=SC1090
[ -f "$CONFIG_FILE" ] && . "$CONFIG_FILE"

# shellcheck disable=SC1091
. "$ZSSH_DIR/lib/colorize.sh"
# shellcheck disable=SC1091
. "$ZSSH_DIR/lib/prompt.sh"

target="${1:-}"
if [ -z "$target" ]; then
  echo "usage: zssh <ip-or-serial>" >&2
  exit 2
fi

# 1) self-update (best-effort, never block on failure)
if [ "$ZSSH_SELF_UPDATE" = "1" ] && [ -d "$ZSSH_DIR/.git" ]; then
  ( cd "$ZSSH_DIR" && git fetch --quiet origin main 2>/dev/null \
    && git -c advice.detachedHead=false reset --hard --quiet origin/main 2>/dev/null ) || true
fi

# 2) sticky epic + task prompts: confirm continue first, only ask if "no" / no state
zssh_load_state
if zssh_confirm_continue; then
  ZSSH_EPIC="$ZSSH_LAST_EPIC"
  ZSSH_TASK="$ZSSH_LAST_TASK"
else
  zssh_prompt_epic
  zssh_prompt_task
fi
zssh_save_state

# 3) folder layout
ts="$(date +%Y%m%d-%H%M%S)"
out_dir="$ZOHAR_ROOT/$ZSSH_EPIC/$ZSSH_TASK/${ts}-${target}"
mkdir -p "$out_dir"

cat > "$out_dir/meta.json" <<EOF
{
  "epic": "$ZSSH_EPIC",
  "task": "$ZSSH_TASK",
  "target": "$target",
  "user": "$ZSSH_USER",
  "started_at": "$(date -Iseconds)",
  "tool_version": "$(cat "$ZSSH_DIR/VERSION" 2>/dev/null || echo 0.0.0)"
}
EOF

echo
echo "  epic     : $ZSSH_EPIC"
echo "  task     : $ZSSH_TASK"
echo "  target   : $target"
echo "  recording: $out_dir"
echo

# 4) launch tmux session: top = ssh, bottom-left = wb_agent, bottom-right = wb_fe_agent
session_name="zssh-$$"
session_log="$out_dir/session.log"
timing="$out_dir/session.timing"
wb_log="$out_dir/wb_agent.log"
fe_log="$out_dir/wb_fe_agent.log"

# colorize stream wrappers (read live and tee colored to file + stdout)
colorize_path="$ZSSH_DIR/lib/colorize.sh"

# top pane: typescript-recorded ssh
top_cmd="script -q -t \"$timing\" \"$session_log\" ssh -o StrictHostKeyChecking=no \"${ZSSH_USER}@${target}\""

# bottom panes: ssh, run agent tail, pipe through colorizer, tee to file
left_cmd="ssh -o StrictHostKeyChecking=no \"${ZSSH_USER}@${target}\" '$ZSSH_WB_AGENT_CMD' 2>&1 | bash \"$colorize_path\" stream | tee \"$wb_log\""
right_cmd="ssh -o StrictHostKeyChecking=no \"${ZSSH_USER}@${target}\" '$ZSSH_WB_FE_AGENT_CMD' 2>&1 | bash \"$colorize_path\" stream | tee \"$fe_log\""

# pre-create empty log files so the viewer / tail can open them immediately
: > "$wb_log"
: > "$fe_log"
: > "$session_log"

# 5) optional live HTML viewer (`ssh -rv ...` sets ZSSH_VIEWER=1)
ZSSH_VIEWER_PID=""
if [ "${ZSSH_VIEWER:-0}" = "1" ]; then
  if command -v python3 >/dev/null 2>&1; then
    "$ZSSH_DIR/lib/viewer.sh" "$out_dir" &
    ZSSH_VIEWER_PID=$!
    trap 'kill $ZSSH_VIEWER_PID 2>/dev/null || true' EXIT
  else
    echo "[zssh] python3 not found - skipping HTML viewer"
  fi
fi

if ! command -v tmux >/dev/null 2>&1; then
  echo "[zssh] tmux not found - falling back to plain recorded ssh (no side log panes)"
  echo "[zssh] install tmux:  brew install tmux"
  exec script -q -t "$timing" "$session_log" ssh -o StrictHostKeyChecking=no "${ZSSH_USER}@${target}"
fi

tmux new-session -d -s "$session_name" -x 220 -y 60 "$top_cmd"
tmux split-window -t "$session_name":0 -v "$left_cmd"
tmux split-window -t "$session_name":0 -h "$right_cmd"
tmux select-layout -t "$session_name":0 "$ZSSH_TMUX_LAYOUT"
tmux select-pane -t "$session_name":0.0
tmux set-option -t "$session_name" mouse on
tmux attach -t "$session_name"

# cleanup pointer
[ -n "$ZSSH_VIEWER_PID" ] && kill "$ZSSH_VIEWER_PID" 2>/dev/null || true
echo
echo "[zssh] session ended: $out_dir"
