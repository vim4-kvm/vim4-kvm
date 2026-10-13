#!/bin/sh
# Generate org entrypoints with paths relative to their actual location.
set -eu
repo=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)
workspace=$(dirname -- "$repo")
repo_name=$(basename -- "$repo")
staging=$(mktemp -d)
trap 'rm -rf "$staging"' EXIT HUP INT TERM
printf '# 任务路由\n\n开始工作前读 [%s/AGENTS.md](%s/AGENTS.md) 和 [LESSONS.md](LESSONS.md)。\n' "$repo_name" "$repo_name" > "$staging/AGENTS.md"
printf '@AGENTS.md\n@LESSONS.md\n' > "$staging/CLAUDE.md"
printf '# 错题本入口\n\n见 [%s/LESSONS.md](%s/LESSONS.md)。\n' "$repo_name" "$repo_name" > "$staging/LESSONS.md"

# Check every destination before writing; preserve conflicting content.
for name in AGENTS.md CLAUDE.md LESSONS.md; do
    destination="$workspace/$name"
    if [ ! -f "$repo/$name" ]; then
        printf 'Missing source: %s\n' "$repo/$name" >&2
        exit 1
    fi
    if [ ! -L "$destination" ] && [ -f "$destination" ] && cmp -s "$staging/$name" "$destination"; then
        continue
    fi
    if [ -e "$destination" ] || [ -L "$destination" ]; then
        printf 'Conflict: %s; inspect and migrate before retrying.\n' "$destination" >&2
        exit 1
    fi
done
for name in AGENTS.md CLAUDE.md LESSONS.md; do
    destination="$workspace/$name"
    if [ ! -e "$destination" ]; then
        # noclobber also protects a file created after the preflight.
        (set -C; cat "$staging/$name" > "$destination")
        printf 'Created %s\n' "$destination"
    fi
done
