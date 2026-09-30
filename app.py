# -*- coding: utf-8 -*-
"""Order-intake tool for Bahi Perfumes social-media orders.

A single-password-protected form used to turn a DM conversation (Instagram/
Facebook/TikTok/WhatsApp) into a real Shopify order in a few taps, from
phone or desktop, without going through the storefront checkout.
"""
import os
import time
from functools import wraps

from flask import Flask, request, render_template, redirect, url_for, flash

from shopify_api import gql, SHOP
from catalog import PRODUCTS, PROVINCES, SIZES, PAYMENT_METHODS, ORDER_SOURCES

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-only-not-secret")

TOOL_PASSWORD = os.environ.get("TOOL_PASSWORD")

_cache = {"data": None, "exp": 0}
CACHE_TTL = 300  # seconds

PRODUCTS_QUERY = """{
  products(first: 20) {
    edges { node {
      handle
      variants(first: 10) { edges { node { id title price } } }
    } }
  }
}"""

# Same shape/logic as shopify/update_shipping_from_sheet.py live_egypt(),
# trimmed to just what this form needs (province -> price/zone name).
ZONES_QUERY = """{ deliveryProfiles(first: 10) { edges { node { default
  profileLocationGroups { locationGroupZones(first: 50) { edges { node {
    zone { name countries { code { countryCode } provinces { code } } }
    methodDefinitions(first: 5) { edges { node { rateProvider { __typename
      ... on DeliveryRateDefinition { price { amount } } } } } } } } } } } } } }"""


def require_password(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not TOOL_PASSWORD:
            return view(*args, **kwargs)
        auth = request.authorization
        if not auth or auth.password != TOOL_PASSWORD:
            return (
                "Authentication required",
                401,
                {"WWW-Authenticate": 'Basic realm="Order Intake"'},
            )
        return view(*args, **kwargs)

    return wrapped


def load_catalog(force=False):
    """Fetch (and cache) live variant IDs/prices and shipping zone prices."""
    if not force and _cache["data"] and time.time() < _cache["exp"]:
        return _cache["data"]

    variants_by_handle = {}
    for edge in gql(PRODUCTS_QUERY)["products"]["edges"]:
        node = edge["node"]
        by_size = {}
        for ve in node["variants"]["edges"]:
            v = ve["node"]
            by_size[v["title"]] = {"id": v["id"], "price": v["price"]}
        variants_by_handle[node["handle"]] = by_size

    province_price = {}
    prof = next(
        e["node"] for e in gql(ZONES_QUERY)["deliveryProfiles"]["edges"] if e["node"]["default"]
    )
    for lg in prof["profileLocationGroups"]:
        for ze in lg["locationGroupZones"]["edges"]:
            zone = ze["node"]["zone"]
            codes = [c["code"]["countryCode"] for c in zone["countries"]]
            if codes != ["EG"]:
                continue
            methods = ze["node"]["methodDefinitions"]["edges"]
            if not methods:
                continue
            price = methods[0]["node"]["rateProvider"]["price"]["amount"]
            for p in zone["countries"][0]["provinces"]:
                province_price[p["code"]] = {"price": price, "zone": zone["name"]}

    data = {"variants_by_handle": variants_by_handle, "province_price": province_price}
    _cache["data"] = data
    _cache["exp"] = time.time() + CACHE_TTL
    return data


ORDER_CREATE_MUTATION = """
mutation orderCreate($order: OrderCreateOrderInput!, $options: OrderCreateOptionsInput) {
  orderCreate(order: $order, options: $options) {
    order { id name }
    userErrors { field message }
  }
}
"""


@app.route("/", methods=["GET"])
@require_password
def index():
    catalog = load_catalog()
    products = [
        {"handle": h, "name": n, "sizes": catalog["variants_by_handle"].get(h, {})}
        for h, n in PRODUCTS
    ]
    provinces = [
        {"code": c, "name": n, "price": catalog["province_price"].get(c, {}).get("price")}
        for c, n in PROVINCES
    ]
    return render_template(
        "index.html",
        products=products,
        provinces=provinces,
        sizes=SIZES,
        payment_methods=PAYMENT_METHODS,
        order_sources=ORDER_SOURCES,
    )


@app.route("/order", methods=["POST"])
@require_password
def create_order():
    form = request.form
    catalog = load_catalog()

    customer_name = form.get("customer_name", "").strip()
    phone = form.get("phone", "").strip()
    email = form.get("email", "").strip()
    address1 = form.get("address1", "").strip()
    province_code = form.get("province")
    payment_method = form.get("payment_method")
    order_source = form.get("order_source", "")
    notes = form.get("notes", "").strip()

    if not customer_name or not phone or not address1 or not province_code:
        flash("لازم تملأ اسم العميل ورقم الهاتف والعنوان والمحافظة.")
        return redirect(url_for("index"))

    handles = request.form.getlist("product_handle")
    sizes = request.form.getlist("product_size")
    qtys = request.form.getlist("product_qty")

    line_items = []
    for handle, size, qty in zip(handles, sizes, qtys):
        if not handle or not size:
            continue
        variant = catalog["variants_by_handle"].get(handle, {}).get(size)
        if not variant:
            flash(f"في مشكلة في اختيار المنتج/الحجم: {handle} {size}")
            return redirect(url_for("index"))
        try:
            qty_int = max(1, int(qty))
        except ValueError:
            qty_int = 1
        line_items.append({"variantId": variant["id"], "quantity": qty_int})

    if not line_items:
        flash("لازم تضيف منتج واحد على الأقل.")
        return redirect(url_for("index"))

    zone = catalog["province_price"].get(province_code)
    if not zone:
        flash("محافظة غير معروفة لمنطقة الشحن.")
        return redirect(url_for("index"))

    name_parts = customer_name.split(" ", 1)
    first_name = name_parts[0]
    last_name = name_parts[1] if len(name_parts) > 1 else ""

    province_name = dict(PROVINCES).get(province_code, province_code)

    financial_status = "PAID" if payment_method == "instapay" else "PENDING"
    payment_label = dict(PAYMENT_METHODS).get(payment_method, payment_method)
    source_label = dict(ORDER_SOURCES).get(order_source, order_source)

    note_lines = [f"طريقة الدفع: {payment_label}"]
    if source_label:
        note_lines.append(f"مصدر الطلب: {source_label}")
    if notes:
        note_lines.append(f"ملاحظات: {notes}")

    test_mode = form.get("test_mode") == "on"

    address = {
        "firstName": first_name,
        "lastName": last_name,
        "address1": address1,
        "city": province_name,
        "provinceCode": province_code,
        "countryCode": "EG",
        "phone": phone,
    }

    order_input = {
        "lineItems": line_items,
        "phone": phone,
        "email": email or None,
        "note": "\n".join(note_lines),
        "tags": ["social-media", order_source or "manual", payment_method or "unknown"],
        "financialStatus": financial_status,
        "sourceName": "social_media_manual",
        "test": test_mode,
        "shippingAddress": address,
        "billingAddress": address,
        "shippingLines": [
            {
                "title": f"الشحن - {zone['zone']}",
                "priceSet": {"shopMoney": {"amount": zone["price"], "currencyCode": "EGP"}},
            }
        ],
    }

    send_receipt = bool(email) and not test_mode
    result = gql(
        ORDER_CREATE_MUTATION, {"order": order_input, "options": {"sendReceipt": send_receipt}}
    )
    payload = result["orderCreate"]
    if payload["userErrors"]:
        flash("فشل إنشاء الأوردر: " + "; ".join(e["message"] for e in payload["userErrors"]))
        return redirect(url_for("index"))

    order = payload["order"]
    numeric_id = order["id"].rsplit("/", 1)[-1]
    store_handle = SHOP.replace(".myshopify.com", "")
    admin_url = f"https://admin.shopify.com/store/{store_handle}/orders/{numeric_id}"
    return render_template(
        "result.html", order_name=order["name"], admin_url=admin_url, test_mode=test_mode
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
