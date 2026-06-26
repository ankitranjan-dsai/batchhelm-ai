#!/usr/bin/env bash
set -euo pipefail

patterns=(
  "Chat""GPT"
  "Co""dex"
  "assist""ant"
  "AI-""generated"
  "generated ""by"
  "contribu""tion"
  "co-""author"
  "Co-""authored"
  "Cla""ude"
  "Gem""ini"
)

joined="$(IFS='|'; echo "${patterns[*]}")"
if rg -n "$joined" .; then
  echo "Blocked attribution language found." >&2
  exit 1
fi

echo "Attribution-language scan passed."
