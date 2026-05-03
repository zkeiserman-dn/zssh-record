# Source from ~/.zshrc on your Mac to enable `ssh -r` / `ssh -rv`:
#     . "$HOME/zohar/zssh/zssh-fn.sh"
#
# Behavior on the Mac:
#   ssh -r  <target>     -> a *plain* SSH session to the device, recorded
#                           transparently in the background on the dev VM
#   ssh -rv <target>     -> same as -r, plus a live HTML viewer
#                           opened automatically in your Mac browser
#   ssh ...              -> normal /usr/bin/ssh, untouched
#
# First invocation auto-pushes your SSH key to ZSSH_DEV_VM so you never see
# a password prompt again.
#
# Configurable via ~/.zssh.conf on the Mac:
#   ZSSH_DEV_VM       hostname of your dev VM       (default: ${USER}-dev)
#   ZSSH_DEV_PASSWORD password used ONLY for first-time key push (no default; set in ~/.zssh.conf)
#   ZSSH_VIEWER_PORT  TCP port for -rv viewer       (default: 8765)
#   ZSSH_VIEWER_URL   override URL the Mac browser opens
#                     (default: http://<ZSSH_DEV_VM>:<port>/   no tunnel)

# shellcheck disable=SC1090
[ -f "$HOME/.zssh.conf" ] && . "$HOME/.zssh.conf"
# Override these for your own dev VM in ~/.zssh.conf:
: "${ZSSH_DEV_VM:=${USER}-dev}"
: "${ZSSH_DEV_PASSWORD:=${ZSSH_DEV_PASSWORD:-}}"
: "${ZSSH_VIEWER_PORT:=8765}"
# Default URL = direct dev-VM hostname (viewer.py binds 0.0.0.0 so no tunnel needed)
: "${ZSSH_VIEWER_URL:=http://${ZSSH_DEV_VM}:${ZSSH_VIEWER_PORT}/}"
# Stamp passed to zssh.sh so the dev VM can detect old wrappers and warn.
ZSSH_FN_VERSION="0.5.5"

# One-time SSH-key push so future ssh's are password-less.
_zssh_ensure_key_auth() {
  # already password-less?  done.
  command ssh -o BatchMode=yes -o ConnectTimeout=4 -o StrictHostKeyChecking=no \
    "$ZSSH_DEV_VM" true 2>/dev/null && return 0

  # need to set up
  echo "[zssh] one-time setup: pushing your SSH key to $ZSSH_DEV_VM ..."
  [ -d "$HOME/.ssh" ] || mkdir -p "$HOME/.ssh" && chmod 700 "$HOME/.ssh"
  if [ ! -f "$HOME/.ssh/id_ed25519" ] && [ ! -f "$HOME/.ssh/id_rsa" ]; then
    ssh-keygen -t ed25519 -N "" -f "$HOME/.ssh/id_ed25519" >/dev/null
  fi

  if command -v sshpass >/dev/null 2>&1; then
    sshpass -p "$ZSSH_DEV_PASSWORD" ssh-copy-id -o StrictHostKeyChecking=no "$ZSSH_DEV_VM" \
      >/dev/null 2>&1 \
      && echo "[zssh] key pushed via sshpass; you won't be asked again." \
      && return 0
  fi
  if command -v expect >/dev/null 2>&1; then
    expect <<EOF >/dev/null
log_user 0
set timeout 20
spawn ssh-copy-id -o StrictHostKeyChecking=no $ZSSH_DEV_VM
expect {
  -re {[Pp]assword:} { send "$ZSSH_DEV_PASSWORD\r"; exp_continue }
  -re {Are you sure you want to continue connecting} { send "yes\r"; exp_continue }
  eof
}
EOF
    if command ssh -o BatchMode=yes -o ConnectTimeout=4 "$ZSSH_DEV_VM" true 2>/dev/null; then
      echo "[zssh] key pushed via expect; you won't be asked again."
      return 0
    fi
  fi

  echo "[zssh] couldn't auto-push key; please run once:  ssh-copy-id $ZSSH_DEV_VM"
  return 1
}

ssh() {
  case "${1:-}" in
    -r)
      shift
      local target="${1:?ssh -r: target required}"
      shift || true
      _zssh_ensure_key_auth
      command ssh -t "$ZSSH_DEV_VM" \
        "ZSSH_FN_VERSION=${ZSSH_FN_VERSION} ~/zohar/zssh/zssh.sh '$target'"
      ;;
    -v)
      shift
      local target="${1:?ssh -v: target required}"
      shift || true
      _zssh_ensure_key_auth
      local _ssh_cmd="ZSSH_FN_VERSION=${ZSSH_FN_VERSION} ZSSH_VIEWER=1 ZSSH_NO_RECORD=1 ZSSH_VIEWER_PORT=${ZSSH_VIEWER_PORT} ~/zohar/zssh/zssh.sh '$target'"
      echo "[zssh] view-only mode (no recording, no Jira upload)"
      echo "[zssh] viewer: $ZSSH_VIEWER_URL  (browser opens ~10s after connect)"
      _zssh_open_browser() {
        sleep 10
        if command -v open >/dev/null 2>&1; then open "$ZSSH_VIEWER_URL" >/dev/null 2>&1
        elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$ZSSH_VIEWER_URL" >/dev/null 2>&1
        fi
      }
      if [ -n "${ZSH_VERSION:-}" ]; then
        _zssh_open_browser >/dev/null 2>&1 &!
      else
        _zssh_open_browser >/dev/null 2>&1 &
        disown 2>/dev/null || true
      fi
      command ssh -t "$ZSSH_DEV_VM" "$_ssh_cmd"
      ;;
    -rv)
      shift
      local target="${1:?ssh -rv: target required}"
      shift || true
      _zssh_ensure_key_auth
      local _ssh_cmd="ZSSH_FN_VERSION=${ZSSH_FN_VERSION} ZSSH_VIEWER=1 ZSSH_VIEWER_PORT=${ZSSH_VIEWER_PORT} ~/zohar/zssh/zssh.sh '$target'"

      echo "[zssh] viewer: $ZSSH_VIEWER_URL  (browser opens ~10s after connect)"
      _zssh_open_browser() {
        sleep 10
        if command -v open >/dev/null 2>&1; then open "$ZSSH_VIEWER_URL" >/dev/null 2>&1
        elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$ZSSH_VIEWER_URL" >/dev/null 2>&1
        fi
      }
      if [ -n "${ZSH_VERSION:-}" ]; then
        _zssh_open_browser >/dev/null 2>&1 &!
      else
        _zssh_open_browser >/dev/null 2>&1 &
        disown 2>/dev/null || true
      fi
      command ssh -t "$ZSSH_DEV_VM" "$_ssh_cmd"
      ;;
    *)
      command ssh "$@"
      ;;
  esac
}
