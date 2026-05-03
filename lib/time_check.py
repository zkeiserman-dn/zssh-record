#!/usr/bin/env python3
"""
Verify the DNOS device's clock is in sync with the dev VM, and
optionally fix it if it drifts.

Behavior:
    * Always prints a one-line summary like:
          [zssh-time] device=2026-04-29 15:30:12  drift=0s  OK (NTP)
    * If ZSSH_TIME_AUTOFIX=1 and drift > ZSSH_TIME_DRIFT_THRESHOLD seconds:
          - flips system timing-mode to manual
          - `set system datetime <now>` from the dev VM clock
          - prints what it did

Intended to be invoked from zssh.sh before each recording session.
Never blocks the SSH session for more than ~10s; on any error it just
prints a warning and exits 0 so the recorder still runs.

Usage:
    time_check.py <target>

Env:
    ZSSH_USER                 default dnroot
    ZSSH_DEVICE_PASSWORD      default dnroot
    ZSSH_NCP_ID               default 0
    ZSSH_TIME_DRIFT_THRESHOLD default 60      (seconds)
    ZSSH_TIME_AUTOFIX         default 0       (1 = apply manual time)
"""

from __future__ import annotations

import datetime as dt
import os
import re
import sys
import time
import warnings

# Silence paramiko's third-party CryptographyDeprecationWarning noise.
warnings.filterwarnings("ignore")
os.environ.setdefault("PYTHONWARNINGS", "ignore")

try:
    import paramiko
except ImportError:
    sys.stderr.write("[zssh-time] paramiko not installed; skipping\n")
    sys.exit(0)


PROMPT_DNOS = re.compile(rb"[A-Za-z0-9._-]+#\s*$")
PROMPT_BASH = re.compile(rb"[\w.-]+@[\w.-]+:\S+[#$]\s*$")
PROMPT_PWD = re.compile(rb"[Pp]assword:\s*$")
EPOCH_RE = re.compile(rb"(\d{10})\s")


def drain(shell, deadline: float, until=None) -> bytes:
    buf = b""
    while time.time() < deadline:
        if shell.recv_ready():
            chunk = shell.recv(65536)
            if not chunk:
                break
            buf += chunk
            if until is not None and until.search(buf):
                return buf
        else:
            time.sleep(0.05)
    return buf


def main() -> int:
    if len(sys.argv) < 2:
        sys.stderr.write("usage: time_check.py <target>\n")
        return 0

    target = sys.argv[1]
    user = os.environ.get("ZSSH_USER", "dnroot").strip() or "dnroot"
    password = os.environ.get("ZSSH_DEVICE_PASSWORD", "dnroot")
    ncp_id = os.environ.get("ZSSH_NCP_ID", "0")
    threshold = int(os.environ.get("ZSSH_TIME_DRIFT_THRESHOLD", "60"))
    autofix = os.environ.get("ZSSH_TIME_AUTOFIX", "0") == "1"

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            target, username=user, password=password,
            look_for_keys=False, allow_agent=False, timeout=15,
        )
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"[zssh-time] cannot connect to {target}: {e}\n")
        return 0

    shell = client.invoke_shell(width=240, height=80)
    time.sleep(1.2)
    while shell.recv_ready():
        shell.recv(65536)

    shell.send(b"terminal length 0\n")
    drain(shell, time.time() + 1.0, until=PROMPT_DNOS)

    # 1) Read device epoch via bash shell
    shell.send(f"run start shell ncp {ncp_id}\n".encode())
    out = drain(shell, time.time() + 4.0, until=PROMPT_PWD)
    if PROMPT_PWD.search(out or b""):
        shell.send((password + "\n").encode())
        drain(shell, time.time() + 4.0, until=PROMPT_BASH)
    else:
        drain(shell, time.time() + 1.5, until=PROMPT_BASH)

    shell.send(b"date '+%s '\n")
    out = drain(shell, time.time() + 3.0, until=PROMPT_BASH)
    m = EPOCH_RE.search(out or b"")
    if not m:
        sys.stderr.write("[zssh-time] could not read device clock; skipping\n")
        client.close()
        return 0
    dev_epoch = int(m.group(1))
    local_epoch = int(time.time())
    drift = dev_epoch - local_epoch
    abs_drift = abs(drift)

    # 2) Read NTP / timing-mode status
    shell.send(b"exit\n")
    drain(shell, time.time() + 2.0, until=PROMPT_DNOS)
    shell.send(b"show config system timing-mode\n")
    cfg_out = drain(shell, time.time() + 2.5, until=PROMPT_DNOS)
    timing_mode = "ntp" if b"manual" not in cfg_out else "manual"

    shell.send(b"show system ntp\n")
    ntp_out = drain(shell, time.time() + 3.0, until=PROMPT_DNOS)
    ntp_active = bool(re.search(rb"^\|\s+\S", ntp_out, re.M))

    dev_iso = dt.datetime.utcfromtimestamp(dev_epoch).strftime("%Y-%m-%d %H:%M:%S")
    sign = "+" if drift >= 0 else "-"
    status = "OK" if abs_drift <= threshold else "DRIFT"
    src = "NTP" if (timing_mode == "ntp" and ntp_active) else timing_mode
    sys.stderr.write(
        f"[zssh-time] device={dev_iso}Z  drift={sign}{abs_drift}s  {status} ({src})\n"
    )

    if abs_drift <= threshold:
        client.close()
        return 0

    if not autofix:
        sys.stderr.write(
            f"[zssh-time] drift exceeds {threshold}s threshold. "
            f"Set ZSSH_TIME_AUTOFIX=1 in ~/.zssh.conf on the dev VM "
            f"to auto-set the device clock.\n"
        )
        client.close()
        return 0

    # 3) Auto-fix: switch to manual mode + set datetime to dev-VM now
    now = dt.datetime.now(dt.timezone.utc).strftime("%d-%m-%YT%H:%M:%S")
    sys.stderr.write(f"[zssh-time] auto-fixing: setting device time to {now} (UTC)\n")
    shell.send(b"configure\n")
    drain(shell, time.time() + 2.0, until=re.compile(rb"\(cfg.*\)#\s*$"))
    shell.send(b"system timing-mode manual\n")
    drain(shell, time.time() + 2.0, until=re.compile(rb"\(cfg.*\)#\s*$"))
    shell.send(b"commit\n")
    drain(shell, time.time() + 6.0, until=re.compile(rb"\(cfg.*\)#\s*$"))
    # answer any "are you sure" prompt
    shell.send(b"yes\n")
    drain(shell, time.time() + 4.0, until=re.compile(rb"\(cfg.*\)#\s*$"))
    shell.send(b"end\n")
    drain(shell, time.time() + 2.0, until=PROMPT_DNOS)

    shell.send(f"set system datetime {now}\n".encode())
    set_out = drain(shell, time.time() + 3.0, until=PROMPT_DNOS)
    sys.stderr.write(
        f"[zssh-time] {set_out.decode(errors='replace').strip().splitlines()[-1] if set_out else ''}\n"
    )

    client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
