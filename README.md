# zssh-record

Auto-record SSH sessions to DNOS lab devices, organized by Jira **Epic** and **Testing Task**, with live colorized side panes for `wb_agent` and `wb_fe_agent` logs.

```
ssh -r YE21F5VV0000EP2
   Epic   [SW-217283]:                   <- defaults to your last epic
   Task   (e.g. SW-262109): SW-262109
   recording: ~/zohar/SW-217283/SW-262109/20260429-104812-YE21F5VV0000EP2/
```

You get one tmux session with three panes:

```
+-----------------------------------------------------------+
|  ssh dnroot@<target>                  (typescript: full)  |
|                                                           |
+-------------------------+---------------------------------+
| tail wb_agent  (color)  |  tail wb_fe_agent (color)       |
+-------------------------+---------------------------------+
```

Yellow = WARN, red = ERROR/FATAL, green = INFO, dim = DEBUG.

---

## Install (macOS or Linux)

One line:

```bash
curl -fsSL https://raw.githubusercontent.com/zkeiserman-dn/zssh-record/main/install.sh | bash
```

The installer:

- clones to `~/zohar/zssh/`
- hooks an `ssh()` shell function into `~/.zshrc` (and `~/.bashrc` if present) so that **`ssh -r <target>`** triggers the recorder while plain `ssh ...` is unchanged
- writes a default `~/.zssh.conf` you can edit
- reminds you to `brew install tmux` on macOS if missing

Open a new terminal (or `source ~/.zshrc`) once after install.

---

## Use

```bash
ssh -r 100.64.x.y           # IP
ssh -r YE21F5VV0000EP2      # serial / hostname
```

The tool prompts you the first time for:

| Field | Example |
|---|---|
| Epic | `SW-217283` |
| Testing Task | `SW-262109` |

Both are remembered in `~/.zssh-state`; press Enter at the prompts to reuse them. If you switch tickets, just type the new ID — IDs are auto-normalized (`sw217283` -> `SW-217283`).

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

## Auto-update

On every launch, `zssh.sh` does a non-blocking `git fetch + git reset origin/main` against this repo. To pin a version, set `ZSSH_SELF_UPDATE=0` in `~/.zssh.conf`.

The current version is in [`VERSION`](VERSION).

---

## Layout in this repo

```
zssh-record/
├── zssh.sh            # main entry; recorder + tmux launcher
├── zssh-fn.sh         # `ssh -r ...` shell hook (sourced from ~/.zshrc)
├── install.sh         # one-time installer
├── lib/
│   ├── prompt.sh      # sticky epic/task prompts + Jira-id normalization
│   └── colorize.sh    # awk colorizer (red=ERROR, yellow=WARN, ...)
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

**Wrong epic/task picked up** -> blow away the cache: `rm ~/.zssh-state`.

---

## License

MIT. See [LICENSE](LICENSE).
