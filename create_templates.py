# -*- coding: utf-8 -*-
"""Create the WhatsApp message templates via the Cloud API.

Fallback for when WhatsApp Manager's UI refuses to create templates; the
API also returns the precise reason when the account is restricted.

Reads WHATSAPP_TOKEN from the environment or from a local .env file
(git-ignored), so the token never has to be pasted anywhere else.

Usage:  python create_templates.py          # account health + create templates
        python create_templates.py NAME...  # create only the named templates
        python create_templates.py --check  # account health only
"""
import json
import os
import sys

import requests

WABA_ID = os.environ.get("WHATSAPP_BUSINESS_ACCOUNT_ID", "2232640800640288")
GRAPH = f"https://graph.facebook.com/{os.environ.get('WHATSAPP_GRAPH_VERSION', 'v23.0')}"

# Keep in sync with the template texts in README.md.
TEMPLATES = [
    {
        "name": "order_confirmation",
        "text": (
            "أهلاً {{1}} 👋\n"
            "شكراً لطلبك من باهي للعطور 🤍\n"
            "تم استلام طلبك رقم {{2}} بإجمالي {{3}} جنيه شامل الشحن.\n"
            "هنتواصل معاك أول ما الطلب يتشحن."
        ),
        "example": ["أحمد", "#1012", "1,250"],
    },
    {
        "name": "order_instapay_payment",
        "text": (
            "أهلاً {{1}} 👋\n"
            "شكراً لطلبك من باهي للعطور 🤍\n"
            "تم استلام طلبك رقم {{2}} بإجمالي {{3}} جنيه شامل الشحن.\n\n"
            "لتأكيد الطلب، حوّل المبلغ عن طريق إنستاباي على:\n"
            "{{4}}\n\n"
            "وبعد التحويل ابعت صورة الإيصال هنا في نفس المحادثة.\n\n"
            "الطلب هيتأكد ويتجهز للشحن أول ما نستلم التحويل."
        ),
        "example": ["أحمد", "#1012", "1,250", "https://ipn.eg/S/abdullahbahi.bm/instapay/9leWro"],
    },
    {
        "name": "order_instapay_link",
        "text": (
            "أهلاً {{1}} 👋\n"
            "شكراً لطلبك من باهي للعطور 🤍\n"
            "تم استلام طلبك رقم {{2}} بإجمالي {{3}} جنيه شامل الشحن.\n\n"
            "لتأكيد الطلب، ادفع المبلغ عن طريق إنستاباي من اللينك ده:\n"
            "{{4}}\n\n"
            "وبعد الدفع ابعت صورة الإيصال هنا في نفس المحادثة.\n\n"
            "الطلب هيتأكد ويتجهز للشحن أول ما نستلم المبلغ."
        ),
        "example": ["أحمد", "#1012", "1,250", "https://ipn.eg/S/abdullahbahi.bm/instapay/9leWro"],
    },
]


def load_token():
    token = os.environ.get("WHATSAPP_TOKEN")
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not token and os.path.exists(env_path):
        with open(env_path, encoding="utf-8-sig") as f:
            for line in f:
                key, _, value = line.strip().partition("=")
                if key.strip() == "WHATSAPP_TOKEN":
                    token = value.strip().strip('"').strip("'")
    if not token:
        sys.exit("WHATSAPP_TOKEN not found (env var or .env next to this script).")
    return token


def show(label, r):
    print(f"--- {label}: HTTP {r.status_code}")
    print(json.dumps(r.json(), ensure_ascii=False, indent=2))


def main():
    headers = {"Authorization": f"Bearer {load_token()}"}

    show("account", requests.get(
        f"{GRAPH}/{WABA_ID}", headers=headers, timeout=30,
        params={"fields": "name,account_review_status,business_verification_status,"
                          "ownership_type,health_status"}))
    if "--check" in sys.argv:
        return

    names = [a for a in sys.argv[1:] if not a.startswith("--")]
    for t in TEMPLATES:
        if names and t["name"] not in names:
            continue
        show(f"create {t['name']}", requests.post(
            f"{GRAPH}/{WABA_ID}/message_templates", headers=headers, timeout=30,
            json={
                "name": t["name"],
                "language": "ar",
                "category": "UTILITY",
                "components": [{
                    "type": "BODY",
                    "text": t["text"],
                    "example": {"body_text": [t["example"]]},
                }],
            }))


if __name__ == "__main__":
    main()
