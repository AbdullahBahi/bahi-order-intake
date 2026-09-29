# أداة إدخال أوردرات السوشيال ميديا - باهي للعطور

فورم بسيط محمي بباسورد، بتحوّل بيانات طلب جاله على انستجرام/فيسبوك/تيك توك/واتساب
لأوردر حقيقي على المتجر مباشرة (بدون Draft، وبدون المرور بالـ checkout).

- المنتجات والمقاسات وأسعار الشحن بتتسحب لايف من Shopify في كل مرة تفتح فيها الفورم.
- طريقة الدفع "الدفع عند الاستلام" → الأوردر بيتسجل كـ **Pending**.
- طريقة الدفع "إنستاباي" → الأوردر بيتسجل كـ **Paid** (تستخدمها بعد ما تتأكد من إيصال
  الدفع على واتساب).

## التشغيل محليًا (اختبار على جهازك)

```
pip install -r requirements.txt
set SHOPIFY_AI_CLIENT_ID=...
set SHOPIFY_AI_PASS=...
set TOOL_PASSWORD=اختار-باسورد-قوي
python app.py
```

افتح http://127.0.0.1:5000

## النشر على Render (عشان تفتحها من الموبايل من أي مكان)

1. اعمل حساب مجاني على https://render.com (ينفع تسجل بالـ GitHub مباشرة).
2. ارفع الفولدر ده (`order-intake`) كـ repo على GitHub (شرح تحت).
3. في Render: **New → Web Service** → اختار الـ repo.
   - Render هيقرأ `render.yaml` تلقائيًا (Build: `pip install -r requirements.txt`،
     Start: `gunicorn app:app`).
4. في تبويب **Environment** بتاع الـ Service، ضيف المتغيرات دي (القيم بس، من غير
   علامات اقتباس):
   - `SHOPIFY_AI_CLIENT_ID` — نفس القيمة المستخدمة في باقي سكريبتات shopify/
   - `SHOPIFY_AI_PASS` — نفس القيمة
   - `TOOL_PASSWORD` — باسورد تختاره انت بس (ده اللي هيطلب منك تدخله كل ما تفتح
     الرابط من المتصفح — HTTP Basic Auth، Username تسيبه فاضي)
5. اضغط **Deploy**. Render هيديك رابط زي:
   `https://bahi-order-intake.onrender.com`
   — افتحه من الموبايل أو الكمبيوتر، هيطلب الباسورد، وبعدين تقدر تستخدم الفورم.

**ملاحظة:** الخطة المجانية في Render بتـ"تنام" لو محدش استخدم الرابط لمدة، وأول
فتح بعد النوم بياخد حوالي 30-50 ثانية لحد ما يصحى. لو ده مزعج، ترقية لخطة مدفوعة
صغيرة ($7/شهر تقريبًا) بتخليه شغال طول الوقت.

## رفع الفولدر على GitHub (لو أول مرة)

```
cd order-intake
git init
git add .
git commit -m "Order intake tool"
```

بعدين اعمل repo جديد فاضي على github.com (بدون README)، وهيديك أوامر زي:

```
git remote add origin https://github.com/<username>/bahi-order-intake.git
git branch -M main
git push -u origin main
```

**مهم:** ملف `.gitignore` مظبوط بحيث محدش من الأسرار (التوكينات) بيترفع مع
الكود — دول بتتحطوا بس في Environment Variables في Render، مش في الملفات.
