import json,subprocess,sys
sys.path.insert(0,'work'); from lines import PH
d=json.load(open('work/durs.json'))
LEAD=0.3; t=LEAD; tl=[]
for (sc,disp,sp,p),dur in zip(PH,d):
    tl.append({'scene':sc,'text':disp,'a':round(t,3),'b':round(t+dur,3)}); t+=dur+p
total=round(t,2)
json.dump({'total':total,'phr':tl},open('work/timeline.json','w'),ensure_ascii=False,indent=1)
inp=[];flt=[]
for i,x in enumerate(tl):
    inp+=['-i',f'work/ph/{i:02d}.wav']; ms=int(x['a']*1000); flt.append(f'[{i}]adelay={ms}|{ms}[p{i}]')
n=len(tl)
inp+=['-stream_loop','-1','-i','../hillstate-59b/audio/bgm.wav']
flt.append(''.join(f'[p{i}]' for i in range(n))+f'amix=inputs={n}:normalize=0[v]')
flt.append(f'[{n}]atrim=0:{total},volume=0.15,afade=t=out:st={total-1.5}:d=1.5[m]')
flt.append('[v][m]amix=inputs=2:normalize=0,loudnorm=I=-14:TP=-1.5,aresample=48000[a]')
subprocess.run(['ffmpeg','-y','-v','error',*inp,'-filter_complex',';'.join(flt),'-map','[a]','-ac','2','-t',str(total),'assets/audio/mix.wav'],check=True)
print('total',total)
