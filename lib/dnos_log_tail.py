#!/usr/bin/env python3
"""
Tail a DNOS NCP trace file via DNOS CLI -> bash shell.

Equivalent of doing this by hand:
    ssh dnroot@<target>
    > run start shell ncp <ncp_id>     # password: dnroot
    $ cd traces
    $ tail -f <log_name>

Usage:
    dnos_log_tail.py <target> <log_name> [ncp_id]

Env vars:
    ZSSH_USER             default: dnroot
    ZSSH_DEVICE_PASSWORD  default: dnroot
    ZSSH_TRACES_DIR       default: traces      (relative or absolute)

Output is written to stdout so the caller can `tee` it to a log file.
Stops cleanly on SIGTERM / SIGINT so zssh.sh's cleanup trap can shut it
down at the end of a session.
"""

from __future__ import annotations

import os
import re
import signal
import sys
import time
import warnings

# Silence paramiko's third-party CryptographyDeprecationWarning noise.
warnings.filterwarnings("ignore")
os.environ.setdefault("PYTHONWARNINGS", "ignore")

try:
    import paramiko
except ImportError:
    sys.stderr.write("[dnos-tail] paramiko not installed: pip install paramiko\n")
    sys.exit(1)


PROMPT_DNOS = re.compile(rb"[A-Za-z0-9._-]+#\s*$")
PROMPT_BASH = re.compile(rb"[\w.-]+@[\w.-]+:\S+[#$]\s*$")
PROMPT_PWD = re.compile(rb"[Pp]assword:\s*$")


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
    if len(sys.argv) < 3:
        sys.stderr.write("usage: dnos_log_tail.py <target> <log_name> [ncp_id]\n")
        return 2

    target = sys.argv[1]
    log_name = sys.argv[2]
    ncp_id = sys.argv[3] if len(sys.argv) > 3 else "0"

    user = os.environ.get("ZSSH_USER", "dnroot").strip() or "dnroot"
    password = os.environ.get("ZSSH_DEVICE_PASSWORD", "dnroot")
    traces_dir = os.environ.get("ZSSH_TRACES_DIR", "traces").strip() or "traces"

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            target,
            username=user,
            password=password,
            look_for_keys=False,
            allow_agent=False,
            timeout=20,
        )
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"[dnos-tail] ssh to {user}@{target} failed: {e}\n")
        return 1

    shell = client.invoke_shell(width=240, height=80)
    time.sleep(1.5)
    # discard banner
    while shell.recv_ready():
        shell.recv(65536)

    # disable pagination on the DNOS CLI side, just in case
    shell.send(b"terminal length 0\n")
    drain(shell, time.time() + 1.0, until=PROMPT_DNOS)

    # drop into NCP bash shell
    shell.send(f"run start shell ncp {ncp_id}\n".encode())
    out = drain(shell, time.time() + 4.0, until=PROMPT_PWD)
    if PROMPT_PWD.search(out or b""):
        shell.send((password + "\n").encode())
        drain(shell, time.time() + 4.0, until=PROMPT_BASH)
    else:
        # may have already dropped into bash without password
        drain(shell, time.time() + 1.5, until=PROMPT_BASH)

    # cd into traces and start tail -f
    cmd = f"cd {traces_dir} 2>/dev/null && tail -f {log_name} 2>&1\n"
    shell.send(cmd.encode())

    stopping = {"flag": False}

    def stop(*_):
        stopping["flag"] = True
        try:
            shell.send(b"\x03")  # ^C the tail
        except Exception:
            pass
        try:
            shell.close()
        except Exception:
            pass
        try:
            client.close()
        except Exception:
            pass

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    try:
        while not stopping["flag"]:
            if shell.recv_ready():
                data = shell.recv(65536)
                if not data:
                    break
                try:
                    sys.stdout.buffer.write(data)
                    sys.stdout.flush()
                except (BrokenPipeError, ValueError):
                    break
            else:
                time.sleep(0.1)
    finally:
        stop()

    return 0


if __name__ == "__main__":
    sys.exit(main())
