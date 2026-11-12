#!/usr/bin/env python3
"""Generates the HyperFrames project for the 운정중앙역 GTX shorts.

Run from the project root:  python3 work/gen.py
Writes index.html and compositions/*.html. Narration timing lives in TIMING below.
"""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
COMP = ROOT / "compositions"
COMP.mkdir(exist_ok=True)

W, H, FPS = 1080, 1920, 30
TOTAL = 42.0

# Scene slots (global seconds)
SCENES = [
    ("s1", 0.0, 7.45),
    ("s2", 7.45, 14.75),
    ("s3", 14.75, 24.2),
    ("s4", 24.2, 31.15),
    ("s5", 31.15, 38.35),
    ("s6", 38.35, 42.0),
]

# Narration lines: global offset, and caption groups as (display, spoken, local_start, local_end)
# local times come from silencedetect pauses; inner splits are proportional to spoken length.
def split(groups, t0, t1):
    """groups: list of (display, spoken). Spread [t0,t1] by spoken char weight."""
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
    (0.30, split([("GTX 운정중앙역,", "GTX 운정중앙역,")], 0.0, 1.66)
          + split([("서울역까지 22분.", "서울역까지 이십이분.")], 2.0, 3.64)
          + split([("지금 집값은", "지금 집값은"), ("어디쯤 와 있을까요?", "어디쯤 와 있을까요?")], 4.64, 6.89)),
    (7.65, split([("역 도보권", "역 도보권"), ("운정신도시 아이파크", "운정신도시 아이파크"), ("84㎡,", "팔십사제곱미터,")], 0.0, 3.42)
          + split([("지난 10월", "지난 시월"), ("7억 9,500만 원에", "칠억 구천오백만 원에"), ("거래됐습니다.", "거래됐습니다.")], 3.88, 6.87)),
    (14.95, split([("역 앞 신축 시티프라디움은", "역 앞 신축 시티프라디움은"),
                   ("평균 분양가 7억 5천만 원.", "평균 분양가 칠억 오천만 원."),
                   ("3년 전 주변 분양보다", "삼년 전 주변 분양보다"),
                   ("2억 원 비싼데도,", "이억 원 비싼데도,")], 0.0, 6.43)
          + split([("1순위 경쟁률은 42대 1.", "일순위 경쟁률은 사십이대 일.")], 6.80, 8.97)),
    (24.40, split([("다음 열쇠는 삼성역입니다.", "다음 열쇠는 삼성역입니다.")], 0.0, 1.84)
          + split([("국토부는 무정차 통과를", "국토부는 무정차 통과를"), ("내년 상반기로 보고 있습니다.", "내년 상반기로 보고 있습니다.")], 2.86, 6.50)),
    (31.35, split([("다만 대출 규제와", "다만 대출 규제와"), ("입주 물량은 변수.", "입주 물량은 변수.")], 0.0, 2.77)
          + split([("역까지 거리와 실거래가,", "역까지 거리와 실거래가,")], 3.79, 5.55)
          + split([("꼭 비교해 보세요.", "꼭 비교해 보세요.")], 5.82, 6.94)),
]

CAPTIONS = []
for off, groups in LINES:
    for disp, a, b in groups:
        CAPTIONS.append((disp, round(off + a - 0.05, 2), round(off + b + 0.08, 2)))
# no overlaps: each group ends where the next begins at the latest
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

PALETTE = """
  --bg: #0d1322; --panel: #161f35; --panel2: #1d2844; --line: #2b3a5e;
  --ink: #f4f1ea; --muted: #9aa6bd; --violet: #a77bff; --violet-soft: rgba(167,123,255,.18);
  --gold: #f2c14e; --up: #ff7a6b; --ok: #4fd1a5; --warn: #ffb35c;
"""


def scene(cid, dur, css, body, js):
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
.kicker { position: absolute; left: 90px; right: 90px; top: 230px; font-size: 34px; font-weight: 600; color: var(--violet); letter-spacing: .02em; }
.title  { position: absolute; left: 90px; right: 90px; top: 285px; font-size: 92px; font-weight: 800; line-height: 1.08; letter-spacing: -.02em; }
.src    { position: absolute; left: 90px; right: 90px; top: 1040px; font-size: 26px; color: var(--muted); }
"""

# ---------------- Scene 1: hook ----------------
S1_STOPS = [("운정중앙", 0.0), ("킨텍스", 0.27), ("대곡", 0.47), ("연신내", 0.72), ("서울역", 1.0)]
s1_nodes = "\n".join(
    f'    <div class="s1-node" id="s1-n{i}" style="left:{140 + int(800 * p)}px"><span class="dot{" big" if i in (0, 4) else ""}"></span><span class="lab{" strong" if i in (0, 4) else ""}">{n}</span></div>'
    for i, (n, p) in enumerate(S1_STOPS))
s1 = scene("s1", 7.45, COMMON_CSS + """
#s1 .badge { position: absolute; left: 90px; top: 250px; padding: 10px 26px; border-radius: 40px; background: var(--violet); color: #140b2b; font-size: 38px; font-weight: 800; }
#s1 .title { top: 330px; font-size: 150px; }
#s1 .track { position: absolute; left: 140px; width: 800px; top: 700px; height: 10px; border-radius: 6px; background: var(--line); }
#s1 .fill  { position: absolute; left: 140px; width: 800px; top: 700px; height: 10px; border-radius: 6px; background: var(--violet); transform-origin: left center; }
#s1 .s1-node { position: absolute; top: 683px; width: 0; }
#s1 .s1-node .dot { position: absolute; left: -16px; top: 6px; width: 32px; height: 32px; border-radius: 50%; background: var(--bg); border: 6px solid var(--violet); }
#s1 .s1-node .dot.big { left: -24px; top: -2px; width: 48px; height: 48px; background: var(--violet); border-color: #e7dcff; }
#s1 .s1-node .lab { position: absolute; top: 70px; left: -120px; width: 240px; text-align: center; font-size: 32px; color: var(--muted); font-weight: 600; white-space: nowrap; }
#s1 .s1-node .lab.strong { color: var(--ink); font-size: 38px; font-weight: 800; }
#s1 .train { position: absolute; left: 116px; top: 666px; width: 78px; height: 78px; border-radius: 22px; background: #fff; box-shadow: 0 0 40px rgba(167,123,255,.8); display: flex; align-items: center; justify-content: center; font-size: 30px; font-weight: 800; color: #3b1f86; }
#s1 .min { position: absolute; left: 90px; right: 90px; top: 830px; display: flex; align-items: baseline; gap: 18px; }
#s1 .min .pre { font-size: 46px; font-weight: 600; color: var(--muted); }
#s1 .min .num { font-size: 190px; font-weight: 800; color: var(--gold); letter-spacing: -.03em; line-height: 1; }
#s1 .min .unit { font-size: 80px; font-weight: 800; color: var(--gold); }
#s1 .ask { position: absolute; left: 90px; right: 90px; top: 1065px; font-size: 52px; font-weight: 700; color: var(--ink); }
#s1 .ask b { color: var(--gold); }
""", f"""
    <div class="badge" id="s1-badge">GTX-A</div>
    <div class="title" id="s1-title">운정중앙역</div>
    <div class="track"></div>
    <div class="fill" id="s1-fill"></div>
{s1_nodes}
    <div class="train" id="s1-train">A</div>
    <div class="min" id="s1-min"><span class="pre">서울역까지</span><span class="num" id="s1-num">22</span><span class="unit">분</span></div>
    <div class="ask" id="s1-ask">지금 집값은, <b>어디쯤?</b></div>
""", """
      tl.fromTo(q('#s1-title'), { y: 0, scale: 1 }, { scale: 1.03, duration: 7.4, ease: 'none', transformOrigin: 'left center' }, 0);
      tl.fromTo(q('#s1-fill'), { scaleX: 0 }, { scaleX: 1, duration: 3.0, ease: 'power2.inOut' }, 0.4);
      tl.fromTo(q('#s1-train'), { x: 0 }, { x: 800, duration: 3.0, ease: 'power2.inOut' }, 0.4);
      for (let i = 0; i < 5; i++) tl.fromTo(q('#s1-n' + i), { opacity: 0.35 }, { opacity: 1, duration: 0.25 }, 0.4 + [0, .27, .47, .72, 1][i] * 3.0 * 0.92);
      const c = { v: 0 };
      tl.fromTo(c, { v: 0 }, { v: 22, duration: 3.0, ease: 'power2.inOut', onUpdate: () => { q('#s1-num').textContent = Math.round(c.v) || 22; } }, 0.4);
      tl.set(q('#s1-num'), { textContent: 22 }, 3.45);
      tl.fromTo(q('#s1-num'), { scale: 1 }, { scale: 1.12, duration: 0.18, yoyo: true, repeat: 1, ease: 'power2.out', transformOrigin: 'left bottom' }, 3.45);
      tl.fromTo(q('#s1-ask'), { opacity: 0, y: 30 }, { opacity: 1, y: 0, duration: 0.5, ease: 'power3.out' }, 4.75);
""")

# ---------------- Scene 2: IPark price ----------------
s2 = scene("s2", 7.3, COMMON_CSS + """
#s2 .card { position: absolute; left: 70px; right: 70px; top: 400px; height: 560px; border-radius: 36px; background: var(--panel); border: 2px solid var(--line); }
#s2 .name { position: absolute; left: 60px; top: 50px; font-size: 64px; font-weight: 800; }
#s2 .chips { position: absolute; left: 60px; top: 145px; display: flex; gap: 14px; }
#s2 .chip { padding: 8px 22px; border-radius: 30px; background: var(--panel2); color: var(--muted); font-size: 30px; font-weight: 600; }
#s2 .price { position: absolute; left: 60px; top: 230px; font-size: 136px; font-weight: 800; color: var(--gold); letter-spacing: -.03em; line-height: 1; }
#s2 .price small { font-size: 64px; }
#s2 .when { position: absolute; left: 60px; top: 390px; font-size: 32px; color: var(--muted); }
#s2 .from { position: absolute; left: 60px; top: 455px; font-size: 34px; color: var(--ink); font-weight: 600; }
#s2 .from b { color: var(--up); }
#s2 .map { position: absolute; right: 60px; top: 50px; width: 230px; height: 150px; }
#s2 .map .st { position: absolute; left: 10px; top: 92px; width: 34px; height: 34px; border-radius: 50%; background: var(--violet); box-shadow: 0 0 0 10px var(--violet-soft); }
#s2 .map .ap { position: absolute; left: 180px; top: 20px; width: 30px; height: 30px; border-radius: 8px; background: var(--gold); }
#s2 .map svg { position: absolute; inset: 0; }
#s2 .map .ml { position: absolute; left: -60px; top: 140px; width: 300px; white-space: nowrap; text-align: center; font-size: 28px; color: var(--muted); }
""", """
    <div class="kicker" id="s2-k">역 도보권 대표 단지 · 최근 실거래</div>
    <div class="title" id="s2-t">아이파크 84㎡</div>
    <div class="card" id="s2-card">
      <div class="name">운정신도시 아이파크</div>
      <div class="chips"><span class="chip">전용 84㎡</span><span class="chip">23층</span></div>
      <div class="price"><span id="s2-num">7억 9,500</span><small>만</small></div>
      <div class="when">2026.10.24 거래 · 국토부 실거래가</div>
      <div class="from" id="s2-from">2017년 분양가 3억 8,500만 → <b>+4억 1,000만</b></div>
      <div class="map"><svg viewBox="0 0 230 150"><path d="M27 109 C 80 100, 130 60, 195 35" stroke="#9aa6bd" stroke-width="3" stroke-dasharray="6 8" fill="none"/></svg><span class="st"></span><span class="ap"></span><div class="ml">역 ↔ 단지 약 300m</div></div>
    </div>
""", """
      tl.fromTo(q('#s2-k'), { opacity: 0, y: 20 }, { opacity: 1, y: 0, duration: 0.4, ease: 'power3.out' }, 0.05);
      tl.fromTo(q('#s2-t'), { opacity: 0, y: 30 }, { opacity: 1, y: 0, duration: 0.45, ease: 'power3.out' }, 0.15);
      tl.fromTo(q('#s2-card'), { opacity: 0, y: 60 }, { opacity: 1, y: 0, duration: 0.6, ease: 'power3.out' }, 0.35);
      const c = { v: 0 };
      const fmt = (v) => { const e = Math.floor(v / 10000); const m = Math.round(v % 10000); return e + '억 ' + m.toLocaleString('en-US'); };
      tl.fromTo(c, { v: 60000 }, { v: 79500, duration: 1.5, ease: 'power3.out', onUpdate: () => { q('#s2-num').textContent = fmt(c.v); } }, 4.45);
      tl.set(q('#s2-num'), { textContent: '7억 9,500' }, 5.98);
      tl.fromTo(q('#s2-from'), { opacity: 0, x: -20 }, { opacity: 1, x: 0, duration: 0.5, ease: 'power3.out' }, 4.3);
""")

# ---------------- Scene 3: presale vs nearby ----------------
s3 = scene("s3", 9.45, COMMON_CSS + """
#s3 .title { font-size: 78px; }
#s3 .row { position: absolute; left: 90px; right: 90px; }
#s3 .row .lab { font-size: 32px; color: var(--muted); font-weight: 600; }
#s3 .row .bar { margin-top: 14px; height: 96px; border-radius: 18px; transform-origin: left center; display: flex; align-items: center; justify-content: flex-end; padding-right: 28px; font-size: 56px; font-weight: 800; }
#s3 #s3-r1 { top: 520px; } #s3 #s3-r2 { top: 700px; }
#s3 #s3-b1 { width: 520px; background: #3a4a72; color: var(--ink); }
#s3 #s3-b2 { width: 722px; background: var(--gold); color: #2b1d00; }
#s3 .delta { position: absolute; left: 830px; top: 768px; padding: 8px 22px; border-radius: 30px; background: rgba(255,122,107,.16); color: var(--up); font-size: 40px; font-weight: 800; }
#s3 .stamp { position: absolute; left: 90px; right: 90px; top: 880px; height: 200px; border-radius: 30px; background: var(--violet-soft); border: 3px solid var(--violet); display: flex; align-items: center; gap: 30px; padding: 0 44px; }
#s3 .stamp .big { font-size: 120px; font-weight: 800; color: #fff; letter-spacing: -.02em; }
#s3 .stamp .small { font-size: 34px; color: var(--ink); font-weight: 600; line-height: 1.35; }
""", """
    <div class="kicker" id="s3-k">역 앞 신축 · 84㎡ 평균 분양가</div>
    <div class="title" id="s3-t">GTX운정중앙역<br>시티프라디움</div>
    <div class="row" id="s3-r1"><div class="lab">2023.11 주변 분양 (제일풍경채·우미린)</div><div class="bar" id="s3-b1">5.4억</div></div>
    <div class="row" id="s3-r2"><div class="lab">2026.11 시티프라디움 (3·4단지 평균)</div><div class="bar" id="s3-b2">7.5억</div></div>
    <div class="delta" id="s3-d">+2.1억</div>
    <div class="stamp" id="s3-stamp"><span class="big">42 : 1</span><span class="small">1순위<br>평균 경쟁률</span></div>
""", """
      tl.fromTo(q('#s3-k'), { opacity: 0, y: 20 }, { opacity: 1, y: 0, duration: 0.4, ease: 'power3.out' }, 0.05);
      tl.fromTo(q('#s3-t'), { opacity: 0, y: 30 }, { opacity: 1, y: 0, duration: 0.5, ease: 'power3.out' }, 0.15);
      tl.fromTo(q('#s3-r1'), { opacity: 0 }, { opacity: 1, duration: 0.3 }, 1.0);
      tl.fromTo(q('#s3-b1'), { scaleX: 0 }, { scaleX: 1, duration: 0.7, ease: 'power3.out' }, 1.05);
      tl.fromTo(q('#s3-r2'), { opacity: 0 }, { opacity: 1, duration: 0.3 }, 1.6);
      tl.fromTo(q('#s3-b2'), { scaleX: 0 }, { scaleX: 1, duration: 0.9, ease: 'power3.out' }, 1.65);
      tl.fromTo(q('#s3-d'), { opacity: 0, scale: 0.6 }, { opacity: 1, scale: 1, duration: 0.4, ease: 'back.out(2)' }, 4.6);
      tl.fromTo(q('#s3-stamp'), { opacity: 0, scale: 1.25 }, { opacity: 1, scale: 1, duration: 0.45, ease: 'power4.out' }, 6.95);
""")

# ---------------- Scene 4: Samsung station ----------------
S4 = [("운정중앙", "운행 중", 0), ("서울역", "운행 중", 1), ("삼성", "무정차 통과 예정", 2), ("수서", "운행 중", 3), ("동탄", "운행 중", 4)]
s4_nodes = "\n".join(
    f'    <div class="s4-node{" pend" if i == 2 else ""}" id="s4-n{i}" style="top:{470 + i * 125}px"><span class="dot"></span><span class="nm">{n}</span><span class="st">{s}</span></div>'
    for n, s, i in S4)
s4 = scene("s4", 6.95, COMMON_CSS + """
#s4 .title { font-size: 104px; }
#s4 .title b { color: var(--violet); }
#s4 .rail { position: absolute; left: 150px; top: 492px; width: 10px; height: 500px; border-radius: 6px; background: var(--violet); }
#s4 .gap { position: absolute; left: 150px; top: 617px; width: 10px; height: 250px; background: repeating-linear-gradient(var(--bg) 0 14px, transparent 14px 28px); }
#s4 .gapfill { position: absolute; left: 150px; top: 617px; width: 10px; height: 250px; background: var(--gold); transform-origin: center top; }
#s4 .s4-node { position: absolute; left: 0; right: 0; height: 60px; }
#s4 .s4-node .dot { position: absolute; left: 134px; top: 6px; width: 42px; height: 42px; border-radius: 50%; background: var(--bg); border: 8px solid var(--violet); }
#s4 .s4-node .nm { position: absolute; left: 220px; top: -4px; font-size: 52px; font-weight: 800; }
#s4 .s4-node .st { position: absolute; left: 520px; top: 8px; font-size: 32px; color: var(--muted); font-weight: 600; }
#s4 .s4-node.pend .dot { border-color: var(--gold); }
#s4 .s4-node.pend .nm, #s4 .s4-node.pend .st { color: var(--gold); }
#s4 .when { position: absolute; left: 90px; right: 90px; top: 1070px; font-size: 40px; font-weight: 700; }
#s4 .when span { color: var(--gold); }
""", f"""
    <div class="kicker" id="s4-k">GTX-A 전 구간 연결</div>
    <div class="title" id="s4-t">열쇠는 <b>삼성역</b></div>
    <div class="rail"></div>
    <div class="gap"></div>
    <div class="gapfill" id="s4-fill"></div>
{s4_nodes}
    <div class="when" id="s4-w">국토부 예상 · <span>2027년 상반기</span></div>
""", """
      tl.fromTo(q('#s4-k'), { opacity: 0, y: 20 }, { opacity: 1, y: 0, duration: 0.4, ease: 'power3.out' }, 0.05);
      tl.fromTo(q('#s4-t'), { opacity: 0, y: 30 }, { opacity: 1, y: 0, duration: 0.5, ease: 'power3.out' }, 0.15);
      for (let i = 0; i < 5; i++) tl.fromTo(q('#s4-n' + i), { opacity: 0, x: -24 }, { opacity: 1, x: 0, duration: 0.35, ease: 'power3.out' }, 0.5 + i * 0.12);
      tl.fromTo(q('#s4-fill'), { scaleY: 0 }, { scaleY: 1, duration: 1.4, ease: 'power2.inOut' }, 3.0);
      tl.fromTo(q('#s4-n2'), { scale: 1 }, { scale: 1.06, duration: 0.25, yoyo: true, repeat: 1, ease: 'power2.out', transformOrigin: '150px 30px' }, 1.4);
      tl.fromTo(q('#s4-w'), { opacity: 0, y: 24 }, { opacity: 1, y: 0, duration: 0.45, ease: 'power3.out' }, 4.4);
""")

# ---------------- Scene 5: checkpoints ----------------
s5 = scene("s5", 7.2, COMMON_CSS + """
#s5 .item { position: absolute; left: 90px; right: 90px; height: 150px; border-radius: 28px; background: var(--panel); border: 2px solid var(--line); display: flex; align-items: center; gap: 30px; padding: 0 40px; }
#s5 .ic { width: 78px; height: 78px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 50px; font-weight: 800; flex: none; }
#s5 .ic.w { background: rgba(255,179,92,.18); color: var(--warn); }
#s5 .ic.k { background: rgba(79,209,165,.18); color: var(--ok); }
#s5 .tx { font-size: 54px; font-weight: 800; }
#s5 .tx small { display: block; font-size: 30px; color: var(--muted); font-weight: 600; margin-top: 4px; }
#s5 #s5-i1 { top: 470px; } #s5 #s5-i2 { top: 650px; } #s5 #s5-i3 { top: 860px; border-color: var(--ok); }
""", """
    <div class="kicker" id="s5-k">사기 전에</div>
    <div class="title" id="s5-t">체크 포인트</div>
    <div class="item" id="s5-i1"><span class="ic w">!</span><span class="tx">대출 규제<small>매수 여력을 좌우</small></span></div>
    <div class="item" id="s5-i2"><span class="ic w">!</span><span class="tx">주변 입주 물량<small>운정3지구 신축 공급</small></span></div>
    <div class="item" id="s5-i3"><span class="ic k">✓</span><span class="tx">역까지 거리 · 실거래가<small>단지별로 꼭 비교</small></span></div>
""", """
      tl.fromTo(q('#s5-k'), { opacity: 0, y: 20 }, { opacity: 1, y: 0, duration: 0.4, ease: 'power3.out' }, 0.05);
      tl.fromTo(q('#s5-t'), { opacity: 0, y: 30 }, { opacity: 1, y: 0, duration: 0.5, ease: 'power3.out' }, 0.15);
      tl.fromTo(q('#s5-i1'), { opacity: 0, x: -40 }, { opacity: 1, x: 0, duration: 0.45, ease: 'power3.out' }, 0.75);
      tl.fromTo(q('#s5-i2'), { opacity: 0, x: -40 }, { opacity: 1, x: 0, duration: 0.45, ease: 'power3.out' }, 1.9);
      tl.fromTo(q('#s5-i3'), { opacity: 0, x: -40 }, { opacity: 1, x: 0, duration: 0.45, ease: 'power3.out' }, 3.95);
""")

# ---------------- Scene 6: outro ----------------
s6 = scene("s6", 3.65, COMMON_CSS + """
#s6 .logo { position: absolute; left: 50%; top: 250px; width: 440px; margin-left: -220px; border-radius: 44px; box-shadow: 0 24px 60px rgba(0,0,0,.5); }
#s6 .name { position: absolute; left: 60px; right: 60px; top: 745px; text-align: center; font-size: 76px; font-weight: 800; letter-spacing: -.02em; }
#s6 .tel { position: absolute; left: 60px; right: 60px; top: 845px; text-align: center; font-size: 112px; font-weight: 800; color: var(--gold); letter-spacing: -.01em; }
#s6 .ask { position: absolute; left: 60px; right: 60px; top: 990px; text-align: center; font-size: 40px; font-weight: 700; color: var(--violet); }
#s6 .note { position: absolute; left: 60px; right: 60px; top: 1150px; text-align: center; font-size: 28px; color: var(--muted); line-height: 1.55; }
""", """
    <img class="logo" id="s6-logo" src="assets/images/logo.png" alt="현대베스트부동산" />
    <div class="name" id="s6-name">현대베스트부동산</div>
    <div class="tel" id="s6-tel">031-949-6649</div>
    <div class="ask" id="s6-ask">운정중앙역 시세 · 매물 문의</div>
    <div class="note" id="s6-n">투자 권유가 아닌 정보 제공 영상입니다<br>출처: 국토부 실거래가 · 스트레이트뉴스 · 헤럴드경제 · 파이낸셜뉴스</div>
""", """
      tl.fromTo(q('#s6-logo'), { opacity: 0, scale: 0.8 }, { opacity: 1, scale: 1, duration: 0.5, ease: 'back.out(1.8)' }, 0.0);
      tl.fromTo(q('#s6-name'), { opacity: 0, y: 24 }, { opacity: 1, y: 0, duration: 0.4, ease: 'power3.out' }, 0.25);
      tl.fromTo(q('#s6-tel'), { opacity: 0, y: 24 }, { opacity: 1, y: 0, duration: 0.4, ease: 'power3.out' }, 0.4);
      tl.fromTo(q('#s6-ask'), { opacity: 0 }, { opacity: 1, duration: 0.4 }, 0.6);
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
caps = scene("caps", TOTAL, """
#caps .cg { position: absolute; left: 0; right: 0; top: 1150px; text-align: center; overflow: visible; opacity: 0; }
#caps .cg span { display: inline-block; padding: 10px 26px; border-radius: 16px; background: rgba(6,9,18,.62); font-weight: 700; color: #fff; letter-spacing: -.01em; }
""", "\n".join(cap_divs), "\n".join(cap_js))

for name, html in [("s1", s1), ("s2", s2), ("s3", s3), ("s4", s4), ("s5", s5), ("s6", s6), ("caps", caps)]:
    (COMP / f"{name}.html").write_text(html, encoding="utf-8")

# ---------------- Root ----------------
hosts = "\n".join(
    f'      <div id="{cid}" data-composition-id="{cid}" data-composition-src="compositions/{cid}.html" data-start="{a}" data-duration="{round(b - a, 2)}" data-track-index="1" data-track-kind="graphics" data-width="{W}" data-height="{H}" style="z-index:2"></div>'
    for cid, a, b in SCENES)
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
              radial-gradient(900px 700px at 20% 15%, rgba(167,123,255,.20), transparent 70%),
              radial-gradient(800px 800px at 90% 80%, rgba(242,193,78,.10), transparent 70%), var(--bg); }}
      #grid {{ position: absolute; inset: -80px; z-index: 1; opacity: .35;
              background-image: linear-gradient(rgba(255,255,255,.05) 2px, transparent 2px), linear-gradient(90deg, rgba(255,255,255,.05) 2px, transparent 2px);
              background-size: 80px 80px; }}
      #logo {{ position: absolute; right: 36px; top: 178px; width: 170px; height: auto; z-index: 6; border-radius: 22px; box-shadow: 0 10px 30px rgba(0,0,0,.45); }}
      #foot {{ position: absolute; left: 0; right: 0; top: 1360px; z-index: 1; text-align: center; font-family: 'Pretendard', sans-serif; font-size: 28px; color: rgba(154,166,189,.55); font-weight: 600; letter-spacing: .3em; }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{TOTAL}" data-width="{W}" data-height="{H}">
      <div id="bg"></div>
      <div id="grid"></div>
      <div id="foot" data-layout-ignore>PAJU · UNJEONG · GTX-A</div>
      <img id="logo" src="assets/images/logo.png" alt="현대베스트부동산 031-949-6649" />
{hosts}
      <div id="caps" data-composition-id="caps" data-composition-src="compositions/caps.html" data-start="0" data-duration="{TOTAL}" data-track-index="2" data-track-kind="captions" data-width="{W}" data-height="{H}" style="z-index:5"></div>
      <audio id="mix" src="assets/audio/mix.wav" data-start="0" data-duration="{TOTAL}" data-track-index="3"></audio>
    </div>
    <script>
      const tl = gsap.timeline({{ paused: true }});
      tl.to('#logo', {{ opacity: 0, duration: 0.3 }}, 38.2);
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
