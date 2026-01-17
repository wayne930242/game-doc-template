#!/bin/bash
# 從此 template 建立新 repo（預設 private）

if [ -z "$1" ]; then
  echo "Usage: ./gh-clone.sh <repo-name> [--public]"
  exit 1
fi

VISIBILITY="--private"
if [ "$2" = "--public" ]; then
  VISIBILITY="--public"
fi

gh repo create "$1" --template wayne930242/game-doc-template $VISIBILITY --clone
