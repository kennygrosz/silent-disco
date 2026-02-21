#!/bin/bash
# Clean up generated/cached files from the Silent Disco repo.
# Safe to run anytime — only removes files that are .gitignored.

set -e
cd "$(dirname "$0")"

echo "Cleaning up Silent Disco repo..."

# Audio snippets
rm -rf song_snippets/*.wav
echo "  Removed audio snippets"

# Python caches
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find . -name '*.pyc' -o -name '*.pyo' | xargs rm -f 2>/dev/null || true
echo "  Removed Python caches"

# Logs
rm -rf logs/
echo "  Removed logs"

# Cache files (preserve .cache — Spotify auth token)
find . -maxdepth 1 -name '.cache*' ! -name '.cache' -exec rm -rf {} +
echo "  Removed cache files (kept Spotify token)"

# macOS junk
find . -name '.DS_Store' -delete 2>/dev/null || true
echo "  Removed .DS_Store files"

# Recreate song_snippets dir (needed at runtime)
mkdir -p song_snippets

echo ""
echo "Done! Repo is clean."
