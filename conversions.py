# -*- coding: utf-8 -*-
"""Report DM orders to Meta and TikTok as server-side Purchase events.

Storefront orders are already reported by the official Facebook & Instagram
and TikTok Shopify apps (pixel + server API). Orders entered through this
tool's form never pass the storefront checkout, so the pixels never see them;
this module fills that gap from the orders/create webhook.

Only orders with source_name == ORDER_SOURCE_NAME are sent. The event id is
derived from the Shopify order id, so Shopify's webhook retries are
de-duplicated by Meta/TikTok instead of being counted twice.

Each platform is skipped until its env vars are set. Test orders are sent
only when that platform's test event code is set, and then they show up
under "Test events" in Events Manager without counting as real purchases.
"""
import hashlib
import logging
import os
import threading
import time
from datetime import datetime

import requests

log = logging.getLogger(__name__)

# Must match "sourceName" in app.py's create_order().
ORDER_SOURCE_NAME = "social_media_manual"

META_PIXEL_ID = os.environ.get("META_PIXEL_ID")
META_CAPI_TOKEN = os.environ.get("META_CAPI_TOKEN")
META_TEST_EVENT_CODE = os.environ.get("META_TEST_EVENT_CODE")
META_GRAPH_VERSION = os.environ.get("META_GRAPH_VERSION", "v23.0")

TIKTOK_PIXEL_CODE = os.environ.get("TIKTOK_PIXEL_CODE")
TIKTOK_ACCESS_TOKEN = os.environ.get("TIKTOK_ACCESS_TOKEN")
TIKTOK_TEST_EVENT_CODE = os.environ.get("TIKTOK_TEST_EVENT_CODE")
# Must be the same event name the TikTok Shopify app sends for purchases,
# otherwise campaigns optimising for that event won't count these orders.
TIKTOK_PURCHASE_EVENT = os.environ.get("TIKTOK_PURCHASE_EVENT", "CompletePayment")


def sha256(value):
    value = (value or "").strip().lower()
    return hashlib.sha256(value.encode("utf-8")).hexdigest() if value else None


def event_time(order):
    try:
        return int(datetime.fromisoformat(order["created_at"]).timestamp())
    except (KeyError, TypeError, ValueError):
        return int(time.time())


def order_email(order):
    return order.get("email") or (order.get("customer") or {}).get("email")


def order_value(order):
    return round(float(order.get("total_price") or 0), 2)


def send_meta(order, phone):
    addr = order.get("shipping_address") or {}
    customer_id = (order.get("customer") or {}).get("id")
    user_data = {
        "ph": [sha256(phone)] if phone else None,
        "em": [sha256(order_email(order))] if order_email(order) else None,
        "fn": [sha256(addr.get("first_name"))] if addr.get("first_name") else None,
        "ln": [sha256(addr.get("last_name"))] if addr.get("last_name") else None,
        "ct": [sha256((addr.get("city") or "").replace(" ", ""))] if addr.get("city") else None,
        "country": [sha256("eg")],
        "external_id": [sha256(str(customer_id))] if customer_id else None,
    }
    event = {
        "event_name": "Purchase",
        "event_time": event_time(order),
        "event_id": f"order-{order['id']}",
        # The sale was closed in a DM conversation, not on the website.
        "action_source": "chat",
        "user_data": {k: v for k, v in user_data.items() if v},
        "custom_data": {
            "currency": order.get("currency", "EGP"),
            "value": order_value(order),
            "order_id": str(order["id"]),
            "content_type": "product",
            "contents": [
                {"id": str(li.get("variant_id") or li.get("product_id")),
                 "quantity": li.get("quantity", 1),
                 "item_price": float(li.get("price") or 0)}
                for li in order.get("line_items") or []
            ],
            "num_items": sum(li.get("quantity", 1) for li in order.get("line_items") or []),
        },
    }
    body = {"data": [event]}
    if order.get("test"):
        body["test_event_code"] = META_TEST_EVENT_CODE
    return requests.post(
        f"https://graph.facebook.com/{META_GRAPH_VERSION}/{META_PIXEL_ID}/events",
        params={"access_token": META_CAPI_TOKEN},
        json=body,
        timeout=20,
    )


def send_tiktok(order, phone):
    customer_id = (order.get("customer") or {}).get("id")
    user = {
        # TikTok expects E.164 (with the leading +) before hashing.
        "phone": sha256("+" + phone) if phone else None,
        "email": sha256(order_email(order)),
        "external_id": sha256(str(customer_id)) if customer_id else None,
    }
    event = {
        "event": TIKTOK_PURCHASE_EVENT,
        "event_time": event_time(order),
        "event_id": f"order-{order['id']}",
        "user": {k: v for k, v in user.items() if v},
        "properties": {
            "currency": order.get("currency", "EGP"),
            "value": order_value(order),
            "order_id": str(order["id"]),
            "content_type": "product",
            "contents": [
                {"content_id": str(li.get("variant_id") or li.get("product_id")),
                 "content_name": li.get("title"),
                 "quantity": li.get("quantity", 1),
                 "price": float(li.get("price") or 0)}
                for li in order.get("line_items") or []
            ],
        },
    }
    body = {"event_source": "web", "event_source_id": TIKTOK_PIXEL_CODE, "data": [event]}
    if order.get("test"):
        body["test_event_code"] = TIKTOK_TEST_EVENT_CODE
    return requests.post(
        "https://business-api.tiktok.com/open_api/v1.3/event/track/",
        headers={"Access-Token": TIKTOK_ACCESS_TOKEN},
        json=body,
        timeout=20,
    )


def platforms_for(order):
    """(name, sender) pairs that are configured and should get this order."""
    test = bool(order.get("test"))
    out = []
    if META_PIXEL_ID and META_CAPI_TOKEN and (not test or META_TEST_EVENT_CODE):
        out.append(("Meta", send_meta))
    if TIKTOK_PIXEL_CODE and TIKTOK_ACCESS_TOKEN and (not test or TIKTOK_TEST_EVENT_CODE):
        out.append(("TikTok", send_tiktok))
    return out


def _report(order, phone):
    for name, sender in platforms_for(order):
        try:
            r = sender(order, phone)
            # TikTok answers 200 with a non-zero "code" on rejected events.
            rejected = not r.ok or (name == "TikTok" and r.json().get("code") != 0)
            if rejected:
                log.error("%s rejected Purchase for %s: %s %s",
                          name, order.get("name"), r.status_code, r.text)
            else:
                log.info("%s Purchase sent for %s", name, order.get("name"))
        except Exception:
            log.exception("%s Purchase failed for %s", name, order.get("name"))


def report_purchase(order, phone):
    """Fire-and-forget: runs in a thread so the webhook still answers within
    Shopify's 5s timeout. `phone` is digits with country code, or None."""
    if order.get("source_name") != ORDER_SOURCE_NAME or not platforms_for(order):
        return
    threading.Thread(target=_report, args=(order, phone), daemon=True).start()
