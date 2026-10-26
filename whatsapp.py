# -*- coding: utf-8 -*-
"""Automatic WhatsApp order confirmation (Shopify orders/create webhook).

Every new order (storefront checkout or this tool's form) gets a WhatsApp
message on the customer's phone via the Meta WhatsApp Cloud API:
- InstaPay orders that are not yet paid -> confirmation + transfer
  instructions (template WA_TEMPLATE_INSTAPAY).
- Everything else (COD, or InstaPay already marked paid from the form)
  -> plain confirmation (template WA_TEMPLATE_CONFIRM).

Business-initiated WhatsApp messages must use templates pre-approved in
WhatsApp Manager; see README.md for the exact template texts.
"""
import base64
import hashlib
import hmac
import json
import logging
import os
import re

import requests
from flask import Blueprint, request

from shopify_api import gql
import conversions

bp = Blueprint("whatsapp", __name__)
log = logging.getLogger(__name__)

WA_TOKEN = os.environ.get("WHATSAPP_TOKEN")
WA_PHONE_NUMBER_ID = os.environ.get("WHATSAPP_PHONE_NUMBER_ID")
WA_GRAPH_VERSION = os.environ.get("WHATSAPP_GRAPH_VERSION", "v23.0")
WA_TEMPLATE_CONFIRM = os.environ.get("WA_TEMPLATE_CONFIRM", "order_confirmation")
WA_TEMPLATE_INSTAPAY = os.environ.get("WA_TEMPLATE_INSTAPAY", "order_instapay_payment")
WA_TEMPLATE_LANG = os.environ.get("WA_TEMPLATE_LANG", "ar")
INSTAPAY_ADDRESS = os.environ.get(
    "INSTAPAY_ADDRESS", "https://ipn.eg/S/abdullahbahi.bm/instapay/9leWro")
# Test orders (e.g. the form's test toggle) often carry made-up numbers, so
# they are skipped unless explicitly enabled while trying the setup out.
SEND_TEST_ORDERS = os.environ.get("WHATSAPP_SEND_TEST_ORDERS") == "1"
# Shopify signs app-registered webhooks with the app's client secret.
WEBHOOK_SECRET = os.environ.get("SHOPIFY_AI_PASS", "")

SENT_TAG = "whatsapp-sent"


def verify_hmac(raw_body, header_hmac):
    if not WEBHOOK_SECRET or not header_hmac:
        return False
    digest = hmac.new(WEBHOOK_SECRET.encode(), raw_body, hashlib.sha256).digest()
    return hmac.compare_digest(base64.b64encode(digest).decode(), header_hmac)


def normalize_phone(raw):
    """Return the number as WhatsApp wants it (digits with country code), or None.

    Handles the shapes seen on real orders: 01xxxxxxxxx, +201xxxxxxxxx,
    +2001xxxxxxxxx (country code typed before the local leading 0),
    00201xxxxxxxxx and foreign +971... numbers.
    """
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith("200") and len(digits) == 13:
        digits = "20" + digits[3:]
    elif digits.startswith("0") and len(digits) == 11:
        digits = "20" + digits[1:]
    elif digits.startswith("1") and len(digits) == 10:
        digits = "20" + digits
    return digits if 10 <= len(digits) <= 15 else None


def order_phone(order):
    for src in (order.get("shipping_address"), order.get("billing_address"),
                order.get("customer"), order):
        if src and src.get("phone"):
            return src["phone"]
    return None


def first_name(order):
    for src in (order.get("shipping_address"), order.get("customer"),
                order.get("billing_address")):
        if src and src.get("first_name"):
            return src["first_name"]
    return "عميلنا العزيز"


def needs_instapay_transfer(order):
    gateways = " ".join(order.get("payment_gateway_names") or []).lower()
    return "instapay" in gateways and order.get("financial_status") != "paid"


def format_amount(amount):
    value = float(amount or 0)
    return f"{value:,.0f}" if value.is_integer() else f"{value:,.2f}"


def build_template(order):
    order_name = order.get("name", "")
    total = format_amount(order.get("total_price"))
    params = [first_name(order), order_name, total]
    if needs_instapay_transfer(order):
        name = WA_TEMPLATE_INSTAPAY
        params.append(INSTAPAY_ADDRESS)
    else:
        name = WA_TEMPLATE_CONFIRM
    return {
        "name": name,
        "language": {"code": WA_TEMPLATE_LANG},
        "components": [{
            "type": "body",
            "parameters": [{"type": "text", "text": str(p)} for p in params],
        }],
    }


def send_template(to, template):
    r = requests.post(
        f"https://graph.facebook.com/{WA_GRAPH_VERSION}/{WA_PHONE_NUMBER_ID}/messages",
        headers={"Authorization": f"Bearer {WA_TOKEN}"},
        json={"messaging_product": "whatsapp", "to": to, "type": "template",
              "template": template},
        timeout=20,
    )
    return r


def already_sent(order_gid):
    data = gql("query($id: ID!) { order(id: $id) { tags } }", {"id": order_gid})
    return SENT_TAG in ((data.get("order") or {}).get("tags") or [])


def mark_sent(order_gid):
    gql(
        "mutation($id: ID!, $tags: [String!]!) { tagsAdd(id: $id, tags: $tags) "
        "{ userErrors { message } } }",
        {"id": order_gid, "tags": [SENT_TAG]},
    )


@bp.route("/healthz")
def healthz():
    # Unauthenticated, for an uptime pinger that keeps the free Render
    # instance awake so webhooks are answered within Shopify's 5s timeout.
    return "ok"


@bp.route("/webhooks/orders-create", methods=["POST"])
def orders_create():
    raw = request.get_data()
    if not verify_hmac(raw, request.headers.get("X-Shopify-Hmac-Sha256")):
        return "invalid signature", 401

    order = json.loads(raw or b"{}")
    order_name = order.get("name")
    order_gid = order.get("admin_graphql_api_id")

    # DM orders bypass the storefront pixels; report them to Meta/TikTok.
    conversions.report_purchase(order, normalize_phone(order_phone(order)))

    if not WA_TOKEN or not WA_PHONE_NUMBER_ID:
        log.warning("WhatsApp not configured; skipping %s", order_name)
        return "not configured", 200
    if order.get("test") and not SEND_TEST_ORDERS:
        return "test order skipped", 200

    to = normalize_phone(order_phone(order))
    if not to:
        log.warning("No usable phone on %s", order_name)
        return "no phone", 200

    # Shopify retries deliveries, so the tag on the order is the source of
    # truth for "already messaged" (survives restarts of this app).
    if order_gid and already_sent(order_gid):
        return "already sent", 200

    r = send_template(to, build_template(order))
    if r.status_code >= 500:
        # Meta-side hiccup: a non-2xx makes Shopify retry the webhook later.
        log.error("WhatsApp send failed for %s: %s %s", order_name, r.status_code, r.text)
        return "send failed", 502
    if not r.ok:
        # Bad number / template problem: retrying won't help.
        log.error("WhatsApp rejected %s: %s %s", order_name, r.status_code, r.text)
        return "rejected", 200

    if order_gid:
        mark_sent(order_gid)
    log.info("WhatsApp confirmation sent for %s to %s", order_name, to)
    return "sent", 200
