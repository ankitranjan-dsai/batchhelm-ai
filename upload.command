#!/usr/bin/env bash
# BatchHelm — one-step upload to GitHub (macOS).
# Double-click in Finder, or run: ./upload.command "optional commit message"
set -euo pipefail

cd "$(dirname "$0")"

MSG="${1:-feat: complete Qwen hackathon build - agent orchestration, Qwen-driven workflow, memory, deployment, docs}"

echo "Repository: $(git config --get remote.origin.url)"
echo "Branch:     $(git rev-parse --abbrev-ref HEAD)"
echo

git add -A

if git diff --cached --quiet; then
  echo "No new changes to commit (pushing any pending commits)."
else
  git commit -m "$MSG"
fi

git push -u origin "$(git rev-parse --abbrev-ref HEAD)"

echo
echo "Uploaded. View it at: https://github.com/ankitranjan-dsai/batchhelm-ai"
