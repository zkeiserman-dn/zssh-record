# zssh-record

Transparently record SSH sessions to DNOS lab devices, organized by Jira **Epic** and **Testing Task**. Live wb_agent / wb_fe_agent logs in your browser. Auto-attach `session.log` to the testing task on exit.

| Mac command | What happens |
|---|---|
| `ssh -r <target>`  | Plain SSH session, recorded silently. On exit, `session.log` uploads to the Jira testing task. |
| `ssh -rv <target>` | Same as `-r` plus a 4-pane live HTML viewer in your default browser. |
| `ssh -v <target>`  | Same browser viewer, but **no recording** and **no Jira upload**. Use when you just want to see live wb_agent / wb_fe_agent. |
| `ssh ...`          | Untouched - normal `/usr/bin/ssh`. |

Browser layout (`-rv` and `-v`):

```
+-----------------------------------------------------+
|  zssh-record   epic SW-... | task SW-... | target.. |
+----------------------------+------------------------+
|  wb_agent (live, full)     |  wb_fe_agent (full)    |
+----------------------------+------------------------+
|  wb_agent - ERRORS only    |  wb_fe_agent - ERRORS  |
+----------------------------+------------------------+
```

Color rules: red = `ERROR/FATAL/CRIT/Traceback`, yellow = `WARN/WARNING`, green = `INFO`, dim = `DEBUG/TRACE`.

---

## Install (Mac side)

One line, in a Mac terminal:

```bash
curl -fsSL https://raw.githubusercontent.com/zkeiserman-dn/zssh-record/main/install.sh | bash
```

The installer:

- clones to `~/zohar/zssh/`
- hooks an `ssh()` shell function into `~/.zshrc` (and `~/.bashrc` if present) so that **`ssh -r`**, **`ssh -rv`**, and **`ssh -v`** trigger the recorder; plain `ssh ...` is unchanged
- writes a default `~/.zssh.conf` you can edit
- on first run, pushes your SSH key to the dev VM (asks `ZSSH_DEV_PASSWORD` once via `expect`; never again afterwards)

Edit `~/.zssh.conf` once with your dev-VM hostname and password:

```bash
ZSSH_DEV_VM="<your>-dev"
ZSSH_DEV_PASSWORD="<your-dev-vm-password>"   # only used for one-time ssh-copy-id
```

## Install (dev VM side)

The recorder runs on your dev VM. Clone there too and add credentials:

```bash
ssh dn@<your>-dev
git clone https://github.com/zkeiserman-dn/zssh-record.git ~/zohar/zssh
cat >> ~/.zssh.conf <<'EOF'
export JIRA_EMAIL='you@drivenets.com'
export JIRA_API_TOKEN='ATATT...your-token...'
EOF
chmod 600 ~/.zssh.conf
```

Token at <https://id.atlassian.com/manage-profile/security/api-tokens>.

Open a new terminal on your Mac (or `source ~/.zshrc`) once after install.

---

## Use

```bash
ssh -r  100.64.x.y           # IP, terminal-only recorder
ssh -r  YE21F5VV0000EP2      # serial / hostname
ssh -rv YE21F5VV0000EP2      # same + live HTML viewer in your browser
```

On launch:

- **First time** (no cached state) you're asked once for the **Epic** (e.g. `SW-217283`) and the **Testing Task** (e.g. `SW-262109`).
- **Every subsequent launch** asks one question only:
  ```
  Continue on SW-217283 / SW-262109 ? [Y/n]:
  ```
  - Press Enter or `y` -> reuse, no further prompts.
  - Type `n` -> drops into the two prompts so you can switch tickets.

State is cached in `~/.zssh-state`. Jira IDs are auto-normalized (`sw217283` -> `SW-217283`).

Each session creates:

```
~/zohar/<EPIC>/<TASK>/<timestamp>-<target>/
   session.log         full typescript of the SSH session
   session.timing      timing file (replay with: scriptreplay)
   wb_agent.log        colorized agent log (raw + ANSI codes)
   wb_fe_agent.log     colorized FE agent log
   meta.json           epic, task, target, started_at, tool_version
```

Recordings for the **same epic+task pair always land in the same folder**, with one timestamped subfolder per SSH session.

Replay a session later:

```bash
cd ~/zohar/SW-217283/SW-262109/20260429-104812-YE21F5VV0000EP2
scriptreplay session.timing session.log
```

---

## Configuration

Per-user, in `~/.zssh.conf` (sourced by `zssh.sh`). Examples:

```bash
# different ssh user
ZSSH_USER="dnroot"

# DNOS bash-style log paths (if reachable directly)
ZSSH_WB_AGENT_CMD='request shell node-id 1 "tail -f -n 50 /var/log/dn/wb_agent.log"'
ZSSH_WB_FE_AGENT_CMD='request shell node-id 1 "tail -f -n 50 /var/log/dn/wb_fe_agent.log"'

# alternative: drop straight to bash on a node
# ZSSH_WB_AGENT_CMD='nsenter -t 1 -m -p tail -f /var/log/dn/wb_agent.log'

# layout: main-horizontal | tiled | even-vertical
ZSSH_TMUX_LAYOUT="main-horizontal"

# disable auto-update on every launch
ZSSH_SELF_UPDATE=0
```

Default commands are wrapped through DNOS `request shell` to be portable across releases. If your image needs different paths, edit them once here.

---

## Live HTML viewer (`-rv`)

When you run `ssh -rv <target>`, a tiny stdlib HTTP server is started on `127.0.0.1:<random-free-port>` and your default browser opens to it. The page has three live, colorized, auto-scrolling panes:

| Pane | Source |
|---|---|
| ssh session | `session.log` (typescript) |
| wb_agent    | `wb_agent.log` |
| wb_fe_agent | `wb_fe_agent.log` |

The page consumes three Server-Sent Event streams (`/stream/session`, `/stream/wb`, `/stream/fe`) and re-applies the same coloring rules as the tmux pane (yellow WARN, red ERROR/FATAL/Traceback, green INFO, dim DEBUG/TRACE). Closing the tab does not stop recording. The HTTP server is bound to localhost and is killed automatically when you exit the SSH session.

If `python3` isn't installed, `-rv` quietly degrades to plain `-r`.

---

## Auto-update

On every launch, `zssh.sh` does a non-blocking `git fetch + git reset origin/main` against this repo. To pin a version, set `ZSSH_SELF_UPDATE=0` in `~/.zssh.conf`.

The current version is in [`VERSION`](VERSION).

---

## Layout in this repo

```
zssh-record/
├── zssh.sh            # main entry; recorder + tmux launcher
├── zssh-fn.sh         # `ssh -r` / `ssh -rv` shell hook (sourced from ~/.zshrc)
├── install.sh         # one-time installer
├── lib/
│   ├── prompt.sh      # sticky epic/task prompts + Y/n confirm + Jira-id normalization
│   ├── colorize.sh    # awk colorizer (red=ERROR, yellow=WARN, ...)
│   ├── viewer.sh      # picks free port, copies index.html, opens browser, exec viewer.py
│   ├── viewer.py      # stdlib HTTP+SSE server (127.0.0.1 only)
│   └── viewer.html    # 3-pane live HTML viewer
├── VERSION
├── CHANGELOG.md
├── LICENSE
└── README.md
```

---

## Troubleshooting

**`ssh -r` just runs normal ssh** -> the hook isn't loaded; `source ~/.zshrc` and confirm the file shows the `# >>> zssh-record >>>` block.

**Empty side panes** -> the `request shell` command failed (different DNOS release path). Edit `ZSSH_WB_*_CMD` in `~/.zssh.conf`.

**`tmux: command not found`** -> falls back to plain `script`-recorded SSH (no side panes). Install tmux to get the full layout.

**Wrong epic/task picked up** -> answer `n` at the `Continue on … [Y/n]:` prompt, or blow away the cache: `rm ~/.zssh-state`.

**`-rv` browser tab shows "stream closed"** -> the SSH session ended; the viewer process is shut down on exit by design. Re-open with another `ssh -rv <target>`.

**`-rv` did not open the browser** -> the URL is printed in your terminal as `[zssh-viewer] http://127.0.0.1:<port>/`. Paste it manually.

---

## License

MIT. See [LICENSE](LICENSE).
