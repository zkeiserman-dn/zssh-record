#!/usr/bin/env bash
# Colorize a log stream:
#   - ERROR / FATAL / CRIT  -> red
#   - WARN / WARNING        -> yellow
#   - INFO                  -> green (subtle)
#   - DEBUG                 -> dim
# Usage:
#   echo "..." | bash colorize.sh stream
#   bash colorize.sh stream < file
#
# Sourced (no args) -> just defines color helpers, does not run filter.

zssh_color_red='\033[31m'
zssh_color_yellow='\033[33m'
zssh_color_green='\033[32m'
zssh_color_dim='\033[2m'
zssh_color_reset='\033[0m'

zssh_colorize_stream() {
  awk -v R="$zssh_color_red" -v Y="$zssh_color_yellow" \
      -v G="$zssh_color_green" -v D="$zssh_color_dim" -v X="$zssh_color_reset" '
    /([Ee][Rr][Rr][Oo][Rr]|FATAL|CRIT|panic|Traceback)/ { print R $0 X; next }
    /([Ww][Aa][Rr][Nn][Ii][Nn][Gg]?|[Ww][Aa][Rr][Nn])/  { print Y $0 X; next }
    /([Ii][Nn][Ff][Oo])/                                { print G $0 X; next }
    /([Dd][Ee][Bb][Uu][Gg]|TRACE)/                      { print D $0 X; next }
    { print }
  '
}

# Only act on positional args when this file is *executed* (not sourced).
# Sourced parents inherit positional params, so checking $1 alone is unsafe.
if [ "${BASH_SOURCE[0]:-$0}" = "$0" ]; then
  case "${1:-}" in
    stream) zssh_colorize_stream ;;
    "")     echo "usage: $0 stream" >&2; exit 2 ;;
    *)      echo "usage: $0 stream" >&2; exit 2 ;;
  esac
fi
