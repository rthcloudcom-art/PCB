# AgriNode — سخت‌افزار IoT برای مدیریت هوشمند کشاورزی و دامپروری

خانواده‌ای از بردهای الکترونیکی برای کنترل، مانیتورینگ و مدیریت **گلخانه، مرغداری، دامداری،
پرورش ماهی، مزرعه و باغ**.

| سند | محتوا |
|---|---|
| [`docs/01-features.md`](docs/01-features.md) | فاز ۱ — فهرست جامع قابلیت‌ها برای هر کاربری و ترجمه‌ی آن به نیازمندی سخت‌افزاری |
| [`docs/02-architecture.md`](docs/02-architecture.md) | فاز ۲ — معماری (نودها + هاب)، تغذیه، قوانین ساخت برای دستگاه کم‌دقت، اقدامات صنعتی |
| [`docs/03-roadmap.md`](docs/03-roadmap.md) | فاز ۳ — نقشه‌ی راه بردهای بعدی |
| [`hardware/hub/`](hardware/hub/README.md) | **HUB-1** — هاب/گیت‌وی واحد دو لایه (Wi-Fi / LoRa / سیم‌کارت / LAN) |
| [`hardware/lib/`](hardware/lib) | کتابخانه‌ی سمبل و فوت‌پرینت برای ساخت با دستگاه کم‌دقت (پدهای باریک‌شده، فاصله ≥ 0.55mm) |
| [`hardware/archive/mc1-4layer/`](hardware/archive/mc1-4layer/README.md) | نسخه‌ی قبلی (برد یکپارچه‌ی ۴ لایه، کنار گذاشته شد) |

## ساختار مخزن

```
docs/                      اسناد نیازمندی و معماری
hardware/<board>/
    design/*.py            منبع طراحی مدار (پایتون)
    build.py               تولید شماتیک KiCad + بررسی نت‌لیست + BOM + PDF
    pcb.py                 تولید PCB (چیدمان، زون‌ها، قوانین، مسیریابی خودکار)
    kicad/                 پروژه‌ی KiCad تولیدشده
    outputs/               PDF شماتیک، BOM، گزارش DRC، تصاویر
tools/kigen/               کتابخانه‌ی کوچک «مدار به صورت کد» برای تولید فایل‌های KiCad
```

## پیش‌نیازها

- KiCad 7 یا جدیدتر (کتابخانه‌های رسمی symbol و footprint)
- Python 3.10+ (ماژول `pcbnew` که همراه KiCad نصب می‌شود)
- برای مسیریابی خودکار: Java 25 و [Freerouting](https://github.com/freerouting/freerouting) 2.4+
  (`FREEROUTING_JAR` و `FREEROUTING_JAVA` را تنظیم کنید)
