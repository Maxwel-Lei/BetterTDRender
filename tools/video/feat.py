import numpy as np, wave
from scipy.signal import butter, sosfilt
w=wave.open('music.wav'); sr=w.getframerate(); x=np.frombuffer(w.readframes(w.getnframes()),'<i2').reshape(-1,2).mean(1)/32768
def band(lo,hi):
    if lo is None: sos=butter(4,hi,'lowpass',fs=sr,output='sos')
    elif hi is None: sos=butter(4,lo,'highpass',fs=sr,output='sos')
    else: sos=butter(4,[lo,hi],'bandpass',fs=sr,output='sos')
    return sosfilt(sos,x)
F=3600; hop=sr//60
def env(y): return np.array([np.sqrt(np.mean(y[i*hop:(i+1)*hop]**2)) for i in range(F)])
def norm(e): return np.clip(e/np.percentile(e,98),0,1.3)
def lag(e,up,dn):
    o=np.zeros_like(e); v=0
    for i,s in enumerate(e):
        v+=(s-v)*(up if s>v else dn); o[i]=v
    return o
b=lag(norm(env(band(None,150))),0.6,0.12); m=lag(norm(env(band(150,2000))),0.5,0.1); h=lag(norm(env(band(3000,None))),0.7,0.2)
d=np.maximum(np.diff(np.concatenate([[0],env(band(None,120))])),0); d/=d.max()
k=np.zeros(F); v=0
for i in range(F):
    v=max(v*0.9, d[i]*1.2 if d[i]>0.15 else 0); k[i]=min(v,1)
np.savetxt('assets/audio_feat.csv',np.stack([b,m,h,k],1),fmt='%.4f',delimiter=',')
for tt in (28.0,28.1,30,43.05,45): i=int(tt*60); print(tt,b[i].round(2),m[i].round(2),h[i].round(2),k[i].round(2))
