#!/usr/bin/env bash
# One-shot install: clone (or update) repo, venv, editable install.
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/the-4rch1t3ct/privex-starter/main/install.sh | bash
# Optional:
#   INSTALL_DIR=~/my-privex curl -fsSL ... | bash

set -euo pipefail

REPO="${PRIVEX_REPO:-https://github.com/the-4rch1t3ct/privex-starter.git}"
INSTALL_DIR="${INSTALL_DIR:-${HOME}/privex-starter}"
VENV="${INSTALL_DIR}/.venv"
PYTHON="${PYTHON:-python3}"

need() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "error: '$1' is required but not installed." >&2
    exit 1
  }
}

need git
need "$PYTHON"

if [[ -d "${INSTALL_DIR}/.git" ]]; then
  echo "Updating existing clone: ${INSTALL_DIR}"
  git -C "${INSTALL_DIR}" pull --ff-only
elif [[ -d "${INSTALL_DIR}" ]]; then
  echo "error: ${INSTALL_DIR} exists and is not a git clone. Remove it or set INSTALL_DIR." >&2
  exit 1
else
  echo "Cloning into ${INSTALL_DIR}"
  git clone "${REPO}" "${INSTALL_DIR}"
fi

echo "Creating venv and installing (this may take a minute)..."
"$PYTHON" -m venv "${VENV}"
"${VENV}/bin/python" -m pip install --upgrade pip
"${VENV}/bin/pip" install -r "${INSTALL_DIR}/requirements-dev.txt"

echo ""
echo "✔ PriveX starter installed at ${INSTALL_DIR}"
echo ""
echo "Next — add the CLI to your PATH for this shell, then run onboarding:"
echo "  export PATH=\"${VENV}/bin:\${PATH}\""
echo "  privex init --connect"
echo ""
echo "Or call the binary directly:"
echo "  ${VENV}/bin/privex init --connect"
echo ""
