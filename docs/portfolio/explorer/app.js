/* رابط گرافیکی سبد محصولات اگری‌نود — منطق صفحه */
'use strict';

const $ = (s, r = document) => r.querySelector(s);
const esc = (t) => String(t).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const fa = (n) => String(n).replace(/\d/g, (d) => '۰۱۲۳۴۵۶۷۸۹'[d]);
const IND = Object.fromEntries(INDUSTRIES.map((i) => [i.id, i]));
const W = 1000, H = 640;

/* ------------------------------------------------------------------ نقاشی پس‌زمینه‌ی سالن‌ها */
function room(x, y, w, h, title, cls = 'room') {
  return `<rect class="${cls}" x="${x}" y="${y}" width="${w}" height="${h}" rx="14"/>` +
    (title ? `<text class="roomtitle" x="${x + w - 12}" y="${y + 22}" text-anchor="end">${esc(title)}</text>` : '');
}
function control(y1 = 200, y2 = 630, x = 12, w = 166) { return room(x, y1, w, y2 - y1, 'اتاق کنترل و تابلو برق', 'room ctrlroom'); }
function rows(x1, x2, y1, y2, step, cls = 'croprow') {
  let s = '';
  for (let y = y1; y <= y2; y += step) s += `<line class="${cls}" x1="${x1}" x2="${x2}" y1="${y}" y2="${y}"/>`;
  return s;
}
function dots(x1, x2, y1, y2, n, cls, r = 3, seed = 7) {
  let s = '', a = seed;
  for (let i = 0; i < n; i++) {
    a = (a * 9301 + 49297) % 233280; const x = x1 + (a / 233280) * (x2 - x1);
    a = (a * 9301 + 49297) % 233280; const y = y1 + (a / 233280) * (y2 - y1);
    s += `<circle class="${cls}" cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${r}"/>`;
  }
  return s;
}
const SCENES = {
  greenhouse() {
    let s = control(250, 632) + room(200, 140, 770, 490, 'سالن گلخانه', 'room glass');
    for (let x = 200; x <= 970; x += 70) s += `<path class="arch" d="M${x} 140 q35 -34 70 0"/>`;
    for (let x = 270; x < 970; x += 70) s += `<line class="bay" x1="${x}" x2="${x}" y1="140" y2="630"/>`;
    s += rows(230, 950, 380, 600, 26, 'plantrow') + dots(230, 950, 385, 600, 70, 'leaf', 4);
    s += `<text class="outside" x="985" y="60" text-anchor="end">بیرون گلخانه</text>`;
    return s;
  },
  hydro() {
    let s = control(250, 632) + room(200, 140, 770, 330, 'سالن کشت عمودی') + room(200, 490, 770, 140, 'اتاق محلول غذایی');
    for (let x = 250; x < 860; x += 150) {
      s += `<rect class="rack" x="${x}" y="230" width="110" height="220" rx="6"/>`;
      for (let y = 250; y < 450; y += 36) s += `<line class="shelf" x1="${x + 6}" x2="${x + 104}" y1="${y}" y2="${y}"/><line class="ledstrip" x1="${x + 10}" x2="${x + 100}" y1="${y + 6}" y2="${y + 6}"/>`;
    }
    return s;
  },
  mushroom() {
    let s = control(200, 632) + room(220, 140, 245, 240, 'اتاق پرورش ۱', 'room dark') + room(475, 140, 245, 240, 'اتاق پرورش ۲', 'room dark') +
      room(730, 140, 240, 190, 'تونل پاستوریزه', 'room warm') + room(200, 390, 770, 44, '', 'room corridor') +
      room(220, 450, 500, 180, 'سالن بسته‌بندی') + room(730, 450, 240, 180, 'موتورخانه');
    s += `<text class="roomtitle" x="960" y="418" text-anchor="end">راهرو</text>`;
    for (const x0 of [230, 485]) for (let y = 230; y < 375; y += 22) s += `<line class="bedline" x1="${x0}" x2="${x0 + 225}" y1="${y}" y2="${y}"/>`;
    s += rows(745, 955, 250, 320, 14, 'compostline');
    return s;
  },
  poultry() {
    let s = control(200, 632) + room(190, 150, 780, 430, 'سالن مرغداری') + `<rect class="padwall" x="194" y="160" width="16" height="410" rx="4"/>`;
    s += rows(230, 950, 280, 500, 110, 'feedline') + dots(230, 950, 225, 560, 150, 'bird', 3.2, 11);
    for (let y = 230; y < 560; y += 60) s += `<circle class="fanwall" cx="955" cy="${y}" r="13"/>`;
    s += `<circle class="silo" cx="930" cy="95" r="34"/><text class="outside" x="880" y="60" text-anchor="end">بیرون سالن</text>`;
    return s;
  },
  hatchery() {
    let s = control(200, 632) + room(190, 140, 780, 490, 'سالن جوجه‌کشی');
    [['ستر ۱', 230], ['ستر ۲', 440], ['هچر', 650]].forEach(([t, x]) => {
      s += `<rect class="machine" x="${x}" y="170" width="190" height="210" rx="10"/><text class="roomtitle" x="${x + 180}" y="370" text-anchor="end">${t}</text>`;
      for (let y = 230; y < 360; y += 18) s += `<line class="tray" x1="${x + 12}" x2="${x + 178}" y1="${y}" y2="${y}"/>`;
    });
    return s;
  },
  dairy() {
    let s = control(200, 632) + room(190, 140, 560, 490, 'سالن نگهداری دام') + room(760, 140, 210, 240, 'شیرخانه') + room(760, 390, 210, 240, 'آبشخور و باسکول', 'room open');
    for (let x = 220; x < 740; x += 26) s += `<line class="stall" x1="${x}" x2="${x}" y1="250" y2="300"/>`;
    s += dots(220, 730, 320, 520, 26, 'cow', 7, 5);
    return s;
  },
  aqua() {
    let s = room(12, 180, 166, 452, 'پمپ‌خانه', 'room ctrlroom');
    [[230, 140], [600, 140], [230, 400], [600, 400]].forEach(([x, y], i) => {
      s += `<rect class="pond" x="${x}" y="${y}" width="340" height="215" rx="40"/><text class="pondtitle" x="${x + 320}" y="${y + 28}" text-anchor="end">استخر ${fa(i + 1)}</text>`;
      s += `<path class="ripple" d="M${x + 60} ${y + 150} q20 -10 40 0 t40 0 t40 0 t40 0"/>`;
    });
    return s;
  },
  field() {
    let s = room(12, 100, 166, 150, 'ساختمان مزرعه', 'room ctrlroom') + room(12, 410, 166, 222, 'پمپ‌خانه', 'room ctrlroom');
    [[230, 110], [600, 110], [230, 380], [600, 380]].forEach(([x, y], i) => {
      s += `<rect class="field" x="${x}" y="${y}" width="340" height="215" rx="10"/><text class="pondtitle" x="${x + 320}" y="${y + 26}" text-anchor="end">زون ${fa(i + 1)}</text>`;
      for (let k = y + 40; k < y + 210; k += 16) s += `<line class="furrow" x1="${x + 12}" x2="${x + 328}" y1="${k}" y2="${k}"/>`;
    });
    s += `<text class="outside" x="140" y="300" text-anchor="middle">چند کیلومتر فاصله</text><line class="distance" x1="95" x2="95" y1="255" y2="405"/>`;
    return s;
  },
  orchard() {
    let s = room(12, 100, 166, 140, 'ساختمان باغ', 'room ctrlroom') + room(12, 430, 166, 202, 'پمپ‌خانه', 'room ctrlroom');
    for (let x = 250; x < 960; x += 70) for (let y = 130; y < 620; y += 70) s += `<circle class="tree" cx="${x}" cy="${y}" r="20"/><circle class="fruit" cx="${x + 7}" cy="${y - 5}" r="3.5"/>`;
    return s;
  },
  well() {
    let s = room(20, 250, 280, 382, 'پمپ‌خانه', 'room ctrlroom');
    s += `<circle class="wellring" cx="400" cy="470" r="44"/><path class="pipe" d="M400 470 L620 400 L860 220"/><rect class="tankbox" x="810" y="150" width="100" height="80" rx="10"/>`;
    s += `<path class="hill" d="M680 330 Q860 60 1000 250 L1000 330 Z"/><text class="outside" x="980" y="360" text-anchor="end">تپه‌ی مخزن</text>`;
    return s;
  },
  cold() {
    let s = control(200, 632) + room(200, 140, 250, 270, 'اتاق سرد ۱', 'room cold') + room(460, 140, 250, 270, 'اتاق سرد ۲', 'room cold') +
      room(720, 140, 250, 270, 'اتاق ۳ (اتمسفر کنترل‌شده)', 'room cold') + room(200, 420, 770, 212, 'راهرو و موتورخانه');
    s += dots(210, 960, 150, 400, 40, 'snow', 2.5, 3);
    return s;
  },
  dryer() {
    let s = control(200, 632) + room(200, 140, 385, 330, 'خشک‌کن ۱', 'room warm') + room(595, 140, 375, 330, 'خشک‌کن ۲', 'room warm') + room(200, 480, 770, 152, 'سالن ورود محصول');
    for (const x0 of [230, 620]) for (let y = 260; y < 460; y += 24) s += `<line class="tray" x1="${x0}" x2="${x0 + 150}" y1="${y}" y2="${y}"/>`;
    return s;
  },
  silo() {
    let s = control(200, 632);
    [330, 560, 790].forEach((x, i) => { s += `<circle class="siloBig" cx="${x}" cy="300" r="100"/><text class="pondtitle" x="${x}" y="220" text-anchor="middle">سیلوی ${fa(i + 1)}</text>`; });
    s += room(200, 470, 770, 162, 'انبار غلات');
    return s;
  },
  bee() {
    let s = room(12, 360, 166, 200, 'اتاقک هاب', 'room ctrlroom') + room(12, 100, 166, 110, 'دفتر زنبوردار', 'room ctrlroom');
    s += dots(220, 980, 110, 630, 90, 'flower', 3, 21);
    [[250, 150], [610, 150], [250, 370], [610, 370]].forEach(([x, y]) => { for (let k = 0; k < 5; k++) s += `<rect class="hive" x="${x + k * 30}" y="${y + 70}" width="22" height="26" rx="3"/>`; });
    s += `<text class="outside" x="140" y="300" text-anchor="middle">چند کیلومتر فاصله</text><line class="distance" x1="95" x2="95" y1="215" y2="355"/>`;
    return s;
  },
  compost() {
    let s = control(200, 632) + room(200, 140, 530, 492, 'محوطه‌ی توده‌ها', 'room open') + room(740, 140, 230, 492, 'هاضم بیوگاز');
    [200, 320, 440].forEach((y) => { s += `<path class="windrow" d="M225 ${y + 30} Q465 ${y - 30} 705 ${y + 30} Z"/>`; });
    s += `<circle class="digester" cx="840" cy="280" r="80"/>`;
    return s;
  },
};

/* ------------------------------------------------------------------ اجزای مشترک SVG */
function chipW(label, sub = '') { return Math.max(118, Math.min(230, Math.max(label.length * 6.6, sub.length * 5.6) + 54)); }
function modelOf(inst) { const b = BOARDS[inst.board]; return b.models.find((x) => x.code === inst.model) || b.models[0]; }
function linkPath(a, b, bend = 0.18) {
  const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2, dx = b.x - a.x, dy = b.y - a.y;
  const cx = mx - dy * bend, cy = my + dx * bend;
  return `M${a.x.toFixed(1)} ${a.y.toFixed(1)} Q${cx.toFixed(1)} ${cy.toFixed(1)} ${b.x.toFixed(1)} ${b.y.toFixed(1)}`;
}
function linkSvg(d, kind, owner, extra = '') {
  const L = LINKS[kind];
  return `<g class="link k-${kind}" data-owner="${owner}" ${extra}>` +
    `<path class="lbase" d="${d}" stroke="${L.color}" ${L.dash ? `stroke-dasharray="${L.dash}"` : ''}/>` +
    `<path class="lflow" d="${d}" stroke="${L.color}"/></g>`;
}
function cloudSvg(x, y, mini) {
  return `<g class="cloud" transform="translate(${x} ${y})"><path d="M-46 14 a20 20 0 0 1 6 -38 a26 26 0 0 1 48 -6 a18 18 0 0 1 32 12 a16 16 0 0 1 4 32 z"/>` +
    (mini ? '' : `<text y="6" text-anchor="middle">سرور و اپلیکیشن</text>`) + `</g>`;
}
function chipSvg(inst, opts = {}) {
  const b = BOARDS[inst.board], mn = modelOf(inst).chip || modelOf(inst).name, w = chipW(inst.label, mn), h = 42;
  return `<g class="chip b-${inst.board}" data-inst="${inst.id}" tabindex="0" role="button" aria-label="${esc(inst.label)}" transform="translate(${inst.x} ${inst.y})" style="--c:${b.color}">` +
    `<rect class="chipglow" x="${-w / 2 - 6}" y="${-h / 2 - 6}" width="${w + 12}" height="${h + 12}" rx="14"/>` +
    `<rect class="chipbody" x="${-w / 2}" y="${-h / 2}" width="${w}" height="${h}" rx="10"/>` +
    `<circle class="led" cx="${-w / 2 + 11}" cy="${-h / 2 + 10}" r="3.5" style="animation-delay:${(inst.x % 7) / 5}s"/>` +
    `<text class="chipicon" x="${w / 2 - 17}" y="7" text-anchor="middle">${b.icon}</text>` +
    `<text class="chiplabel" x="${w / 2 - 33}" y="-3" text-anchor="end">${esc(inst.label)}</text>` +
    `<text class="chipcode" x="${w / 2 - 33}" y="13" text-anchor="end">${esc(mn)}</text>` +
    `</g>`;
}
function equipSvg(e, mini) {
  return `<g class="equip" data-eq="${e.id}" transform="translate(${e.x} ${e.y})"><title>${esc(e.label)}</title>` +
    `<circle class="eqring" r="21"/><circle class="eqbg" r="17"/>` +
    `<text class="eqemo${e.spin ? ' spin' : ''}" y="6" text-anchor="middle">${e.emoji}</text>` +
    (mini ? '' : `<text class="eqlabel" y="34" text-anchor="middle">${esc(e.label)}</text>`) + `</g>`;
}

/* ------------------------------------------------------------------ نمای سالن */
function sceneSvg(ind, opts = {}) {
  const pos = { cloud: { x: 70, y: 48 } };
  ind.instances.forEach((i) => (pos[i.id] = i));
  let links = '';
  ind.instances.forEach((i) => { links += linkSvg(linkPath(i, pos[i.to]), i.link, i.id); });
  const eq = ind.equipment.map((e) => equipSvg(e, opts.mini)).join('');
  const chips = ind.instances.map((i) => chipSvg(i)).join('');
  const cls = opts.focusBoard ? ` focus-board focus-${opts.focusBoard}` : '';
  return `<svg class="scene${opts.mini ? ' mini' : ''}${cls}" viewBox="0 0 ${W} ${H}" role="img" aria-label="نمای ${esc(ind.name)}">` +
    `<defs><linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="var(--sky1)"/><stop offset="1" stop-color="var(--sky2)"/></linearGradient></defs>` +
    `<rect class="ground" x="0" y="0" width="${W}" height="${H}" rx="18"/>` +
    `<g class="bgart">${SCENES[ind.scene]()}</g>` + cloudSvg(70, 48, opts.mini) +
    `<g class="links">${links}</g><g class="equips">${eq}</g><g class="chips">${chips}</g></svg>`;
}

/* ------------------------------------------------------------------ نقشه‌ی اتصال (درختی) */
function topologySvg(ind, fit = false) {
  const kids = { cloud: [] };
  ind.instances.forEach((i) => (kids[i.id] = []));
  ind.instances.forEach((i) => kids[i.to].push(i));
  const NW = 190, NH = 64, GX = 22, GY = 118;
  const place = {}; let leaf = 0, maxD = 0;
  (function walk(id, d) {
    maxD = Math.max(maxD, d);
    const ch = kids[id];
    if (!ch.length) { place[id] = { x: leaf++ * (NW + GX), d }; return; }
    ch.forEach((c) => walk(c.id, d + 1));
    const xs = ch.map((c) => place[c.id].x);
    place[id] = { x: (Math.min(...xs) + Math.max(...xs)) / 2, d };
  })('cloud', 0);
  const width = Math.max(leaf * (NW + GX), 600) + 40, height = (maxD + 1) * GY + 60;
  const P = (id) => ({ x: width - 20 - NW / 2 - place[id].x, y: 50 + place[id].d * GY });
  let s = '';
  ind.instances.forEach((i) => {
    const a = P(i.id), b = P(i.to);
    const d = `M${a.x} ${a.y - NH / 2} C${a.x} ${a.y - GY / 2} ${b.x} ${b.y + GY / 2} ${b.x} ${b.y + NH / 2}`;
    s += linkSvg(d, i.link, i.id);
    s += `<text class="tlinklabel" x="${a.x}" y="${a.y - NH / 2 - 9}" text-anchor="middle">${esc(LINKS[i.link].name)}</text>`;
  });
  const c = P('cloud');
  s += `<g class="tnode cloudnode" transform="translate(${c.x} ${c.y})"><rect x="${-NW / 2}" y="${-NH / 2}" width="${NW}" height="${NH}" rx="16"/><text y="-2" text-anchor="middle">☁️ سرور، داشبورد و</text><text y="18" text-anchor="middle">اپلیکیشن موبایل</text></g>`;
  ind.instances.forEach((i) => {
    const p = P(i.id), b = BOARDS[i.board];
    const eqs = i.controls.map((id) => ind.equipment.find((e) => e.id === id)).filter(Boolean);
    s += `<g class="tnode chip b-${i.board}" data-inst="${i.id}" tabindex="0" role="button" transform="translate(${p.x} ${p.y})" style="--c:${b.color}">` +
      `<rect class="chipbody" x="${-NW / 2}" y="${-NH / 2}" width="${NW}" height="${NH}" rx="14"/>` +
      `<circle class="led" cx="${-NW / 2 + 12}" cy="${-NH / 2 + 12}" r="4"/>` +
      `<text class="chipicon" x="${NW / 2 - 20}" y="-6" text-anchor="middle">${b.icon}</text>` +
      `<text class="chiplabel" x="${NW / 2 - 38}" y="-8" text-anchor="end">${esc(i.label)}</text>` +
      `<text class="chipcode" x="${NW / 2 - 38}" y="10" text-anchor="end">${esc(modelOf(i).chip || modelOf(i).name)}</text>` +
      (eqs.length ? `<text class="tequip" x="0" y="26" text-anchor="middle">${eqs.map((e) => e.emoji).join(' ')}</text>` : '') + `</g>`;
  });
  return `<svg class="topo" viewBox="0 0 ${width} ${height}" ${fit ? '' : `style="min-width:${Math.round(Math.min(width, 1600) * 0.7)}px"`}>${s}</svg>`;
}

/* ------------------------------------------------------------------ تصویر برد */
function boardArt(type) {
  const b = BOARDS[type];
  const leds = (arr) => arr.map(([x, y, c, d]) => `<circle class="pled" cx="${x}" cy="${y}" r="4" fill="${c}" style="animation-delay:${d}s"/>`).join('');
  const term = (x, y, n, big) => { let s = ''; for (let i = 0; i < n; i++) s += `<rect class="term" x="${x + i * (big ? 22 : 15)}" y="${y}" width="${big ? 20 : 13}" height="${big ? 20 : 15}" rx="2"/><circle class="screw" cx="${x + i * (big ? 22 : 15) + (big ? 10 : 6.5)}" cy="${y + (big ? 10 : 7.5)}" r="${big ? 5 : 3.5}"/>`; return s; };
  const chip = (x, y, w, h, t) => `<rect class="ic" x="${x}" y="${y}" width="${w}" height="${h}" rx="2"/>` + (t ? `<text class="ictext" x="${x + w / 2}" y="${y + h / 2 + 3}" text-anchor="middle">${t}</text>` : '');
  const esp = (x, y) => `<rect class="espmod" x="${x}" y="${y}" width="70" height="52" rx="3"/><path class="antenna" d="M${x + 8} ${y + 8} h12 v10 h10 v-10 h10 v10 h10 v-10 h10"/><rect class="shield" x="${x + 6}" y="${y + 22}" width="58" height="26" rx="2"/><text class="ictext" x="${x + 35}" y="${y + 39}" text-anchor="middle">ای‌اس‌پی ۳۲</text>`;
  let s = '', w = 420, h = 260;
  if (type === 'hub') {
    s = esp(170, 12) + `<rect class="batt" x="30" y="190" width="250" height="44" rx="8"/><text class="silk" x="155" y="217" text-anchor="middle">باتری ۱۸۶۵۰</text>` +
      `<rect class="usb" x="360" y="30" width="44" height="48" rx="4"/>` + term(20, 30, 2, true) + term(20, 90, 2, true) + term(20, 130, 2, true) +
      chip(230, 110, 40, 24, 'ساعت') + chip(300, 110, 50, 24, 'مبدل') + `<rect class="lora" x="310" y="160" width="80" height="70" rx="4"/><text class="silk" x="350" y="200" text-anchor="middle">لورا / نسل ۴</text>` +
      `<circle class="coin" cx="120" cy="120" r="24"/>` + leds([[150, 90, '#22c55e', 0], [165, 90, '#38bdf8', .4], [180, 90, '#f59e0b', .8]]);
  } else if (type === 'ctrl') {
    s = esp(175, 90) + term(20, 14, 18) + term(20, 222, 18) + `<rect class="rj" x="340" y="80" width="54" height="44" rx="4"/><rect class="rj" x="340" y="132" width="54" height="44" rx="4"/>` +
      `<rect class="sd" x="30" y="100" width="70" height="46" rx="4"/><text class="silk" x="65" y="128" text-anchor="middle">کارت حافظه</text>` +
      chip(110, 60, 44, 24, 'آنالوگ') + chip(110, 150, 44, 24, 'آنالوگ') + chip(260, 60, 60, 22, 'ایزوله') + chip(260, 160, 40, 22, 'حافظه') + chip(115, 100, 36, 30, 'پردازنده') +
      `<rect class="batt" x="20" y="160" width="80" height="40" rx="6"/>` + leds([[260, 196, '#22c55e', 0], [275, 196, '#22c55e', .3], [290, 196, '#f59e0b', .6], [305, 196, '#38bdf8', .9], [320, 196, '#22c55e', 1.2]]);
  } else if (type === 'pwr') {
    let r = '';
    for (let i = 0; i < 8; i++) r += `<rect class="relay" x="${24 + i * 48}" y="60" width="40" height="62" rx="4"/><text class="relaytext" x="${44 + i * 48}" y="95" text-anchor="middle">۱۶ آمپر</text><rect class="toggle" x="${34 + i * 48}" y="132" width="20" height="12" rx="3"/><rect class="lever" x="${41 + i * 48}" y="124" width="6" height="12" rx="2" style="animation-delay:${i * .3}s"/>`;
    s = r + term(20, 214, 16, true).replace(/term"/g, 'term hv"') + `<line class="slot" x1="10" x2="410" y1="160" y2="160"/>` +
      `<rect class="psu" x="300" y="166" width="100" height="40" rx="4"/><text class="silk" x="350" y="191" text-anchor="middle">منبع ۲۴ ولت</text>` +
      `<rect class="xfmr" x="30" y="170" width="32" height="34" rx="3"/><rect class="xfmr" x="70" y="170" width="32" height="34" rx="3"/><rect class="xfmr" x="110" y="170" width="32" height="34" rx="3"/>` +
      `<rect class="rj" x="170" y="10" width="46" height="36" rx="4"/><rect class="rj" x="224" y="10" width="46" height="36" rx="4"/>` + chip(290, 16, 50, 24, 'پردازنده') + chip(160, 172, 50, 26, 'مقایسه') +
      leds([[34, 50, '#f59e0b', 0], [82, 50, '#f59e0b', .25], [130, 50, '#f59e0b', .5], [178, 50, '#f59e0b', .75], [226, 50, '#f59e0b', 1], [274, 50, '#f59e0b', 1.25], [322, 50, '#f59e0b', 1.5], [370, 50, '#f59e0b', 1.75]]);
  } else if (type === 'node') {
    w = 320; h = 220;
    s = esp(120, 12) + `<rect class="batt" x="20" y="150" width="200" height="50" rx="10"/><text class="silk" x="120" y="180" text-anchor="middle">باتری ۱۸۶۵۰</text>` +
      `<rect class="lora" x="230" y="100" width="72" height="60" rx="4"/><text class="silk" x="266" y="134" text-anchor="middle">لورا</text>` +
      term(20, 20, 3) + term(20, 60, 3) + term(20, 100, 3) + `<rect class="solar" x="240" y="170" width="60" height="36" rx="4"/><text class="silk" x="270" y="193" text-anchor="middle">☀️</text>` +
      `<line class="whip" x1="300" y1="100" x2="300" y2="20"/><circle class="wave" cx="300" cy="20" r="8"/>` + leds([[210, 80, '#a78bfa', 0], [225, 80, '#22c55e', .7]]);
  } else if (type === 'probe') {
    w = 260; h = 170;
    s = `<rect class="sensor" x="120" y="20" width="110" height="80" rx="8"/>` + Array.from({ length: 12 }, (_, i) => `<circle class="vent" cx="${138 + (i % 6) * 15}" cy="${42 + Math.floor(i / 6) * 24}" r="4"/>`).join('') +
      chip(30, 30, 50, 26, 'پردازنده') + chip(30, 70, 50, 22, 'ارتباط') + term(20, 120, 4, true) + `<rect class="fanbox" x="140" y="112" width="46" height="46" rx="6"/><text class="silk spin" x="163" y="142" text-anchor="middle">🌀</text>` + leds([[210, 125, '#f472b6', 0]]);
  } else {
    w = 360; h = 230;
    s = `<rect class="bezel" x="10" y="10" width="340" height="210" rx="16"/><rect class="screen" x="26" y="24" width="308" height="182" rx="6"/>` +
      `<text class="scrtext" x="318" y="48" text-anchor="end">سالن ۱ · روز ۱۲</text>` +
      [0, 1, 2, 3].map((i) => `<rect class="scrbar" x="${60 + i * 64}" y="${190 - 40 - i * 18}" width="40" height="${40 + i * 18}" rx="4" style="animation-delay:${i * .3}s"/>`).join('') +
      `<circle class="scrdot" cx="46" cy="44" r="6"/>`;
    return `<svg class="boardart" viewBox="0 0 ${w} ${h}" style="--c:${b.color}">${s}</svg>`;
  }
  return `<svg class="boardart" viewBox="0 0 ${w} ${h}" style="--c:${b.color}"><rect class="pcb" x="2" y="2" width="${w - 4}" height="${h - 4}" rx="14"/>` +
    `<circle class="hole" cx="14" cy="14" r="6"/><circle class="hole" cx="${w - 14}" cy="14" r="6"/><circle class="hole" cx="14" cy="${h - 14}" r="6"/><circle class="hole" cx="${w - 14}" cy="${h - 14}" r="6"/>` +
    s + `<text class="silk brand" x="${w - 26}" y="${h - 10}" text-anchor="end">اگری‌نود</text></svg>`;
}

/* ------------------------------------------------------------------ پنل جزئیات */
function openPanel(html) {
  const p = $('#panel');
  $('#panelBody').innerHTML = html;
  p.classList.add('open'); p.setAttribute('aria-hidden', 'false');
  $('#panelBody').scrollTop = 0;
}
function closePanel() {
  const p = $('#panel'); p.classList.remove('open'); p.setAttribute('aria-hidden', 'true');
  document.querySelectorAll('.scene.has-sel, .topo.has-sel').forEach((s) => s.classList.remove('has-sel'));
  document.querySelectorAll('.sel, .hl').forEach((e) => e.classList.remove('sel', 'hl'));
}
function featureHtml(b, open) {
  return b.features.map((g, i) => `<details class="feat" ${open || i === 0 ? 'open' : ''}><summary>${esc(g.title)}<span class="cnt">${fa(g.items.length)} مورد</span></summary><ul>${g.items.map((t) => `<li>${esc(t)}</li>`).join('')}</ul></details>`).join('');
}
function instancePanel(ind, inst) {
  const b = BOARDS[inst.board], m = b.models.find((x) => x.code === inst.model) || b.models[0];
  const parent = inst.to === 'cloud' ? 'سرور و اپلیکیشن' : ind.instances.find((x) => x.id === inst.to).label;
  const kids = ind.instances.filter((x) => x.to === inst.id);
  const eqs = inst.controls.map((id) => ind.equipment.find((e) => e.id === id)).filter(Boolean);
  const L = LINKS[inst.link];
  return `<div class="ph" style="--c:${b.color}"><span class="pico">${b.icon}</span><div><div class="pkind">${esc(b.name)}</div><h2>${esc(inst.label)}</h2></div></div>` +
    `<div class="pmodel" style="--c:${b.color}"><b>مدل: ${esc(m.name)}</b><p>${esc(m.desc)}</p></div>` +
    `<h3>نقش این برد در «${esc(ind.name)}»</h3><p class="role">${esc(inst.role)}</p>` +
    (eqs.length ? `<h3>تجهیزاتی که فرمان می‌دهد یا پایش می‌کند</h3><ul class="eqlist">${eqs.map((e) => `<li><span>${e.emoji}</span>${esc(e.label)}</li>`).join('')}</ul>` : '') +
    `<h3>اتصال‌ها</h3><ul class="conn"><li><i style="background:${L.color}"></i>به «${esc(parent)}» از طریق <b>${esc(L.name)}</b><small>${esc(L.desc)}</small></li>` +
    kids.map((k) => `<li><i style="background:${LINKS[k.link].color}"></i>«${esc(k.label)}» از طریق <b>${esc(LINKS[k.link].name)}</b> به این برد وصل است</li>`).join('') + `</ul>` +
    `<h3>همه‌ی امکانات «${esc(b.name)}»</h3>${featureHtml(b)}` +
    `<a class="btn" href="#/board/${inst.board}">صفحه‌ی کامل این برد و صنایعی که در آن‌ها به کار می‌رود ←</a>`;
}
function boardPanel(id) {
  const b = BOARDS[id];
  return `<div class="ph" style="--c:${b.color}"><span class="pico">${b.icon}</span><div><div class="pkind">${esc(b.short)}</div><h2>${esc(b.name)}</h2></div></div>` +
    `<p class="role">${esc(b.summary)}</p>${featureHtml(b)}<a class="btn" href="#/board/${id}">صفحه‌ی کامل این برد ←</a>`;
}

function wireSelect(root, ind) {
  root.querySelectorAll('.chip[data-inst]').forEach((el) => {
    const act = () => {
      const inst = ind.instances.find((x) => x.id === el.dataset.inst);
      root.querySelectorAll('.sel, .hl').forEach((e) => e.classList.remove('sel', 'hl'));
      root.querySelectorAll('svg').forEach((s) => s.classList.add('has-sel'));
      root.querySelectorAll(`.chip[data-inst="${inst.id}"]`).forEach((c) => c.classList.add('sel'));
      root.querySelectorAll(`.link[data-owner="${inst.id}"]`).forEach((c) => c.classList.add('sel'));
      ind.instances.filter((x) => x.to === inst.id).forEach((k) => root.querySelectorAll(`.link[data-owner="${k.id}"]`).forEach((c) => c.classList.add('sel')));
      inst.controls.forEach((id) => root.querySelectorAll(`.equip[data-eq="${id}"]`).forEach((c) => c.classList.add('hl')));
      openPanel(instancePanel(ind, inst));
    };
    el.addEventListener('click', act);
    el.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); act(); } });
  });
}

/* ------------------------------------------------------------------ صفحه‌ها */
function legend(ind) {
  const kinds = [...new Set(ind.instances.map((i) => i.link))];
  const boards = [...new Set(ind.instances.map((i) => i.board))];
  return `<div class="legend"><div>${boards.map((b) => `<span class="lg"><i style="background:${BOARDS[b].color}"></i>${esc(BOARDS[b].name)}</span>`).join('')}</div>` +
    `<div>${kinds.map((k) => `<span class="lg" title="${esc(LINKS[k].desc)}"><svg width="34" height="10"><line x1="2" x2="32" y1="5" y2="5" stroke="${LINKS[k].color}" stroke-width="3" ${LINKS[k].dash ? `stroke-dasharray="${LINKS[k].dash}"` : ''}/></svg>${esc(LINKS[k].name)}</span>`).join('')}</div></div>`;
}
function countBoards(ind) {
  const c = {};
  ind.instances.forEach((i) => (c[i.board] = (c[i.board] || 0) + 1));
  return c;
}

function pageHome() {
  const demo = {
    name: 'نمونه', equipment: [], instances: [
      { id: 'h', board: 'hub', model: 'HUB-C', label: 'هاب', to: 'cloud', link: 'internet', controls: [] },
      { id: 'c', board: 'ctrl', model: 'CTRL-P', label: 'کنترلر اصلی', to: 'h', link: 'wifi', controls: [] },
      { id: 'p1', board: 'pwr', model: 'PWR-8E', label: 'برد قدرت ۱', to: 'c', link: 'agribus', controls: [] },
      { id: 'p2', board: 'pwr', model: 'PWR-8', label: 'برد قدرت ۲', to: 'p1', link: 'agribus', controls: [] },
      { id: 'r1', board: 'probe', model: 'PROBE-CL', label: 'پروب اقلیم', to: 'c', link: 'sensorbus', controls: [] },
      { id: 'r2', board: 'probe', model: 'PROBE-GS', label: 'پروب گاز', to: 'r1', link: 'sensorbus', controls: [] },
      { id: 'n1', board: 'node', model: 'NODE-C', label: 'نود بی‌سیم', to: 'c', link: 'wifi', controls: [] },
      { id: 'n2', board: 'node', model: 'NODE-W', label: 'نود هواشناسی', to: 'c', link: 'lora', controls: [] },
      { id: 'm', board: 'hmi', model: 'HMI-7', label: 'نمایشگر لمسی', to: 'c', link: 'panel', controls: [] },
    ]
  };
  return `<section class="hero"><div class="herotext"><h1>سبد محصولات هوشمند <span>اگری‌نود</span></h1>
    <p>خانواده‌ی بردهای کنترل و پایش برای گلخانه، قارچ، مرغداری، دامداری، آبزی‌پروری، مزرعه، باغ، سردخانه و ده‌ها کاربرد دیگر. فقط چهار برد جدید به‌علاوه‌ی چهار هاب آماده، بیش از بیست مدل محصول و پانزده صنعت.</p>
    <div class="stats"><div><b>${fa(4)}</b>هاب آماده</div><div><b>${fa(4)}</b>برد جدید</div><div><b>${fa(Object.values(BOARDS).reduce((a, b) => a + b.models.length, 0))}</b>مدل محصول</div><div><b>${fa(INDUSTRIES.length)}</b>صنعت</div></div>
    <div class="herobtns"><a class="btn big" href="#ind">انتخاب بر اساس صنعت</a><a class="btn big alt" href="#brd">انتخاب بر اساس برد</a><a class="btn big ghost" href="#/arch">معماری کلی سیستم</a></div></div>
    <div class="herofig">${topologySvg(demo, true)}</div></section>
    <h2 class="sec" id="ind">یک صنعت را انتخاب کنید</h2><p class="secsub">سالن آن صنعت نمایش داده می‌شود: کدام برد کجا نصب می‌شود، چه کاری انجام می‌دهد و بردها چطور به هم وصل می‌شوند.</p>
    <div class="grid inds">${INDUSTRIES.map((i, k) => {
      const c = countBoards(i);
      return `<a class="card ind" href="#/industry/${i.id}" style="animation-delay:${k * 40}ms"><span class="big">${i.icon}</span><b>${esc(i.name)}</b><small>${esc(i.tagline)}</small><span class="dotsrow">${Object.keys(c).map((b) => `<i title="${esc(BOARDS[b].name)}" style="background:${BOARDS[b].color}"></i>`).join('')}</span></a>`;
    }).join('')}</div>
    <h2 class="sec" id="brd">یا یک برد را انتخاب کنید</h2><p class="secsub">می‌بینید این برد در کدام صنعت‌ها و کجای سالن به کار می‌رود و چه امکاناتی دارد.</p>
    <div class="grid brds">${Object.entries(BOARDS).map(([id, b], k) => `<a class="card brd" href="#/board/${id}" style="--c:${b.color};animation-delay:${k * 60}ms"><div class="artwrap">${boardArt(id)}</div><b>${b.icon} ${esc(b.name)}</b><small>${esc(b.status)}</small><span class="models">${b.models.map((m) => `<em>${esc(m.name)}</em>`).join('')}</span></a>`).join('')}</div>`;
}

function pageIndustry(id, tab = 'scene', focus) {
  const ind = IND[id];
  if (!ind) return pageHome();
  const c = countBoards(ind);
  const tabs = [['scene', 'نمای سالن و جانمایی بردها'], ['topo', 'نقشه‌ی اتصال بردها'], ['logic', 'امکانات و منطق کنترل']];
  let body = '';
  if (tab === 'scene') body = `<p class="hint">روی هر برد کلیک کنید تا نقش آن، تجهیزاتی که فرمان می‌دهد و همه‌ی امکاناتش نمایش داده شود.</p><div class="scenewrap">${sceneSvg(ind, { focusBoard: focus })}</div>${legend(ind)}`;
  else if (tab === 'topo') body = `<p class="hint">مسیر داده از هر برد تا سرور؛ نقطه‌های متحرک جهت ارسال داده را نشان می‌دهند. روی هر برد کلیک کنید.</p><div class="topowrap">${topologySvg(ind)}</div>${legend(ind)}`;
  else body = `<div class="logic"><h3>منطق کنترل و امکانات ویژه‌ی ${esc(ind.name)}</h3><ol>${ind.logic.map((t) => `<li>${esc(t)}</li>`).join('')}</ol>` +
    (ind.phases ? `<h3>فازهای کنترل (قارچ دکمه‌ای)</h3><div class="tblwrap"><table><thead><tr><th>فاز</th><th>دمای کمپوست</th><th>دمای هوا</th><th>رطوبت</th><th>دی‌اکسید کربن</th></tr></thead><tbody>${ind.phases.map((r) => `<tr>${r.map((x) => `<td>${esc(x)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>` : '') +
    `<h3>بردهای به‌کاررفته در این صنعت</h3><div class="grid mini">${Object.entries(c).map(([b, n]) => `<a class="card brd small" href="#/board/${b}" style="--c:${BOARDS[b].color}"><div class="artwrap">${boardArt(b)}</div><b>${BOARDS[b].icon} ${esc(BOARDS[b].name)}</b><small>${fa(n)} عدد در این نمونه: ${ind.instances.filter((i) => i.board === b).map((i) => esc(i.label)).join('، ')}</small></a>`).join('')}</div></div>`;
  return `<nav class="crumb"><a href="#/">خانه</a> › <a href="#ind" onclick="location.hash='#/';setTimeout(()=>document.getElementById('ind').scrollIntoView(),60)">صنایع</a> › <span>${esc(ind.name)}</span></nav>
    <header class="phead"><span class="big">${ind.icon}</span><div><h1>${esc(ind.name)}</h1><p>${esc(ind.desc)}</p>
    <div class="chips">${Object.entries(c).map(([b, n]) => `<a class="pill" href="#/industry/${id}/scene/${b}" style="--c:${BOARDS[b].color}">${BOARDS[b].icon} ${esc(BOARDS[b].short)} × ${fa(n)}</a>`).join('')}</div></div></header>
    <div class="tabs">${tabs.map(([k, t]) => `<a class="tab${k === tab ? ' on' : ''}" href="#/industry/${id}/${k}">${t}</a>`).join('')}</div>
    <div class="tabbody" data-ind="${id}">${body}</div>`;
}

function pageBoard(id) {
  const b = BOARDS[id];
  if (!b) return pageHome();
  const used = INDUSTRIES.filter((i) => i.instances.some((x) => x.board === id));
  const unused = INDUSTRIES.filter((i) => !used.includes(i));
  return `<nav class="crumb"><a href="#/">خانه</a> › <a href="#brd" onclick="location.hash='#/';setTimeout(()=>document.getElementById('brd').scrollIntoView(),60)">بردها</a> › <span>${esc(b.name)}</span></nav>
    <header class="bhead" style="--c:${b.color}"><div class="bart">${boardArt(id)}</div><div><div class="status">${esc(b.status)}</div><h1>${b.icon} ${esc(b.name)}</h1><p>${esc(b.summary)}</p>
    <div class="stats small"><div><b>${fa(b.models.length)}</b>مدل</div><div><b>${fa(used.length)}</b>صنعت</div><div><b>${fa(used.reduce((a, i) => a + i.instances.filter((x) => x.board === id).length, 0))}</b>جایگاه در نمونه‌ها</div></div></div></header>
    <h2 class="sec">مدل‌ها</h2><div class="grid models">${b.models.map((m, k) => `<div class="card model" style="--c:${b.color};animation-delay:${k * 60}ms"><b>${esc(m.name)}</b><p>${esc(m.desc)}</p></div>`).join('')}</div>
    <h2 class="sec">این برد در کدام صنعت‌ها و کجای سالن به کار می‌رود؟</h2><p class="secsub">بردهای این نوع در هر سالن روشن و چشمک‌زن نشان داده شده‌اند. روی هر کارت کلیک کنید تا سالن کامل آن صنعت باز شود.</p>
    <div class="grid uses">${used.map((i, k) => `<a class="card use" href="#/industry/${i.id}/scene/${id}" style="animation-delay:${k * 50}ms"><div class="minisc">${sceneSvg(i, { mini: true, focusBoard: id })}</div><b>${i.icon} ${esc(i.name)}</b><ul>${i.instances.filter((x) => x.board === id).map((x) => `<li><strong>${esc(x.label)}</strong> (${esc(modelOf(x).name)}): ${esc(x.role)}</li>`).join('')}</ul></a>`).join('')}</div>
    ${unused.length ? `<p class="secsub">در نمونه‌های این صنایع به کار نرفته است: ${unused.map((i) => esc(i.name)).join('، ')}</p>` : ''}
    <h2 class="sec">همه‌ی امکانات</h2><div class="featgrid">${featureHtml(b, true)}</div>`;
}

function pageArch() {
  const ex = IND.poultry;
  const safety = [
    ['۱', 'نرم‌افزار کنترلر اصلی', 'کنترل عادی، هشدارها و سنسورهای افزونه با رأی‌گیری'],
    ['۲', 'ناظر سخت‌افزاری کنترلر', 'هنگ یا ری‌استارت مکرر پردازنده‌ی اصلی: ریست و قطع ضربان خط ایمنی'],
    ['۳', 'پردازنده‌ی برد قدرت', 'قطع ارتباط کابل شبکه: رفتن به حالت امن نرم‌افزاری'],
    ['۴', 'منطق سخت‌افزاری برد قدرت', 'قطع خط ایمنی یا خرابی پردازنده‌ی برد قدرت: حالت امن تعیین‌شده با کلید، در کمتر از یک ثانیه'],
    ['۵', 'ترموستات سخت‌افزاری پشتیبان', 'دمای خطر: فن‌ها روشن، هیتر خاموش، آژیر روشن؛ بدون هیچ پردازنده‌ای'],
    ['۶', 'کلیدهای دستی خودکار، خاموش و روشن', 'کنترل کامل اپراتور در هر شرایطی'],
  ];
  const pins = [['۱', 'داده (سیم مثبت)', '#f472b6'], ['۲', 'داده (سیم منفی)', '#f472b6'], ['۳', 'خط ایمنی', '#ef4444'], ['۴', '+۲۴ ولت', '#f59e0b'], ['۵', '+۲۴ ولت', '#f59e0b'], ['۶', 'خط ایمنی', '#ef4444'], ['۷', 'زمین', '#64748b'], ['۸', 'زمین', '#64748b']];
  return `<nav class="crumb"><a href="#/">خانه</a> › <span>معماری کلی سیستم</span></nav>
    <header class="phead"><span class="big">🧭</span><div><h1>معماری کلی سیستم</h1><p>هر فضای مستقل (سالن، اتاق، گلخانه، استخر) یک کنترلر اصلی دارد. کنترلر کاملاً ولتاژ پایین است؛ بردهای قدرت داخل تابلو برق با یک کابل شبکه به آن وصل می‌شوند؛ پروب‌های هوشمند با باس سنسور و نودهای بی‌سیم با بی‌سیم کوتاه‌برد یا لورا. هاب داده را به اینترنت می‌رساند. اگر اینترنت یا هاب قطع شود، کنترل محلی بدون وقفه ادامه دارد.</p></div></header>
    <h2 class="sec">نمونه: نقشه‌ی اتصال یک سالن مرغداری</h2><div class="topowrap" data-ind="poultry">${topologySvg(ex)}</div>
    <h2 class="sec">انواع اتصال</h2><div class="grid links">${Object.values(LINKS).map((L) => `<div class="card linkcard"><svg width="100%" height="24" viewBox="0 0 200 24" preserveAspectRatio="none"><path class="lbase" d="M4 12 H196" stroke="${L.color}" ${L.dash ? `stroke-dasharray="${L.dash}"` : ''}/><path class="lflow" d="M4 12 H196" stroke="${L.color}"/></svg><b>${esc(L.name)}</b><p>${esc(L.desc)}</p></div>`).join('')}</div>
    <h2 class="sec">کابل شبکه‌ی اگری‌باس: پایه‌های سوکت</h2><div class="rj45">${pins.map(([n, t, c], k) => `<div class="pin" style="--c:${c};animation-delay:${k * 80}ms"><b>${n}</b><span>${t}</span></div>`).join('')}</div>
    <p class="secsub">کنترلر روی زوج پایه‌های ۳ و ۶ یک ضربان سخت‌افزاری می‌فرستد. اگر کابل قطع شود، کنترلر هنگ کند یا برقش برود، بردهای قدرت در کمتر از یک ثانیه با سخت‌افزار به حالت امن می‌روند. برد قدرت با منبع تغذیه‌ی داخلی، کنترلر را از همین کابل تغذیه می‌کند؛ پس بین تابلو و کنترلر فقط یک کابل شبکه کشیده می‌شود.</p>
    <h2 class="sec">شش لایه‌ی ایمنی</h2><div class="safety">${safety.map(([n, who, what], k) => `<div class="layer" style="animation-delay:${k * 90}ms"><b>${n}</b><div><strong>${esc(who)}</strong><span>${esc(what)}</span></div></div>`).join('')}</div>
    <p class="secsub">هدف: هیچ خرابی تکی (سنسور، کابل، پردازنده، برق یا اینترنت) نباید به تلفات گله، محصول یا ماهی منجر شود.</p>`;
}

/* ------------------------------------------------------------------ مسیریابی صفحه */
function route() {
  closePanel();
  const h = location.hash;
  const parts = h.replace(/^#\/?/, '').split('/');
  const app = $('#app');
  document.querySelectorAll('.nav a').forEach((a) => a.classList.remove('on'));
  if (parts[0] === 'industry') {
    app.innerHTML = pageIndustry(parts[1], parts[2] || 'scene', parts[3]);
    $('.nav a[data-n="ind"]').classList.add('on');
    const tb = $('.tabbody'); if (tb) wireSelect(tb, IND[parts[1]]);
    if (parts[3] && (parts[2] || 'scene') === 'scene') {
      const first = tb.querySelector(`.chip.b-${parts[3]}`); if (first) setTimeout(() => first.dispatchEvent(new Event('click')), 350);
    }
  } else if (parts[0] === 'board') {
    app.innerHTML = pageBoard(parts[1]); $('.nav a[data-n="brd"]').classList.add('on');
  } else if (parts[0] === 'arch') {
    app.innerHTML = pageArch(); $('.nav a[data-n="arch"]').classList.add('on');
    wireSelect($('.topowrap'), IND.poultry);
  } else if (!h || h === '#/' || h === '#') {
    app.innerHTML = pageHome(); $('.nav a[data-n="home"]').classList.add('on');
  } else return; /* لنگرهای داخل صفحه */
  window.scrollTo({ top: 0, behavior: 'instant' in window ? 'instant' : 'auto' });
  app.classList.remove('enter'); void app.offsetWidth; app.classList.add('enter');
}

/* هیچ برچسبی از کادر نما بیرون نزند */
INDUSTRIES.forEach((ind) => ind.instances.forEach((i) => {
  const m = modelOf(i), half = chipW(i.label, m.chip || m.name) / 2 + 6;
  i.x = Math.min(W - half, Math.max(half, i.x));
}));

window.addEventListener('hashchange', route);
document.addEventListener('DOMContentLoaded', () => {
  $('#panelClose').addEventListener('click', closePanel);
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closePanel(); });
  if (!location.hash) history.replaceState(null, '', '#/');
  route();
});
