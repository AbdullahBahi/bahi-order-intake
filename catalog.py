# -*- coding: utf-8 -*-
"""Static reference data for the order-intake form.

Product prices/variant IDs are fetched live from Shopify; this file only
holds display order/labels and the Egypt province list, which must match
the province codes already configured on the store's delivery zones
(see ../update_shipping_from_sheet.py DEST mapping).
"""

# Display order for the product dropdown (handle -> Arabic name)
PRODUCTS = [
    ("zafar", "ظفر"),
    ("ulfah", "ألفة"),
    ("hayam", "هيام"),
    ("fetnah", "فتنة"),
    ("khodor", "خدور"),
    ("soadad", "سؤدد"),
    ("athar", "أثر"),
    ("lahab", "لهب"),
    ("wahaj", "وهج"),
]

# Egypt province code -> Arabic display name (code must match Shopify's
# province codes used in the store's delivery zones).
PROVINCES = [
    ("C", "القاهرة"),
    ("GZ", "الجيزة"),
    ("KB", "القليوبية"),
    ("FYM", "الفيوم"),
    ("BNS", "بني سويف"),
    ("MN", "المنيا"),
    ("AST", "أسيوط"),
    ("SHG", "سوهاج"),
    ("KN", "قنا"),
    ("ASN", "أسوان"),
    ("LX", "الأقصر"),
    ("BA", "البحر الأحمر"),
    ("IS", "الإسماعيلية"),
    ("SUZ", "السويس"),
    ("PTS", "بورسعيد"),
    ("ALX", "الإسكندرية"),
    ("BH", "البحيرة"),
    ("GH", "الغربية"),
    ("MNF", "المنوفية"),
    ("DT", "دمياط"),
    ("DK", "الدقهلية"),
    ("KFS", "كفر الشيخ"),
    ("SHR", "الشرقية"),
    ("MT", "مرسى مطروح"),
    ("WAD", "الوادي الجديد"),
    ("SIN", "شمال سيناء"),
    ("JS", "جنوب سيناء"),
]

SIZES = ["50 مل", "100 مل"]

PAYMENT_METHODS = [
    ("cod", "الدفع عند الاستلام (COD)"),
    ("instapay", "مدفوع مقدمًا - إنستاباي (تم تأكيد استلام المبلغ)"),
]

ORDER_SOURCES = [
    ("instagram", "انستجرام"),
    ("facebook", "فيسبوك"),
    ("tiktok", "تيك توك"),
    ("whatsapp", "واتساب"),
]
