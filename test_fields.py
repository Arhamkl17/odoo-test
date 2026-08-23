#!/usr/bin/env python3
import xmlrpc.client

URL = "http://localhost:8069"
DB = "Test1"
USERNAME = "arhamkamal98@gmail.com"
PASSWORD = "Lowongan01"

common = xmlrpc.client.ServerProxy(f"{URL}/xmlrpc/2/common")
uid = common.authenticate(DB, USERNAME, PASSWORD, {})
models = xmlrpc.client.ServerProxy(f"{URL}/xmlrpc/2/object")

def execute(model, method, *args):
    return models.execute_kw(DB, uid, PASSWORD, model, method, list(args))

# Tes 1: dengan type
try:
    pid = execute("product.template", "create", [{
        "name": "TEST type consu",
        "list_price": 19000,
        "type": "consu",
    }])
    print(f"OK - type='consu' berhasil, id: {pid}")
except Exception as e:
    print(f"GAGAL - type='consu': {e}")

# Tes 2: dengan available_in_pos + sale_ok
try:
    pid = execute("product.template", "create", [{
        "name": "TEST pos flags",
        "list_price": 19000,
        "available_in_pos": True,
        "sale_ok": True,
    }])
    print(f"OK - available_in_pos & sale_ok berhasil, id: {pid}")
except Exception as e:
    print(f"GAGAL - available_in_pos/sale_ok: {e}")

# Tes 3: dengan pos_categ_ids (bikin kategori dulu)
try:
    cat_id = execute("pos.category", "search", [["name", "=", "TestKategori"]])
    if not cat_id:
        cat_id = [execute("pos.category", "create", [{"name": "TestKategori"}])]
    pid = execute("product.template", "create", [{
        "name": "TEST pos_categ_ids",
        "list_price": 19000,
        "pos_categ_ids": [(6, 0, cat_id)],
    }])
    print(f"OK - pos_categ_ids berhasil, id: {pid}")
except Exception as e:
    print(f"GAGAL - pos_categ_ids: {e}")
