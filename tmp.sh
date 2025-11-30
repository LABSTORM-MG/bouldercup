#!/usr/bin/env bash

set -e

# Make sure we have all branches and up-to-date info
git fetch --all --prune

# Switch to master and update it
git checkout master
git pull origin master

echo "Finding branches fully merged into master..."

# List branches merged into master, excluding master itself
merged_branches=$(git branch --merged master | sed 's/*//' | sed 's/^[[:space:]]*//' | grep -v '^master$' || true)

if [ -z "$merged_branches" ]; then
    echo "No merged branches to delete."
    exit 0
fi

echo "Merged branches that will be deleted:"
echo "$merged_branches"

# Delete each merged branch locally and on origin
for branch in $merged_branches; do
    echo "Deleting local branch: $branch"
    git branch -d "$branch" || true

    echo "Deleting remote branch: $branch"
    git push origin --delete "$branch" || true
done

echo "Done. Run: git fetch --all --prune"
echo "Then refresh GitHub; the branch count should be lower."
