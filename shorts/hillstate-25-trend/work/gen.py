#!/usr/bin/env python3
"""힐스테이트운정 25평형 3개월 실거래 추이 쇼츠 (HyperFrames).

Run from the project root, in order:
  python3 work/tts.py   # narration phrases -> work/ph/*.wav, work/durs.json
  python3 work/mix.py   # timeline.json + assets/audio/mix.wav
  python3 work/gen.py   # index.html + compositions/*.html
Numbers come from work/stats.py (asil.kr = 국토부 실거래, 11/24 신고분까지).
"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "work"))
from stats import S  # noqa: E402

COMP = ROOT / "compositions"
COMP.mkdir(exist_ok=True)
W, H = 1080, 1920

TL = json.loads((ROOT / "work/timeline.json").read_text())
TOTAL = TL["total"]
PHR = TL["phr"]

order = []
for p in PHR:
    if p["scene"] not in order:
        order.append(p["scene"])
first = {s: min(p["a"] for p in PHR if p["scene"] == s) for s in order}
SCENES = []
for i, s in enumerate(order):
    a = 0.0 if i == 0 else round(first[s] - 0.2, 2)
    b = TOTAL if i == len(order) - 1 else round(first[order[i + 1]] - 0.2, 2)
    SCENES.append((s, a, b))
START = {s: a for s, a, _ in SCENES}


def at(scene, k):
    """local time (in scene) of k-th phrase of scene"""
    ps = [p for p in PHR if p["scene"] == scene]
    return round(ps[k]["a"] - START[scene], 2)


A, B = S["A"], S["B"]


def won(v):  # 50500 -> "5억 500"
    e, r = divmod(int(v), 10000)
    return f"{e}억 {r:,}" if r else f"{e}억"


FONT_FACE = """
@font-face { font-family: 'Pretendard'; src: url('assets/fonts/Pretendard-Regular.woff2') format('woff2'); font-weight: 400; }
@font-face { font-family: 'Pretendard'; src: url('assets/fonts/Pretendard-SemiBold.woff2') format('woff2'); font-weight: 600; }
@font-face { font-family: 'Pretendard'; src: url('assets/fonts/Pretendard-Bold.woff2') format('woff2'); font-weight: 700; }
@font-face { font-family: 'Pretendard'; src: url('assets/fonts/Pretendard-ExtraBold.woff2') format('woff2'); font-weight: 800; }
"""
PALETTE = """
  --bg: #0c1519; --panel: #13232a; --line: #27424c;
  --ink: #f3f1ea; --muted: #93a7ad; --hill: #3fd0b0; --hill-soft: rgba(63,208,176,.16);
  --gold: #f2c14e; --pru: #8fa8ff; --up: #ff7a6b;
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


COMMON = """
.kicker { position: absolute; left: 90px; right: 280px; top: 230px; font-size: 36px; font-weight: 700; color: var(--hill); }
.title  { position: absolute; left: 90px; right: 90px; top: 290px; font-size: 90px; font-weight: 800; line-height: 1.08; letter-spacing: -.02em; }
.badge { display: inline-block; padding: 6px 22px; border-radius: 24px; font-size: 32px; font-weight: 800; color: #0c1519; }
.fine { position: absolute; left: 90px; right: 90px; top: 1290px; font-size: 26px; color: var(--muted); font-weight: 600; }
"""
UP = "{ opacity: 0, y: 24 }, { opacity: 1, y: 0, duration: 0.45, ease: 'power3.out' }"
POP = "{ opacity: 0, scale: 0.8 }, { opacity: 1, scale: 1, duration: 0.4, ease: 'back.out(1.8)' }"

# ---------------- S1: hook + 6-month stacked bars ----------------
MON = ["6월", "7월", "8월", "9월", "10월", "11월"]
mx = max(sum(m.values()) for m in S["monthly"])
BAR_H = 470
bars = []
for i, (m, lab) in enumerate(zip(S["monthly"], MON)):
    tot = sum(m.values())
    segs = "".join(
        f'<span class="sg {c}" style="height:{round(m[k] / mx * BAR_H)}px"></span>'
        for k, c in (("월세", "w"), ("전세", "j"), ("매매", "s")))
    grp = "a" if i < 3 else "b"
    bars.append(f'<div class="col {grp}" id="s1-c{i}"><div class="n">{tot}</div><div class="stk">{segs}</div><div class="m">{lab}{"*" if i == 5 else ""}</div></div>')
s1 = scene("s1", COMMON + f"""
#s1 .title {{ font-size: 96px; }}
#s1 .title b {{ color: var(--gold); }}
#s1 .chart {{ position: absolute; left: 90px; right: 90px; top: 560px; height: {BAR_H + 120}px; display: flex; align-items: flex-end; gap: 22px; }}
#s1 .col {{ flex: 1; display: flex; flex-direction: column; align-items: center; }}
#s1 .col .n {{ font-size: 36px; font-weight: 800; margin-bottom: 8px; }}
#s1 .col .stk {{ width: 100%; display: flex; flex-direction: column-reverse; border-radius: 14px; overflow: hidden; transform-origin: bottom center; }}
#s1 .col.a {{ opacity: .55; }}
#s1 .sg.s {{ background: var(--gold); }} #s1 .sg.j {{ background: var(--hill); }} #s1 .sg.w {{ background: var(--pru); }}
#s1 .col .m {{ margin-top: 12px; font-size: 32px; font-weight: 700; color: var(--muted); }}
#s1 .grp {{ position: absolute; top: 500px; width: 420px; text-align: center; font-size: 34px; font-weight: 800; }}
#s1 .grp.a {{ left: 90px; color: var(--muted); }} #s1 .grp.b {{ right: 90px; color: var(--gold); }}
#s1 .legend {{ position: absolute; left: 90px; right: 90px; top: 1210px; display: flex; gap: 30px; font-size: 30px; font-weight: 700; }}
#s1 .legend i {{ display: inline-block; width: 24px; height: 24px; border-radius: 6px; margin-right: 10px; vertical-align: -3px; }}
""", f"""
    <div class="kicker" id="s1-k">힐스테이트운정 25평형 · 실거래</div>
    <div class="title" id="s1-t">3개월 <b>{B['total']}건</b></div>
    <div class="grp a" id="s1-ga">6~8월 {A['total']}건</div>
    <div class="grp b" id="s1-gb">9~11월 {B['total']}건</div>
    <div class="chart">{''.join(bars)}</div>
    <div class="legend"><span><i style="background:var(--gold)"></i>매매</span><span><i style="background:var(--hill)"></i>전세</span><span><i style="background:var(--pru)"></i>월세</span></div>
    <div class="fine" style="top:1270px">* 11월은 24일 신고분까지</div>
""", f"""
      tl.fromTo(q('#s1-k'), {UP}, 0.05);
      tl.fromTo(q('#s1-t'), {POP}, 0.15);
""" + "".join(
    f"      tl.fromTo(q('#s1-c{i} .stk'), {{ scaleY: 0 }}, {{ scaleY: 1, duration: 0.5, ease: 'power3.out' }}, {0.5 + i * 0.12:.2f});\n"
    f"      tl.fromTo(q('#s1-c{i} .n'), {{ opacity: 0 }}, {{ opacity: 1, duration: 0.2 }}, {0.8 + i * 0.12:.2f});\n"
    for i in range(6)) + f"""
      tl.fromTo(q('#s1-ga'), {UP}, {at('s1', 2)});
      tl.fromTo(q('#s1-gb'), {UP}, {at('s1', 2) + 0.4});
""")

# ---------------- S2/S3/S4: compare cards ----------------
CMP_CSS = COMMON + """
.cmp { position: absolute; left: 70px; right: 70px; top: 470px; height: 330px; display: flex; align-items: center; gap: 20px; }
.cmp .bx { flex: 1; height: 100%; border-radius: 30px; background: var(--panel); border: 2px solid var(--line); display: flex; flex-direction: column; align-items: center; justify-content: center; }
.cmp .bx.now { border-color: var(--gold); background: rgba(242,193,78,.10); }
.cmp .bx small { font-size: 32px; font-weight: 700; color: var(--muted); }
.cmp .bx b { font-size: 84px; font-weight: 800; letter-spacing: -.03em; margin-top: 6px; }
.cmp .bx.now b { color: var(--gold); }
.cmp .bx em { font-style: normal; font-size: 30px; color: var(--muted); font-weight: 600; margin-top: 6px; }
.cmp .ar { font-size: 64px; font-weight: 800; color: var(--gold); }
.delta { position: absolute; left: 0; right: 0; top: 830px; text-align: center; }
.delta span { display: inline-block; padding: 12px 36px; border-radius: 40px; background: var(--up); color: #fff; font-size: 52px; font-weight: 800; }
.delta span.flat { background: var(--line); color: var(--ink); }
.info { position: absolute; left: 70px; right: 70px; top: 960px; height: 150px; border-radius: 28px; background: var(--hill-soft); border: 2px solid var(--hill); display: flex; align-items: center; justify-content: space-between; padding: 0 40px; }
.info span { font-size: 38px; font-weight: 800; }
.info b { font-size: 54px; font-weight: 800; color: var(--hill); }
.info b small { font-size: 32px; color: var(--muted); margin-left: 10px; }
"""


def cmp(cid, a_val, b_val, a_note, b_note, unit=""):
    return f"""    <div class="cmp" id="{cid}-cmp"><div class="bx" id="{cid}-a"><small>6~8월</small><b>{a_val}{unit}</b><em>{a_note}</em></div><div class="ar">→</div><div class="bx now" id="{cid}-b"><small>9~11월</small><b>{b_val}{unit}</b><em>{b_note}</em></div></div>"""


def cmp_js(cid, ta, tb, tdelta, tinfo):
    return f"""
      tl.fromTo(q('#{cid}-k'), {UP}, 0.0);
      tl.fromTo(q('#{cid}-t'), {UP}, 0.1);
      tl.fromTo(q('#{cid}-a'), {{ opacity: 0, x: -40 }}, {{ opacity: 1, x: 0, duration: 0.4, ease: 'power3.out' }}, {ta});
      tl.fromTo(q('#{cid}-b'), {{ opacity: 0, x: 40 }}, {{ opacity: 1, x: 0, duration: 0.4, ease: 'power3.out' }}, {tb});
      tl.fromTo(q('#{cid}-d'), {POP}, {tdelta});
      tl.fromTo(q('#{cid}-i'), {UP}, {tinfo});
"""


s2 = scene("s2", CMP_CSS, f"""
    <div class="kicker" id="s2-k">매매 · 중간값</div>
    <div class="title" id="s2-t"><span class="badge" style="background:var(--gold);font-size:44px;vertical-align:14px">매매</span> {A['sale']}건 → {B['sale']}건</div>
{cmp('s2', won(A['sale_med']), won(B['sale_med']), f"{A['sale']}건", f"{B['sale']}건")}
    <div class="delta" id="s2-d"><span>▲ {(B['sale_med'] - A['sale_med']):,.0f}만 원</span></div>
    <div class="info" id="s2-i"><span>최고가 · 10월</span><b>{won(S['top']['val'])}<small>{S['top']['floor']}</small></b></div>
    <div class="fine">만 원 단위 · 취소 건 제외</div>
""", cmp_js("s2", 0.3, at("s2", 1), at("s2", 2), at("s2", 3)))

s3 = scene("s3", CMP_CSS + """
#s3 .split { position: absolute; left: 70px; right: 70px; top: 960px; height: 150px; border-radius: 28px; overflow: hidden; display: flex; }
#s3 .split div { display: flex; align-items: center; justify-content: center; font-size: 38px; font-weight: 800; color: #0c1519; transform-origin: left center; }
#s3 .split .n { background: var(--hill); } #s3 .split .r { background: var(--pru); }
""", f"""
    <div class="kicker" id="s3-k">전세 · 신규 계약 중간값</div>
    <div class="title" id="s3-t"><span class="badge" style="background:var(--hill);font-size:44px;vertical-align:14px">전세</span> {A['jeon']}건 → {B['jeon']}건</div>
{cmp('s3', won(A['jeon_new_med']), won(B['jeon_new_med']), f"신규 {A['jeon_new']}건", f"신규 {B['jeon_new']}건")}
    <div class="delta" id="s3-d"><span>▲ {(B['jeon_new_med'] - A['jeon_new_med']):,.0f}만 원</span></div>
    <div class="split" id="s3-i"><div class="n" style="flex:{B['jeon_new']}">신규 {B['jeon_new']}건</div><div class="r" style="flex:{B['jeon_renew']}">갱신 {B['jeon_renew']}건</div></div>
    <div class="fine">9~11월 기준 · 갱신 계약은 중간값에서 제외</div>
""", cmp_js("s3", 0.3, at("s3", 1), at("s3", 2), at("s3", 3)))

s4 = scene("s4", CMP_CSS + "#s4 .cmp { top: 530px; } #s4 .delta { top: 890px; } #s4 .info { top: 1020px; }", f"""
    <div class="kicker" id="s4-k">월세 · 거래 건수</div>
    <div class="title" id="s4-t" style="right:280px;font-size:84px"><span class="badge" style="background:var(--pru);font-size:44px;vertical-align:14px">월세</span> 제일 많이<br/>늘었어요</div>
{cmp('s4', A['wol'], B['wol'], '전체 월세', '전체 월세', '건')}
    <div class="delta" id="s4-d"><span>▲ {B['wol'] - A['wol']}건</span></div>
    <div class="info" id="s4-i"><span>보증금 3천 기준 월세</span><b>{A['wol3_med']} → {B['wol3_med']}<small>만 원</small></b></div>
    <div class="fine">월세 금액은 보증금 3,000만 원 신규 계약 중간값 ({len(A['wol3'])}건 → {len(B['wol3'])}건)</div>
""", cmp_js("s4", 0.3, at("s4", 1) - 0.4, at("s4", 1) + 0.5, at("s4", 2)))

# ---------------- S5: summary ----------------
s5 = scene("s5", COMMON + """
#s5 .row { position: absolute; left: 70px; right: 70px; height: 140px; border-radius: 28px; background: var(--panel); border: 2px solid var(--line); display: flex; align-items: center; justify-content: space-between; padding: 0 40px; }
#s5 .row span { font-size: 44px; font-weight: 800; }
#s5 .row b { font-size: 52px; font-weight: 800; color: var(--up); }
#s5 #s5-r1 { top: 470px; } #s5 #s5-r2 { top: 630px; } #s5 #s5-r3 { top: 790px; }
#s5 .warn { position: absolute; left: 70px; right: 70px; top: 970px; padding: 30px 40px; border-radius: 28px; border: 2px dashed var(--gold); font-size: 38px; font-weight: 700; line-height: 1.4; color: var(--gold); }
""", f"""
    <div class="kicker" id="s5-k">9~11월 정리 · 직전 3개월 대비</div>
    <div class="title" id="s5-t">한눈에 보기</div>
    <div class="row" id="s5-r1"><span>매매 중간값</span><b>▲ {(B['sale_med'] - A['sale_med']):,.0f}만</b></div>
    <div class="row" id="s5-r2"><span>전세 신규 중간값</span><b>▲ {(B['jeon_new_med'] - A['jeon_new_med']):,.0f}만</b></div>
    <div class="row" id="s5-r3"><span>월세 거래</span><b>▲ {B['wol'] - A['wol']}건</b></div>
    <div class="warn" id="s5-w">11월은 아직 신고 기간이라<br/>건수가 더 늘 수 있어요</div>
""", f"""
      tl.fromTo(q('#s5-k'), {UP}, 0.0);
      tl.fromTo(q('#s5-t'), {UP}, 0.1);
      tl.fromTo(q('#s5-r1'), {{ opacity: 0, x: -40 }}, {{ opacity: 1, x: 0, duration: 0.35, ease: 'power3.out' }}, 0.25);
      tl.fromTo(q('#s5-r2'), {{ opacity: 0, x: -40 }}, {{ opacity: 1, x: 0, duration: 0.35, ease: 'power3.out' }}, 0.45);
      tl.fromTo(q('#s5-r3'), {{ opacity: 0, x: -40 }}, {{ opacity: 1, x: 0, duration: 0.35, ease: 'power3.out' }}, 0.65);
      tl.fromTo(q('#s5-w'), {UP}, 0.9);
""")

# ---------------- S6: outro ----------------
s6 = scene("s6", """
#s6 .logo { position: absolute; left: 50%; top: 250px; width: 440px; margin-left: -220px; border-radius: 44px; box-shadow: 0 24px 60px rgba(0,0,0,.5); }
#s6 .ask { position: absolute; left: 60px; right: 60px; top: 735px; text-align: center; font-size: 46px; font-weight: 800; color: var(--hill); }
#s6 .name { position: absolute; left: 60px; right: 60px; top: 810px; text-align: center; font-size: 76px; font-weight: 800; letter-spacing: -.02em; }
#s6 .tel { position: absolute; left: 60px; right: 60px; top: 905px; text-align: center; font-size: 112px; font-weight: 800; color: var(--gold); }
#s6 .note { position: absolute; left: 60px; right: 60px; top: 1290px; text-align: center; font-size: 26px; color: var(--muted); line-height: 1.5; }
""", """
    <img class="logo" id="s6-logo" src="assets/images/logo.png" alt="현대베스트부동산" />
    <div class="ask" id="s6-ask">힐스테이트운정 25평형 매매 · 전월세 상담</div>
    <div class="name" id="s6-name">현대베스트부동산</div>
    <div class="tel" id="s6-tel">031-949-6649</div>
    <div class="note" id="s6-n">국토부 실거래(아실) 2026.6.1~11.24 신고분 · 전용 59·60㎡<br/>취소 건 제외 · 시세 예측·투자 권유 아님</div>
""", """
      tl.fromTo(q('#s6-logo'), { opacity: 0, scale: 0.8 }, { opacity: 1, scale: 1, duration: 0.5, ease: 'back.out(1.8)' }, 0.0);
      tl.fromTo(q('#s6-ask'), { opacity: 0, y: 20 }, { opacity: 1, y: 0, duration: 0.4, ease: 'power3.out' }, 0.25);
      tl.fromTo(q('#s6-name'), { opacity: 0, y: 24 }, { opacity: 1, y: 0, duration: 0.4, ease: 'power3.out' }, 0.4);
      tl.fromTo(q('#s6-tel'), { opacity: 0, y: 24 }, { opacity: 1, y: 0, duration: 0.4, ease: 'power3.out' }, 0.55);
      tl.fromTo(q('#s6-tel'), { scale: 1 }, { scale: 1.06, duration: 0.3, yoyo: true, repeat: 1, ease: 'power2.out' }, 3.6);
      tl.fromTo(q('#s6-n'), { opacity: 0 }, { opacity: 1, duration: 0.4 }, 0.7);
""")


# ---------------- Captions ----------------
def cap_size(text, base=62, minimum=44, maxw=920):
    est = sum(0.28 if c == " " else 0.3 if c in ",." else 0.58 if c.isascii() else 1.0 for c in text)
    size = base
    while size > minimum and est * size > maxw:
        size -= 2
    return size


cap_divs, cap_js = [], []
for i, p in enumerate(PHR):
    if p["scene"] == "s6":
        continue
    plain = p["text"].replace("[[", "").replace("]]", "")
    html = re.sub(r"\[\[(.+?)\]\]", r"<b>\1</b>", p["text"])
    a = round(p["a"] - 0.05, 2)
    b = round(p["b"] + 0.12, 2)
    if i + 1 < len(PHR):
        b = min(b, round(PHR[i + 1]["a"] - 0.05, 2))
    cap_divs.append(f'    <div class="cg" id="cap-{i}"><span style="font-size:{cap_size(plain)}px">{html}</span></div>')
    cap_js.append(
        f"      tl.fromTo(q('#cap-{i}'), {{ opacity: 0, y: 14 }}, {{ opacity: 1, y: 0, duration: 0.14, ease: 'power2.out' }}, {a});\n"
        f"      tl.to(q('#cap-{i}'), {{ opacity: 0, duration: 0.08 }}, {round(b - 0.08, 2)});\n"
        f"      tl.set(q('#cap-{i}'), {{ opacity: 0, visibility: 'hidden' }}, {b});")
caps = scene("caps", """
#caps .cg { position: absolute; left: 0; right: 0; top: 1390px; text-align: center; opacity: 0; }
#caps .cg span { display: inline-block; padding: 12px 28px; border-radius: 18px; background: rgba(4,10,12,.72); font-weight: 700; color: #fff; letter-spacing: -.01em; }
#caps .cg b { color: #FFD43B; font-weight: 800; }
""", "\n".join(cap_divs), "\n".join(cap_js))

for name, html in [("s1", s1), ("s2", s2), ("s3", s3), ("s4", s4), ("s5", s5), ("s6", s6), ("caps", caps)]:
    (COMP / f"{name}.html").write_text(html, encoding="utf-8")

hosts = "\n".join(
    f'      <div id="{cid}" data-composition-id="{cid}" data-composition-src="compositions/{cid}.html" data-start="{a}" data-duration="{round(b - a, 2)}" data-track-index="1" data-track-kind="graphics" data-width="{W}" data-height="{H}" style="z-index:2"></div>'
    for cid, a, b in SCENES)
outro_start = START["s6"]
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
      #logo {{ position: absolute; right: 36px; top: 178px; width: 170px; height: auto; z-index: 6; border-radius: 22px; box-shadow: 0 10px 30px rgba(0,0,0,.45); }}
      #foot {{ position: absolute; left: 0; right: 0; bottom: 0; height: 120px; z-index: 6; background: rgba(4,10,12,.85); display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 4px; font-family: 'Pretendard', sans-serif; }}
      #foot b {{ color: #fff; font-size: 34px; font-weight: 800; }}
      #foot span {{ color: var(--muted); font-size: 24px; font-weight: 600; }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{TOTAL}" data-width="{W}" data-height="{H}">
      <div id="bg"></div>
      <div id="grid"></div>
      <img id="logo" src="assets/images/logo.png" alt="현대베스트부동산 031-949-6649" />
      <div id="foot"><b>현대베스트부동산 031-949-6649</b><span>국토부 실거래 기준 · 시세 예측 아님</span></div>
{hosts}
      <div id="caps" data-composition-id="caps" data-composition-src="compositions/caps.html" data-start="0" data-duration="{TOTAL}" data-track-index="2" data-track-kind="captions" data-width="{W}" data-height="{H}" style="z-index:5"></div>
      <audio id="mix" src="assets/audio/mix.wav" data-start="0" data-duration="{TOTAL}" data-track-index="3"></audio>
    </div>
    <script>
      const tl = gsap.timeline({{ paused: true }});
      tl.to(['#logo', '#foot'], {{ opacity: 0, duration: 0.3 }}, {outro_start - 0.15});
      tl.fromTo('#grid', {{ x: 0, y: 0 }}, {{ x: -80, y: -80, duration: {TOTAL}, ease: 'none' }}, 0);
      window.__timelines["main"] = tl;
    </script>
  </body>
</html>
"""
(ROOT / "index.html").write_text(index, encoding="utf-8")
print("scenes:", SCENES)
