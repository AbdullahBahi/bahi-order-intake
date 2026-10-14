# -*- coding: utf-8 -*-
"""Product reviews for the Bahi storefront.

Customers submit reviews from the product page (sections/bahi-reviews.liquid), which POSTs
here. Each review is saved as a `bahi_review` metaobject in DRAFT status, so nothing shows on
the store until it is approved from /reviews/admin. Approving a review publishes it and
recomputes the product's metafields:

  bahi.reviews          approved reviews, newest first (rendered by the reviews section)
  reviews.rating        average rating (Shopify standard; drives the theme's star block and
                        the product's structured data for Google)
  reviews.rating_count  number of approved reviews

The metaobject/metafield definitions are created once by shopify/setup_reviews.py.
"""
import json
import time
from collections import defaultdict, deque
from datetime import date

from flask import (Blueprint, request, jsonify, make_response, render_template, redirect,
                   url_for, flash)

from auth import require_password
from shopify_api import gql, SHOP

REVIEW_TYPE = "bahi_review"
ALLOWED_ORIGINS = {
    "https://bahi-perfumes.com",
    "https://www.bahi-perfumes.com",
    f"https://{SHOP}",
}
MAX_AUTHOR = 60
MAX_BODY = 1500
RATE_LIMIT = 5          # submissions per IP ...
RATE_WINDOW = 3600      # ... per hour

bp = Blueprint("reviews", __name__)
_recent = defaultdict(deque)


# ---------------------------------------------------------------- public endpoint

def _cors(resp):
    resp = make_response(resp)
    origin = request.headers.get("Origin", "")
    if origin in ALLOWED_ORIGINS:
        resp.headers["Access-Control-Allow-Origin"] = origin
        resp.headers["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
        resp.headers["Vary"] = "Origin"
    return resp


def _rate_limited(ip):
    q = _recent[ip]
    now = time.time()
    while q and now - q[0] > RATE_WINDOW:
        q.popleft()
    if len(q) >= RATE_LIMIT:
        return True
    q.append(now)
    return False


@bp.route("/reviews/ping", methods=["GET"])
def ping():
    """Called when a visitor opens the review form, to wake the free Render instance early."""
    return _cors(jsonify(ok=True))


@bp.route("/reviews", methods=["POST", "OPTIONS"])
def submit():
    if request.method == "OPTIONS":
        return _cors(("", 204))

    def fail(msg, code=400):
        return _cors((jsonify(ok=False, error=msg), code))

    data = request.get_json(silent=True) or {}
    if data.get("website"):  # honeypot field, hidden from real visitors
        return _cors(jsonify(ok=True))

    product_id = str(data.get("product_id", "")).strip()
    author = " ".join(str(data.get("author", "")).split())[:MAX_AUTHOR]
    body = str(data.get("body", "")).strip()[:MAX_BODY]
    try:
        rating = int(data.get("rating"))
    except (TypeError, ValueError):
        rating = 0

    if not product_id.isdigit():
        return fail("منتج غير معروف.")
    if not 1 <= rating <= 5:
        return fail("اختار تقييم من نجمة لخمس نجوم.")
    if len(author) < 2:
        return fail("اكتب اسمك.")
    if len(body) < 5:
        return fail("اكتب رأيك في العطر.")

    ip = (request.headers.get("X-Forwarded-For") or request.remote_addr or "").split(",")[0].strip()
    if _rate_limited(ip):
        return fail("استلمنا تقييمات كتير منك، جرّب تاني بعد شوية.", 429)

    r = gql("""mutation($m: MetaobjectCreateInput!) { metaobjectCreate(metaobject: $m) {
                 metaobject { id } userErrors { field message } } }""",
            {"m": {
                "type": REVIEW_TYPE,
                "capabilities": {"publishable": {"status": "DRAFT"}},
                "fields": [
                    {"key": "product", "value": f"gid://shopify/Product/{product_id}"},
                    {"key": "rating", "value": str(rating)},
                    {"key": "author", "value": author},
                    {"key": "body", "value": body},
                    {"key": "submitted_on", "value": date.today().isoformat()},
                ],
            }})
    if r["metaobjectCreate"]["userErrors"]:
        return fail("حصلت مشكلة في حفظ التقييم، جرّب تاني.", 500)
    return _cors(jsonify(ok=True))


# ---------------------------------------------------------------- moderation

LIST_QUERY = """query($after: String) {
  metaobjects(type: "bahi_review", first: 250, after: $after, sortKey: "updated_at", reverse: true) {
    nodes {
      id
      capabilities { publishable { status } }
      product: field(key: "product") { value reference { ... on Product { id title handle } } }
      rating: field(key: "rating") { value }
      author: field(key: "author") { value }
      body: field(key: "body") { value }
      submitted_on: field(key: "submitted_on") { value }
    }
    pageInfo { hasNextPage endCursor }
  }
}"""


def all_reviews():
    out, cursor = [], None
    while True:
        d = gql(LIST_QUERY, {"after": cursor})["metaobjects"]
        for n in d["nodes"]:
            prod = (n["product"] or {}).get("reference") or {}
            out.append({
                "id": n["id"],
                "status": n["capabilities"]["publishable"]["status"],
                "product_id": (n["product"] or {}).get("value"),
                "product_title": prod.get("title", "منتج محذوف"),
                "product_handle": prod.get("handle"),
                "rating": int((n["rating"] or {}).get("value") or 0),
                "author": (n["author"] or {}).get("value", ""),
                "body": (n["body"] or {}).get("value", ""),
                "submitted_on": (n["submitted_on"] or {}).get("value", ""),
            })
        if not d["pageInfo"]["hasNextPage"]:
            break
        cursor = d["pageInfo"]["endCursor"]
    out.sort(key=lambda x: x["submitted_on"], reverse=True)
    return out


def sync_product(product_id):
    """Rewrite a product's review metafields from its currently approved reviews."""
    approved = [r for r in all_reviews()
                if r["product_id"] == product_id and r["status"] == "ACTIVE"]
    if not approved:
        gql("""mutation($m: [MetafieldIdentifierInput!]!) { metafieldsDelete(metafields: $m) {
                 userErrors { message } } }""",
            {"m": [{"ownerId": product_id, "namespace": ns, "key": k}
                   for ns, k in (("bahi", "reviews"), ("reviews", "rating"),
                                 ("reviews", "rating_count"))]})
        return
    avg = round(sum(r["rating"] for r in approved) / len(approved), 1)
    r = gql("""mutation($m: [MetafieldsSetInput!]!) { metafieldsSet(metafields: $m) {
                 userErrors { field message } } }""",
            {"m": [
                {"ownerId": product_id, "namespace": "bahi", "key": "reviews",
                 "type": "list.metaobject_reference",
                 "value": json.dumps([r["id"] for r in approved])},
                {"ownerId": product_id, "namespace": "reviews", "key": "rating",
                 "type": "rating",
                 "value": json.dumps({"value": f"{avg:.1f}", "scale_min": "1.0", "scale_max": "5.0"})},
                {"ownerId": product_id, "namespace": "reviews", "key": "rating_count",
                 "type": "number_integer", "value": str(len(approved))},
            ]})
    if r["metafieldsSet"]["userErrors"]:
        raise RuntimeError(json.dumps(r["metafieldsSet"]["userErrors"], ensure_ascii=False))


@bp.route("/reviews/admin", methods=["GET"])
@require_password
def admin():
    reviews = all_reviews()
    return render_template(
        "reviews.html",
        pending=[r for r in reviews if r["status"] == "DRAFT"],
        approved=[r for r in reviews if r["status"] == "ACTIVE"],
    )


@bp.route("/reviews/admin/<action>", methods=["POST"])
@require_password
def moderate(action):
    review_id = request.form.get("id", "")
    product_id = request.form.get("product_id", "")
    if not review_id.startswith("gid://shopify/Metaobject/"):
        flash("تقييم غير معروف.")
        return redirect(url_for("reviews.admin"))

    if action in ("approve", "hide"):
        status = "ACTIVE" if action == "approve" else "DRAFT"
        r = gql("""mutation($id: ID!, $m: MetaobjectUpdateInput!) {
                     metaobjectUpdate(id: $id, metaobject: $m) { userErrors { message } } }""",
                {"id": review_id, "m": {"capabilities": {"publishable": {"status": status}}}})
        errs = r["metaobjectUpdate"]["userErrors"]
    elif action == "delete":
        r = gql("""mutation($id: ID!) { metaobjectDelete(id: $id) { userErrors { message } } }""",
                {"id": review_id})
        errs = r["metaobjectDelete"]["userErrors"]
    else:
        flash("أمر غير معروف.")
        return redirect(url_for("reviews.admin"))

    if errs:
        flash("فشلت العملية: " + "; ".join(e["message"] for e in errs))
    else:
        if product_id.startswith("gid://shopify/Product/"):
            sync_product(product_id)
        flash({"approve": "تم نشر التقييم ✅", "hide": "تم إخفاء التقييم",
               "delete": "تم حذف التقييم"}[action])
    return redirect(url_for("reviews.admin"))
