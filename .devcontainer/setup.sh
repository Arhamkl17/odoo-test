#!/usr/bin/env bash
set -e

echo "== Installing OpenCode CLI =="
curl -fsSL https://opencode.ai/install | bash

# Odoo runs as user `odoo`, but files copied into the workspace may arrive
# root-owned with no read/execute bit for others (rw-r--rw- / rwxr-xrw-).
# That makes every custom addon silently unloadable by the Odoo process
# (Python import fails -> fields/views from those modules "do not exist").
chmod -R a+rX /workspaces/Odoo-mv/addons 2>/dev/null || true

echo "== Done. Odoo will be reachable on port 8069 once containers finish starting. =="
echo "== Run 'opencode' in this folder, then /connect to choose a provider =="
echo "== (select Ox Alpha via /models once connected). =="
