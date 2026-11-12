#!/usr/bin/env python3
"""Generates the HyperFrames project for the 힐스테이트운정 promo shorts.

Run from the project root:  python3 work/gen.py
Writes index.html and compositions/*.html.
Prices: MOLIT 실거래 (via dapt.kr, 2026-11-11), 84㎡ unless noted.
"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
COMP = ROOT / "compositions"
COMP.mkdir(exist_ok=True)

W, H = 1080, 1920
TOTAL = 42.0

SCENES = [
    ("s1", 0.0, 6.55),
    ("s2", 6.55, 17.0),
    ("s3", 17.0, 24.65),
    ("s4", 24.65, 32.7),
    ("s5", 32.7, 35.95),
    ("s6", 35.95, 42.0),
]


def split(groups, t0, t1):
    def weight(s):
        return sum(0 if c == " " else (0.6 if c in ",." else 1.0) for c in s)
    total = sum(weight(sp) for _, sp in groups)
    out, t = [], t0
    for disp, sp in groups:
        d = (t1 - t0) * weight(sp) / total
        out.append((disp, t, t + d))
        t += d
    return out


LINES = [
    (0.30, split([("한때 운정의 대장은", "한때 운정의 대장은"), ("힐푸아.", "힐푸아.")], 0.0, 1.89)
          + split([("힐스테이트,", "힐스테이트,")], 2.89, 3.76)
          + split([("푸르지오,", "푸르지오,")], 4.02, 4.61)
          + split([("아이파크였습니다.", "아이파크였습니다.")], 4.89, 6.03)),
    (6.75, split([("2020년 무렵엔 셋 다", "이천이십년 무렵엔 셋 다"), ("84㎡ 고점이 9억 원 안팎.", "팔십사제곱미터 고점이 구억 원 안팎.")], 0.0, 4.33)
          + split([("하지만 GTX 개통 뒤,", "하지만 GTX 개통 뒤,")], 5.36, 7.10)
          + split([("연식과 역 거리에서", "연식과 역 거리에서"), ("순위가 갈렸습니다.", "순위가 갈렸습니다.")], 7.48, 10.05)),
    (17.20, split([("최근 실거래를 보면,", "최근 실거래를 보면,")], 0.0, 1.33)
          + split([("아이파크 7억 중반,", "아이파크 칠억 중반,")], 1.64, 2.95)
          + split([("푸르지오 6억 후반,", "푸르지오 육억 후반,")], 3.23, 4.53)
          + split([("힐스테이트운정은", "힐스테이트운정은"), ("6억 중반입니다.", "육억 중반입니다.")], 4.88, 7.25)),
    (24.85, split([("고점보다 2억 원 이상", "고점보다 이억 원 이상"), ("낮아진 가격.", "낮아진 가격.")], 0.0, 2.24)
          + split([("2,998세대 대단지에,", "이천구백구십팔 세대 대단지에,")], 3.26, 5.47)
          + split([("운정중앙역 도보권입니다.", "운정중앙역 도보권입니다.")], 5.86, 7.65)),
    (32.90, split([("59㎡는 5억 원 안팎.", "오십구제곱미터는 오억 원 안팎.")], 0.0, 2.19)
          + split([("힐스테이트운정 매물과 시세,", "힐스테이트운정 매물과 시세,")], 3.22, 5.18)
          + split([("현대베스트부동산에", "현대베스트부동산에"), ("문의하세요.", "문의하세요.")], 5.50, 7.50)),
]

CAPTIONS = []
for off, groups in LINES:
    for disp, a, b in groups:
        CAPTIONS.append((disp, round(off + a - 0.05, 2), round(off + b + 0.08, 2)))
for i in range(len(CAPTIONS) - 1):
    d, a, b = CAPTIONS[i]
    na = CAPTIONS[i + 1][1]
    if b > na:
        CAPTIONS[i] = (d, a, na)


def cap_size(text, base=64, minimum=44, maxw=900):
    def w(c):
        if c == " ":
            return 0.28
        if c in ",.":
            return 0.3
        if c.isascii():
            return 0.58
        return 1.0
    est = sum(w(c) for c in text)
    size = base
    while size > minimum and est * size > maxw:
        size -= 2
    return size


FONT_FACE = """
@font-face { font-family: 'Pretendard'; src: url('assets/fonts/Pretendard-Regular.woff2') format('woff2'); font-weight: 400; }
@font-face { font-family: 'Pretendard'; src: url('assets/fonts/Pretendard-SemiBold.woff2') format('woff2'); font-weight: 600; }
@font-face { font-family: 'Pretendard'; src: url('assets/fonts/Pretendard-Bold.woff2') format('woff2'); font-weight: 700; }
@font-face { font-family: 'Pretendard'; src: url('assets/fonts/Pretendard-ExtraBold.woff2') format('woff2'); font-weight: 800; }
"""

# Hillstate = brand teal-green; others muted
PALETTE = """
  --bg: #0c1519; --panel: #13232a; --panel2: #1a2f37; --line: #27424c;
  --ink: #f3f1ea; --muted: #93a7ad; --hill: #3fd0b0; --hill-soft: rgba(63,208,176,.16);
  --gold: #f2c14e; --pru: #8fa8ff; --ipk: #ff8f6b; --down: #6fb6ff;
"""


def scene(cid, css, body, js):
    return f"""<template>
  <style>
    {FONT_FACE}
    #{cid} {{ position: absolute; inset: 0; font-family: 'Pretendard', sans-serif; color: var(--ink); {PALETTE} }}
    {css}
  </style>
  <div id="{cid}" data-composition-id="{cid}" data-width="{W}" data-height="{H}">
{body}
  </div>
  <script>
    (function () {{
      const tl = gsap.timeline({{ paused: true }});
      const q = (s) => document.querySelector("#{cid} " + s);
{js}
      window.__timelines["{cid}"] = tl;
    }})();
  </script>
</template>
"""


COMMON_CSS = """
.kicker { position: absolute; left: 90px; right: 280px; top: 230px; font-size: 34px; font-weight: 600; color: var(--hill); letter-spacing: .02em; }
.title  { position: absolute; left: 90px; right: 90px; top: 285px; font-size: 92px; font-weight: 800; line-height: 1.08; letter-spacing: -.02em; }
"""

UP = "{ opacity: 0, y: 24 }, { opacity: 1, y: 0, duration: 0.45, ease: 'power3.out' }"

# ---------------- S1: 힐푸아 ----------------
s1 = scene("s1", COMMON_CSS + """
#s1 .title { top: 300px; font-size: 76px; }
#s1 .big { position: absolute; left: 90px; right: 90px; top: 400px; font-size: 210px; font-weight: 800; letter-spacing: -.04em; line-height: 1; }
#s1 .big span { display: inline-block; }
#s1 .big .h { color: var(--hill); } #s1 .big .p { color: var(--pru); } #s1 .big .a { color: var(--ipk); }
#s1 .row { position: absolute; left: 90px; right: 90px; height: 110px; border-radius: 24px; background: var(--panel); border: 2px solid var(--line); display: flex; align-items: center; gap: 26px; padding: 0 34px; }
#s1 .row .k { width: 64px; height: 64px; border-radius: 18px; display: flex; align-items: center; justify-content: center; font-size: 38px; font-weight: 800; color: #0c1519; flex: none; }
#s1 .row .n { font-size: 46px; font-weight: 800; }
#s1 #s1-r1 { top: 700px; } #s1 #s1-r2 { top: 830px; } #s1 #s1-r3 { top: 960px; }
#s1 #s1-r1 .k { background: var(--hill); } #s1 #s1-r2 .k { background: var(--pru); } #s1 #s1-r3 .k { background: var(--ipk); }
#s1 #s1-r1 { border-color: var(--hill); }
""", """
    <div class="title" id="s1-t">운정 대장 3인방</div>
    <div class="big" id="s1-big"><span class="h" id="s1-h">힐</span><span class="p" id="s1-p">푸</span><span class="a" id="s1-a">아</span></div>
    <div class="row" id="s1-r1"><span class="k">힐</span><span class="n">힐스테이트운정</span></div>
    <div class="row" id="s1-r2"><span class="k">푸</span><span class="n">운정신도시 센트럴푸르지오</span></div>
    <div class="row" id="s1-r3"><span class="k">아</span><span class="n">운정신도시 아이파크</span></div>
""", f"""
      tl.fromTo(q('#s1-big'), {{ scale: 1 }}, {{ scale: 1.04, duration: 6.5, ease: 'none', transformOrigin: 'left center' }}, 0);
      tl.fromTo(q('#s1-r1'), {{ opacity: 0, x: -40 }}, {{ opacity: 1, x: 0, duration: 0.4, ease: 'power3.out' }}, 3.1);
      tl.fromTo(q('#s1-r2'), {{ opacity: 0, x: -40 }}, {{ opacity: 1, x: 0, duration: 0.4, ease: 'power3.out' }}, 4.25);
      tl.fromTo(q('#s1-r3'), {{ opacity: 0, x: -40 }}, {{ opacity: 1, x: 0, duration: 0.4, ease: 'power3.out' }}, 5.15);
      tl.fromTo(q('#s1-h'), {{ y: 0 }}, {{ y: -18, duration: 0.2, yoyo: true, repeat: 1, ease: 'power2.out' }}, 3.1);
      tl.fromTo(q('#s1-p'), {{ y: 0 }}, {{ y: -18, duration: 0.2, yoyo: true, repeat: 1, ease: 'power2.out' }}, 4.25);
      tl.fromTo(q('#s1-a'), {{ y: 0 }}, {{ y: -18, duration: 0.2, yoyo: true, repeat: 1, ease: 'power2.out' }}, 5.15);
""")

# ---------------- S2: 2020-21 peaks, then split ----------------
# bars scaled: 9.7억 -> 760px
def bw(v, full=9.7, px=760):
    return int(px * v / full)

s2 = scene("s2", COMMON_CSS + """
#s2 .title { font-size: 80px; }
#s2 .bar-row { position: absolute; left: 90px; right: 90px; }
#s2 .bar-row .lab { font-size: 32px; font-weight: 700; display: flex; justify-content: space-between; width: 760px; }
#s2 .bar-row .lab small { color: var(--muted); font-weight: 600; font-size: 28px; }
#s2 .bar-row .bar { margin-top: 10px; height: 78px; border-radius: 16px; transform-origin: left center; display: flex; align-items: center; justify-content: flex-end; padding-right: 22px; font-size: 44px; font-weight: 800; color: #0c1519; }
#s2 #s2-r1 { top: 470px; } #s2 #s2-r2 { top: 620px; } #s2 #s2-r3 { top: 770px; }
#s2 #s2-b1 { background: var(--hill); } #s2 #s2-b2 { background: var(--pru); } #s2 #s2-b3 { background: var(--ipk); }
#s2 .split { position: absolute; left: 90px; right: 90px; top: 950px; height: 150px; border-radius: 26px; background: var(--panel2); border: 2px solid var(--gold); display: flex; align-items: center; gap: 24px; padding: 0 36px; }
#s2 .split .a { font-size: 46px; font-weight: 800; color: var(--gold); white-space: nowrap; }
#s2 .split .b { font-size: 34px; font-weight: 700; line-height: 1.35; }
""", f"""
    <div class="kicker" id="s2-k">2020~21년 · 84㎡ 최고가</div>
    <div class="title" id="s2-t">셋 다 9억 안팎</div>
    <div class="bar-row" id="s2-r1"><div class="lab">힐스테이트운정 <small>2020.11</small></div><div class="bar" id="s2-b1" style="width:{bw(8.99)}px">8.99억</div></div>
    <div class="bar-row" id="s2-r2"><div class="lab">센트럴푸르지오 <small>2021.10</small></div><div class="bar" id="s2-b2" style="width:{bw(9.4)}px">9.4억</div></div>
    <div class="bar-row" id="s2-r3"><div class="lab">아이파크 <small>2021.07</small></div><div class="bar" id="s2-b3" style="width:{bw(9.7)}px">9.7억</div></div>
    <div class="split" id="s2-split"><span class="a">GTX 개통 후</span><span class="b">연식 · 역 거리로<br>순위가 갈렸다</span></div>
""", f"""
      tl.fromTo(q('#s2-k'), {UP}, 0.05);
      tl.fromTo(q('#s2-t'), {UP}, 0.15);
      for (let i = 1; i <= 3; i++) {{
        tl.fromTo(q('#s2-r' + i), {{ opacity: 0 }}, {{ opacity: 1, duration: 0.25 }}, 0.6 + i * 0.35);
        tl.fromTo(q('#s2-b' + i), {{ scaleX: 0 }}, {{ scaleX: 1, duration: 0.8, ease: 'power3.out' }}, 0.65 + i * 0.35);
      }}
      tl.fromTo(q('#s2-split'), {{ opacity: 0, scale: 1.15 }}, {{ opacity: 1, scale: 1, duration: 0.45, ease: 'power4.out' }}, 5.5);
""")

# ---------------- S3: current ranking ----------------
RANK = [
    ("1", "아이파크", "2020년 입주", "7억 중반", "6.9~8.0억", "ipk", False),
    ("2", "센트럴푸르지오", "2018년 입주", "6억 후반", "6.5~7.1억", "pru", False),
    ("3", "힐스테이트운정", "2018년 입주", "6억 중반", "6.4~6.7억", "hill", True),
]
s3_rows = "\n".join(
    f'    <div class="rk{" me" if me else ""}" id="s3-r{i}" style="top:{470 + (i - 1) * 190}px"><span class="no {c}">{n}</span><span class="nm">{nm}<small>{yr}</small></span><span class="pr">{p}<small>{rg}</small></span></div>'
    for i, (n, nm, yr, p, rg, c, me) in enumerate(RANK, 1))
s3 = scene("s3", COMMON_CSS + """
#s3 .title { font-size: 84px; }
#s3 .rk { position: absolute; left: 90px; right: 90px; height: 160px; border-radius: 26px; background: var(--panel); border: 2px solid var(--line); display: flex; align-items: center; gap: 26px; padding: 0 32px; }
#s3 .rk.me { border-color: var(--hill); background: var(--hill-soft); }
#s3 .no { width: 70px; height: 70px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 40px; font-weight: 800; color: #0c1519; flex: none; }
#s3 .no.ipk { background: var(--ipk); } #s3 .no.pru { background: var(--pru); } #s3 .no.hill { background: var(--hill); }
#s3 .nm { font-size: 44px; font-weight: 800; flex: 1; }
#s3 .nm small, #s3 .pr small { display: block; font-size: 28px; color: var(--muted); font-weight: 600; margin-top: 4px; }
#s3 .pr { font-size: 50px; font-weight: 800; text-align: right; color: var(--gold); }
#s3 .note { position: absolute; left: 90px; right: 90px; top: 1050px; font-size: 28px; color: var(--muted); }
""", s3_rows.join(["""
    <div class="kicker" id="s3-k">지금 · 84㎡ 실거래</div>
    <div class="title" id="s3-t">순위가 바뀌었다</div>
""", """
    <div class="note" id="s3-n">각 단지 84㎡ 최근 실거래 10건 범위 · 국토부</div>
"""]), f"""
      tl.fromTo(q('#s3-k'), {UP}, 0.05);
      tl.fromTo(q('#s3-t'), {UP}, 0.15);
      tl.fromTo(q('#s3-r1'), {{ opacity: 0, x: 50 }}, {{ opacity: 1, x: 0, duration: 0.4, ease: 'power3.out' }}, 1.7);
      tl.fromTo(q('#s3-r2'), {{ opacity: 0, x: 50 }}, {{ opacity: 1, x: 0, duration: 0.4, ease: 'power3.out' }}, 3.3);
      tl.fromTo(q('#s3-r3'), {{ opacity: 0, x: 50 }}, {{ opacity: 1, x: 0, duration: 0.4, ease: 'power3.out' }}, 4.95);
      tl.fromTo(q('#s3-r3'), {{ scale: 1 }}, {{ scale: 1.04, duration: 0.25, yoyo: true, repeat: 1, ease: 'power2.out' }}, 5.6);
      tl.fromTo(q('#s3-n'), {{ opacity: 0 }}, {{ opacity: 1, duration: 0.4 }}, 1.0);
""")

# ---------------- S4: Hillstate spotlight ----------------
s4 = scene("s4", COMMON_CSS + """
#s4 .title { font-size: 88px; color: var(--hill); }
#s4 .card { position: absolute; left: 70px; right: 70px; top: 420px; height: 330px; border-radius: 32px; background: var(--panel); border: 2px solid var(--line); }
#s4 .from { position: absolute; left: 50px; top: 44px; font-size: 34px; color: var(--muted); font-weight: 600; }
#s4 .from s { color: var(--muted); }
#s4 .now { position: absolute; left: 50px; top: 100px; font-size: 130px; font-weight: 800; color: var(--gold); letter-spacing: -.03em; line-height: 1; }
#s4 .now small { font-size: 56px; }
#s4 .delta { position: absolute; right: 44px; top: 128px; padding: 10px 24px; border-radius: 30px; background: rgba(111,182,255,.16); color: var(--down); font-size: 44px; font-weight: 800; }
#s4 .when { position: absolute; left: 50px; top: 255px; font-size: 28px; color: var(--muted); }
#s4 .chips { position: absolute; left: 70px; right: 70px; top: 790px; display: flex; flex-direction: column; gap: 22px; }
#s4 .chip { height: 104px; border-radius: 24px; background: var(--hill-soft); border: 2px solid var(--hill); display: flex; align-items: center; gap: 22px; padding: 0 32px; font-size: 46px; font-weight: 800; }
#s4 .chip i { font-style: normal; width: 54px; height: 54px; border-radius: 50%; background: var(--hill); color: #0c1519; display: flex; align-items: center; justify-content: center; font-size: 32px; }
""", """
    <div class="kicker" id="s4-k">84㎡ · 고점 대비</div>
    <div class="title" id="s4-t">힐스테이트운정</div>
    <div class="card" id="s4-card">
      <div class="from">2020.11 최고가 <s>8.99억</s> →</div>
      <div class="now"><span id="s4-num">6.5</span><small>억</small></div>
      <div class="delta" id="s4-d">−2.49억</div>
      <div class="when">2026.11.7 실거래 · 13층 · 국토부</div>
    </div>
    <div class="chips">
      <div class="chip" id="s4-c1"><i>✓</i>2,998세대 대단지</div>
      <div class="chip" id="s4-c2"><i>✓</i>운정중앙역 도보권</div>
    </div>
""", f"""
      tl.fromTo(q('#s4-k'), {UP}, 0.05);
      tl.fromTo(q('#s4-t'), {UP}, 0.15);
      tl.fromTo(q('#s4-card'), {{ opacity: 0, y: 50 }}, {{ opacity: 1, y: 0, duration: 0.55, ease: 'power3.out' }}, 0.3);
      const c = {{ v: 8.99 }};
      tl.fromTo(c, {{ v: 8.99 }}, {{ v: 6.5, duration: 1.4, ease: 'power3.out', onUpdate: () => {{ q('#s4-num').textContent = c.v.toFixed(2).replace(/0$/, ''); }} }}, 0.5);
      tl.set(q('#s4-num'), {{ textContent: '6.5' }}, 1.95);
      tl.fromTo(q('#s4-d'), {{ opacity: 0, scale: 0.6 }}, {{ opacity: 1, scale: 1, duration: 0.4, ease: 'back.out(2)' }}, 1.9);
      tl.fromTo(q('#s4-c1'), {{ opacity: 0, x: -40 }}, {{ opacity: 1, x: 0, duration: 0.4, ease: 'power3.out' }}, 3.25);
      tl.fromTo(q('#s4-c2'), {{ opacity: 0, x: -40 }}, {{ opacity: 1, x: 0, duration: 0.4, ease: 'power3.out' }}, 5.85);
""")

# ---------------- S5: 59㎡ ----------------
s5 = scene("s5", COMMON_CSS + """
#s5 .title { font-size: 80px; }
#s5 .card { position: absolute; left: 70px; right: 70px; top: 470px; height: 420px; border-radius: 32px; background: var(--hill-soft); border: 3px solid var(--hill); }
#s5 .sz { position: absolute; left: 50px; top: 46px; font-size: 44px; font-weight: 800; }
#s5 .sz small { font-size: 30px; color: var(--muted); font-weight: 600; margin-left: 10px; }
#s5 .pr { position: absolute; left: 50px; top: 120px; font-size: 170px; font-weight: 800; color: var(--gold); letter-spacing: -.03em; line-height: 1; }
#s5 .pr small { font-size: 70px; }
#s5 .when { position: absolute; left: 50px; top: 320px; font-size: 30px; color: var(--muted); }
""", """
    <div class="kicker" id="s5-k">작은 평형도</div>
    <div class="title" id="s5-t">힐스테이트운정 59㎡</div>
    <div class="card" id="s5-card">
      <div class="sz">전용 59㎡<small>25평형</small></div>
      <div class="pr">5<small>억 안팎</small></div>
      <div class="when">최근 실거래 4.7~5.0억 · 2026.10~11 · 국토부</div>
    </div>
""", f"""
      tl.fromTo(q('#s5-k'), {UP}, 0.05);
      tl.fromTo(q('#s5-t'), {UP}, 0.12);
      tl.fromTo(q('#s5-card'), {{ opacity: 0, scale: 0.92 }}, {{ opacity: 1, scale: 1, duration: 0.5, ease: 'back.out(1.6)' }}, 0.25);
""")

# ---------------- S6: outro ----------------
s6 = scene("s6", """
#s6 .logo { position: absolute; left: 50%; top: 250px; width: 440px; margin-left: -220px; border-radius: 44px; box-shadow: 0 24px 60px rgba(0,0,0,.5); }
#s6 .ask { position: absolute; left: 60px; right: 60px; top: 735px; text-align: center; font-size: 46px; font-weight: 800; color: var(--hill); }
#s6 .name { position: absolute; left: 60px; right: 60px; top: 810px; text-align: center; font-size: 76px; font-weight: 800; letter-spacing: -.02em; }
#s6 .tel { position: absolute; left: 60px; right: 60px; top: 905px; text-align: center; font-size: 112px; font-weight: 800; color: var(--gold); letter-spacing: -.01em; }
#s6 .note { position: absolute; left: 60px; right: 60px; top: 1265px; text-align: center; font-size: 28px; color: var(--muted); }
""", """
    <img class="logo" id="s6-logo" src="assets/images/logo.png" alt="현대베스트부동산" />
    <div class="ask" id="s6-ask">힐스테이트운정 매물 · 시세 문의</div>
    <div class="name" id="s6-name">현대베스트부동산</div>
    <div class="tel" id="s6-tel">031-949-6649</div>
    <div class="note" id="s6-n">시세: 국토부 실거래가(2026.11 기준) · 투자 권유 아님</div>
""", """
      tl.fromTo(q('#s6-logo'), { opacity: 0, scale: 0.8 }, { opacity: 1, scale: 1, duration: 0.5, ease: 'back.out(1.8)' }, 0.0);
      tl.fromTo(q('#s6-ask'), { opacity: 0, y: 20 }, { opacity: 1, y: 0, duration: 0.4, ease: 'power3.out' }, 0.25);
      tl.fromTo(q('#s6-name'), { opacity: 0, y: 24 }, { opacity: 1, y: 0, duration: 0.4, ease: 'power3.out' }, 0.4);
      tl.fromTo(q('#s6-tel'), { opacity: 0, y: 24 }, { opacity: 1, y: 0, duration: 0.4, ease: 'power3.out' }, 0.55);
      tl.fromTo(q('#s6-tel'), { scale: 1 }, { scale: 1.06, duration: 0.3, yoyo: true, repeat: 1, ease: 'power2.out' }, 2.4);
      tl.fromTo(q('#s6-n'), { opacity: 0 }, { opacity: 1, duration: 0.4 }, 0.7);
""")

# ---------------- Captions ----------------
cap_divs, cap_js = [], []
for i, (text, a, b) in enumerate(CAPTIONS):
    cap_divs.append(f'    <div class="cg" id="cap-{i}"><span style="font-size:{cap_size(text)}px">{text}</span></div>')
    cap_js.append(
        f"      tl.fromTo(q('#cap-{i}'), {{ opacity: 0, y: 14 }}, {{ opacity: 1, y: 0, duration: 0.16, ease: 'power2.out' }}, {a});\n"
        f"      tl.to(q('#cap-{i}'), {{ opacity: 0, duration: 0.1, ease: 'power2.in' }}, {round(b - 0.1, 2)});\n"
        f"      tl.set(q('#cap-{i}'), {{ opacity: 0, visibility: 'hidden' }}, {b});")
caps = scene("caps", """
#caps .cg { position: absolute; left: 0; right: 0; top: 1150px; text-align: center; overflow: visible; opacity: 0; }
#caps .cg span { display: inline-block; padding: 10px 26px; border-radius: 16px; background: rgba(4,10,12,.66); font-weight: 700; color: #fff; letter-spacing: -.01em; }
""", "\n".join(cap_divs), "\n".join(cap_js))

for name, html in [("s1", s1), ("s2", s2), ("s3", s3), ("s4", s4), ("s5", s5), ("s6", s6), ("caps", caps)]:
    (COMP / f"{name}.html").write_text(html, encoding="utf-8")

hosts = "\n".join(
    f'      <div id="{cid}" data-composition-id="{cid}" data-composition-src="compositions/{cid}.html" data-start="{a}" data-duration="{round(b - a, 2)}" data-track-index="1" data-track-kind="graphics" data-width="{W}" data-height="{H}" style="z-index:2"></div>'
    for cid, a, b in SCENES)
outro_start = SCENES[-1][1]
index = f"""<!doctype html>
<html lang="ko">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={W}, height={H}" />
    <script src="assets/js/gsap.min.js"></script>
    <style>
      {FONT_FACE}
      :root {{ {PALETTE} }}
      * {{ margin: 0; padding: 0; box-sizing: border-box; }}
      html, body {{ width: {W}px; height: {H}px; overflow: hidden; background: var(--bg); }}
      #root {{ width: 100%; height: 100%; position: relative; font-family: 'Pretendard', sans-serif; }}
      #bg {{ position: absolute; inset: 0; z-index: 0; background:
              radial-gradient(900px 700px at 15% 12%, rgba(63,208,176,.20), transparent 70%),
              radial-gradient(800px 800px at 90% 80%, rgba(242,193,78,.10), transparent 70%), var(--bg); }}
      #grid {{ position: absolute; inset: -80px; z-index: 1; opacity: .35;
              background-image: linear-gradient(rgba(255,255,255,.05) 2px, transparent 2px), linear-gradient(90deg, rgba(255,255,255,.05) 2px, transparent 2px);
              background-size: 80px 80px; }}
      #foot {{ position: absolute; left: 0; right: 0; top: 1360px; z-index: 1; text-align: center; font-size: 28px; color: rgba(147,167,173,.55); font-weight: 600; letter-spacing: .3em; }}
      #logo {{ position: absolute; right: 36px; top: 178px; width: 170px; height: auto; z-index: 6; border-radius: 22px; box-shadow: 0 10px 30px rgba(0,0,0,.45); }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{TOTAL}" data-width="{W}" data-height="{H}">
      <div id="bg"></div>
      <div id="grid"></div>
      <div id="foot" data-layout-ignore>HILLSTATE · UNJEONG</div>
      <img id="logo" src="assets/images/logo.png" alt="현대베스트부동산 031-949-6649" />
{hosts}
      <div id="caps" data-composition-id="caps" data-composition-src="compositions/caps.html" data-start="0" data-duration="{TOTAL}" data-track-index="2" data-track-kind="captions" data-width="{W}" data-height="{H}" style="z-index:5"></div>
      <audio id="mix" src="assets/audio/mix.wav" data-start="0" data-duration="{TOTAL}" data-track-index="3"></audio>
    </div>
    <script>
      const tl = gsap.timeline({{ paused: true }});
      tl.to('#logo', {{ opacity: 0, duration: 0.3 }}, {outro_start - 0.15});
      tl.fromTo('#grid', {{ x: 0, y: 0 }}, {{ x: -80, y: -80, duration: {TOTAL}, ease: 'none' }}, 0);
      window.__timelines["main"] = tl;
    </script>
  </body>
</html>
"""
(ROOT / "index.html").write_text(index, encoding="utf-8")
print("captions:", len(CAPTIONS))
for c in CAPTIONS:
    print(c)
