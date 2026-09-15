#!/usr/bin/env bash
set -e

# Folder repo diturunkan dari lokasi skrip ini, BUKAN hardcode "/workspaces/Odoo-mv":
# repo ini bisa dibuka di codespace mana pun dengan nama folder apa pun
# (Odoo-mv, odoo-test, <repo>), dan folder yang salah membuat chmod di bawah
# diam-diam tidak berpengaruh.
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "== Installing OpenCode CLI =="
curl -fsSL https://opencode.ai/install | bash

# Odoo runs as user `odoo`, but files copied into the workspace may arrive
# root-owned with no read/execute bit for others (rw-r--rw- / rwxr-xrw-).
# That makes every custom addon silently unloadable by the Odoo process
# (Python import fails -> fields/views from those modules "do not exist").
for d in "$REPO_DIR/addons" "$REPO_DIR/import_data"; do
    if [ -d "$d" ]; then
        chmod -R a+rX "$d" 2>/dev/null || true
    fi
done

echo "== Done. Odoo will be reachable on port 8069 once containers finish starting. =="
echo "== Run 'opencode' in this folder, then /connect to choose a provider =="
echo "== (select Ox Alpha via /models once connected). =="
