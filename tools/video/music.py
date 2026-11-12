import numpy as np, wave
SR=48000; T=60.0; N=int(SR*T)
t=np.arange(N)/SR
rng=np.random.default_rng(7)
BPM=105; beat=60/BPM
def env_adsr(n,a,r):
    e=np.ones(n); A=min(int(a*SR),n//2); R=min(int(r*SR),n//2)
    e[:A]=np.linspace(0,1,A); e[-R:]*=np.linspace(1,0,R); return e
def lp(x,fc):
    # one-pole lowpass
    a=np.exp(-2*np.pi*fc/SR); y=np.empty_like(x); s=0.0
    from scipy.signal import lfilter
    return lfilter([1-a],[1,-a],x)
def note(f): return 440*2**((f-69)/12)
out=np.zeros((N,2))
# pad chords (midi), 4 bars each chord (bar=4 beats)
chords=[[57,64,67,71,74],[53,60,64,67,72],[48,55,64,67,71],[55,62,67,71,74]]
bar=4*beat
pos=0.0; k=0
while pos<T:
    dur=2*bar
    s=int(pos*SR); e=min(N,int((pos+dur+1.5)*SR)); n=e-s
    tt=np.arange(n)/SR
    sig=np.zeros(n)
    for m in chords[k%4]:
        f=note(m)
        for det in (-0.08,0.08):
            ff=f*2**(det/12)
            sig+=np.sin(2*np.pi*ff*tt+rng.uniform(0,6))*0.5+0.18*np.sin(2*np.pi*2*ff*tt)
    sig*=env_adsr(n,1.2,1.6)
    out[s:e,0]+=sig*0.5; out[s:e,1]+=np.roll(sig,90)*0.5
    pos+=dur; k+=1
out[:,0]=lp(out[:,0],1800); out[:,1]=lp(out[:,1],1800)
out*=0.06
# low drone
out+=(0.05*np.sin(2*np.pi*note(33)*t))[:,None]
def add(x,at,gain=1.0,st=0.0):
    s=int(at*SR); e=min(N,s+len(x)); out[s:e,0]+=x[:e-s]*gain*(1-st); out[s:e,1]+=x[:e-s]*gain*(1+st)
def kick(g=1.0):
    n=int(0.45*SR); tt=np.arange(n)/SR
    f=45+90*np.exp(-tt*28)
    ph=2*np.pi*np.cumsum(f)/SR
    return np.sin(ph)*np.exp(-tt*7)*g
def hat():
    n=int(0.06*SR); x=rng.standard_normal(n)
    x=x-lp(x,6000); return x*np.exp(-np.arange(n)/SR*70)*0.12
def impact():
    n=int(3.5*SR); tt=np.arange(n)/SR
    sub=np.sin(2*np.pi*(38+40*np.exp(-tt*6))*tt)*np.exp(-tt*1.3)
    nz=lp(rng.standard_normal(n),900)*np.exp(-tt*1.8)*0.6
    return sub*0.9+nz
def riser(d):
    n=int(d*SR); tt=np.arange(n)/SR
    x=rng.standard_normal(n); y=np.zeros(n)
    # sweep lowpass in chunks
    for i in range(0,n,2400):
        fc=200+5000*(i/n)**2; seg=x[i:i+2400]; y[i:i+2400]=lp(seg,fc)
    return y*(tt/d)**2*0.35
add(riser(2.6),0.4)
add(impact(),3.0,0.9)
add(riser(1.8),26.2,0.8)
add(impact(),28.0,1.0)
add(riser(1.8),41.2,0.8)
add(impact(),43.0,0.85)
# beat from 3s to 44, and 46 to 56
for s0,s1 in ((3.0,26.6),(28.0,41.6),(43.0,56.0)):
    b=s0; i=0
    while b<s1:
        add(kick(0.55 if i%4==0 else 0.32),b)
        add(hat(),b+beat/2,1.0,0.3*((i%2)*2-1))
        b+=beat; i+=1
# end hit at 56
add(impact(),56.0,0.6)
# reverb (simple noise IR)
from scipy.signal import fftconvolve
ir_n=int(2.2*SR); irt=np.arange(ir_n)/SR
for ch in range(2):
    ir=rng.standard_normal(ir_n)*np.exp(-irt*2.6); ir=lp(ir,4000); ir/=np.sqrt((ir**2).sum())
    wet=fftconvolve(out[:,ch],ir)[:N]
    out[:,ch]=out[:,ch]*0.8+wet*0.35
# fades
fo=np.ones(N); fo[:int(0.3*SR)]=np.linspace(0,1,int(0.3*SR))
s=int(57.5*SR); fo[s:]=np.linspace(1,0,N-s)**2
out*=fo[:,None]
out/=np.abs(out).max()/0.89
w=wave.open('music.wav','wb'); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
w.writeframes((out*32767).astype('<i2').tobytes()); w.close()
print('ok')
