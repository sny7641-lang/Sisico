#!/usr/bin/env python3
"""Build www/decks.js from the source word lists in data/.

Decks
  elem / mid / high : 2022 개정 영어과 교육과정 [별표 3] 기본 어휘 (교육부·한국교육과정평가원)
                      * = 초등 권장 800, ** = 중학교·고등 공통 권장 1,200, 표시 없음 = 그 외 1,000
  csat              : 2014~2026학년도 수능 영어(문제지 + 듣기 대본)에 3개 연도 이상 나온 단어,
                      초등 수준 단어와 기능어 제외, 출제 연도 수 순
  toeic             : TOEIC Service List 1.2 (Browne & Culligan, CC BY-SA 4.0), 순위 순
  daily             : 일상 회화 표현 (직접 정리, 기존 www/words.js)

Korean meanings and most examples: data/dict/*.tsv (word|pos|meaning|example)
Example sentences with Korean translations: Tatoeba (CC BY 2.0 FR), data/sources/tatoeba_eng_kor.tsv
"""
import csv, glob, json, os, re, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'data', 'sources')
DICT = os.path.join(ROOT, 'data', 'dict')

# ---------- lemmatizer (form -> headword) ----------
edu = {}
for line in open(os.path.join(SRC, 'edu_2022_basic_vocab.tsv'), encoding='utf-8'):
    if line.strip():
        w, lv = line.rstrip('\n').split('\t')
        edu[w.lower()] = lv

form2lem = {}
for fn in ['NGSL_1.2_lemmatized.csv', 'NAWL_1.2_lemmatized.csv', 'TSL_1.2_lemmatized.csv', 'NGSL_SUP_lemmatized.csv']:
    for line in open(os.path.join(SRC, fn), encoding='utf-8', errors='replace'):
        line = line.strip().lstrip('﻿')
        if not line or line.startswith('#'):
            continue
        parts = [x.strip().lower() for x in line.split(',') if x.strip()]
        for f in parts:
            form2lem.setdefault(f, parts[0])


def lemma(t):
    if t in edu:
        return t
    if t in form2lem:
        return form2lem[t]
    for suf, rep in [('ies', 'y'), ('ied', 'y'), ('es', ''), ('s', ''), ('ed', ''), ('ed', 'e'), ('ing', ''), ('ing', 'e'), ('ly', ''), ('er', ''), ('est', '')]:
        if t.endswith(suf):
            b = t[:-len(suf)] + rep
            if b in edu or b in form2lem:
                return form2lem.get(b, b)
            if len(b) > 2 and b[-1] == b[-2] and b[:-1] in edu:
                return b[:-1]
    return None

# ---------- decks ----------
csat = json.load(open(os.path.join(SRC, 'csat_2014_2026_counts.json'), encoding='utf-8'))
STOP = set('a an the and or but if of to in on at by for with from as is be am are was were been being do does did have has had '
           'i you he she it we they me him her us them my your his its our their this that these those there here not no yes so '
           'than then too very can could will would shall should may might must'.split())
csat_words = [(w, y) for w, y, f, lv in csat['words'] if y >= 3 and lv != 'elem' and w not in STOP and len(w) > 2]
tsl = [r['Word'].strip().lower() for r in csv.DictReader(open(os.path.join(SRC, 'TSL_1.2_stats.csv'), encoding='latin-1'))]

# ---------- meanings ----------
entries = {}
for fn in sorted(glob.glob(os.path.join(DICT, '[0-9]*.tsv'))):
    for line in open(fn, encoding='utf-8'):
        if not line.strip():
            continue
        w, pos, m, ex = line.rstrip('\n').split('|')
        entries[w.lower()] = {'p': pos, 'm': m, 'e': ex}
for line in open(os.path.join(DICT, 'prev.tsv'), encoding='utf-8'):
    p = line.rstrip('\n').split('\t')
    if len(p) == 4 and p[0] not in entries:
        entries[p[0]] = {'p': p[1], 'm': p[2], 'e': p[3]}

# ---------- Tatoeba examples ----------
pairs = []
for line in open(os.path.join(SRC, 'tatoeba_eng_kor.tsv'), encoding='utf-8'):
    p = line.rstrip('\n').split('\t')
    if len(p) >= 3:
        ids = re.findall(r'#(\d+)', p[2])
        pairs.append((p[0], p[1], ids[0] if ids else ''))
cands = collections.defaultdict(list)
for i, (en, ko, _) in enumerate(pairs):
    toks = re.findall(r"[A-Za-z]+", en)
    if not (4 <= len(toks) <= 14):
        continue
    for t in set(x.lower() for x in toks):
        lm = lemma(t)
        if lm:
            cands[lm].append(i)
used = collections.Counter()

def pick_tatoeba(w):
    best = None
    for i in cands.get(w, []):
        n = len(re.findall(r"[A-Za-z]+", pairs[i][0]))
        score = (used[i], abs(n - 8), i)
        if best is None or score < best[0]:
            best = (score, i)
    if best is None:
        return None
    used[best[1]] += 1
    return pairs[best[1]]

# ---------- assemble ----------
order = list(edu) + [w for w, _ in csat_words] + tsl
words = {}
missing = []
tatoeba_used = 0
for w in order:
    if w in words:
        continue
    e = entries.get(w)
    if not e:
        missing.append(w)
        continue
    rec = [e['p'], e['m'], e['e'], '', '']
    t = pick_tatoeba(w)
    if t:
        rec[2], rec[3], rec[4] = t[0], t[1], t[2]
        tatoeba_used += 1
    words[w] = rec

if missing:
    raise SystemExit('missing meanings: ' + ', '.join(missing[:50]))

decks = [
    {'id': 'elem', 'name': '교육과정 초등 필수', 'desc': '2022 개정 교육과정 기본 어휘 중 초등 권장 단어', 'src': 'edu',
     'words': [w for w, lv in edu.items() if lv == 'elem']},
    {'id': 'mid', 'name': '교육과정 중·고 필수', 'desc': '2022 개정 교육과정 기본 어휘 중 중학교·고등 공통 권장 단어', 'src': 'edu',
     'words': [w for w, lv in edu.items() if lv == 'mid']},
    {'id': 'high', 'name': '교육과정 고등 심화', 'desc': '2022 개정 교육과정 기본 어휘 중 고등 선택과목 단어', 'src': 'edu',
     'words': [w for w, lv in edu.items() if lv == 'high']},
    {'id': 'csat', 'name': '수능 기출 빈출', 'desc': '2014~2026학년도 수능 영어 13개년 중 3개 연도 이상 출제 (초등 단어 제외, 많이 나온 순)', 'src': 'csat',
     'words': [w for w, _ in csat_words], 'years': {w: y for w, y in csat_words}, 'yearsTotal': csat['nyears']},
    {'id': 'toeic', 'name': '토익 빈출 (TSL)', 'desc': 'TOEIC Service List 1.2, 토익 지문 말뭉치에서 자주 나온 순', 'src': 'tsl',
     'words': tsl},
]
out = {
    'version': 2,
    'words': words,
    'decks': decks,
}
js = '// Generated by tools/build_decks.py. Do not edit by hand.\nwindow.SISICO_DATA = ' + json.dumps(out, ensure_ascii=False, separators=(',', ':')) + ';\n'
open(os.path.join(ROOT, 'www', 'decks.js'), 'w', encoding='utf-8').write(js)
print('words', len(words), 'tatoeba examples', tatoeba_used, 'size', len(js.encode()) // 1024, 'KB')
for d in decks:
    print(d['id'], len(d['words']))
