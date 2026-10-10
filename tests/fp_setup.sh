#!/usr/bin/env bash
# Puts a real code repository into ~/demo/project/realrepo for the
# false-positive test. Pinned to a tag so every run sees the same files.
#
#   bash tests/fp_setup.sh
#
# Run it with the daemon STOPPED, then start the daemon again: it only
# marks the folders that exist when it starts.

set -euo pipefail

REPO_URL="https://github.com/pallets/click.git"
REPO_TAG="8.1.7"
DEST="$HOME/demo/project/realrepo"

if pgrep -f "daemon.py" >/dev/null; then
    echo "The daemon is running. Stop it first, then run this again."
    exit 1
fi

if [ -d "$DEST/.git" ]; then
    echo "already cloned: $DEST"
else
    mkdir -p "$(dirname "$DEST")"
    git clone --quiet "$REPO_URL" "$DEST"
fi
git -C "$DEST" -c advice.detachedHead=false checkout --quiet "$REPO_TAG"

# Let git rewrite its index now, so the first measured "git status" does
# not do extra one-off work.
git -C "$DEST" status >/dev/null

# A .env file would hit the '%/.env' block rule and muddy the results.
envfiles=$(find "$DEST" -name .env | wc -l)

echo "repo:      $REPO_URL @ $REPO_TAG"
echo "commit:    $(git -C "$DEST" rev-parse HEAD)"
echo "files (excluding .git): $(find "$DEST" -path "$DEST/.git" -prune -o -type f -print | wc -l)"
echo "files (including .git): $(find "$DEST" -type f | wc -l)"
echo "folders the daemon will mark: $(find "$DEST" -type d | wc -l)"
echo ".env files: $envfiles"
echo
echo "NOW RESTART THE DAEMON so it marks the new folders."
