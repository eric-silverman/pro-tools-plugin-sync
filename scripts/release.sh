#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ -n "$(git status --porcelain)" ]]; then
  echo "Working tree is dirty. Commit or stash changes before releasing."
  exit 1
fi

echo "Previous tags:"
if git tag --list | rg . >/dev/null 2>&1; then
  git tag --list --sort=-v:refname | head -n 20
else
  git tag --list --sort=-v:refname
fi

if command -v gh >/dev/null 2>&1; then
  echo ""
  echo "Previous GitHub releases:"
  gh release list || true
fi

echo ""
read -r -p "Enter new version (semver, e.g. 0.2.0): " VERSION

if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Invalid version. Use semver like 0.2.0."
  exit 1
fi

TAG="v${VERSION}"

if git rev-parse "$TAG" >/dev/null 2>&1; then
  echo "Tag already exists: $TAG"
  exit 1
fi

echo "Updating pyproject.toml version to $VERSION"
python3 - "$VERSION" <<'PY'
import re
from pathlib import Path
import sys

version = sys.argv[1]
path = Path("pyproject.toml")
text = path.read_text(encoding="utf-8")
patterns = [
    r'(?m)^version\s*=\s*"[^"]+"\s*$',
    r'(?ms)^\[project\](.*?)(^version\s*=\s*"[^"]+"\s*$)',
]

new_text, count = re.subn(patterns[0], f'version = "{version}"', text, count=1)
if count == 0:
    def repl(match):
        block = match.group(0)
        return re.sub(patterns[0], f'version = "{version}"', block, count=1)

    new_text, count = re.subn(patterns[1], repl, text, count=1)

if count != 1:
    raise SystemExit("Failed to update version in pyproject.toml")
path.write_text(new_text, encoding="utf-8")
PY

git add pyproject.toml
git commit -m "Bump version to $TAG"

echo "Creating tag $TAG"
git tag -a "$TAG" -m "Release $TAG"

echo "Pushing commit and tag to origin"
git push origin HEAD
git push origin "$TAG"

if command -v gh >/dev/null 2>&1; then
  echo "Creating GitHub release $TAG"
  gh release create "$TAG" --title "$TAG" --generate-notes
else
  echo "gh not found; create the GitHub release manually if desired."
fi

echo "Done."
