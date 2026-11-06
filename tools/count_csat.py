#!/usr/bin/env python3
"""Count how many 수능 years each word appears in.

Input: a folder of text files extracted (pdftotext) from the 수능 영어 문제지 and 듣기 대본 PDFs
published by 한국교육과정평가원 (suneung.re.kr > 기출문제). Each file must contain "20XX학년도".
The exam texts themselves are not stored in this repository; only the counts are.

Usage: python3 tools/count_csat.py <txt_dir>  -> writes data/sources/csat_2014_2026_counts.json
"""
import sys
import re,glob,os,csv,json,collections
D=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),'data','sources')
TXT=sys.argv[1]
edu={}
for l in open(D+'/edu_2022_basic_vocab.tsv'):
    if l.strip(): w,lv=l.rstrip('\n').split('\t'); edu[w.lower()]=lv
form2lem={}
def addfile(p,enc='utf-8'):
    for l in open(p,encoding=enc,errors='replace'):
        l=l.strip().lstrip('﻿')
        if not l or l.startswith('#'): continue
        parts=[x.strip().lower() for x in l.split(',') if x.strip()]
        lem=parts[0]
        for f in parts: form2lem.setdefault(f,lem)
for p in ['NGSL_1.2_lemmatized.csv','NAWL_1.2_lemmatized.csv','TSL_1.2_lemmatized.csv','NGSL_SUP_lemmatized.csv']:
    addfile(D+'/'+p)
lemset=set(form2lem.values())|set(edu)
def lemma(t):
    if t in edu: return t
    if t in form2lem: return form2lem[t]
    for suf,rep in [('ies','y'),('ied','y'),('es',''),('s',''),('ed',''),('ed','e'),('ing',''),('ing','e'),('ly',''),('er',''),('est','')]:
        if t.endswith(suf):
            b=t[:-len(suf)]+rep
            if b in edu or b in form2lem: return form2lem.get(b,b)
            if len(b)>2 and b[-1]==b[-2] and b[:-1] in edu: return b[:-1]
    return None
year_of={}
for f in glob.glob(TXT+'/*.txt'):
    m=re.search(r'(\d{4})학년도',open(f,encoding='utf-8',errors='replace').read())
    year_of[f]=m.group(1)
years=collections.defaultdict(set); freq=collections.Counter(); unknown=collections.Counter()
for f,y in year_of.items():
    txt=open(f,encoding='utf-8',errors='replace').read()
    for t in re.findall(r"[A-Za-z]+(?:'[a-z]+)?",txt):
        if len(t)<2 and t not in ('a','I'): continue
        lt=t.lower().split("'")[0]
        lm=lemma(lt)
        if lm: years[lm].add(y); freq[lm]+=1
        elif t.islower(): unknown[lt]+=1
ny=len(set(year_of.values()))
rows=sorted(years,key=lambda w:(-len(years[w]),-freq[w]))
json.dump({'nyears':ny,'yearsrange':sorted(set(year_of.values())),'words':[[w,len(years[w]),freq[w],edu.get(w,'')] for w in rows]},open(D+'/csat_2014_2026_counts.json','w'))
print('exam years',ny,sorted(set(year_of.values())))
print('lemmas seen',len(rows))
for th in [13,10,8,6,4,3,2]:
    s=[w for w in rows if len(years[w])>=th]
    print(th, len(s), 'non-elem', sum(1 for w in s if edu.get(w)!='elem'), 'not in edu', sum(1 for w in s if w not in edu))
print('top unknown', unknown.most_common(40))
