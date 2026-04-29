# Source from ~/.zshrc to enable `ssh -r <target>`:
#   . "$HOME/zohar/zssh/zssh-fn.sh"
#
# Behavior:
#   ssh -r <target> [args...]   -> run the recorder
#   ssh ...                     -> normal /usr/bin/ssh

ssh() {
  if [ "${1:-}" = "-r" ]; then
    shift
    "$HOME/zohar/zssh/zssh.sh" "$@"
  else
    command ssh "$@"
  fi
}
