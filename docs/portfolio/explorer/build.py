#!/usr/bin/env python3
"""ساخت فایل تک‌صفحه‌ای v2-explorer.html از template.html + data.js + app.js + فونت وزیرمتن.

اجرا:  python3 docs/portfolio/explorer/build.py
خروجی: docs/portfolio/v2-explorer.html (کاملاً مستقل، بدون نیاز به اینترنت)
"""
import base64
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE.parent / 'v2-explorer.html'

# زیرمجموعه‌های فونت Vazirmatn (مجوز SIL OFL 1.1) — همان تقسیم‌بندی Google Fonts
FONTS = [
    ('Dxxo8j6PP2D_kU2muijlGMWWMmk.woff2',
     'U+0600-06FF, U+0750-077F, U+0870-088E, U+0890-0891, U+0897-08E1, U+08E3-08FF, '
     'U+200C-200E, U+2010-2011, U+204F, U+2E41, U+FB50-FDFF, U+FE70-FE74, U+FE76-FEFC'),
    ('Dxxo8j6PP2D_kU2muijlE8WWMmk.woff2',
     'U+0100-02BA, U+02BD-02C5, U+02C7-02CC, U+02CE-02D7, U+02DD-02FF, U+0304, U+0308, '
     'U+0329, U+1D00-1DBF, U+1E00-1E9F, U+1EF2-1EFF, U+2020, U+20A0-20AB, U+20AD-20C0, '
     'U+2113, U+2C60-2C7F, U+A720-A7FF'),
    ('Dxxo8j6PP2D_kU2muijlHcWW.woff2',
     'U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304, '
     'U+0308, U+0329, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, '
     'U+FEFF, U+FFFD'),
]


def font_css():
    rules = []
    for name, rng in FONTS:
        b64 = base64.b64encode((HERE / 'fonts' / name).read_bytes()).decode()
        rules.append(
            "@font-face{font-family:'Vazirmatn';font-style:normal;font-weight:300 900;"
            f"font-display:swap;src:url(data:font/woff2;base64,{b64}) format('woff2');"
            f"unicode-range:{rng};}}")
    return '\n'.join(rules)


def main():
    html = (HERE / 'template.html').read_text(encoding='utf-8')
    for key, val in (('/*@FONTS@*/', font_css()),
                     ('/*@DATA@*/', (HERE / 'data.js').read_text(encoding='utf-8')),
                     ('/*@APP@*/', (HERE / 'app.js').read_text(encoding='utf-8'))):
        assert html.count(key) == 1, key
        html = html.replace(key, val)
    assert '</script' not in (HERE / 'data.js').read_text() + (HERE / 'app.js').read_text()
    OUT.write_text(html, encoding='utf-8')
    print(f'{OUT}  ({OUT.stat().st_size / 1024:.0f} KB)')


if __name__ == '__main__':
    main()
