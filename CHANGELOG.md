# Changelog

All notable changes to **zssh-record** are tracked here.

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
