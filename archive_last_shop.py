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


try:
    execute("pos.config", "write", [2], {"active": False})
    print("Shop id 2 berhasil di-archive (disembunyikan).")
except Exception as e:
    print(f"Gagal archive: {e}")