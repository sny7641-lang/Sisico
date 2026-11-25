import subprocess,os,sys,json
sys.path.insert(0,'work'); from lines import PH
os.makedirs('work/ph',exist_ok=True)
out=[]
for i,(sc,disp,sp,pause) in enumerate(PH):
    mp3=f'work/ph/{i:02d}.mp3'; wav=f'work/ph/{i:02d}.wav'
    for a in range(5):
        if not os.path.exists(wav):
            subprocess.run(['edge-tts','--proxy',os.environ['HTTPS_PROXY'],'--voice','ko-KR-SunHiNeural','--rate=+6%','--text',sp,'--write-media',mp3],capture_output=True)
            r=subprocess.run(['ffmpeg','-y','-v','error','-i',mp3,'-af','silenceremove=start_periods=1:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse','-ar','48000','-ac','1',wav],capture_output=True)
            if r.returncode: os.path.exists(wav) and os.remove(wav); continue
        break
    d=float(subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',wav],capture_output=True,text=True).stdout)
    out.append(d); print(i,round(d,2),sp)
json.dump(out,open('work/durs.json','w'))
print('speech total',round(sum(out),2),'pauses',round(sum(p[3] for p in PH),2))
