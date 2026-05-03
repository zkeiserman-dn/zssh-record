#!/usr/bin/env bash
# Spawn the local HTML viewer for a zssh recording.
# Usage: viewer.sh <out_dir>
#   <out_dir> already contains session.log, wb_agent.log, wb_fe_agent.log, meta.json
#
# Picks a free port, copies index.html into out_dir, starts viewer.py serving
# from out_dir on the dev VM, and opens the default browser to it.

set -euo pipefail

out_dir="${1:?usage: viewer.sh <out_dir>}"
self_dir="$(cd "$(dirname "$0")" && pwd)"

if ! command -v python3 >/dev/null 2>&1; then
  echo "[zssh-viewer] python3 not found, viewer disabled" >&2
  exit 1
fi

# pick port: explicit ZSSH_VIEWER_PORT > free port
if [ -n "${ZSSH_VIEWER_PORT:-}" ]; then
  port="$ZSSH_VIEWER_PORT"
else
  port="$(python3 - <<'PY'
import socket
s = socket.socket()
s.bind(("", 0))
print(s.getsockname()[1])
s.close()
PY
)"
fi

# materialize the static index.html into the recording folder
cp "$self_dir/viewer.html" "$out_dir/index.html"

# Bind address (where the python server actually listens on the dev VM)
bind="${ZSSH_VIEWER_BIND:-0.0.0.0}"
# Hostname/IP the user's Mac browser should navigate to
host="${ZSSH_VIEWER_HOST:-$(hostname -f 2>/dev/null || hostname)}"
url="http://${host}:${port}/"
echo "[zssh-viewer] open in your Mac browser: $url"
echo "[zssh-viewer] (server bound to ${bind}:${port} on the dev VM)"

# foreground the server so the parent's `kill $PID` cleans it up on exit
exec python3 "$self_dir/viewer.py" "$port" "$out_dir" "$bind"
