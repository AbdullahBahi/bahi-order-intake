# -*- coding: utf-8 -*-
"""One-time setup: point Shopify's orders/create webhook at this app.

Usage:  python register_webhook.py https://bahi-order-intake.onrender.com
Re-running is safe: an existing subscription for the same URL is reused.
"""
import sys

from shopify_api import gql

LIST = """{ webhookSubscriptions(first: 50, topics: [ORDERS_CREATE]) {
  edges { node { id uri } } } }"""

CREATE = """mutation($sub: WebhookSubscriptionInput!) {
  webhookSubscriptionCreate(topic: ORDERS_CREATE, webhookSubscription: $sub) {
    webhookSubscription { id uri }
    userErrors { field message }
  } }"""


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    uri = sys.argv[1].rstrip("/") + "/webhooks/orders-create"

    for e in gql(LIST)["webhookSubscriptions"]["edges"]:
        if e["node"]["uri"] == uri:
            print("Already registered:", e["node"]["id"], uri)
            return

    res = gql(CREATE, {"sub": {"uri": uri, "format": "JSON"}})["webhookSubscriptionCreate"]
    if res["userErrors"]:
        sys.exit(f"Failed: {res['userErrors']}")
    print("Registered:", res["webhookSubscription"]["id"], uri)


if __name__ == "__main__":
    main()
