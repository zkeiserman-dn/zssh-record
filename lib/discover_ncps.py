#!/usr/bin/env python3
"""
Discover the deployment type (SA vs cluster) and list all NCP IDs.

Output (stdout, one line):
    SA 0                      -> standalone, single NCP 0
    CL 3 6 7                  -> cluster, NCPs 3, 6, 7

Used by zssh.sh to decide how many wb_agent / wb_fe_agent tail workers
to start and how to label them in the HTML viewer.

Usage:
    discover_ncps.py <target>

Env:
    ZSSH_USER             default dnroot
    ZSSH_DEVICE_PASSWORD  default dnroot
"""
from __future__ import annotations

import os
import re
import sys
import time
import warnings

warnings.filterwarnings("ignore")

try:
    import paramiko
except ImportError:
    print("SA 0")
    sys.exit(0)

PROMPT = re.compile(rb"[A-Za-z0-9._-]+#\s*$")
ANSI = re.compile(rb"\x1b\[[0-9;]*[a-zA-Z]")


def drain(shell, deadline, until=None):
    buf = b""
    while time.time() < deadline:
        if shell.recv_ready():
            buf += shell.recv(65536)
            if until and until.search(buf):
                return buf
        else:
            time.sleep(0.05)
    return buf


def main():
    if len(sys.argv) < 2:
        print("SA 0")
        return

    target = sys.argv[1]
    user = os.environ.get("ZSSH_USER", "dnroot").strip() or "dnroot"
    password = os.environ.get("ZSSH_DEVICE_PASSWORD", "dnroot")

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            target, username=user, password=password,
            look_for_keys=False, allow_agent=False, timeout=15,
        )
    except Exception:
        print("SA 0")
        return

    shell = client.invoke_shell(width=240, height=80)
    time.sleep(1.5)
    while shell.recv_ready():
        shell.recv(65536)

    shell.send(b"terminal length 0\n")
    drain(shell, time.time() + 1.0, until=PROMPT)

    shell.send(b"show system\n")
    out = drain(shell, time.time() + 5.0, until=PROMPT)
    client.close()

    text = ANSI.sub(b"", out).decode(errors="replace")

    # Detect SA vs CL from "System Type:" line
    deployment = "SA"
    if re.search(r"System Type:\s*CL-", text):
        deployment = "CL"

    # Parse NCP rows from the table:
    # | NCP  | 3      | enabled  | up      | ...
    ncp_ids = []
    for m in re.finditer(
        r"^\|\s*NCP\s*\|\s*(\d+)\s*\|\s*enabled\s*\|\s*up\b",
        text,
        re.MULTILINE,
    ):
        ncp_ids.append(m.group(1))

    if not ncp_ids:
        ncp_ids = ["0"]

    print(f"{deployment} {' '.join(ncp_ids)}")


if __name__ == "__main__":
    main()
