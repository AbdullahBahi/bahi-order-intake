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

## رسالة تأكيد الطلب الأوتوماتيكية على واتساب

أول ما أي أوردر يتعمل (من المتجر أو من الفورم دي)، Shopify بيبعت إشعار للأداة على
`/webhooks/orders-create`، والأداة بتبعت للعميل رسالة واتساب عن طريق Meta WhatsApp
Cloud API:

- **إنستاباي ولسه متدفعش** → رسالة تأكيد + لينك الدفع (القالب `order_instapay_link`، أو `order_instapay_payment` القديم لحد ما
  `WA_TEMPLATE_INSTAPAY` يتغيّر في Render).
- **أي حاجة تانية** (الدفع عند الاستلام، أو إنستاباي متسجل Paid من الفورم) → رسالة
  تأكيد عادية (القالب `order_confirmation`).

بعد ما الرسالة تتبعت، الأوردر بياخد تاج `whatsapp-sent`، عشان العميل ميوصلوش نفس الرسالة
مرتين لو Shopify بعت الإشعار تاني. الأوردرات التجريبية (Test) مبيتبعتلهاش رسايل، إلا لو
ضفت `WHATSAPP_SEND_TEST_ORDERS=1` وانت بتجرب.

### 1) تجهيز WhatsApp Cloud API (مرة واحدة)

1. ادخل https://developers.facebook.com → **My Apps → Create App** → نوع **Business**،
   واربطه بحساب Meta Business بتاعك.
2. ضيف منتج **WhatsApp** للتطبيق، وضيف رقم تليفون للإرسال.
   رقم المتجر (01041464663) متربط بطريقة Coexistence، يعني شغال على تطبيق واتساب بيزنس
   والـ API في نفس الوقت. الرسايل بتطلع من رقم المتجر، وبتظهر على الموبايل، والعميل
   بيرد ويبعت الإيصال في نفس المحادثة.
   الربط ده اتعمل عن طريق **Pabbly Chatflow (الخطة المجانية)**، لأن Meta مش بتسمح
   بالـ Coexistence غير عن طريق شريك. **متفصلش الرقم من Pabbly**، لأن ده بيوقف الـ API.
   إرسال الرسايل نفسه بيتم من الكود ده بالـ Token بتاعنا، مش من Pabbly.
3. من **Business Settings → System Users** اعمل System User بصلاحية Admin، وطلّع له
   Token دائم بالصلاحيات `whatsapp_business_messaging` و`whatsapp_business_management`.
   ده هيبقى `WHATSAPP_TOKEN`.
4. من صفحة **WhatsApp → API Setup** خد الـ **Phone number ID**. ده هيبقى
   `WHATSAPP_PHONE_NUMBER_ID`.
5. ضيف وسيلة دفع في حساب Meta Business. Meta بتحاسب على كل رسالة.

### 2) قوالب الرسايل (لازم Meta توافق عليهم)

من **WhatsApp Manager → Message Templates → Create template**: النوع **Utility**، واللغة
**Arabic (ar)**. الاسم لازم يبقى بالظبط زي ما هو مكتوب تحت.

**`order_confirmation`**

```
أهلاً {{1}} 👋
شكراً لطلبك من باهي للعطور 🤍
تم استلام طلبك رقم {{2}} بإجمالي {{3}} جنيه شامل الشحن.
هنتواصل معاك أول ما الطلب يتشحن.
```

**`order_instapay_payment`**

```
أهلاً {{1}} 👋
شكراً لطلبك من باهي للعطور 🤍
تم استلام طلبك رقم {{2}} بإجمالي {{3}} جنيه شامل الشحن.

لتأكيد الطلب، حوّل المبلغ عن طريق إنستاباي على:
{{4}}

وبعد التحويل ابعت صورة الإيصال هنا في نفس المحادثة.

الطلب هيتأكد ويتجهز للشحن أول ما نستلم التحويل.
```

**`order_instapay_link`** (البديل للي فوق، بصياغة مناسبة للينك الدفع)

```
أهلاً {{1}} 👋
شكراً لطلبك من باهي للعطور 🤍
تم استلام طلبك رقم {{2}} بإجمالي {{3}} جنيه شامل الشحن.

لتأكيد الطلب، ادفع المبلغ عن طريق إنستاباي من اللينك ده:
{{4}}

وبعد الدفع ابعت صورة الإيصال هنا في نفس المحادثة.

الطلب هيتأكد ويتجهز للشحن أول ما نستلم المبلغ.
```

أول ما Meta توافق عليه، ضيف في Render `WA_TEMPLATE_INSTAPAY=order_instapay_link`.

بدل ما تعملهم يدويًا، تقدر تشغّل `python create_templates.py`. السكريبت بيقرا
`WHATSAPP_TOKEN` من ملف `.env` جنبه، وبيعمل القوالب ويبعتهم لـ Meta تراجعهم
(`python create_templates.py order_instapay_link` بيعمل قالب واحد بس بالاسم).
(`python create_templates.py --check` بيعرض حالة الحساب بس.)

قيم المتغيرات: `{{1}}` اسم العميل، `{{2}}` رقم الأوردر، `{{3}}` الإجمالي،
و`{{4}}` قيمة `INSTAPAY_ADDRESS`.
Meta هتطلب أمثلة للقيم دي وانت بتعمل القالب، حط مثلاً: `أحمد`، `#1012`، `1,250`،
`https://ipn.eg/S/abdullahbahi.bm/instapay/9leWro`.

لو حبيت تغيّر الكلام بعدين، لازم تبعت القالب لـ Meta تراجعه تاني. لكن لينك الدفع بتاع إنستاباي
بيتغير من Render بس، من غير مراجعة.

### 3) المتغيرات في Render (تبويب Environment)

| المتغير | القيمة |
|---|---|
| `WHATSAPP_TOKEN` | الـ Token الدائم من الخطوة 1 |
| `WHATSAPP_PHONE_NUMBER_ID` | الـ Phone number ID |
| `INSTAPAY_ADDRESS` | لينك الدفع على إنستاباي: `https://ipn.eg/S/abdullahbahi.bm/instapay/9leWro` (لو المتغير مش موجود، الأداة بتستخدم اللينك ده تلقائيًا) |

### 4) ربط Shopify بالأداة (مرة واحدة، بعد الـ Deploy)

من جهازك، وفي فولدر `order-intake`:

```
python register_webhook.py https://bahi-order-intake.onrender.com
```

(حط رابط الـ Service بتاعك بالظبط زي ما هو على Render.)

### 5) خلي السيرفر صاحي

لو الأداة نايمة (الخطة المجانية)، Shopify مش هيستنى أكتر من 5 ثواني. هيعيد المحاولة بعد
شوية، فالرسالة هتوصل بس متأخرة. عشان تتبعت فورًا، اعمل واحدة من دول:
- اعمل حساب مجاني على https://uptimerobot.com واعمل Monitor يفتح
  `https://<رابطك>/healthz` كل 5 دقايق، أو
- رقّي الـ Service لخطة مدفوعة.

### التجربة (واتساب)

1. ضيف `WHATSAPP_SEND_TEST_ORDERS=1` في Render.
2. اعمل أوردر Test من الفورم برقمك انت، مرة بالدفع عند الاستلام ومرة بإنستاباي.
3. لو الرسالة موصلتش، شوف **Logs** في Render (هتلاقي سطر `WhatsApp rejected ...` فيه
   سبب الرفض من Meta).
4. في الآخر شيل `WHATSAPP_SEND_TEST_ORDERS`.

## تتبّع أوردرات الرسايل في ميتا وتيك توك

أوردرات المتجر بتتبعت لميتا وتيك توك عن طريق تطبيقاتهم الرسمية على شوبيفاي. أما أوردرات
الفورم دي فمش بتعدّي على الـ checkout، فالـ Pixel مش بيشوفها. عشان كده، أول ما أوردر من
الفورم يوصل على `/webhooks/orders-create`، الأداة بتبعته لهم كـ Purchase من السيرفر
(الكود في `conversions.py`)، ومعاه رقم العميل وإيميله واسمه بعد التشفير، عشان المنصة تعرف
توصّله بالشخص اللي شاف الإعلان.

- بيتبعت بس الأوردرات اللي `sourceName` بتاعها `social_media_manual`، يعني أوردرات الفورم.
- لو Shopify بعت نفس الإشعار مرتين، الأوردر مش هيتحسب مرتين، لأن رقم الحدث مبني على رقم الأوردر.
- كل منصة بتشتغل بس لما المتغيرات بتاعتها تتحط في Render.

### المتغيرات

| المتغير | تجيبه منين |
|---|---|
| `META_PIXEL_ID` | Meta Events Manager → الـ Pixel → الرقم تحت اسمه |
| `META_CAPI_TOKEN` | نفس الـ Pixel → Settings → Conversions API → Generate access token |
| `TIKTOK_PIXEL_CODE` | TikTok Events Manager → Web Events → الـ Pixel → الكود اللي جنب اسمه |
| `TIKTOK_ACCESS_TOKEN` | نفس الـ Pixel → Settings → Events API → Generate Access Token |
| `TIKTOK_PURCHASE_EVENT` | اختياري. اسم حدث الشراء اللي تطبيق تيك توك على شوبيفاي بيبعته (الافتراضي `CompletePayment`، ولو التطبيق بيبعت `Purchase` حطها) |

### التجربة

1. من Test events في Events Manager، خد الـ Test code بتاع كل منصة، وحطه في Render في
   `META_TEST_EVENT_CODE` و`TIKTOK_TEST_EVENT_CODE`.
2. اعمل أوردر Test من الفورم. هيظهر في تبويب Test events بس، من غير ما يتحسب شراء حقيقي.
   (أوردرات الـ Test مبتتبعتش خالص لو الكود ده مش موجود.)
3. لو مظهرش، شوف **Logs** في Render (هتلاقي سطر `rejected Purchase` فيه السبب).
4. في الآخر شيل المتغيرين دول.
