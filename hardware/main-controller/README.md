# AgriNode MC-1 — برد کنترلر اصلی (rev A)

برد مرکزی سیستم برای گلخانه، مرغداری، دامداری، پرورش ماهی و مزرعه/باغ.
معماری کلی در [`docs/02-architecture.md`](../../docs/02-architecture.md).

## فایل‌ها

| مسیر | توضیح |
|---|---|
| `design/main_controller.py` | **منبع اصلی طراحی** (مدار به صورت کد پایتون) |
| `build.py` | تولید شماتیک KiCad، بررسی نت‌لیست، BOM و PDF |
| `pcb.py` | تولید PCB (چیدمان، لایه‌ها، کلاس نت‌ها، زون‌ها)؛ `--route` مسیریابی با Freerouting |
| `kicad/` | پروژه‌ی KiCad (باز شود با KiCad 7 یا جدیدتر) |
| `outputs/agrinode_mc_schematic.pdf` | شماتیک PDF |
| `outputs/bom.csv` | لیست قطعات |
| `outputs/drc.rpt` | گزارش DRC |

```bash
python3 build.py         # شماتیک + نت‌لیست + BOM + PDF
python3 pcb.py --route   # PCB + مسیریابی خودکار (نیاز به Java 25 و freerouting.jar)
```

> شماتیک و PCB **از روی کد تولید می‌شوند**؛ برای تغییر مدار، `design/main_controller.py` را ویرایش و
> دوباره build کنید. بعد از شروع ویرایش دستی layout در KiCad، دیگر `pcb.py` را اجرا نکنید
> (برای همگام‌سازی از Update PCB from Schematic — F8 — استفاده کنید؛ مسیر UUIDها ثابت است).

## مشخصات

| مورد | مقدار |
|---|---|
| ابعاد | 240 × 180 mm، 4 لایه، 4 سوراخ M3 |
| تغذیه | 9-32V DC (نامی 24V) + ورودی باتری پشتیبان، diode-OR، فیوز PTC، TVS 33V |
| مصرف | حدود 1.5W بی‌بار؛ تا 6W با 8 رله روشن و مودم فعال |
| پردازنده | ESP32-S3 (240MHz دو هسته، 16MB Flash، 2MB PSRAM)، Wi-Fi 4 + BLE 5 |
| ارتباط | Ethernet 10/100، LoRa 433MHz، اسلات مودم 2G/4G، USB-C، 2× RS-485 |
| خروجی | 8 رله 10A/250VAC (NO/C/NC)، 4 MOSFET سمت پایین 2A با PWM، 2 آنالوگ 0-10V |
| ورودی | 8 دیجیتال ایزوله 10-32V AC/DC (DI1/DI2 شمارنده‌ی پالس)، 4 آنالوگ 16 بیت 0-10V/4-20mA |
| باس سنسور | 1-Wire (DS18B20)، I²C خارجی، RS-485 ایزوله (Modbus) |
| محلی | OLED I²C، 4 دکمه، 3 LED وضعیت، بازر، RTC با باتری، microSD |

## نقشه‌ی پایه‌های ESP32-S3

| GPIO | سیگنال | GPIO | سیگنال |
|---|---|---|---|
| 0 | BOOT / دکمه‌ی OK | 21 | OUT1 (PWM) |
| 1 | VIN_MAIN_SENSE (ADC، تشخیص قطع برق) | 35 | WDT_WAKE |
| 2 | VIN_BAT_SENSE (ADC) | 36 | MODEM_RI |
| 3 | OUT3 (PWM) | 37 | BUZZER |
| 4 / 5 | I²C SDA / SCL | 38 / 39 / 40 | RS485-A TX / RX / DE |
| 6 | EXP_INT (وقفه‌ی دو PCA9555) | 41 / 42 / 47 | RS485-B TX / RX / DE |
| 7 / 8 | DI1 / DI2 (شمارنده پالس PCNT) | 43 / 44 | MODEM TXD / RXD (UART0) |
| 9 / 10 / 11 | SPI SCK / MOSI / MISO | 45 | OUT4 (PWM، پایه‌ی Strap با pull-down) |
| 12 / 13 | ETH_CS / ETH_INT | 46 | LED STATUS (Strap) |
| 14 | WDT_DONE | 48 | OUT2 (PWM) |
| 15 / 16 | LORA_CS / LORA_DIO0 | 19 / 20 | USB D- / D+ (کنسول و پروگرام) |
| 17 | SD_CS | 18 | 1-Wire |

کنسول دیباگ از طریق USB-Serial-JTAG داخلی است (UART0 به مودم اختصاص دارد).

## آدرس‌های I²C

| آدرس | قطعه | کاربرد |
|---|---|---|
| 0x20 | PCA9555 #1 | IO0: رله 1..8 · IO1: ورودی دیجیتال 1..8 |
| 0x21 | PCA9555 #2 | IO0: ETH_RST, LORA_RST, MODEM_PWRKEY, MODEM_RST, LED_NET, LED_ALARM, SD_CD, MODEM_STATUS · IO1: BTN_UP/DOWN/BACK, RTC_INT, LORA_DIO1, SPARE 5..7 |
| 0x48 | ADS1115 | AI1..AI4 |
| 0x60 | MCP4728 | AO1, AO2 (کانال A/B) |
| 0x68 | DS3231M | RTC |
| 0x35 | ATECC608B-TNGTLS | عنصر امن (نسخه‌ی TNGTLS انتخاب شد تا با MCP4728 در 0x60 تداخل نکند) |
| 0x3C | OLED | نمایشگر |

## ترمینال‌ها (Phoenix MSTB 5.08mm)

| ترمینال | پایه‌ها |
|---|---|
| MAIN IN / BATTERY IN | + ، GND |
| RELAY 1..8 | NO ، COM ، NC |
| DI 1-4 / DI 5-8 | DI×4 ، COM (COM به + یا − منبع ورودی) |
| AI 1-2 / AI 3-4 | VSENS(24V تغذیه‌ی ترنسمیتر) ، AIx ، AIy ، GND |
| AO 1-2 | AO1 ، AO2 ، GND |
| OUT 1-2 / OUT 3-4 | VFIELD(+24V) ، OUTx ، OUTy (بار بین +24V و OUT) |
| RS485-A EXP BUS | +24V ، A ، B ، GND |
| RS485-B FIELD | A ، B ، GND_ISO |
| 1-WIRE | 3V3 ، DQ ، GND |
| I2C EXT | 3V3 ، SDA ، SCL ، GND |

## مواردی که پیش از سفارش ساخت باید بازبینی شوند

1. هنگام خرید، ATECC608B حتماً نسخه‌ی **TNGTLS** باشد (آدرس 0x35)؛ نسخه‌ی معمولی 0x60 با MCP4728 تداخل دارد.
2. مقادیر جبران‌ساز TPS54360 (R/C روی COMP) با WEBENCH یا محاسبات دیتاشیت تأیید شود.
3. مدار ترمینیشن W5500 با طرح مرجع WIZnet مطابقت داده شود.
4. مقاومت DELAY واچ‌داگ TPL5010 از جدول دیتاشیت برای زمان دلخواه انتخاب شود.
5. شکاف (slot) فرزکاری زیر رله‌ها برای افزایش فاصله‌ی خزشی 250VAC اضافه شود.
6. ERC کامل در KiCad 8/9 (نسخه‌ی 7 خط فرمان ERC ندارد؛ اتصالات با نت‌لیست خود KiCad تطبیق داده شده‌اند).
7. مسیریابی خودکار فقط نقطه‌ی شروع است: مسیرهای سوییچینگ بک‌ها، کریستال W5500 و جفت‌های
   دیفرانسیل USB/Ethernet باید دستی بازبینی و بهینه شوند.
