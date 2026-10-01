#!/usr/bin/env bash
# Pull the latest commits from the three per-part repos into their folders here,
# keeping each commit's original history. Run from the repository root.
set -euo pipefail

ORG=https://github.com/RAM-AS-RAP

for part in backend ml frontend; do
  echo "== $part =="
  git subtree pull --prefix="$part" "$ORG/ucs31-kimathi-$part.git" main \
    -m "Sync $part from ucs31-kimathi-$part"
done

echo
echo "Done. Review with 'git log --oneline -10', then 'git push'."
