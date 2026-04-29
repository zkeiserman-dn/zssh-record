#!/usr/bin/env bash
# Spawn the local HTML viewer for a zssh recording.
# Usage: viewer.sh <out_dir>
#   <out_dir> already contains session.log, wb_agent.log, wb_fe_agent.log, meta.json
#
# Picks a free port, copies index.html into out_dir, starts viewer.py serving
# from out_dir on 127.0.0.1, and opens the default browser to it.

set -euo pipefail

out_dir="${1:?usage: viewer.sh <out_dir>}"
self_dir="$(cd "$(dirname "$0")" && pwd)"

if ! command -v python3 >/dev/null 2>&1; then
  echo "[zssh-viewer] python3 not found, viewer disabled" >&2
  exit 1
fi

# free port
port="$(python3 - <<'PY'
import socket
s = socket.socket()
s.bind(("127.0.0.1", 0))
print(s.getsockname()[1])
s.close()
PY
)"

# materialize the static index.html into the recording folder
cp "$self_dir/viewer.html" "$out_dir/index.html"

url="http://127.0.0.1:${port}/"
echo "[zssh-viewer] $url"

# fire the browser (best-effort)
( command -v open >/dev/null 2>&1 && open "$url" >/dev/null 2>&1 ) || \
( command -v xdg-open >/dev/null 2>&1 && xdg-open "$url" >/dev/null 2>&1 ) || \
true

# foreground the server so the parent's `kill $PID` cleans it up on exit
exec python3 "$self_dir/viewer.py" "$port" "$out_dir"
