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

_zssh_open_browser_after() {
  local url="$1"
  if [ -n "${ZSH_VERSION:-}" ]; then
    ( sleep 10
      if command -v open >/dev/null 2>&1; then open "$url" >/dev/null 2>&1
      elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$url" >/dev/null 2>&1
      fi
    ) >/dev/null 2>&1 &!
  else
    ( sleep 10
      if command -v open >/dev/null 2>&1; then open "$url" >/dev/null 2>&1
      elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$url" >/dev/null 2>&1
      fi
    ) >/dev/null 2>&1 &
    disown 2>/dev/null || true
  fi
}

ssh() {
  local arg="${1:-}"
  # Match any combination of the letters r, v, t (1-3 chars) after a single -
  case "$arg" in
    -[rvt]|-[rvt][rvt]|-[rvt][rvt][rvt])
      shift
      local target="${1:?ssh $arg: target required}"
      shift || true
      local opt="${arg#-}"

      local rec=0 view=0 timesync=0
      case "$opt" in *r*) rec=1 ;; esac
      case "$opt" in *v*) view=1 ;; esac
      case "$opt" in *t*) timesync=1 ;; esac

      local _env="ZSSH_FN_VERSION=${ZSSH_FN_VERSION}"
      [ "$rec" = 0 ]      && _env="$_env ZSSH_NO_RECORD=1"
      [ "$view" = 1 ]     && _env="$_env ZSSH_VIEWER=1 ZSSH_VIEWER_PORT=${ZSSH_VIEWER_PORT}"
      [ "$timesync" = 1 ] && _env="$_env ZSSH_TIME_AUTOFIX=1"

      _zssh_ensure_key_auth

      local _label_rec="OFF" _label_view="OFF" _label_ts="OFF"
      [ "$rec" = 1 ]      && _label_rec="ON"
      [ "$view" = 1 ]     && _label_view="ON"
      [ "$timesync" = 1 ] && _label_ts="ON"
      echo "[zssh] mode: record=${_label_rec}  viewer=${_label_view}  time-sync=${_label_ts}"
      [ "$view" = 1 ] && {
        echo "[zssh] viewer: $ZSSH_VIEWER_URL  (browser opens ~10s after connect)"
        _zssh_open_browser_after "$ZSSH_VIEWER_URL"
      }

      command ssh -t "$ZSSH_DEV_VM" "${_env} ~/zohar/zssh/zssh.sh '$target'"
      ;;
    *)
      command ssh "$@"
      ;;
  esac
}
