# Source from ~/.zshrc to enable `ssh -r <target>` and `ssh -rv <target>`:
#   . "$HOME/zohar/zssh/zssh-fn.sh"
#
# Behavior:
#   ssh -r  <target> [args...]   -> run the recorder (tmux + colorized tails)
#   ssh -rv <target> [args...]   -> run the recorder + open the live HTML viewer
#   ssh ...                      -> normal /usr/bin/ssh

ssh() {
  case "${1:-}" in
    -r)
      shift
      "$HOME/zohar/zssh/zssh.sh" "$@"
      ;;
    -rv)
      shift
      ZSSH_VIEWER=1 "$HOME/zohar/zssh/zssh.sh" "$@"
      ;;
    *)
      command ssh "$@"
      ;;
  esac
}
