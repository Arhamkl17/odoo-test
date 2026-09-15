"""Structural audit of all addons in addons/ directory for Odoo 19.

Checks:
1. Manifest referenced files exist (data/assets/demo/qweb).
2. Python files compile (syntax check).
3. XML files parse (well-formedness).
4. __init__.py vs files-on-disk consistency (models/, wizard/, report/, controller/).
"""
import ast
import os
import re
import sys
import xml.etree.ElementTree as ET

ROOT = "addons"

FILES_KEYS = ["data", "demo", "qweb", "assets", "init_xml"]


def check_manifest_files(mod, m):
    problems = []
    for key in FILES_KEYS:
        val = m.get(key)
        if not val:
            continue
        if isinstance(val, dict):  # assets
            for _k, fl in val.items():
                for f in fl:
                    if isinstance(f, str):
                        _check_file(mod, f, problems)
                    elif isinstance(f, dict):
                        for ff in f.get("path", []) if "path" in f else [f]:
                            pass
        elif isinstance(val, list):
            for f in val:
                _check_file(mod, f, problems)
    return problems


def _check_file(mod, f, problems):
    # bundle entries like "addon/path.file" or relative "path.file"
    cand = os.path.join(ROOT, mod, f)
    cand2 = os.path.join(ROOT, f)
    if not (os.path.isfile(cand) or os.path.isfile(cand2)):
        problems.append(f"manifest file missing: {f}")


def check_py(mod):
    problems = []
    for dirpath, _dirnames, filenames in os.walk(os.path.join(ROOT, mod)):
        for fn in filenames:
            if fn.endswith(".py"):
                p = os.path.join(dirpath, fn)
                try:
                    with open(p) as f:
                        compile(f.read(), p, "exec")
                except SyntaxError as e:
                    problems.append(f"PY SYNTAX {p}: {e}")
    return problems


def check_xml(mod):
    problems = []
    for dirpath, _dirnames, filenames in os.walk(os.path.join(ROOT, mod)):
        for fn in filenames:
            if fn.endswith(".xml"):
                p = os.path.join(dirpath, fn)
                try:
                    ET.parse(p)
                except ET.ParseError as e:
                    problems.append(f"XML PARSE {p}: {e}")
    return problems


def check_init(mod):
    problems = []
    for sub in ["models", "wizard", "report", "controllers", "wizards"]:
        d = os.path.join(ROOT, mod, sub)
        if not os.path.isdir(d):
            continue
        init = os.path.join(d, "__init__.py")
        pyfiles = sorted(
            fn for fn in os.listdir(d)
            if fn.endswith(".py") and fn != "__init__.py"
        )
        imported = []
        if os.path.isfile(init):
            with open(init) as f:
                src = f.read()
            for fn in pyfiles:
                name = fn[:-3]
                if re.search(rf"import\s+{name}\b|from\s+\.{name}\s+import", src):
                    imported.append(fn)
        else:
            problems.append(f"missing {init}")
            continue
        for fn in pyfiles:
            if fn not in imported:
                problems.append(f"{sub}/{fn} not imported in {sub}/__init__.py")
    return problems


def main():
    mods = sorted(
        d for d in os.listdir(ROOT)
        if os.path.isdir(os.path.join(ROOT, d))
    )
    total_issues = 0
    for mod in mods:
        mf = os.path.join(ROOT, mod, "__manifest__.py")
        if not os.path.isfile(mf):
            print(f"[SKIP] {mod}: no __manifest__.py")
            continue
        try:
            with open(mf) as fp:
                m = ast.literal_eval(fp.read())
        except Exception as e:
            print(f"[ERROR] {mod}: manifest parse error: {e}")
            total_issues += 1
            continue
        problems = []
        problems += check_manifest_files(mod, m)
        problems += check_py(mod)
        problems += check_xml(mod)
        problems += check_init(mod)
        if problems:
            total_issues += len(problems)
            print(f"\n[ISSUES] {mod} ({m.get('version')})")
            for p in problems:
                print(f"   - {p}")
        else:
            print(f"[OK]    {mod} ({m.get('version')})")
    print(f"\nTotal issues: {total_issues}")
    return 0 if total_issues == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
