#!/usr/bin/env bash
# zssh - SSH session recorder for DNOS lab work, runs on the dev VM.
#
# Usage from the Mac (via the zssh-fn.sh shell hook):
#   ssh -r  <target>     -> a *plain* SSH session to the device, recorded
#                           transparently in the background on the dev VM
#   ssh -rv <target>     -> same as -r, plus a live HTML viewer
#                           opened automatically in your Mac browser
#
# Recording layout on the dev VM:
#   ~/zohar/<EPIC>/<TASK>/<YYYYmmdd-HHMMSS>-<target>/recording/
#       session.log         full typescript of the SSH session
#       session.timing      replay timing  (scriptreplay session.timing session.log)
#       wb_agent.log        whatever ZSSH_WB_AGENT_CMD streams
#       wb_fe_agent.log     whatever ZSSH_WB_FE_AGENT_CMD streams
#       meta.json           epic, task, target, started_at, tool_version
#       viewer.log          (only if -rv) viewer server stdout/stderr
#
# After the SSH session ends, session.log is uploaded as an attachment to
# the testing-task you typed (e.g. SW-262109) - requires JIRA_EMAIL +
# JIRA_API_TOKEN in ~/.zssh.conf or your dev-VM environment.

set -euo pipefail

ZSSH_DIR="${ZSSH_DIR:-$HOME/zohar/zssh}"
ZOHAR_ROOT="${ZOHAR_ROOT:-$HOME/zohar}"
STATE_FILE="$HOME/.zssh-state"
CONFIG_FILE="${ZSSH_CONFIG:-$HOME/.zssh.conf}"

# Defaults; override via $CONFIG_FILE
ZSSH_USER="${ZSSH_USER:-dnroot}"
export ZSSH_USER
ZSSH_DEVICE_PASSWORD="${ZSSH_DEVICE_PASSWORD:-dnroot}"
export ZSSH_DEVICE_PASSWORD
# DNOS NCP id whose `traces/` is tailed by the default workers (run start shell ncp <id>)
ZSSH_NCP_ID="${ZSSH_NCP_ID:-0}"
# Subdir inside the NCP shell that holds wb_agent / wb_fe_agent files (relative or absolute)
ZSSH_TRACES_DIR="${ZSSH_TRACES_DIR:-/core/traces/datapath}"
export ZSSH_TRACES_DIR
# Background log workers (run on the dev VM; write to wb_agent.log / wb_fe_agent.log).
# Leave $ZSSH_WB_AGENT_CMD / $ZSSH_WB_FE_AGENT_CMD empty for "use the built-in
# DNOS-shell tailer" (lib/dnos_log_tail.py).  Override in ~/.zssh.conf to point
# at any other shell command that prints a log to stdout.
ZSSH_WB_AGENT_CMD="${ZSSH_WB_AGENT_CMD:-}"
ZSSH_WB_FE_AGENT_CMD="${ZSSH_WB_FE_AGENT_CMD:-}"
ZSSH_SELF_UPDATE="${ZSSH_SELF_UPDATE:-1}"
# Viewer reachability:
#   ZSSH_VIEWER_BIND   what python binds on the dev VM (default 0.0.0.0)
#   ZSSH_VIEWER_HOST   hostname/IP shown in the URL hint
# Bind on all interfaces by default so the Mac can hit http://<dev-vm>:8765/
# directly even when the SSH -L tunnel fails (e.g. local port already bound
# from a leftover ssh session).  Restrict by overriding in ~/.zssh.conf.
export ZSSH_VIEWER_BIND="${ZSSH_VIEWER_BIND:-0.0.0.0}"
export ZSSH_VIEWER_HOST="${ZSSH_VIEWER_HOST:-$(hostname -f 2>/dev/null || hostname)}"
export ZSSH_VIEWER_PORT="${ZSSH_VIEWER_PORT:-8765}"

# shellcheck disable=SC1090
[ -f "$CONFIG_FILE" ] && . "$CONFIG_FILE"

# shellcheck disable=SC1091
. "$ZSSH_DIR/lib/prompt.sh"

target="${1:-}"
if [ -z "$target" ]; then
  echo "usage: zssh <ip-or-serial>" >&2
  exit 2
fi

# Strip any leading 'user@' so callers can pass either 'YE21...' or 'dnroot@YE21...'.
case "$target" in *@*) target="${target#*@}" ;; esac

# 0) detect outdated Mac wrapper and SHOUT the install command
if [ -z "${ZSSH_FN_VERSION:-}" ]; then
  printf '\n\033[1;41;37m  ===========================================================  \033[0m\n'
  printf   '\033[1;41;37m   YOUR MAC WRAPPER IS OLD - it still opens http://127.0.0.1:8765/   \033[0m\n'
  printf   '\033[1;41;37m   To fix it, paste THIS ONE LINE on your Mac (then re-run):   \033[0m\n'
  printf   '\033[1;41;37m  ===========================================================  \033[0m\n\n'
  printf '\033[1;33m   curl -fsSL http://%s:8000/zssh-fn.sh > ~/zohar/zssh/zssh-fn.sh && exec zsh\033[0m\n\n' \
    "${ZSSH_VIEWER_HOST:-$(hostname -f 2>/dev/null || hostname)}"
fi

# 1) self-update (only if the install dir is a git checkout)
if [ "$ZSSH_SELF_UPDATE" = "1" ] && [ -d "$ZSSH_DIR/.git" ]; then
  ( cd "$ZSSH_DIR" && git fetch --quiet origin main 2>/dev/null \
    && git -c advice.detachedHead=false reset --hard --quiet origin/main 2>/dev/null ) || true
fi

# 2) sticky epic + task prompts: confirm continue first, only ask if "no" / no state.
# In view-only mode (ssh -v from Mac), skip prompts entirely - no Jira, no folder.
if [ "${ZSSH_NO_RECORD:-0}" = "1" ]; then
  ZSSH_EPIC="${ZSSH_LAST_EPIC:-VIEW-ONLY}"
  ZSSH_TASK="${ZSSH_LAST_TASK:-VIEW-ONLY}"
else
  zssh_load_state
  if zssh_confirm_continue; then
    ZSSH_EPIC="$ZSSH_LAST_EPIC"
    ZSSH_TASK="$ZSSH_LAST_TASK"
  else
    zssh_prompt_epic
    zssh_prompt_task
  fi
  zssh_save_state
fi

# 3) folder layout: <EPIC>/<TASK>/<ts>-<target>/recording/
ts="$(date +%Y%m%d-%H%M%S)"
session_dir="$ZOHAR_ROOT/$ZSSH_EPIC/$ZSSH_TASK/${ts}-${target}"
out_dir="$session_dir/recording"
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

session_log="$out_dir/session.log"
timing="$out_dir/session.timing"
wb_log="$out_dir/wb_agent.log"
fe_log="$out_dir/wb_fe_agent.log"
viewer_log="$out_dir/viewer.log"

# pre-create empty log files so the viewer / tail can open them immediately
: > "$wb_log" "$fe_log" "$session_log" "$viewer_log"

# 4a) verify the device's clock is in sync with the dev VM (fast paramiko probe).
#     Prints one summary line; only changes anything if ZSSH_TIME_AUTOFIX=1.
TIME_CHECK="$ZSSH_DIR/lib/time_check.py"
if [ -f "$TIME_CHECK" ] && command -v python3 >/dev/null 2>&1; then
  python3 "$TIME_CHECK" "$target" 2>&1 || true
fi

# 4b) launch background workers (silent).
# If the user didn't override ZSSH_WB_AGENT_CMD / ZSSH_WB_FE_AGENT_CMD, use the
# built-in DNOS-shell tailer that does:
#     ssh dnroot@<target>
#     run start shell ncp <ZSSH_NCP_ID>     # password: dnroot
#     cd <ZSSH_TRACES_DIR>
#     tail -f <agent>
DNOS_TAIL="$ZSSH_DIR/lib/dnos_log_tail.py"
if [ -z "$ZSSH_WB_AGENT_CMD" ] && [ -x "$DNOS_TAIL" -o -f "$DNOS_TAIL" ] && command -v python3 >/dev/null 2>&1; then
  ZSSH_WB_AGENT_CMD="python3 $(printf %q "$DNOS_TAIL") $(printf %q "$target") wb_agent $(printf %q "$ZSSH_NCP_ID")"
fi
if [ -z "$ZSSH_WB_FE_AGENT_CMD" ] && [ -x "$DNOS_TAIL" -o -f "$DNOS_TAIL" ] && command -v python3 >/dev/null 2>&1; then
  ZSSH_WB_FE_AGENT_CMD="python3 $(printf %q "$DNOS_TAIL") $(printf %q "$target") wb_fe_agent $(printf %q "$ZSSH_NCP_ID")"
fi

WORKER_PIDS=()
if [ -n "$ZSSH_WB_AGENT_CMD" ]; then
  ( bash -c "$ZSSH_WB_AGENT_CMD" >> "$wb_log" 2>&1 ) &
  WORKER_PIDS+=($!)
  disown $! 2>/dev/null || true
fi
if [ -n "$ZSSH_WB_FE_AGENT_CMD" ]; then
  ( bash -c "$ZSSH_WB_FE_AGENT_CMD" >> "$fe_log" 2>&1 ) &
  WORKER_PIDS+=($!)
  disown $! 2>/dev/null || true
fi

# 5) live HTML viewer (only when ssh -rv was used).
# Free the viewer port first - a previous orphan zssh.sh / viewer.py from a
# dropped SSH connection commonly leaves it bound, and the next viewer.py
# would die with "Address already in use" leaving the tunnel pointing at
# nothing (= blank tab in the Mac browser).
VIEWER_PID=""
if [ "${ZSSH_VIEWER:-0}" = "1" ]; then
  if command -v python3 >/dev/null 2>&1; then
    if command -v fuser >/dev/null 2>&1; then
      fuser -k "${ZSSH_VIEWER_PORT}/tcp" >/dev/null 2>&1 || true
      sleep 0.3
    fi
    ( "$ZSSH_DIR/lib/viewer.sh" "$out_dir" >> "$viewer_log" 2>&1 ) &
    VIEWER_PID=$!
    # disown so bash never prints "Killed" / "Terminated" job-control noise
    # when our cleanup trap shuts the viewer down at session end.
    disown $VIEWER_PID 2>/dev/null || true
  else
    echo "[zssh] python3 not found - skipping HTML viewer" >&2
  fi
fi

# Cleanup runs even if user Ctrl-C's, ssh dies, etc.
cleanup() {
  # SIGTERM background workers, then SIGKILL anything still alive after 1s.
  for pid in "${WORKER_PIDS[@]}" $VIEWER_PID; do
    [ -n "${pid:-}" ] && kill "$pid" 2>/dev/null || true
  done
  sleep 1
  for pid in "${WORKER_PIDS[@]}" $VIEWER_PID; do
    [ -n "${pid:-}" ] && kill -9 "$pid" 2>/dev/null || true
  done
  # Belt-and-braces: forcibly free the viewer port so the next session can bind.
  if [ "${ZSSH_VIEWER:-0}" = "1" ] && command -v fuser >/dev/null 2>&1; then
    fuser -k "${ZSSH_VIEWER_PORT}/tcp" >/dev/null 2>&1 || true
  fi
  if [ "${ZSSH_NO_RECORD:-0}" = "1" ]; then
    # View-only mode: nothing to upload; remove the empty/unused recording dir.
    rm -rf "$session_dir" 2>/dev/null || true
    echo
    echo "[zssh] view-only session ended (no files saved)"
    return 0
  fi
  if [ -s "$session_log" ] && command -v python3 >/dev/null 2>&1; then
    echo
    echo "[zssh] uploading session.log to Jira ${ZSSH_TASK}..."
    python3 "$ZSSH_DIR/lib/jira_upload.py" "$ZSSH_TASK" "$session_log" \
      || echo "[zssh] Jira upload failed (set JIRA_EMAIL + JIRA_API_TOKEN in ~/.zshrc)" >&2
  fi
  echo
  echo "[zssh] session ended: $out_dir/"
  echo "[zssh]   - session.log     ($(stat -c%s "$session_log" 2>/dev/null || echo 0) bytes)"
  echo "[zssh]   - wb_agent.log    ($(stat -c%s "$wb_log"      2>/dev/null || echo 0) bytes)"
  echo "[zssh]   - wb_fe_agent.log ($(stat -c%s "$fe_log"      2>/dev/null || echo 0) bytes)"
}
trap cleanup EXIT HUP INT TERM

# 6) the user-facing SSH session: pure interactive ssh, recorded transparently.
echo
if [ "${ZSSH_NO_RECORD:-0}" = "1" ]; then
  echo "  view-only mode (no recording, no Jira upload)"
  echo "  target   : $target"
else
  echo "  epic     : $ZSSH_EPIC"
  echo "  task     : $ZSSH_TASK"
  echo "  target   : $target"
  echo "  recording: $out_dir/"
fi
if [ "${ZSSH_VIEWER:-0}" = "1" ]; then
  echo "  viewer   : http://${ZSSH_VIEWER_HOST}:${ZSSH_VIEWER_PORT:-8765}/"
fi
echo

SSH_OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR -o ConnectTimeout=15"

if command -v sshpass >/dev/null 2>&1; then
  inner_cmd="sshpass -p $(printf %q "$ZSSH_DEVICE_PASSWORD") ssh ${SSH_OPTS} ${ZSSH_USER}@${target}"
else
  echo "[zssh] sshpass not found - you'll be prompted for the device password" >&2
  inner_cmd="ssh ${SSH_OPTS} ${ZSSH_USER}@${target}"
fi

# `script -q -T <timing> <typescript> -c <cmd>` records the entire interactive
# session transparently.  No tmux, no panes, no UI - the user sees a normal
# SSH prompt.  In view-only mode (ssh -v) we skip script entirely and just
# exec the inner ssh command directly so nothing lands on disk.
if [ "${ZSSH_NO_RECORD:-0}" = "1" ]; then
  bash -c "$inner_cmd" || true
else
  script -q -T "$timing" "$session_log" -c "$inner_cmd" || true
fi
