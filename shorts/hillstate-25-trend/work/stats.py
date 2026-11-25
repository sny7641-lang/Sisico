"""힐스테이트운정 25평형(전용 59·60㎡) 실거래, 6~8월 vs 9~11월(11/24 신고분까지). 취소 건 제외."""
import json,statistics as st,pathlib
D=pathlib.Path(__file__).resolve().parent.parent/'data'
old=json.load(open(D/'asil_trades_2026-04_11.json')); new=json.load(open(D/'asil_trades_2026-06_11-25.json'))
R=[x for x in old if '2026-06'<=x['date']<'2026-07']+[x for x in new if x['date']>='2026-07']
R=[x for x in R if x['tag']!='취소' and x['type'] in('59','60')]
MONTHS=['2026-06','2026-07','2026-08','2026-09','2026-10','2026-11']
A,B=MONTHS[:3],MONTHS[3:]
def sub(ms,kind=None): return [x for x in R if x['date'][:7] in ms and (kind is None or x['kind']==kind)]
monthly=[{k:len(sub([m],k)) for k in('매매','전세','월세')} for m in MONTHS]
def blk(ms):
    s=[x['val'] for x in sub(ms,'매매')]; j=sub(ms,'전세'); jn=[x['val'] for x in j if x['tag']!='갱신']
    w=sub(ms,'월세'); w3=[x['rent'] for x in w if x['tag']!='갱신' and x['deposit']==3000]
    return dict(total=len(sub(ms)),sale=len(s),sale_med=st.median(s),sale_max=max(s),jeon=len(j),jeon_new=len(jn),jeon_renew=len(j)-len(jn),jeon_new_med=st.median(jn),wol=len(w),wol3_med=st.median(w3),wol3=sorted(w3))
S={'monthly':monthly,'A':blk(A),'B':blk(B)}
top=max(sub(B,'매매'),key=lambda x:x['val']); S['top']=top
if __name__=='__main__':
    print(json.dumps(S,ensure_ascii=False,indent=1))
