# Changelog

All notable changes to **zssh-record** are tracked here.

## 0.2.0 - 2026-04-29

- **Sticky prompt is now confirm-first.** When `~/.zssh-state` already has an Epic+Task, zssh asks `Continue on <EPIC> / <TASK> ? [Y/n]:` first. Y/Enter reuses silently; `n` drops into the existing two prompts. First-ever launch (no state) still goes straight to the two prompts.
- **New `ssh -rv <target>` flag = recorder + live HTML viewer.** Same recording behavior as `-r`, plus a tiny stdlib HTTP server on 127.0.0.1 (random free port) that streams `session.log`, `wb_agent.log`, and `wb_fe_agent.log` to a single browser page via Server-Sent Events. Default browser opens automatically (`open` on macOS, `xdg-open` on Linux). New files: `lib/viewer.sh`, `lib/viewer.py`, `lib/viewer.html`.
- Browser viewer mirrors `lib/colorize.sh` rules in JS (red ERROR/FATAL/CRIT/Traceback, yellow WARN, green INFO, dim DEBUG/TRACE), strips ANSI escapes, auto-scrolls unless the user has scrolled up, and shows Epic/Task/target/started_at from `meta.json` in the header.
- Viewer process is bound to `127.0.0.1` only and is killed automatically when the recording session exits.
- `zssh.sh` now pre-creates empty `session.log` / `wb_agent.log` / `wb_fe_agent.log` so the viewer and tail panes can attach immediately.

## 0.1.0 - 2026-04-29

Initial release.

- `ssh -r <target>` shell hook (zsh + bash) installed by `install.sh`.
- Sticky Epic + Testing-Task prompts (state in `~/.zssh-state`); same epic+task -> same folder.
- Folder layout: `~/zohar/<EPIC>/<TASK>/<YYYYmmdd-HHMMSS>-<target>/`.
- `script(1)` typescript of the full interactive SSH session (`session.log` + `session.timing`).
- Tmux 3-pane live view: SSH session on top, `wb_agent` and `wb_fe_agent` tails below.
- Colorizer: red = ERROR/FATAL/CRIT/Traceback, yellow = WARN/WARNING, green = INFO, dim = DEBUG/TRACE.
- Per-user config in `~/.zssh.conf` (`ZSSH_USER`, `ZSSH_WB_AGENT_CMD`, `ZSSH_WB_FE_AGENT_CMD`, `ZSSH_TMUX_LAYOUT`, `ZSSH_SELF_UPDATE`).
- Self-update on launch via `git fetch + reset origin/main`.
- Graceful fallback to plain recorded SSH when `tmux` is missing.
