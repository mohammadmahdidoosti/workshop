# داشبورد فرصت آنلاین واحدهای تولیدی

داشبورد تحلیلی لیست واحدهای شهرک‌های صنعتی (۴۸٬۰۴۹ واحد، داده حدود ۱۴۰۰): دسته‌بندی، امتیاز فروش مستقیم (D2C) و امتیاز پلتفرم B2B/سرنخ، خوشه‌های شهرکی و لیست تأمین‌کننده‌ها.

- فایل‌های سایت: `site/` (HTML ساده + d3، بدون build)
- داده‌ها **در مخزن نیستند** (شامل نام واحدها و شماره تماس). روی سرور در `/srv/smeanalysis-data` نگه داشته می‌شوند و در Coolify به `/usr/share/nginx/html/data` وصل (mount) می‌شوند.
- اجرا: Dockerfile با nginx و رمز ورود (Basic Auth)

## تنظیمات Coolify
- Build pack: Dockerfile، پورت 80
- متغیرهای محیطی: `BASIC_AUTH_USER` (پیش‌فرض caravan) و `BASIC_AUTH_PASSWORD` (خود صاحب پروژه وارد می‌کند)
- بدون رمز، کانتینر بالا نمی‌آید (عمداً)
- Health check: `/healthz`
- Persistent storage (bind mount): `/srv/smeanalysis-data` → `/usr/share/nginx/html/data`

## به‌روزرسانی داده
فایل‌های JSON را در `/srv/smeanalysis-data` روی سرور جایگزین کنید؛ نیازی به push یا Redeploy نیست.

## شکاف کاتالوگ کاروان صنعت (gaps.html)

اسکریپت `market/gaps.py` دسته‌های caravansanat.com را از API عمومی وردپرس می‌خواند (فقط خواندن، آهسته)، با محصولات کارگاه‌های داشبورد تطبیق می‌دهد و `DATA_DIR/gaps.json` را می‌سازد. صفحه‌ی `gaps.html` همین فایل را نشان می‌دهد.

اجرا داخل کانتینر (ترمینال Coolify):

    python3 /app/market/gaps.py            # حدود ۳-۴ دقیقه
    python3 /app/market/gaps.py --no-fetch # بدون خواندن دوباره‌ی دسته‌ها

نیازهای صنعتی کارگاه‌های مصرفی در `market/needs.json` تعریف شده‌اند.
