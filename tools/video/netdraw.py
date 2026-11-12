import json, sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter
nodes=json.load(open('/mnt/user-data/uploads/ue5/btdr/out/video/net_blinds.json'))
thumb=Image.open(sys.argv[1]).convert('RGB')
skip={'native_render','native_out','ambient1'}
nodes=[n for n in nodes if n['name'] not in skip]
W,H=2560,1440
im=Image.new('RGB',(W,H),(38,38,40)); d=ImageDraw.Draw(im)
for x in range(0,W,40): d.line([(x,0),(x,H)],fill=(44,44,47))
for y in range(0,H,40): d.line([(0,y),(W,y)],fill=(44,44,47))
F=ImageFont.truetype('/usr/share/fonts/opentype/inter/Inter-Medium.otf',26)
FB=ImageFont.truetype('/usr/share/fonts/opentype/inter/Inter-SemiBold.otf',30)
FS=ImageFont.truetype('/usr/share/fonts/opentype/inter/Inter-Regular.otf',19)
xs=[n['x'] for n in nodes]; ys=[n['y'] for n in nodes]
x0,x1=min(xs),max(xs)+160; y0,y1=min(ys),max(ys)+140
sc=min((W-700)/(x1-x0),(H-300)/(y1-y0))
def P(x,y): return (150+(x-x0)*sc, H-150-(y-y0)*sc)
col={'COMP':(70,82,94),'MAT':(96,84,58),'TOP':(78,64,104)}
boxes={}
geos=[n for n in nodes if n['type']=='geometryCOMP']; mats=[n for n in nodes if n['family']=='MAT']
others=[n for n in nodes if n['name'] in ('cam1','target','light1')]
def put(n,x,y,w,h): boxes[n['name']]=(x,y,x+w,y+h)
top=330
for i,n in enumerate(others): put(n,120,top+i*120,250,80)
for i,n in enumerate(geos): put(n,470+(i%2)*280,top+(i//2)*120,250,80)
for i,n in enumerate(mats): put(n,1060,top+i*120,250,80)
bw=560; bh=int((bw-16)*9/16)+86
for n in nodes:
    if n['name']=='renderBTDR1': put(n,1380,640,bw,bh)
    if n['name']=='OUT': put(n,2060,640,460,int((460-16)*9/16)+86)
for n in nodes:
    for i in n['inputs']:
        src='renderBTDR1' if i=='out1' else i
        if src in boxes:
            a=boxes[src]; b=boxes[n['name']]
            d.line([(a[2],(a[1]+a[3])/2),(b[0],(b[1]+b[3])/2)],fill=(170,170,175),width=4)
for n in nodes:
    r=boxes[n['name']]; big=n['name'] in ('renderBTDR1','OUT')
    c=col.get(n['family'],(70,70,70))
    d.rounded_rectangle(r,radius=8,fill=c,outline=(110,170,255) if n['name']=='renderBTDR1' else (20,20,22),width=5 if n['name']=='renderBTDR1' else 2)
    if big:
        tw=int(r[2]-r[0]-16); th=int(tw*9/16)
        t=thumb.resize((tw,th)); im.paste(t,(int(r[0]+8),int(r[1]+8)))
        d.text((r[0]+12,r[3]-12),n['name'],font=FB,fill=(240,240,240),anchor='ls')
        d.text((r[2]-12,r[3]-14),'baseCOMP' if n['name']=='renderBTDR1' else 'nullTOP',font=FS,fill=(200,200,205),anchor='rs')
    else:
        d.text((r[0]+14,(r[1]+r[3])/2-11),n['name'],font=F,fill=(235,235,235),anchor='lm')
        d.text((r[0]+14,(r[1]+r[3])/2+17),n['type'],font=FS,fill=(190,190,195),anchor='lm')
d.text((40,40),'/project1/sc_blinds',font=FB,fill=(200,200,205))
im.save('assets/onenode.png')
b=boxes['renderBTDR1']; fx=((b[0]+b[2])/2)/W; fy=((b[1]+b[3])/2)/H
open('assets/node_focus.txt','w').write('%.3f %.3f'%(min(fx+0.08,0.8),fy))
print(fx,fy)
