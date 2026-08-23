#!/usr/bin/env bash
set -e

echo "== Installing OpenCode CLI =="
curl -fsSL https://opencode.ai/install | bash

echo "== Done. Odoo will be reachable on port 8069 once containers finish starting. =="
echo "== Run 'opencode' in this folder, then /connect to choose a provider =="
echo "== (select Ox Alpha via /models once connected). =="
