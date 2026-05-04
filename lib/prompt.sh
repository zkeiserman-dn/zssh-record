#!/usr/bin/env bash
# Sticky epic / testing-task prompts.
# State file: $STATE_FILE  (key=value)

zssh_load_state() {
  ZSSH_LAST_EPIC=""
  ZSSH_LAST_TASK=""
  if [ -f "$STATE_FILE" ]; then
    # shellcheck disable=SC1090
    . "$STATE_FILE"
  fi
}

# Ask the user whether to continue on the cached Epic+Task.
# Returns 0 if the cached values should be reused, 1 otherwise.
# Behavior on "other" answers:
#   - empty / y / yes  -> reuse cached  (return 0)
#   - n / no           -> ask both fresh (return 1)
#   - a Jira-shaped ID -> "no, switch to this epic": exports ZSSH_NEW_EPIC
#                         so the caller can skip the epic prompt and only ask
#                         for the task. (return 1)
#   - anything else    -> ask both fresh (return 1)  -- conservative; the
#                         old "default to yes on garbage" silently kept the
#                         wrong epic/task on a typo.
zssh_confirm_continue() {
  ZSSH_NEW_EPIC=""
  if [ -z "$ZSSH_LAST_EPIC" ] || [ -z "$ZSSH_LAST_TASK" ]; then
    return 1
  fi
  printf 'Continue on %s / %s ? [Y/n]: ' "$ZSSH_LAST_EPIC" "$ZSSH_LAST_TASK" >&2
  read -r ans || return 1
  case "$ans" in
    ""|y|Y|yes|YES|Yes) return 0 ;;
    n|N|no|NO|No)       return 1 ;;
    *)
      local norm
      norm="$(zssh_normalize_id "$ans")"
      if printf '%s' "$norm" | grep -qE '^[A-Z]+-[0-9]+$'; then
        ZSSH_NEW_EPIC="$norm"
      fi
      return 1
      ;;
  esac
}

zssh_save_state() {
  cat > "$STATE_FILE" <<EOF
ZSSH_LAST_EPIC="$ZSSH_EPIC"
ZSSH_LAST_TASK="$ZSSH_TASK"
EOF
}

# normalize Jira-style ID e.g. "sw-217283", "  SW217283  " -> "SW-217283"
zssh_normalize_id() {
  local raw="$1"
  raw="$(printf '%s' "$raw" | tr -d '[:space:]' | tr '[:lower:]' '[:upper:]')"
  if printf '%s' "$raw" | grep -qE '^[A-Z]+-[0-9]+$'; then
    printf '%s' "$raw"
  elif printf '%s' "$raw" | grep -qE '^[A-Z]+[0-9]+$'; then
    # insert dash between letters and digits
    printf '%s' "$raw" | sed -E 's/^([A-Z]+)([0-9]+)$/\1-\2/'
  else
    printf '%s' "$raw"
  fi
}

zssh_prompt_epic() {
  local default="$ZSSH_LAST_EPIC"
  local prompt
  if [ -n "$default" ]; then
    prompt="Epic   [$default]: "
  else
    prompt="Epic   (e.g. SW-217283): "
  fi
  printf '%s' "$prompt" >&2
  read -r raw
  if [ -z "$raw" ] && [ -n "$default" ]; then
    ZSSH_EPIC="$default"
  else
    ZSSH_EPIC="$(zssh_normalize_id "$raw")"
  fi
  if [ -z "$ZSSH_EPIC" ]; then
    echo "[zssh] epic is required" >&2
    exit 2
  fi
}

zssh_prompt_task() {
  local default="$ZSSH_LAST_TASK"
  local prompt
  if [ -n "$default" ]; then
    prompt="Task   [$default]: "
  else
    prompt="Task   (e.g. SW-262109): "
  fi
  printf '%s' "$prompt" >&2
  read -r raw
  if [ -z "$raw" ] && [ -n "$default" ]; then
    ZSSH_TASK="$default"
  else
    ZSSH_TASK="$(zssh_normalize_id "$raw")"
  fi
  if [ -z "$ZSSH_TASK" ]; then
    echo "[zssh] task is required" >&2
    exit 2
  fi
}
