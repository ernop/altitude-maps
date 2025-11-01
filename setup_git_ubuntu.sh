#!/bin/bash
# Git configuration for Ubuntu/Linux
# Run this script in the altitude-maps directory

cd "$(dirname "$0")"

# Configure Git to use LF line endings
git config core.autocrlf input
git config core.eol lf

echo "Git configured for Ubuntu:"
echo "  core.autocrlf = input"
echo "  core.eol = lf"
echo ""
echo "This ensures LF line endings are committed on Linux."

