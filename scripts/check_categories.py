import xmlrpc.client

url = "http://localhost:8069"
db = "sevenopal-odoo"
user = "admin"
pwd = ""  # set your password here locally (do NOT commit real passwords)

common = xmlrpc.client.ServerProxy(url + "/xmlrpc/2/common")
uid = common.authenticate(db, user, pwd, {})
models = xmlrpc.client.ServerProxy(url + "/xmlrpc/2/object")

total = models.execute_kw(db, uid, pwd, "product.template", "search_count", [[("is_published", "=", True)]])
print("Total published products: " + str(total))

no_cat = models.execute_kw(db, uid, pwd, "product.template", "search_count",
    [[("is_published", "=", True), ("public_categ_ids", "=", False)]])
print("Products without public category: " + str(no_cat))

cats = models.execute_kw(db, uid, pwd, "product.public.category", "search_read", [[]], {"fields": ["name", "product_tmpl_ids"], "limit": 20})
for c in cats:
    print("  Cat " + str(c["id"]) + " | " + c["name"] + ": " + str(len(c["product_tmpl_ids"])) + " products")
