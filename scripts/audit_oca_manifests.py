import ast
import os

root = "addons"
results = []
for d in sorted(os.listdir(root)):
    p = os.path.join(root, d)
    if not os.path.isdir(p):
        continue
    f = os.path.join(p, "__manifest__.py")
    if not os.path.isfile(f):
        print(f"{d}: NO MANIFEST")
        continue
    try:
        with open(f) as fp:
            m = ast.literal_eval(fp.read())
    except Exception as e:
        print(f"{d}: MANIFEST PARSE ERROR {e}")
        continue
    print("=" * 60)
    print(f"module: {d}")
    print(f"  name: {m.get('name')}")
    print(f"  version: {m.get('version')}")
    print(f"  depends: {m.get('depends')}")
    print(f"  license: {m.get('license')}")
    print(f"  category: {m.get('category')}")
    print(f"  installable: {m.get('installable', True)}")
