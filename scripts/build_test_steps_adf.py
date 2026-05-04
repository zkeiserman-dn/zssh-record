#!/usr/bin/env python3
"""Build ADF JSON bodies for the SW-217283 (granularity 4 -> 1) test plan.

v8 — Four Test Categories, eight Testing Tasks, all under SW-217283.

  SW-263478  Test Category    QA | Regression
    SW-263481  Testing Task   QA | tr3cm regression
    SW-263486  Testing Task   QA | QPPB regression

  SW-263538  Test Category    QA | Pool State Functionality
    SW-263929  Testing Task   QA | Non-MEF allocation
    SW-263930  Testing Task   QA | MEF allocation
    SW-263931  Testing Task   QA | QPPB allocation
    SW-263540  Testing Task   QA | Combined allocation

  SW-263539  Test Category    QA | HA
    SW-263541  Testing Task   QA | HA scenarios

  SW-263932  Test Category    QA | Scale
    SW-263933  Testing Task   QA | Scale combined

Pool counter model (per SW-217283):
  - Each non-MEF interface attachment -> `regular_indexes_used += 1`.
  - When `regular_indexes_used` reaches a multiple of 4 -> `regular_blocks += 1`.
  - Each MEF interface attachment -> `blocks_used_as_block += 1` only at block
    boundaries: 1, 2, 3, 4 attachments all share 1 block; the 5th allocates
    a 2nd block; the 9th allocates a 3rd block.
  - Each per-interface QPPB binding behaves like non-MEF -> `regular_indexes_used += 1`.
  - Pool capacity: 16383 indexes total (4095 full 4-index blocks + 3 indexes).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

OUT = Path(__file__).parent / "adf"
OUT.mkdir(exist_ok=True, parents=True)


# ---------- ADF helpers -----------------------------------------------------

def text(s: str, marks=None) -> dict:
    node = {"type": "text", "text": s}
    if marks:
        node["marks"] = [{"type": m} for m in marks]
    return node


def paragraph(*nodes) -> dict:
    return {"type": "paragraph", "content": list(nodes)}


def heading(level: int, *nodes) -> dict:
    return {"type": "heading", "attrs": {"level": level}, "content": list(nodes)}


def code_block(content: str) -> dict:
    return {"type": "codeBlock", "content": [text(content)]}


def bullet_list(items_md: list[str]) -> dict:
    return {
        "type": "bulletList",
        "content": [
            {"type": "listItem", "content": [paragraph(*inline_md(line))]}
            for line in items_md
        ],
    }


def ordered_list(items_md: list[str]) -> dict:
    return {
        "type": "orderedList",
        "content": [
            {"type": "listItem", "content": [paragraph(*inline_md(line))]}
            for line in items_md
        ],
    }


INLINE_RE = re.compile(r"(`[^`]+`|\*\*[^*]+\*\*)")


def inline_md(s: str) -> list[dict]:
    out: list[dict] = []
    pos = 0
    for m in INLINE_RE.finditer(s):
        if m.start() > pos:
            out.append(text(s[pos : m.start()]))
        token = m.group(0)
        if token.startswith("`"):
            out.append(text(token[1:-1], marks=["code"]))
        else:
            out.append(text(token[2:-2], marks=["strong"]))
        pos = m.end()
    if pos < len(s):
        out.append(text(s[pos:]))
    return out


def underlined(s: str) -> dict:
    return heading(3, text(s, marks=["underline"]), text(":"))


def doc(*nodes) -> dict:
    return {"type": "doc", "version": 1, "content": list(nodes)}


def section_test_steps(items: list[str]) -> list[dict]:
    return [underlined("Test Steps"), ordered_list(items)]


def section_pass(items: list[str]) -> list[dict]:
    return [underlined("Pass Criteria"), bullet_list(items)]


def section_cmds(code: str) -> list[dict]:
    return [underlined("Commands legend"), code_block(code)]


def section_show(code: str) -> list[dict]:
    return [underlined("Show commands legend"), code_block(code)]


VARIANTS_LINE = (
    "Interface: physical, sub-interface, bundle, sub-bundle. "
    "Platforms: Q2C and Q2C+."
)


def section_variants() -> list[dict]:
    return [underlined("Variants"), paragraph(*inline_md(VARIANTS_LINE))]


COMMON_SHOW = (
    "show qos interfaces <intf> in\n"
    "show qos interfaces counters <intf> in\n"
    "xraycli /wb_agent/qos/policers/pool_stats   ! regular_indexes_used / regular_blocks / blocks_used_as_block\n"
    "xraycli /wb_agent/qos/policers/show_policers"
)


# ---------- Regression (SW-263478, SW-263481, SW-263486) --------------------

def body_regression_category() -> dict:
    intro = paragraph(*inline_md(
        "Basic regression for the granularity 4 -> 1 epic (SW-217283). Two "
        "Testing Tasks: tr3cm policer rate + burst (MEF and non-MEF) and "
        "basic QPPB rate-limit. Both also verify pool allocation."
    ))
    return doc(
        intro,
        *section_test_steps([
            "Run SW-263481 (tr3cm regression).",
            "Run SW-263486 (QPPB regression).",
        ]),
        *section_pass([
            "Both Testing Tasks pass.",
            "No commit failures, no crashes, no QoS process aborts.",
            "After teardown `xraycli /wb_agent/qos/policers/pool_stats` returns to baseline.",
        ]),
        *section_cmds("(see per-Testing-Task CLI; the Test Category itself only orchestrates execution)"),
        *section_show(COMMON_SHOW),
        *section_variants(),
    )


def body_tr3cm_basic() -> dict:
    intro = paragraph(*inline_md(
        "Very basic tr3cm regression. Verify rate + burst enforcement under "
        "non-MEF (no rank) and MEF (with rank) allocation. Pool counters via "
        "`xraycli /wb_agent/qos/policers/pool_stats`: non-MEF -> "
        "`regular_indexes_used += 1`, MEF -> `blocks_used_as_block += 1`."
    ))
    cmds = (
        "configure\n"
        "qos\n"
        "  policy P_TR3CM\n"
        "    rule 1\n"
        "      match traffic-class <tc>\n"
        "      action\n"
        "        police\n"
        "          meter-type tr3cm\n"
        "            rate <kbps>      ! e.g. 1000000 = 1 gbps\n"
        "            burst <kbytes>   ! e.g. 50\n"
        "            rank <2|3|4>     ! omit for non-MEF; add for MEF\n"
        "exit\n"
        "interfaces <intf> qos policy in P_TR3CM\n"
        "commit"
    )
    return doc(
        intro,
        *section_test_steps([
            "Capture baseline `xraycli /wb_agent/qos/policers/pool_stats`. Record `regular_indexes_used` (R0) and `blocks_used_as_block` (B0).",
            "**Phase A — non-MEF**: Configure `qos policy P_TR3CM rule 1 action police meter-type tr3cm rate 1000000 burst 50 kbytes` (NO rank). Bind to ingress port `<ge100>`. Commit. Send Spirent at 2 gbps. Verify ingress is policed to ~1 gbps (within +/-5 %).",
            "Re-read pool_stats. Verify `regular_indexes_used = R0 + 1` and `blocks_used_as_block = B0`.",
            "**Phase B — MEF**: Add `rank 2` to the same rule. Commit. Send the same traffic. Verify ingress is still policed to ~1 gbps.",
            "Re-read pool_stats. Verify `blocks_used_as_block = B0 + 1` and `regular_indexes_used = R0`.",
            "Rollback. Verify pool_stats returns to (R0, B0).",
        ]),
        *section_pass([
            "Phase A — RX rate ~ configured rate within +/-5 %; pool_stats: `regular_indexes_used = R0 + 1`, `blocks_used_as_block = B0`.",
            "Phase B — rate enforcement still works at the configured CIR; pool_stats: `regular_indexes_used = R0`, `blocks_used_as_block = B0 + 1`.",
            "After rollback — pool_stats returns to (R0, B0); no leaks.",
            "No commit failures, no system crashes.",
        ]),
        *section_cmds(cmds),
        *section_show(COMMON_SHOW),
        *section_variants(),
    )


def body_qppb_basic() -> dict:
    intro = paragraph(*inline_md(
        "Very basic QPPB regression. Configure a QPPB policy with rate-limit, "
        "classify a community-tagged route on the receiver, verify the "
        "policer drops transit traffic at the configured rate, AND verify "
        "the pool: each per-interface QPPB binding consumes one entry in "
        "`regular_indexes_used`. Run in per-interface QPPB mode (remove "
        "`routing-options qppb-per-vrf` first if it is set; the two modes "
        "are mutually exclusive)."
    ))
    cmds = (
        "! Sender (S1)\n"
        "configure\n"
        "routing-policy\n"
        "  policy SET_COMM\n"
        "    rule 10 allow set community additive 65500:100\n"
        "    rule 99 allow\n"
        "protocols bgp <ASN>\n"
        "  neighbor <peer> address-family ipv4-unicast send-community community-type both\n"
        "  neighbor <peer> address-family ipv4-unicast policy SET_COMM out\n"
        "commit\n"
        "\n"
        "! Receiver (R1)\n"
        "configure\n"
        "routing-policy\n"
        "  community-list COMM_QPPB rule 1 allow value 65500:100\n"
        "  policy QPPB_CLASSIFY\n"
        "    rule 10 allow match community COMM_QPPB set qppb-src-class 30\n"
        "    rule 99 allow\n"
        "  qppb-policy QPPB_BASIC\n"
        "    rule 100\n"
        "      action\n"
        "        rate-limit 1000          ! kbps (range 0 OR 64..1000000000)\n"
        "        burst-size 50 kbytes\n"
        "      match-class\n"
        "        applicable-vrf default\n"
        "        src-class 30\n"
        "protocols bgp <ASN>\n"
        "  address-family ipv4-unicast rib-install policy QPPB_CLASSIFY\n"
        "forwarding-options\n"
        "  install-qppb-policy QPPB_BASIC\n"
        "interfaces <ingress-1> qppb enabled\n"
        "interfaces <ingress-2> qppb enabled\n"
        "commit"
    )
    return doc(
        intro,
        *section_test_steps([
            "Pre-check: confirm `routing-options qppb-per-vrf` is NOT set on the receiver's VRF. If it is, remove it and commit before starting.",
            "Capture baseline `xraycli /wb_agent/qos/policers/pool_stats`. Record `regular_indexes_used` (R0) and `blocks_used_as_block` (B0).",
            "On sender (S1), advertise a /32 to receiver (R1) via iBGP and tag it with community `65500:100` using policy `SET_COMM`. Verify peer is Up and `show route <prefix>` on R1 lists the community.",
            "On R1, configure `policy QPPB_CLASSIFY` (community-list -> `set qppb-src-class 30`), apply via `address-family ipv4-unicast rib-install policy`. Configure `qppb-policy QPPB_BASIC` (`rate-limit 1000 kbps`, `burst-size 50 kbytes`, `src-class 30`). Install via `forwarding-options install-qppb-policy`. Verify `show route <prefix>` now shows `Qppb classes: src-class: 30`.",
            "Bind QPPB on the ingress interface: `interfaces <ingress-1> qppb enabled`. Commit. Re-read pool_stats. Verify `regular_indexes_used = R0 + 1`.",
            "Generate transit traffic from S1 (src = tagged-prefix) toward a destination behind R1, offering ~10 mbps. Verify QPPB drops at the configured rate-limit (~90 % at 1 mbps with 10 mbps offered) via `show qppb policy summary`.",
            "Bind QPPB on a second ingress interface: `interfaces <ingress-2> qppb enabled`. Commit. Re-read pool_stats. Verify `regular_indexes_used = R0 + 2`.",
            "Rollback all configuration on R1 and S1. Verify pool_stats returns to (R0, B0).",
        ]),
        *section_pass([
            "Step 3 — BGP peer Up; /32 received on R1 with community `65500:100`.",
            "Step 4 — `show route <prefix>` shows `Qppb classes: src-class: 30`.",
            "Step 5 — pool_stats: `regular_indexes_used = R0 + 1` after first QPPB-enabled interface.",
            "Step 6 — drops ~ (offered - rate-limit) within +/-10 %; `show qppb policy summary` Drop counter increments.",
            "Step 7 — pool_stats: `regular_indexes_used = R0 + 2` after second QPPB-enabled interface.",
            "Step 8 — pool_stats returns to (R0, B0); no leaks.",
            "No commit failures, no system crashes.",
        ]),
        *section_cmds(cmds),
        *section_show(
            "show bgp summary\n"
            "show route <tagged-prefix>                  ! expect: Qppb classes: src-class: 30\n"
            "show qppb policy summary\n"
            "show qppb policy rules\n"
            "show qos interfaces counters <ingress> in\n"
            "xraycli /wb_agent/qos/policers/pool_stats"
        ),
        *section_variants(),
    )


# ---------- Pool State Functionality (SW-263538) ----------------------------

def body_pool_state_category() -> dict:
    intro = paragraph(*inline_md(
        "Functionality test for the policer pool allocation math changed in "
        "this epic (granularity 4 -> 1). Four Testing Tasks: one focused on "
        "non-MEF, one on MEF (parent-child hierarchical), one on QPPB, and "
        "one combined. "
        "\n\n"
        "**Empirical allocation model (verified in lab):** "
        "\n"
        "- **Non-MEF**: `regular_indexes_used += 1` per (active rule × "
        "terminal attachment); `regular_blocks = floor(regular_indexes_used / 4)`. "
        "Shared rules and bundle members do NOT consume entries. "
        "\n"
        "- **MEF (parent-child hierarchical)**: `blocks_used_as_block += 1` "
        "per parent attachment (1:1). Child rules with explicit ranks pack "
        "into the per-attachment block (up to 4 ranks per block). "
        "\n"
        "- **QPPB (per-interface)**: `regular_indexes_used += 1` per "
        "QPPB-enabled terminal interface."
    ))
    return doc(
        intro,
        *section_test_steps([
            "Run SW-263929 (Non-MEF allocation).",
            "Run SW-263930 (MEF allocation).",
            "Run SW-263931 (QPPB allocation).",
            "Run SW-263540 (Combined allocation + parent/sub-interface inheritance).",
        ]),
        *section_pass([
            "All four Testing Tasks pass.",
            "Pool counter math observed exactly as predicted in each focused test.",
            "After every teardown pool_stats returns to baseline. No leaks.",
            "No commit failures, no crashes.",
        ]),
        *section_cmds("(see per-Testing-Task CLI)"),
        *section_show(COMMON_SHOW),
        *section_variants(),
    )


def body_pool_state_non_mef() -> dict:
    intro = paragraph(*inline_md(
        "Focused non-MEF allocation test. Each non-MEF policer attachment "
        "consumes exactly one entry in `regular_indexes_used` — one entry "
        "per **active rule** (rule with its own `meter-type`) × **terminal "
        "interface attachment**. Every 4 non-MEF entries advance "
        "`regular_blocks` by 1. `blocks_used_as_block` stays unchanged. "
        "\n\n"
        "**Terminal interfaces** (count toward pool entries): physical, "
        "sub-interface, bundle, sub-bundle. **Bundle members** "
        "(`interfaces <ge…> bundle-id N`) do NOT count — they are not "
        "terminal and do not allocate pool entries on their own. "
        "\n\n"
        "**Active vs shared rules**: a rule with its own `meter-type` "
        "(sr2cm/sr3cm/tr3cm/tr3ccm, no rank) is active and consumes one "
        "entry per attachment. A rule with `meter-type shared rule-id N` "
        "references another rule's policer and does NOT consume its own "
        "entry."
    ))
    cmds = (
        "configure\n"
        "qos\n"
        "  policy P_NONMEF_<N>\n"
        "    rule 1\n"
        "      match traffic-class <tc>\n"
        "      action police meter-type tr3cm rate 1000000 burst 50 kbytes  ! NO rank\n"
        "exit\n"
        "\n"
        "! Terminal interfaces (these DO consume pool entries when a policy is bound):\n"
        "interfaces <ge-physical>          qos policy in P_NONMEF_<N>\n"
        "interfaces <ge-physical>.<vlan>   vlan-id <vlan> qos policy in P_NONMEF_<N>\n"
        "interfaces bundle-<id>            qos policy in P_NONMEF_<N>\n"
        "interfaces bundle-<id>.<vlan>     vlan-id <vlan> qos policy in P_NONMEF_<N>\n"
        "\n"
        "! Bundle members (do NOT consume pool entries — not terminal):\n"
        "interfaces <ge-physical>          bundle-id <id>\n"
        "\n"
        "! Shared meter-type (DOES NOT consume a pool entry — references rule N's policer):\n"
        "qos policy P_NONMEF_<N> rule 2\n"
        "  action police meter-type shared\n"
        "    rule-id 1     ! references rule 1's policer; rule 2 itself adds 0 pool entries\n"
        "\n"
        "commit\n"
        "\n"
        "! Repeat across the 8 attachments + bundle/sub-bundle to walk the test."
    )
    return doc(
        intro,
        *section_test_steps([
            "Capture baseline `xraycli /wb_agent/qos/policers/pool_stats`. Record R0 = `regular_indexes_used`, RB0 = `regular_blocks`, B0 = `blocks_used_as_block`.",
            "Bind 1 non-MEF policy to interface 1. Re-read pool_stats. Verify `regular_indexes_used = R0 + 1`, `regular_blocks = RB0` (still in first block, only 1 of 4 used), `blocks_used_as_block = B0`.",
            "Bind to interface 2. Verify `regular_indexes_used = R0 + 2`, `regular_blocks = RB0`.",
            "Bind to interface 3. Verify `regular_indexes_used = R0 + 3`, `regular_blocks = RB0`.",
            "Bind to interface 4. Verify `regular_indexes_used = R0 + 4` AND `regular_blocks = RB0 + 1` (first 4-index block now full).",
            "Bind to interface 5. Verify `regular_indexes_used = R0 + 5`, `regular_blocks = RB0 + 1` (entered second block but not full).",
            "Bind to interface 6, 7. Verify counters advance by 1 each, `regular_blocks` stays at RB0 + 1.",
            "Bind to interface 8. Verify `regular_indexes_used = R0 + 8` AND `regular_blocks = RB0 + 2` (second 4-index block now full).",
            "Throughout steps 2-8, verify `blocks_used_as_block = B0` (unchanged — non-MEF never touches the MEF block counter).",
            "**Bundle members do NOT allocate**: create a bundle and add 2-3 physical members via `interfaces <geX/Y/Z> bundle-id <N>` and commit. Re-read pool_stats. Verify counters are unchanged from the previous step. Members are not terminal interfaces; they do not consume pool entries.",
            "**Bundle as a terminal interface**: bind the same non-MEF policy to `bundle-<N>` directly (`interfaces bundle-<N> qos policy <P> direction in`). Commit. Verify `regular_indexes_used` increments by 1 (one rule-with-police × this new terminal attachment). Bundle behaves exactly like any other interface for pool accounting.",
            "**Sub-bundle as a terminal interface**: configure a sub-bundle `bundle-<N>.<M> vlan-id <M>` (vlan-id is mandatory) and bind the same non-MEF policy. Commit. Verify `regular_indexes_used` increments by 1. Sub-bundles also count as terminal attachments.",
            "**Adding more bundle members does NOT change pool**: add another physical member to the bundle (`interfaces <geX/Y/Z> bundle-id <N>`) and commit. Verify pool_stats is unchanged.",
            "**Shared meter-type does NOT allocate**: on the policy already attached to multiple terminal interfaces, add a 2nd rule with its own `meter-type sr2cm rate ...` (no rank). Commit. Verify `regular_indexes_used` increases by exactly the number of terminal attachments using this policy (one per active rule × attachment).",
            "**Convert rule 2 to shared**: change rule 2 to `meter-type shared rule-id 1` (it now references rule 1's policer). Commit. Verify `regular_indexes_used` DROPS by the number of terminal attachments using this policy. The shared rule does not consume its own pool entry — only the rule whose policer it shares (the \"active\" rule) is counted.",
            "**Convert back to own policer**: change rule 2 back to `meter-type sr2cm rate ...` (no rank). Commit. Verify `regular_indexes_used` grows again by the number of attachments. Symmetric to the previous step.",
            "Unbind from interfaces 8, 7, 6, 5 in reverse, plus the bundle and sub-bundle attachments. Verify counters decrement by 1 each. `regular_blocks` should release at the right boundaries (drops by 1 every time `regular_indexes_used` falls below a multiple of 4).",
            "Remove the bundle members and the bundle / sub-bundle interface configs. Verify pool_stats unchanged by member-removal alone.",
            "Unbind the rest of the per-interface attachments. Verify pool_stats returns to (R0, RB0, B0).",
        ]),
        *section_pass([
            "Steps 2-4 — `regular_indexes_used` increments by 1 per binding; `regular_blocks` stays at RB0.",
            "Step 5 — at the 4th binding, `regular_blocks` jumps to RB0 + 1 (block boundary). Formula confirmed: `regular_blocks = floor(regular_indexes_used / 4)`.",
            "Step 8 — at the 8th binding, `regular_blocks` jumps to RB0 + 2.",
            "Step 9 — `blocks_used_as_block` never changes during the entire test (counter families are independent).",
            "Step 10 — adding bundle MEMBERS does NOT change pool_stats. Bundle members are not terminal interfaces.",
            "Step 11 — binding a policy to the bundle itself increments `regular_indexes_used` by 1 (bundle = terminal interface).",
            "Step 12 — binding a policy to a sub-bundle increments `regular_indexes_used` by 1 (sub-bundle = terminal interface).",
            "Step 13 — adding more members to an existing bundle does NOT change pool_stats.",
            "Step 14 — adding a 2nd active (own-meter) non-MEF rule increases `regular_indexes_used` by `attachments_count` (one per rule per attachment).",
            "Step 15 — converting a rule to `meter-type shared rule-id N` decreases `regular_indexes_used` by `attachments_count`. Shared rules do NOT consume pool entries; only the active (own-meter) rule does.",
            "Step 16 — converting back to own meter-type re-allocates symmetrically.",
            "Final teardown — pool counters decrement symmetrically; final state equals baseline. No leaks.",
            "No commit failures, no crashes.",
        ]),
        *section_cmds(cmds),
        *section_show(COMMON_SHOW),
        *section_variants(),
    )


def body_pool_state_mef() -> dict:
    intro = paragraph(*inline_md(
        "Focused MEF allocation test. "
        "\n\n"
        "**Allocation rule (empirically verified):** **each MEF policy "
        "attachment to a terminal interface = 1 block** in "
        "`blocks_used_as_block`. \"MEF policy\" means a policy that "
        "contains at least one rule with `rank 2/3/4`, OR a parent policy "
        "with `rule default action police` + `rule default action "
        "child-policy`. Multiple ranked rules in the same policy share the "
        "per-attachment block (max 4 ranks per block: 1 derived/parent + "
        "3 explicit). "
        "\n\n"
        "**Terminal interfaces** (count toward MEF blocks): physical, "
        "sub-interface, bundle, sub-bundle. **Bundle members** "
        "(`interfaces <ge…> bundle-id <id>`) do NOT count — same rule as "
        "non-MEF. "
        "\n\n"
        "`regular_indexes_used` and `regular_blocks` do NOT move during "
        "MEF allocation."
    ))
    cmds = (
        "configure\n"
        "\n"
        "! MEF policy (one or more ranked rules — rank 2/3/4)\n"
        "qos policy Pol_MEF rule 1 match traffic-class cs1\n"
        "qos policy Pol_MEF rule 1 action police meter-type sr2cm rate 50 mbps rank 2\n"
        "qos policy Pol_MEF rule 1 action set qos-tag 1\n"
        "\n"
        "! (optional) additional ranked rules in the SAME policy share the per-attachment block\n"
        "qos policy Pol_MEF rule 2 match traffic-class cs2\n"
        "qos policy Pol_MEF rule 2 action police meter-type sr2cm rate 50 mbps rank 3\n"
        "qos policy Pol_MEF rule 3 match traffic-class cs3\n"
        "qos policy Pol_MEF rule 3 action police meter-type sr2cm rate 50 mbps rank 4\n"
        "\n"
        "! Terminal interfaces (each MEF binding = 1 block)\n"
        "interfaces <ge-physical>          qos policy in Pol_MEF\n"
        "interfaces <ge-physical>.<vlan>   vlan-id <vlan> qos policy in Pol_MEF\n"
        "interfaces bundle-<id>            qos policy in Pol_MEF\n"
        "interfaces bundle-<id>.<vlan>     vlan-id <vlan> qos policy in Pol_MEF\n"
        "\n"
        "! Bundle members — do NOT count toward blocks\n"
        "interfaces <ge-physical>          bundle-id <id>\n"
        "\n"
        "commit"
    )
    return doc(
        intro,
        *section_test_steps([
            "Capture baseline `xraycli /wb_agent/qos/policers/pool_stats`. Record R0 = `regular_indexes_used`, RB0 = `regular_blocks`, B0 = `blocks_used_as_block`.",
            "**Add (allocate)**: configure `Pol_MEF` with one rule that has `rank 2`. Bind to terminal interface 1. Commit. Verify `blocks_used_as_block = B0 + 1`, `regular_indexes_used = R0` (unchanged).",
            "Bind `Pol_MEF` to terminal interface 2. Commit. Verify `blocks_used_as_block = B0 + 2` (each attachment = 1 block, 1:1).",
            "Bind to interface 3. Verify `blocks_used_as_block = B0 + 3`.",
            "Bind to interface 4, 5. Verify `blocks_used_as_block = B0 + 4`, then `B0 + 5`.",
            "**Multiple ranked rules pack into the same per-attachment block**: add a 2nd rule (`rank 3`) to `Pol_MEF`. Commit. Verify `blocks_used_as_block` UNCHANGED — additional ranked rules in the same policy share the per-attachment block.",
            "Add a 3rd rule (`rank 4`). Verify `blocks_used_as_block` still UNCHANGED.",
            "Throughout, verify `regular_indexes_used = R0` and `regular_blocks = RB0` (MEF never touches the non-MEF counters).",
            "**Bundle (terminal)**: create a bundle with 2-3 members. Bind `Pol_MEF` to `bundle-<id>`. Commit. Verify `blocks_used_as_block += 1`. Members do NOT count.",
            "**Sub-bundle (terminal)**: configure `bundle-<id>.<vlan>` (vlan-id is mandatory) and bind `Pol_MEF`. Commit. Verify `blocks_used_as_block += 1`.",
            "**More bundle members do NOT change pool**: add another member to the bundle. Commit. Verify `blocks_used_as_block` UNCHANGED.",
            "**Remove (decrement) — symmetric**: unbind `Pol_MEF` from terminal interface 5. Verify `blocks_used_as_block -= 1`. Repeat for interfaces 4, 3, 2, 1, then for `bundle-<id>.<vlan>` and `bundle-<id>`. After each unbind, verify `blocks_used_as_block` decrements by exactly 1.",
            "**Remove ranked rules**: with `Pol_MEF` no longer attached anywhere, remove rule 3, then rule 2. Verify pool_stats UNCHANGED (rules in an unattached policy don't allocate or release).",
            "**Remove bundle and members**: remove the sub-bundle config, the bundle members, and the bundle. Verify pool_stats UNCHANGED (member removal does not change pool, consistent with non-MEF).",
            "Remove `Pol_MEF` entirely. Verify pool_stats returns to (R0, RB0, B0).",
        ]),
        *section_pass([
            "Step 2 — first MEF binding allocates exactly 1 block; non-MEF counters unchanged.",
            "Steps 3-5 — every additional MEF attachment increments `blocks_used_as_block` by exactly 1 (1:1 with terminal attachments).",
            "Steps 6-7 — adding more ranked rules to the same policy does NOT add blocks (they pack into the per-attachment block).",
            "Step 8 — `regular_indexes_used` and `regular_blocks` stay at baseline throughout (MEF and non-MEF counter families are independent).",
            "Step 9 — binding `Pol_MEF` to a `bundle-<id>` adds 1 block. Bundle members add 0.",
            "Step 10 — binding to a `bundle-<id>.<vlan>` (sub-bundle) adds 1 block.",
            "Step 11 — adding more members to an existing bundle does NOT change pool_stats.",
            "Step 12 — every unbind drops `blocks_used_as_block` by exactly 1 (symmetric decrement).",
            "Step 13 — rules in an unattached policy do not affect pool_stats.",
            "Step 14 — bundle / member removal alone does not affect pool_stats.",
            "Step 15 — final teardown: pool_stats returns to baseline. No leaks.",
            "No commit failures, no crashes.",
        ]),
        *section_cmds(cmds),
        *section_show(COMMON_SHOW),
        *section_variants(),
    )


def body_pool_state_qppb() -> dict:
    intro = paragraph(*inline_md(
        "Focused QPPB allocation test. Each per-interface QPPB binding "
        "(`interfaces <if> qppb enabled`) consumes exactly one entry in "
        "`regular_indexes_used`, and every 4 bindings advance `regular_blocks` "
        "by 1. `blocks_used_as_block` is unaffected. Run in per-interface "
        "QPPB mode (remove `routing-options qppb-per-vrf` first if set)."
    ))
    cmds = (
        "configure\n"
        "routing-policy\n"
        "  community-list COMM_QPPB rule 1 allow value 65500:100\n"
        "  policy QPPB_CLASSIFY\n"
        "    rule 10 allow match community COMM_QPPB set qppb-src-class 30\n"
        "  qppb-policy QPPB_BASIC\n"
        "    rule 100\n"
        "      action rate-limit 1000\n"
        "      action burst-size 50 kbytes\n"
        "      match-class src-class 30 applicable-vrf default\n"
        "protocols bgp <ASN>\n"
        "  address-family ipv4-unicast rib-install policy QPPB_CLASSIFY\n"
        "forwarding-options\n"
        "  install-qppb-policy QPPB_BASIC\n"
        "\n"
        "! For each interface in the test (4-5 distinct ones):\n"
        "interfaces <ingress-N> qppb enabled\n"
        "commit"
    )
    return doc(
        intro,
        *section_test_steps([
            "Pre-check: confirm `routing-options qppb-per-vrf` is NOT set on the receiver's VRF. If it is, remove it and commit before starting.",
            "Capture baseline `xraycli /wb_agent/qos/policers/pool_stats`. Record R0 = `regular_indexes_used`, RB0 = `regular_blocks`, B0 = `blocks_used_as_block`.",
            "Set up `QPPB_CLASSIFY` and `QPPB_BASIC` (one community match, rate-limit 1000 kbps, src-class 30). Apply `rib-install policy` and `install-qppb-policy`. Do NOT enable QPPB on any interface yet. Re-read pool_stats. Verify it equals baseline (no per-interface binding yet).",
            "Bind QPPB on interface 1 (`interfaces <ingress-1> qppb enabled`). Verify `regular_indexes_used = R0 + 1`, `regular_blocks = RB0`, `blocks_used_as_block = B0`.",
            "Bind QPPB on interface 2. Verify `regular_indexes_used = R0 + 2`, `regular_blocks = RB0`.",
            "Bind QPPB on interface 3. Verify `regular_indexes_used = R0 + 3`, `regular_blocks = RB0`.",
            "Bind QPPB on interface 4. Verify `regular_indexes_used = R0 + 4` AND `regular_blocks = RB0 + 1` (block boundary).",
            "Bind QPPB on interface 5. Verify `regular_indexes_used = R0 + 5`, `regular_blocks = RB0 + 1`.",
            "Throughout, verify `blocks_used_as_block = B0` (QPPB never touches MEF block counter).",
            "Unbind QPPB from interfaces 5, 4, 3, 2, 1 in reverse. Verify counters decrement symmetrically. Specifically going from 4 -> 3 should bring `regular_blocks` back to RB0.",
            "Remove the QPPB classify policy and qppb-policy entirely. Verify pool_stats returns to (R0, RB0, B0).",
        ]),
        *section_pass([
            "Step 3 — pool_stats unchanged when only the policy is configured (no per-IF binding yet).",
            "Steps 4-7 — `regular_indexes_used` increments by 1 per QPPB-enabled interface.",
            "Step 7 — at the 4th binding, `regular_blocks` jumps to RB0 + 1.",
            "Step 9 — `blocks_used_as_block` never changes.",
            "Step 10/11 — symmetric decrement on teardown; final state equals baseline.",
            "No commit failures, no crashes.",
        ]),
        *section_cmds(cmds),
        *section_show(
            "show route <tagged-prefix>                  ! expect: Qppb classes: src-class: 30\n"
            "show qppb policy summary\n"
            "show qppb interfaces counters <ingress>\n"
            + COMMON_SHOW
        ),
        *section_variants(),
    )


def body_pool_state_combined() -> dict:
    intro = paragraph(*inline_md(
        "Combined allocation test. Mixes non-MEF, MEF, and per-interface QPPB "
        "in the same run, plus the parent/sub-interface inheritance check. "
        "Verifies that the three counter families (regular_indexes_used + "
        "regular_blocks vs blocks_used_as_block) remain independent and that "
        "a sub-interface without its own policy inherits the parent's "
        "allocation."
    ))
    cmds = (
        "configure\n"
        "qos\n"
        "  policy P_NONMEF\n"
        "    rule 1 match traffic-class <tc-A>\n"
        "      action police meter-type tr3cm rate 1000000 burst 50 kbytes      ! non-MEF\n"
        "  policy P_MEF\n"
        "    rule 1 match traffic-class <tc-B>\n"
        "      action police meter-type tr3cm rate 500000 burst 50 kbytes rank 2 ! MEF\n"
        "exit\n"
        "interfaces <ge100-0/0/1>     qos policy in P_NONMEF       ! parent (non-MEF)\n"
        "interfaces <ge100-0/0/1.100> qos policy in P_MEF           ! sub override (MEF)\n"
        "interfaces <ge100-0/0/2>     qos policy in P_NONMEF\n"
        "interfaces <ge100-0/0/3>     qos policy in P_MEF\n"
        "interfaces <ge100-0/0/4>     qppb enabled                   ! per-interface QPPB\n"
        "commit"
    )
    return doc(
        intro,
        *section_test_steps([
            "Capture baseline `xraycli /wb_agent/qos/policers/pool_stats`. Record R0, RB0, B0.",
            "**Non-MEF + MEF mix:** Bind P_NONMEF to interface 1, P_MEF to interface 2, P_NONMEF to interface 3, P_MEF to interface 4. Verify `regular_indexes_used = R0 + 2`, `blocks_used_as_block = B0 + 1` (2 MEF rules fit in 1 block).",
            "Add P_NONMEF on interfaces 5, 6 (4 non-MEF total). Verify `regular_indexes_used = R0 + 4`, `regular_blocks = RB0 + 1` (block boundary).",
            "Add P_MEF on interfaces 5, 6, 7 (5 MEF total). Verify `blocks_used_as_block = B0 + 2` (5th MEF crosses the block boundary).",
            "**QPPB mix:** With `qppb-per-vrf` removed, configure QPPB classify + qppb-policy and bind QPPB on interfaces 8, 9. Verify `regular_indexes_used = R0 + 6` (4 non-MEF + 2 QPPB).",
            "**Parent/sub-interface inheritance:** Configure a NEW physical interface 10 with P_NONMEF, then a sub-interface 10.100 with NO policy of its own. Verify `regular_indexes_used = R0 + 7` (parent only; sub inherits the parent's policer, no new pool entry).",
            "Apply P_MEF to sub-interface 10.100. Verify `regular_indexes_used = R0 + 7`, `blocks_used_as_block = B0 + 3` (sub now has its own MEF block, parent unchanged).",
            "Send Spirent traffic on the sub-interface. Verify it is policed by P_MEF, not P_NONMEF (override works).",
            "Remove the policy from sub-interface 10.100. Verify `blocks_used_as_block = B0 + 2` (sub's MEF block freed, sub falls back to inheriting parent's non-MEF policer).",
            "Cross-check via `wbox-cli bcm diag dbal table dump table=METER_ING_PROFILE_CONFIG DATABASE_ID=\"=2\"` that HW row count matches SW pool_stats.",
            "Rollback all configuration. Verify pool_stats returns to (R0, RB0, B0).",
        ]),
        *section_pass([
            "Step 2 — non-MEF and MEF counters increment independently per attachment.",
            "Step 3 — `regular_blocks` boundary observed at 4 non-MEF entries.",
            "Step 4 — `blocks_used_as_block` boundary observed at 5 MEF entries.",
            "Step 5 — QPPB bindings increment `regular_indexes_used` (treated like non-MEF).",
            "Step 6 — sub without its own policy inherits parent's allocation, no extra pool entry.",
            "Step 7 — sub with its own policy gets its own pool entry; parent unchanged.",
            "Step 8 — traffic on the overridden sub follows the sub's policy.",
            "Step 9 — removing sub's policy frees its pool entry; sub falls back to inheritance.",
            "Step 10 — HW dbal row count matches SW pool_stats. No SW/HW skew.",
            "Step 11 — pool_stats returns to baseline. No leaks.",
            "No commit failures, no crashes.",
        ]),
        *section_cmds(cmds),
        *section_show(
            COMMON_SHOW + "\n"
            "wbox-cli bcm diag dbal table dump table=METER_ING_PROFILE_CONFIG DATABASE_ID=\"=2\"  ! HW vs SW cross-check"
        ),
        *section_variants(),
    )


# ---------- HA (SW-263539, SW-263541) ---------------------------------------

def body_ha_category() -> dict:
    intro = paragraph(*inline_md(
        "HA functionality test for the policer pool. Verify pool state and "
        "policer enforcement survive HA events (NCC failover, qos process "
        "restart, factory reset / config reload) without leaks or stale "
        "entries."
    ))
    return doc(
        intro,
        *section_test_steps([
            "Run SW-263541 (HA scenarios — NCC failover, qos process restart, factory reset).",
        ]),
        *section_pass([
            "SW-263541 passes.",
            "Post-HA pool counters match pre-HA snapshot exactly.",
            "Policers continue to enforce traffic correctly post-HA.",
            "Factory reset frees all pool entries; reconfiguration re-allocates cleanly.",
            "No commit failures, no crashes.",
        ]),
        *section_cmds("(see SW-263541 for the HA event commands)"),
        *section_show(COMMON_SHOW),
        *section_variants(),
    )


def body_ha_task() -> dict:
    intro = paragraph(*inline_md(
        "HA functionality test for the policer pool. Configure a small mix "
        "of non-MEF and MEF rules, snapshot pool state, then trigger HA "
        "events and verify the snapshot is preserved (and policers still "
        "enforce). Three HA scenarios: NCC failover, qos / wbox process "
        "restart, and factory reset / load-override-factory-default."
    ))
    cmds = (
        "! Setup before HA event\n"
        "configure\n"
        "qos\n"
        "  policy P_HA\n"
        "    rule 1\n"
        "      match traffic-class <tc-A>\n"
        "      action police meter-type tr3cm rate 1000000 burst 50 kbytes        ! non-MEF\n"
        "    rule 2\n"
        "      match traffic-class <tc-B>\n"
        "      action police meter-type tr3cm rate 1000000 burst 50 kbytes rank 2 ! MEF\n"
        "exit\n"
        "interfaces <intf> qos policy in P_HA\n"
        "commit\n"
        "\n"
        "! HA event A: NCC failover\n"
        "request system switchover\n"
        "\n"
        "! HA event B: qos / wbox process restart\n"
        "request system process restart name <qos-process>\n"
        "\n"
        "! HA event C: factory reset and config reload\n"
        "request system load-override-factory-default\n"
        "load <saved-config>\n"
        "commit"
    )
    return doc(
        intro,
        *section_test_steps([
            "Capture baseline `xraycli /wb_agent/qos/policers/pool_stats`. Record (R0, RB0, B0).",
            "Configure the mix on `policy P_HA`: 1 non-MEF rule and 1 MEF rule (with `rank 2`). Bind to ingress port. Commit. Re-read pool_stats. Record S1. Verify S1 = (R0 + 1, RB0, B0 + 1). Send Spirent traffic; verify both rules enforce.",
            "**HA event A — NCC failover**: trigger failover from primary to secondary NCC. Wait for HA to converge.",
            "After failover, re-read pool_stats. Verify it equals S1. Re-send Spirent traffic; verify both policers still enforce.",
            "**HA event B — qos / wbox process restart**: kill / restart the process. Wait for it to come back up.",
            "After restart, re-read pool_stats. Verify it equals S1. Re-send Spirent traffic. Cross-check `wbox-cli bcm diag dbal table dump table=METER_ING_PROFILE_CONFIG DATABASE_ID=\"=2\"` HW row count matches SW pool_stats.",
            "**HA event C — factory reset**: save the running config. Run `request system load-override-factory-default`. Re-read pool_stats. Verify it returns to (R0, RB0, B0).",
            "Reload the saved config. Re-read pool_stats. Verify it equals S1. Verify policers enforce correctly.",
            "Rollback. Verify pool_stats returns to (R0, RB0, B0).",
        ]),
        *section_pass([
            "Step 2 — S1 = (R0 + 1, RB0, B0 + 1) after configuring the mix.",
            "Step 4 — post-NCC-failover pool_stats equals S1; traffic still policed.",
            "Step 6 — post-process-restart pool_stats equals S1; HW dbal row count matches SW.",
            "Step 7 — post-factory-reset pool_stats returns to (R0, RB0, B0); no leaks.",
            "Step 8 — after reloading config pool_stats equals S1 again.",
            "Step 9 — pool_stats returns to baseline.",
            "No commit failures, no system crashes during any HA event.",
        ]),
        *section_cmds(cmds),
        *section_show(COMMON_SHOW + "\nshow system high-availability"),
        *section_variants(),
    )


# ---------- Scale (SW-263932, SW-263933) ------------------------------------

def body_scale_category() -> dict:
    intro = paragraph(*inline_md(
        "Scale test for the policer pool. Fill the pool with a mix of MEF, "
        "non-MEF, and per-interface QPPB allocations and verify pool counters "
        "at scale boundaries (16383 capacity)."
    ))
    return doc(
        intro,
        *section_test_steps([
            "Run SW-263933 (Scale combined — fill pool with MEF + non-MEF + QPPB to capacity).",
        ]),
        *section_pass([
            "SW-263933 passes.",
            "Pool capacity ceiling (16383) is reached and the next allocation is rejected gracefully (no crash).",
            "Counters track the mix correctly throughout the run.",
            "After teardown pool_stats returns to baseline.",
            "No commit failures except the deliberate over-capacity attempt; no crashes.",
        ]),
        *section_cmds("(see SW-263933 for the scale-fill CLI)"),
        *section_show(COMMON_SHOW),
        *section_variants(),
    )


def body_scale_task() -> dict:
    intro = paragraph(*inline_md(
        "Combined scale test. Allocate a large mix of non-MEF policers, MEF "
        "policers, and per-interface QPPB bindings. Verify the pool fills "
        "correctly along the way and that the 16383 capacity is reached and "
        "enforced. Total expected at full capacity: "
        "`regular_indexes_used + 4 * blocks_used_as_block <= 16383`."
    ))
    cmds = (
        "! Bulk-config approach: build a flattened DNOS config off-box and load + commit\n"
        "! in one shot (use the dnos-bulk-config-push pattern). The config contains:\n"
        "!  - one qos policy per non-MEF rule and per MEF rule\n"
        "!  - bindings to one interface each\n"
        "!  - QPPB classify + qppb-policy + N per-interface bindings\n"
        "configure\n"
        "qos\n"
        "  policy P_NONMEF_<i> rule 1 action police meter-type tr3cm rate 1000000 burst 50 kbytes\n"
        "  policy P_MEF_<j>    rule 1 action police meter-type tr3cm rate 1000000 burst 50 kbytes rank 2\n"
        "interfaces <intf-i>  qos policy in P_NONMEF_<i>\n"
        "interfaces <intf-j>  qos policy in P_MEF_<j>\n"
        "interfaces <intf-q>  qppb enabled\n"
        "commit"
    )
    return doc(
        intro,
        *section_test_steps([
            "Capture baseline `xraycli /wb_agent/qos/policers/pool_stats`. Record (R0, RB0, B0).",
            "Phase 1 — fill ~50 % of capacity with a 70/20/10 mix: ~5700 non-MEF, ~1600 MEF (= 400 blocks * 4), ~700 per-interface QPPB. Bulk-load via flattened config. Commit.",
            "Re-read pool_stats. Verify totals match the configured counts: `regular_indexes_used = R0 + 5700 + 700 = R0 + 6400`, `blocks_used_as_block = B0 + 400`. Compute `total_used = regular_indexes_used + 4 * blocks_used_as_block` and confirm it is below 16383.",
            "Phase 2 — push to ~95 % of capacity. Add another batch to reach near-ceiling. Verify counters still scale linearly.",
            "Phase 3 — attempt to push past 16383. The over-capacity commit must be rejected gracefully (clean error, no crash, no partial state). Capture the exact error.",
            "Send Spirent traffic on a representative sample of interfaces (one non-MEF, one MEF, one QPPB-enabled) and verify policers still enforce correctly under full pool occupancy.",
            "Cross-check `wbox-cli bcm diag dbal table dump table=METER_ING_PROFILE_CONFIG DATABASE_ID=\"=2\"` HW row count matches SW pool_stats.",
            "Tear down by removing the bulk config in chunks. Verify pool_stats decrements monotonically (no double-frees, no negative counters).",
            "Final teardown. Verify pool_stats returns to (R0, RB0, B0).",
        ]),
        *section_pass([
            "Steps 2-3 — counter totals match planned allocation; `total_used = regular_indexes_used + 4 * blocks_used_as_block`.",
            "Step 4 — counters scale linearly to ~95 % capacity.",
            "Step 5 — over-capacity commit rejected with a clear error message; no crash; pool counters unchanged after the rejection.",
            "Step 6 — traffic still policed correctly at full capacity (proves HW programming is intact).",
            "Step 7 — HW row count matches SW pool_stats throughout.",
            "Step 8 — counters decrement monotonically during teardown.",
            "Step 9 — pool_stats returns to baseline. No leaks.",
            "No crashes, no QoS process aborts, no SW/HW skew.",
        ]),
        *section_cmds(cmds),
        *section_show(COMMON_SHOW + "\nwbox-cli bcm diag dbal table dump table=METER_ING_PROFILE_CONFIG DATABASE_ID=\"=2\""),
        *section_variants(),
    )


# ---------- main -------------------------------------------------------------

BODIES = {
    # Regression
    "SW-263478": body_regression_category(),
    "SW-263481": body_tr3cm_basic(),
    "SW-263486": body_qppb_basic(),
    # Pool State Functionality
    "SW-263538": body_pool_state_category(),
    "SW-263929": body_pool_state_non_mef(),
    "SW-263930": body_pool_state_mef(),
    "SW-263931": body_pool_state_qppb(),
    "SW-263540": body_pool_state_combined(),
    # HA
    "SW-263539": body_ha_category(),
    "SW-263541": body_ha_task(),
    # Scale
    "SW-263932": body_scale_category(),
    "SW-263933": body_scale_task(),
}


def main():
    for key, adf in BODIES.items():
        path = OUT / f"{key}.json"
        path.write_text(json.dumps(adf, ensure_ascii=False, indent=2))
        print(f"wrote {path} ({path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
