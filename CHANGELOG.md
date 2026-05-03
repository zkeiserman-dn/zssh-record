# Changelog

All notable changes to **zssh-record** are tracked here.

## 0.6.0 - 2026-05-03

- **New `ssh -v <target>` view-only mode**: same browser viewer (wb_agent + wb_fe_agent live panes, errors-only panes) but skips Epic/Task prompts, skips `script` typescript recording, and skips Jira upload at session end. Useful when you just want the live agent log panes without keeping any artefacts.
- `ZSSH_NO_RECORD=1` is the dev-VM-side switch the new wrapper sets. The recording dir is created and immediately removed at exit; no state file or Jira call.
- Repo cleanup: removed unrelated leftover scripts/ + docs/ from the policer epic.
- Public release prep: `ZSSH_DEV_PASSWORD` no longer defaults to a baked-in value. Set it once in `~/.zssh.conf` on your Mac. The one-time `ssh-copy-id` push asks for it interactively if not set.



## 0.5.2 - 2026-04-29

- **`-rv` opens `http://<ZSSH_DEV_VM>:8765/` directly** (default `http://zkeiserman-dev:8765/`). No more `127.0.0.1` / `localhost` URL. The SSH `-L` tunnel is dropped entirely - `viewer.py` binds `0.0.0.0` on the dev VM, the Mac browser hits the dev VM hostname directly, no `bind: Address already in use` errors when local 8765 is held by a stale process.
- **Paramiko `CryptographyDeprecationWarning` silenced** in `lib/time_check.py` and `lib/dnos_log_tail.py` (TripleDES noise no longer pollutes the user's terminal during `ssh -r` / `ssh -rv`).
- Override the URL or bind in `~/.zssh.conf` if you ever need a private viewer:
  - `ZSSH_VIEWER_URL="http://localhost:8765/"`
  - `ZSSH_VIEWER_BIND="127.0.0.1"`

## 0.5.1 - 2026-04-29

- **Mac wrapper auto-pushes your SSH key on first launch** (`_zssh_ensure_key_auth` in `zssh-fn.sh`). Tries:
  1. `BatchMode=yes` probe - if you can already log in without a password, do nothing
  2. `sshpass -p $ZSSH_DEV_PASSWORD ssh-copy-id` if `sshpass` is on the Mac
  3. `expect` with `ssh-copy-id` (always present on macOS)
  4. Fall through with a hint to run `ssh-copy-id` manually
- `ZSSH_DEV_PASSWORD` (no default) - set in `~/.zssh.conf` for the one-time `ssh-copy-id` push.
- After the one-time push, every future `ssh -r` / `ssh -rv` connects with the key, no password prompt, no zsh `[3] done` noise.

## 0.5.0 - 2026-04-29

- **New `lib/time_check.py`**: every `ssh -r` / `ssh -rv` now runs a 5-second clock-sync probe against the device before recording starts. Prints one summary line, e.g. `[zssh-time] device=2026-04-29 12:35:56Z  drift=-3s  OK (NTP)`. Reads device epoch via `run start shell ncp 0 -> date '+%s'`, then `show config system timing-mode` + `show system ntp` to label the source as `NTP` / `manual`.
- **Auto-fix when drift > threshold**: if `ZSSH_TIME_AUTOFIX=1` (off by default) and `|drift| > ZSSH_TIME_DRIFT_THRESHOLD` (default 60s), `time_check.py` flips `system timing-mode manual` and runs `set system datetime <dev-VM-now>` so the recording's wb_agent timestamps line up with the dev-VM clock.
- **Cleaner end-of-session banner**: announces "uploading session.log to Jira <TASK>..." before the upload, then prints byte sizes for `session.log`, `wb_agent.log`, `wb_fe_agent.log`.
- (Reminder: Jira auto-upload was added in 0.3.0; it requires `JIRA_EMAIL` + `JIRA_API_TOKEN` in `~/.zshrc` on the dev VM.)

## 0.4.3 - 2026-04-29

- **HTML viewer is now 2 panes only**: `wb_agent` (left) and `wb_fe_agent` (right). The previous "SSH SESSION (session.log)" pane was removed at user request - the SSH session is still recorded transparently to `session.log` on disk and still auto-uploaded to the Jira testing task at end of session, just no longer rendered live in the browser. The `/stream/session` endpoint stays in `viewer.py` for backwards compatibility but is no longer wired into the page.

## 0.4.2 - 2026-04-29

- **Stale viewer port no longer breaks `ssh -rv`.** Before launching `viewer.py`, `zssh.sh` now frees `$ZSSH_VIEWER_PORT/tcp` via `fuser -k` so a leftover `viewer.py` from a previously dropped SSH session can't make the new viewer die with `Address already in use` (which manifested as a blank tab in the Mac browser).
- **Cleanup trap is more aggressive**: catches `EXIT HUP INT TERM`, SIGTERMs background workers + viewer, then SIGKILLs anything still alive after 1s, then frees the port one more time.

## 0.4.1 - 2026-04-29

- **wb_agent / wb_fe_agent now tail automatically** without configuration. New `lib/dnos_log_tail.py` (paramiko) drops into the NCP shell on the device the same way you do by hand:
  ```
  ssh dnroot@<target>
  > run start shell ncp 0      (password: dnroot)
  $ cd /core/traces/datapath
  $ tail -f wb_agent           (and wb_fe_agent in a second worker)
  ```
- Both streams write to `wb_agent.log` / `wb_fe_agent.log` in the recording folder and are visible live in the HTML viewer.
- New env knobs (override in `~/.zssh.conf`):
  - `ZSSH_NCP_ID` (default `0`)
  - `ZSSH_TRACES_DIR` (default `/core/traces/datapath`)
- Verified live against `YE21F5VV0000EP2`: full `wb_agent` ASIC error stream and `wb_fe_agent` Python-side logs streaming end-to-end through the recorder.

## 0.4.0 - 2026-04-29

- **`ssh -r` is now a transparent SSH session.** No tmux, no panes, no UI noise - the user sees a normal SSH prompt to the device while everything is recorded silently in the background. Removes the previous "Pane is dead" / "[zssh-pane] command exited" experience.
- **Background workers**: `ZSSH_WB_AGENT_CMD` / `ZSSH_WB_FE_AGENT_CMD` now run as silent background processes whose output goes to `wb_agent.log` / `wb_fe_agent.log`. They never appear on the user's terminal. Cleanup on session end via a single bash `trap`.
- **`ssh -rv` viewer is reliable**: Mac wrapper sets up `ssh -L 127.0.0.1:8765:127.0.0.1:8765` so the browser opens `http://localhost:8765/` over the tunnel - works regardless of whether the dev-VM hostname resolves from the Mac. Auto-launches the default browser ~3s after ssh starts and disowns the helper subshell so zsh doesn't print "[N] done".
- **`script` flag fix**: switched from deprecated `-t TIMING_FILE LOG_FILE` (which on util-linux 2.37 silently breaks: it consumes the timing arg as the typescript path and discards the log positional) to the modern `-T TIMING_FILE LOG_FILE`. Recording files were not being written before this fix on dev VMs running util-linux 2.37+.
- viewer-related env vars are now properly **exported** so `viewer.sh` honours `ZSSH_VIEWER_HOST` / `ZSSH_VIEWER_BIND` / `ZSSH_VIEWER_PORT` from the parent.
- viewer.log is now stored under the recording dir for easier post-mortem.
- `dnroot/dnroot` SSH still uses sshpass, side-pane builder code from 0.3.1 is dropped (no panes any more).

## 0.3.1 - 2026-04-29

- **Side-pane defaults removed**: the previous `request shell node-id 1 "tail -f /var/log/dn/wb_agent.log"` defaults were rejected by DNOS CLI non-interactively ("Invalid command"). Both panes now show a friendly placeholder explaining how to set `ZSSH_WB_AGENT_CMD` / `ZSSH_WB_FE_AGENT_CMD` to any shell command that streams a log on the dev VM (e.g. `tail -F /home/dn/syslog-collector/wb_agent.log` or `kubectl logs -f -n dnos wb_agent`). The pane keeps the local `tail -f` of its log file alive so the HTML viewer pane still updates as soon as something writes to it.
- **Viewer no longer needs SSH `-L` tunnel**. Defaults: `ZSSH_VIEWER_BIND=0.0.0.0` on the dev VM and `ZSSH_VIEWER_HOST=$(hostname -f)`. The Mac browser opens `http://zkeiserman-dev:8765/` directly. Eliminates the silent `ERR_CONNECTION_RESET` users were hitting when SSH local forward was blocked or racy.
- Mac wrapper for `-rv` skips the `-L` tunnel and silences the zsh "[N] done" job-control noise.
- `viewer.py` accepts a 3rd argv = bind address.
- `zssh-record` 0.3.1 tarball.

## 0.3.0 - 2026-04-29

- **Recording lives on the dev VM, not the Mac.** Mac becomes a thin shell wrapper that runs `zssh.sh` over SSH on `ZSSH_DEV_VM` (default `zkeiserman-dev`, override in `~/.zssh.conf`).
- **New folder layout**: `~/zohar/<EPIC>/<TASK>/<ts>-<target>/recording/{session.log,session.timing,wb_agent.log,wb_fe_agent.log,meta.json}` (the recordings now sit under a dedicated `recording/` subfolder so the parent dir can host other artefacts later).
- **Auto-Jira upload**: after the SSH session ends, `session.log` is uploaded as an attachment to the testing task entered at the prompt (e.g. `SW-262109`). New file `lib/jira_upload.py`. Requires `JIRA_EMAIL` + `JIRA_API_TOKEN` (token at <https://id.atlassian.com/manage-profile/security/api-tokens>); without them, upload is silently skipped with a hint.
- **Auto-update via symlink**: install `~/zohar/zssh -> /home/dn/zssh-record/` on the dev VM (live dev tree); every new `ssh -r` picks up the latest code with no `git pull`.
- **`ssh -rv` viewer over SSH tunnel**: Mac wrapper opens `http://127.0.0.1:8765/` automatically (port configurable via `ZSSH_VIEWER_PORT`); Python server on the dev VM binds to that port and `-L`-tunnels back to Mac. Browser auto-launches with `open` (macOS) / `xdg-open` (Linux).
- `zssh-fn.sh` is now the **only** file the Mac needs (plus `install.sh` once); recordings, tail, viewer, upload all run on the dev VM.

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
