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
    ("s1", 0.0, 5.45),
    ("s2", 5.45, 13.85),
    ("s3", 13.85, 21.45),
    ("s4", 21.45, 29.45),
    ("s5", 29.45, 33.9),
    ("s6", 33.9, 42.0),
]

# 2026.05.12 ~ 2026.11.12 MOLIT trades (hogangnono monthly-reports), 힐스테이트운정
STATS = {
    "59": {"sale": 24, "jeon": 54, "wol": 30},
    "84": {"sale": 16, "jeon": 34, "wol": 5},
}


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
    (0.30, split([("요즘 힐스테이트운정에서", "요즘 힐스테이트운정에서")], 0.0, 1.62)
          + split([("가장 바쁜 평형,", "가장 바쁜 평형,")], 1.84, 3.07)
          + split([("59㎡입니다.", "오십구제곱미터입니다.")], 3.40, 4.84)),
    (5.55, split([("최근 6개월 실거래 108건.", "최근 육개월 실거래 백팔건.")], 0.0, 2.41)
          + split([("84㎡의 두 배이고,", "팔십사제곱미터의 두 배이고,")], 3.44, 5.45)
          + split([("월세는 30건 대 5건입니다.", "월세는 삼십건 대 오건입니다.")], 5.80, 8.06)),
    (14.00, split([("GTX로 서울역까지 22분.", "GTX로 서울역까지 이십이분.")], 0.0, 2.44)
          + split([("서울로 출퇴근하는 수요가", "서울로 출퇴근하는 수요가"), ("작은 평형으로 몰리고 있습니다.", "작은 평형으로 몰리고 있습니다.")], 3.45, 7.17)),
    (21.60, split([("59㎡ 매매는 5억 원 안팎,", "오십구제곱미터 매매는 오억 원 안팎,")], 0.0, 1.97)
          + split([("전세는 3억 원대,", "전세는 삼억 원대,")], 2.33, 3.58)
          + split([("월세는 보증금 3천5백에", "월세는 보증금 삼천오백에"), ("130만 원 선입니다.", "백삼십만 원 선입니다.")], 3.95, 7.61)),
    (29.60, split([("2,998세대 대단지에,", "이천구백구십팔 세대 대단지에,")], 0.0, 2.18)
          + split([("단지 안 초등학교까지.", "단지 안 초등학교까지.")], 2.55, 4.09)),
    (34.10, split([("힐스테이트운정 59,", "힐스테이트운정 오십구,")], 0.0, 1.21)
          + split([("매매와 전월세 문의는", "매매와 전월세 문의는"), ("현대베스트부동산으로.", "현대베스트부동산으로.")], 1.36, 4.95)),
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

# ---------------- S1: hook 59㎡ ----------------
s1 = scene("s1", COMMON_CSS + """
#s1 .kicker { top: 330px; font-size: 44px; color: var(--ink); }
#s1 .big { position: absolute; left: 80px; right: 80px; top: 420px; font-size: 330px; font-weight: 800; letter-spacing: -.05em; line-height: 1; color: var(--hill); }
#s1 .big small { font-size: 150px; letter-spacing: -.02em; }
#s1 .sub { position: absolute; left: 90px; right: 90px; top: 790px; font-size: 54px; font-weight: 800; }
#s1 .sub b { color: var(--gold); }
#s1 .tag { position: absolute; left: 90px; top: 900px; padding: 12px 28px; border-radius: 40px; background: var(--hill-soft); border: 2px solid var(--hill); font-size: 36px; font-weight: 700; color: var(--hill); }
""", """
    <div class="kicker" id="s1-k">힐스테이트운정, 요즘 가장 바쁜 평형</div>
    <div class="big" id="s1-big">59<small>㎡</small></div>
    <div class="sub" id="s1-sub">매매 · 전세 · 월세 <b>모두 활발</b></div>
    <div class="tag" id="s1-tag">25평형</div>
""", f"""
      tl.fromTo(q('#s1-big'), {{ scale: 1 }}, {{ scale: 1.05, duration: 5.4, ease: 'none', transformOrigin: 'left center' }}, 0);
      tl.fromTo(q('#s1-sub'), {UP}, 2.0);
      tl.fromTo(q('#s1-tag'), {{ opacity: 0, scale: 0.7 }}, {{ opacity: 1, scale: 1, duration: 0.35, ease: 'back.out(2)' }}, 3.6);
""")

# ---------------- S2: 6-month volume ----------------
PX_PER = 860 / 108
def seg(n, cls, label):
    return f'<span class="sg {cls}" style="width:{int(n * PX_PER)}px">{label if n >= 12 else ""}</span>'
r59 = STATS["59"]; r84 = STATS["84"]
t59 = sum(r59.values()); t84 = sum(r84.values())
s2 = scene("s2", COMMON_CSS + """
#s2 .title { font-size: 84px; }
#s2 .row { position: absolute; left: 90px; right: 90px; }
#s2 .row .lab { font-size: 40px; font-weight: 800; display: flex; align-items: baseline; gap: 16px; }
#s2 .row .lab b { font-size: 64px; color: var(--gold); }
#s2 .row .lab small { font-size: 30px; color: var(--muted); font-weight: 600; }
#s2 .bar { margin-top: 12px; height: 92px; border-radius: 18px; overflow: hidden; display: flex; transform-origin: left center; }
#s2 .sg { height: 100%; display: flex; align-items: center; justify-content: center; font-size: 30px; font-weight: 800; color: #0c1519; }
#s2 .sg.s { background: var(--gold); } #s2 .sg.j { background: var(--hill); } #s2 .sg.w { background: var(--pru); }
#s2 #s2-r59 { top: 440px; } #s2 #s2-r84 { top: 650px; }
#s2 .legend { position: absolute; left: 90px; right: 90px; top: 870px; display: flex; gap: 30px; font-size: 32px; font-weight: 700; }
#s2 .legend i { display: inline-block; width: 26px; height: 26px; border-radius: 6px; margin-right: 10px; vertical-align: -3px; }
#s2 .x2 { position: absolute; right: 90px; top: 430px; padding: 10px 26px; border-radius: 34px; background: var(--gold); color: #2b1d00; font-size: 48px; font-weight: 800; }
#s2 .wol { position: absolute; left: 90px; right: 90px; top: 960px; height: 120px; border-radius: 24px; background: rgba(143,168,255,.14); border: 2px solid var(--pru); display: flex; align-items: center; justify-content: space-between; padding: 0 36px; }
#s2 .wol span { font-size: 38px; font-weight: 800; }
#s2 .wol b { font-size: 60px; font-weight: 800; color: var(--pru); }
#s2 .note { position: absolute; left: 90px; right: 90px; top: 1100px; font-size: 28px; color: var(--muted); }
""", f"""
    <div class="kicker" id="s2-k">최근 6개월 · 실거래 건수</div>
    <div class="title" id="s2-t">59㎡가 2배</div>
    <div class="row" id="s2-r59"><div class="lab">59㎡ <b>{t59}건</b><small>매매 {r59['sale']} · 전세 {r59['jeon']} · 월세 {r59['wol']}</small></div><div class="bar" id="s2-b59">{seg(r59['sale'],'s','매매')}{seg(r59['jeon'],'j','전세')}{seg(r59['wol'],'w','월세')}</div></div>
    <div class="row" id="s2-r84"><div class="lab">84㎡ <b>{t84}건</b><small>매매 {r84['sale']} · 전세 {r84['jeon']} · 월세 {r84['wol']}</small></div><div class="bar" id="s2-b84">{seg(r84['sale'],'s','매매')}{seg(r84['jeon'],'j','전세')}{seg(r84['wol'],'w','')}</div></div>
    <div class="legend"><span><i style="background:var(--gold)"></i>매매</span><span><i style="background:var(--hill)"></i>전세</span><span><i style="background:var(--pru)"></i>월세</span></div>
    <div class="wol" id="s2-wol"><span>월세 거래</span><b>{r59['wol']} : {r84['wol']}</b></div>
""", f"""
      tl.fromTo(q('#s2-k'), {UP}, 0.05);
      tl.fromTo(q('#s2-t'), {UP}, 0.15);
      tl.fromTo(q('#s2-r59'), {{ opacity: 0 }}, {{ opacity: 1, duration: 0.25 }}, 0.5);
      tl.fromTo(q('#s2-b59'), {{ scaleX: 0 }}, {{ scaleX: 1, duration: 1.0, ease: 'power3.out' }}, 0.55);
      tl.fromTo(q('#s2-r84'), {{ opacity: 0 }}, {{ opacity: 1, duration: 0.25 }}, 3.3);
      tl.fromTo(q('#s2-b84'), {{ scaleX: 0 }}, {{ scaleX: 1, duration: 0.8, ease: 'power3.out' }}, 3.35);
      tl.fromTo(q('#s2-wol'), {{ opacity: 0, y: 30 }}, {{ opacity: 1, y: 0, duration: 0.45, ease: 'power3.out' }}, 5.9);
""")

# ---------------- S3: Seoul commute ----------------
s3 = scene("s3", COMMON_CSS + """
#s3 .title { font-size: 84px; }
#s3 .track { position: absolute; left: 150px; width: 780px; top: 560px; height: 12px; border-radius: 6px; background: var(--hill); transform-origin: left center; }
#s3 .st { position: absolute; top: 538px; width: 56px; height: 56px; border-radius: 50%; background: var(--bg); border: 10px solid var(--hill); }
#s3 .st.a { left: 122px; } #s3 .st.b { left: 902px; background: var(--hill); }
#s3 .nm { position: absolute; top: 620px; font-size: 40px; font-weight: 800; width: 300px; }
#s3 .nm.a { left: 70px; } #s3 .nm.b { left: 800px; text-align: right; width: 230px; }
#s3 .min { position: absolute; left: 0; right: 0; top: 430px; text-align: center; font-size: 96px; font-weight: 800; color: var(--gold); }
#s3 .flow { position: absolute; left: 90px; right: 90px; top: 790px; display: flex; align-items: center; gap: 24px; }
#s3 .box { flex: 1; height: 190px; border-radius: 28px; background: var(--panel); border: 2px solid var(--line); display: flex; flex-direction: column; align-items: center; justify-content: center; font-size: 44px; font-weight: 800; text-align: center; line-height: 1.25; }
#s3 .box small { font-size: 30px; color: var(--muted); font-weight: 600; margin-top: 8px; }
#s3 .box.me { border-color: var(--hill); background: var(--hill-soft); color: var(--hill); }
#s3 .arr { font-size: 70px; color: var(--gold); font-weight: 800; }
""", """
    <div class="kicker" id="s3-k">GTX-A 운정중앙역</div>
    <div class="title" id="s3-t">서울 출퇴근</div>
    <div class="min" id="s3-min">22분</div>
    <div class="track" id="s3-track"></div>
    <div class="st a"></div><div class="st b" id="s3-sb"></div>
    <div class="nm a">운정중앙</div><div class="nm b">서울역</div>
    <div class="flow" id="s3-flow"><div class="box">서울 출퇴근<small>세입자 · 실수요</small></div><div class="arr">→</div><div class="box me">59㎡<small>작은 평형</small></div></div>
""", f"""
      tl.fromTo(q('#s3-k'), {UP}, 0.05);
      tl.fromTo(q('#s3-t'), {UP}, 0.15);
      tl.fromTo(q('#s3-track'), {{ scaleX: 0 }}, {{ scaleX: 1, duration: 1.6, ease: 'power2.inOut' }}, 0.4);
      tl.fromTo(q('#s3-sb'), {{ scale: 0.6 }}, {{ scale: 1, duration: 0.3, ease: 'back.out(2)' }}, 1.95);
      tl.fromTo(q('#s3-min'), {{ opacity: 0, scale: 0.8 }}, {{ opacity: 1, scale: 1, duration: 0.4, ease: 'back.out(1.8)' }}, 1.7);
      tl.fromTo(q('#s3-flow'), {{ opacity: 0, y: 40 }}, {{ opacity: 1, y: 0, duration: 0.5, ease: 'power3.out' }}, 3.5);
""")

# ---------------- S4: 59㎡ prices ----------------
CARDS = [
    ("매매", "4.95", "억", "중간값 · 4.68~5.4억 · 24건", "gold"),
    ("전세", "3.1", "억", "중간값 · 최근 3.5억 · 54건", "hill"),
    ("월세", "3,500 / 130", "", "보증금 / 월(만원) 중간값 · 30건", "pru"),
]
s4_cards = "\n".join(
    f'    <div class="cd" id="s4-c{i}" style="top:{420 + (i - 1) * 215}px"><span class="kd {c}">{k}</span><span class="v">{v}<small>{u}</small></span><span class="n">{n}</span></div>'
    for i, (k, v, u, n, c) in enumerate(CARDS, 1))
s4 = scene("s4", COMMON_CSS + """
#s4 .title { font-size: 80px; }
#s4 .cd { position: absolute; left: 70px; right: 70px; height: 190px; border-radius: 28px; background: var(--panel); border: 2px solid var(--line); }
#s4 .kd { position: absolute; left: 36px; top: 34px; padding: 6px 22px; border-radius: 24px; font-size: 32px; font-weight: 800; color: #0c1519; }
#s4 .kd.gold { background: var(--gold); } #s4 .kd.hill { background: var(--hill); } #s4 .kd.pru { background: var(--pru); }
#s4 .v { position: absolute; right: 40px; top: 22px; font-size: 92px; font-weight: 800; letter-spacing: -.02em; }
#s4 .v small { font-size: 46px; }
#s4 .n { position: absolute; left: 36px; right: 40px; bottom: 26px; font-size: 28px; color: var(--muted); font-weight: 600; }
#s4 .note { position: absolute; left: 90px; right: 90px; top: 1075px; font-size: 28px; color: var(--muted); }
""", """
    <div class="kicker" id="s4-k">힐스테이트운정 59㎡ · 최근 6개월</div>
    <div class="title" id="s4-t">얼마에 거래됐나</div>
""" + s4_cards, f"""
      tl.fromTo(q('#s4-k'), {UP}, 0.0);
      tl.fromTo(q('#s4-t'), {UP}, 0.1);
      tl.fromTo(q('#s4-c1'), {{ opacity: 0, x: 50 }}, {{ opacity: 1, x: 0, duration: 0.4, ease: 'power3.out' }}, 0.35);
      tl.fromTo(q('#s4-c2'), {{ opacity: 0, x: 50 }}, {{ opacity: 1, x: 0, duration: 0.4, ease: 'power3.out' }}, 2.45);
      tl.fromTo(q('#s4-c3'), {{ opacity: 0, x: 50 }}, {{ opacity: 1, x: 0, duration: 0.4, ease: 'power3.out' }}, 4.05);
""")

# ---------------- S5: complex strengths ----------------
s5 = scene("s5", COMMON_CSS + """
#s5 .title { font-size: 84px; color: var(--hill); }
#s5 .chip { position: absolute; left: 70px; right: 70px; height: 150px; border-radius: 28px; background: var(--hill-soft); border: 2px solid var(--hill); display: flex; align-items: center; gap: 26px; padding: 0 36px; font-size: 56px; font-weight: 800; }
#s5 .chip i { font-style: normal; width: 66px; height: 66px; border-radius: 50%; background: var(--hill); color: #0c1519; display: flex; align-items: center; justify-content: center; font-size: 38px; flex: none; }
#s5 .chip small { display: block; font-size: 30px; color: var(--muted); font-weight: 600; }
#s5 #s5-c1 { top: 470px; } #s5 #s5-c2 { top: 650px; } #s5 #s5-c3 { top: 830px; }
""", """
    <div class="kicker" id="s5-k">2018년 입주</div>
    <div class="title" id="s5-t">힐스테이트운정</div>
    <div class="chip" id="s5-c1"><i>✓</i><span>2,998세대<small>대단지</small></span></div>
    <div class="chip" id="s5-c2"><i>✓</i><span>단지 안 초등학교<small>산내초</small></span></div>
    <div class="chip" id="s5-c3"><i>✓</i><span>운정중앙역<small>도보권</small></span></div>
""", f"""
      tl.fromTo(q('#s5-k'), {UP}, 0.0);
      tl.fromTo(q('#s5-t'), {UP}, 0.1);
      tl.fromTo(q('#s5-c1'), {{ opacity: 0, x: -40 }}, {{ opacity: 1, x: 0, duration: 0.4, ease: 'power3.out' }}, 0.25);
      tl.fromTo(q('#s5-c2'), {{ opacity: 0, x: -40 }}, {{ opacity: 1, x: 0, duration: 0.4, ease: 'power3.out' }}, 2.7);
      tl.fromTo(q('#s5-c3'), {{ opacity: 0, x: -40 }}, {{ opacity: 1, x: 0, duration: 0.4, ease: 'power3.out' }}, 3.2);
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
    <div class="ask" id="s6-ask">힐스테이트운정 59㎡ 매매 · 전월세 문의</div>
    <div class="name" id="s6-name">현대베스트부동산</div>
    <div class="tel" id="s6-tel">031-949-6649</div>
    <div class="note" id="s6-n">실거래: 국토부(2026.5.12~11.12) · 투자 권유 아님</div>
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
