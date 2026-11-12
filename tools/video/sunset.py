import numpy as np
W,H=2048,1024
u=(np.arange(W)+0.5)/W; v=(np.arange(H)+0.5)/H
U,V=np.meshgrid(u,v)
lon=(U-0.5)*2*np.pi          # 0 at centre
lat=(0.5-V)*np.pi            # +up
d=np.stack([np.cos(lat)*np.sin(lon),np.sin(lat),np.cos(lat)*np.cos(lon)],-1)
sun=np.array([0,np.sin(np.radians(4)),np.cos(np.radians(4))])
cs=np.clip((d*sun).sum(-1),-1,1); ang=np.degrees(np.arccos(cs))
el=np.degrees(lat)
# sky gradient: zenith deep blue-purple, horizon orange, toward sun warm
t=np.clip(el/60,0,1)
zen=np.array([0.05,0.06,0.16]); hor=np.array([1.2,0.55,0.22]); mid=np.array([0.45,0.25,0.35])
sky=(hor*(1-t[...,None])**3 + mid*3*t[...,None]*(1-t[...,None])**2 + zen*(1-(1-t[...,None])**3))
glow=np.exp(-ang/18)[...,None]*np.array([2.2,1.0,0.35]) + np.exp(-ang/4)[...,None]*np.array([6,3.2,1.2])
sky=sky+glow*(el>-2)[...,None]
# sun disc
disc=(ang<0.7)[...,None]*np.array([4000,2600,1400.])
sky=sky+disc
# ground below horizon: dark warm
g=np.clip(-el/10,0,1)[...,None]
ground=np.array([0.06,0.04,0.035])+np.exp(-ang/25)[...,None]*np.array([0.3,0.15,0.06])
img=np.where((el<0)[...,None], sky*(1-g)+ground*g, sky).astype(np.float32)
# write Radiance RGBE (flat, no RLE)
def rgbe(a):
    m=a.max(-1); e=np.zeros(m.shape,np.int32); man=np.zeros(m.shape)
    nz=m>1e-32
    man[nz],e[nz]=np.frexp(m[nz])
    out=np.zeros(a.shape[:2]+(4,),np.uint8)
    sc=np.where(nz,man*256/np.where(nz,m,1),0)
    out[...,:3]=np.clip(a*sc[...,None],0,255).astype(np.uint8)
    out[...,3]=np.where(nz,e+128,0).astype(np.uint8)
    return out
with open('assets/sunset_btdr.hdr','wb') as f:
    f.write(b'#?RADIANCE\nFORMAT=32-bit_rle_rgbe\n\n-Y %d +X %d\n'%(H,W))
    f.write(rgbe(img).tobytes())
from PIL import Image
prev=img/(1+img); Image.fromarray((np.clip(prev,0,1)**(1/2.2)*255).astype(np.uint8)).resize((1024,512)).save('assets/sunset_preview.jpg')
print('ok')
