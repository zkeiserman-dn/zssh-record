#!/usr/bin/env python3
"""
Upload a single file as an attachment to a Jira issue.

Usage:  jira_upload.py <ISSUE-KEY> <file> [<file> ...]

Credentials and base URL come from environment variables (set them in
~/.zssh.conf or ~/.zshrc / ~/.bashrc on the dev VM):

    JIRA_BASE         default https://drivenets.atlassian.net
    JIRA_EMAIL        e.g.    zkeiserman@drivenets.com
    JIRA_API_TOKEN    Atlassian API token (https://id.atlassian.com/manage-profile/security/api-tokens)

Exits 0 on success / nothing-to-do, 1 on any upload error.
"""

import os
import sys
from pathlib import Path

try:
    import requests
    from requests.auth import HTTPBasicAuth
except ImportError:
    print("[zssh-upload] python3-requests not installed; skip", file=sys.stderr)
    sys.exit(0)


def cfg(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: jira_upload.py <ISSUE-KEY> <file> [<file> ...]", file=sys.stderr)
        return 2

    issue = sys.argv[1].strip()
    paths = [Path(p) for p in sys.argv[2:]]

    base = cfg("JIRA_BASE", "https://drivenets.atlassian.net").rstrip("/")
    email = cfg("JIRA_EMAIL")
    token = cfg("JIRA_API_TOKEN")

    if not email or not token:
        # ANSI: red bold for the headline, dim for the recipe
        red = "\033[1;31m"
        dim = "\033[2m"
        rst = "\033[0m"
        print(
            f"\n{red}[zssh-upload] CANNOT UPLOAD TO {issue} - "
            f"Jira credentials missing.{rst}",
            file=sys.stderr,
        )
        print(
            f"{dim}    Run this ONCE on the dev VM (token at "
            f"https://id.atlassian.com/manage-profile/security/api-tokens):{rst}",
            file=sys.stderr,
        )
        print(
            "    cat >> ~/.zshrc <<'EOF'\n"
            "    export JIRA_EMAIL='zkeiserman@drivenets.com'\n"
            "    export JIRA_API_TOKEN='ATATT...paste-your-token...'\n"
            "    EOF\n"
            "    source ~/.zshrc",
            file=sys.stderr,
        )
        return 0

    url = f"{base}/rest/api/3/issue/{issue}/attachments"
    auth = HTTPBasicAuth(email, token)
    headers = {"X-Atlassian-Token": "no-check", "Accept": "application/json"}

    rc = 0
    for p in paths:
        if not p.exists() or p.stat().st_size == 0:
            print(f"[zssh-upload] skip (missing/empty): {p}", file=sys.stderr)
            continue
        try:
            with p.open("rb") as fh:
                r = requests.post(
                    url,
                    auth=auth,
                    headers=headers,
                    files={"file": (p.name, fh, "application/octet-stream")},
                    timeout=60,
                )
        except requests.RequestException as e:
            print(f"[zssh-upload] {issue}: {p.name} FAILED ({e})", file=sys.stderr)
            rc = 1
            continue

        if r.status_code in (200, 201):
            try:
                data = r.json()
                aid = data[0].get("id") if isinstance(data, list) and data else "?"
            except Exception:
                aid = "?"
            print(
                f"[zssh-upload] {issue}: {p.name} uploaded (attachment id {aid})",
                file=sys.stderr,
            )
        else:
            print(
                f"[zssh-upload] {issue}: {p.name} HTTP {r.status_code} - {r.text[:200]}",
                file=sys.stderr,
            )
            rc = 1

    return rc


if __name__ == "__main__":
    sys.exit(main())
