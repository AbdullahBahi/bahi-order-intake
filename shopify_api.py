# -*- coding: utf-8 -*-
"""Minimal Shopify Admin API client (self-contained copy for this standalone app)."""
import os, time, json
import requests

SHOP = "b1vjn0-5b.myshopify.com"
API_VERSION = "2025-07"
_token_cache = {"tok": None, "exp": 0}


def get_token():
    if _token_cache["tok"] and time.time() < _token_cache["exp"]:
        return _token_cache["tok"]
    r = requests.post(
        f"https://{SHOP}/admin/oauth/access_token",
        json={
            "client_id": os.environ["SHOPIFY_AI_CLIENT_ID"],
            "client_secret": os.environ["SHOPIFY_AI_PASS"],
            "grant_type": "client_credentials",
        },
        timeout=30,
    )
    r.raise_for_status()
    d = r.json()
    _token_cache["tok"] = d["access_token"]
    _token_cache["exp"] = time.time() + int(d.get("expires_in", 3600)) - 120
    return _token_cache["tok"]


def gql(query, variables=None, retries=5):
    for attempt in range(retries):
        r = requests.post(
            f"https://{SHOP}/admin/api/{API_VERSION}/graphql.json",
            headers={"X-Shopify-Access-Token": get_token(), "Content-Type": "application/json"},
            json={"query": query, "variables": variables or {}},
            timeout=60,
        )
        if r.status_code == 429:
            time.sleep(2 * (attempt + 1))
            continue
        r.raise_for_status()
        d = r.json()
        errs = d.get("errors")
        if errs:
            if any("THROTTLED" in str(e.get("extensions", {}).get("code", "")) for e in errs):
                time.sleep(2 * (attempt + 1))
                continue
            raise RuntimeError(f"GraphQL errors: {json.dumps(errs, ensure_ascii=False)[:600]}")
        return d["data"]
    raise RuntimeError("GraphQL throttled after retries")
