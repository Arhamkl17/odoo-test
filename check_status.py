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

total = execute("product.template", "search_count", [])
print(f"Total produk sekarang: {total}")

geprek = execute("product.template", "search_count", [["name", "like", "Geprek"]])
print(f"Produk mengandung kata 'Geprek': {geprek}")

furniture = execute("product.template", "search_count", [["name", "like", "Desk"]])
print(f"Produk mengandung kata 'Desk' (furniture demo): {furniture}")
