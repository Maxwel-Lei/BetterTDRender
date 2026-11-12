from PIL import Image, ImageDraw, ImageFont, ImageFilter
W,H=1920,1080
CJK='/usr/share/fonts/opentype/noto/NotoSansCJK-%s.ttc'
INT='/usr/share/fonts/opentype/inter/Inter-%s.otf'
def cjk(sz,w='Medium'): return ImageFont.truetype(CJK%w,sz,index=2)
def inter(sz,w='Regular'): return ImageFont.truetype(INT%w,sz)
def blank(): return Image.new('RGBA',(W,H),(0,0,0,0))

def shadow_text(im, xy, text, font, fill, anchor, blur=6, sh=170):
    lay=Image.new('RGBA',im.size,(0,0,0,0)); d=ImageDraw.Draw(lay)
    d.text(xy,text,font=font,fill=(0,0,0,sh),anchor=anchor)
    lay=lay.filter(ImageFilter.GaussianBlur(blur))
    im.alpha_composite(lay)
    ImageDraw.Draw(im).text(xy,text,font=font,fill=fill,anchor=anchor)

def caption(name, zh, en):
    im=blank()
    # bottom gradient band
    band=Image.new('L',(1,260))
    for y in range(260): band.putpixel((0,y), int(150*(y/259)**1.6))
    band=band.resize((W,260))
    g=Image.new('RGBA',(W,260),(0,0,0,0)); g.putalpha(band)
    im.alpha_composite(g,(0,H-260))
    shadow_text(im,(W//2,H-112),zh,cjk(44),(255,255,255,255),'ms')
    shadow_text(im,(W//2,H-66),en,inter(26),(255,255,255,200),'ms')
    im.save('ov/cap_%s.png'%name)

def label(name, text, side='left', sub=None):
    im=blank(); d=ImageDraw.Draw(im)
    f=inter(26,'SemiBold'); tw=d.textlength(text,font=f)
    pad=18; h=50; y=48
    x=56 if side=='left' else W-56-tw-2*pad
    if side=='center': x=(W-tw)/2-pad
    d.rounded_rectangle([x,y,x+tw+2*pad,y+h],radius=10,fill=(12,14,18,170),outline=(255,255,255,40))
    d.text((x+pad,y+h/2),text,font=f,fill=(255,255,255,235),anchor='lm')
    if sub:
        d.text((x+pad,y+h+12),sub,font=inter(20),fill=(255,255,255,170),anchor='lt')
    im.save('ov/lab_%s.png'%name)

def splitlabels():
    im=blank(); d=ImageDraw.Draw(im); f=inter(26,'SemiBold')
    for text,side in (('BetterTDRender','l'),('TD Render TOP','r')):
        tw=d.textlength(text,font=f); pad=18; h=50; y=48
        x=56 if side=='l' else W-56-tw-2*pad
        fill=(20,110,255,200) if side=='l' else (12,14,18,170)
        d.rounded_rectangle([x,y,x+tw+2*pad,y+h],radius=10,fill=fill,outline=(255,255,255,50))
        d.text((x+pad,y+h/2),text,font=f,fill=(255,255,255,240),anchor='lm')
    im.save('ov/lab_split_left.png')
    # separate right-only and left-only
    for text,side,fn,fill in (('BetterTDRender','l','lab_btdr.png',(20,110,255,200)),('TD Render TOP','r','lab_native_r.png',(12,14,18,170))):
        im=blank(); d=ImageDraw.Draw(im)
        tw=d.textlength(text,font=f); pad=18; h=50; y=48
        x=56 if side=='l' else W-56-tw-2*pad
        d.rounded_rectangle([x,y,x+tw+2*pad,y+h],radius=10,fill=fill,outline=(255,255,255,50))
        d.text((x+pad,y+h/2),text,font=f,fill=(255,255,255,240),anchor='lm')
        im.save('ov/'+fn)

def title():
    im=blank()
    shadow_text(im,(W//2,H//2-10),'BetterTDRender',inter(128,'Bold'),(255,255,255,255),'ms',blur=14,sh=150)
    shadow_text(im,(W//2,H//2+62),'把 UE5 的渲染管线装进 TouchDesigner',cjk(44),(255,255,255,240),'ms',blur=8)
    shadow_text(im,(W//2,H//2+110),'UE5-style rendering, inside TouchDesigner',inter(28),(255,255,255,200),'ms',blur=6)
    im.save('ov/title.png')

def perf_card(i, big, small, en):
    im=blank(); d=ImageDraw.Draw(im)
    cw,ch=470,300; gap=50; x0=(W-(3*cw+2*gap))//2; y=330
    x=x0+i*(cw+gap)
    d.rounded_rectangle([x,y,x+cw,y+ch],radius=22,fill=(14,16,22,215),outline=(255,255,255,45),width=2)
    d.text((x+cw/2,y+150),big,font=inter(104,'Bold'),fill=(255,255,255,255),anchor='ms')
    d.text((x+cw/2,y+212),small,font=cjk(34),fill=(255,255,255,225),anchor='ms')
    d.text((x+cw/2,y+256),en,font=inter(24),fill=(255,255,255,160),anchor='ms')
    im.save('ov/perf_%d.png'%i)

def perf_note():
    im=blank(); d=ImageDraw.Draw(im)
    d.text((W//2,880),'RTX 5080 Laptop · 1080p · High · 本片场景实测 / measured on these scenes · 粒子场景 40 万实例约 10 ms',font=cjk(26,'Regular'),fill=(255,255,255,170),anchor='ms')
    im.save('ov/perf_note.png')

def endcard():
    im=Image.new('RGBA',(W,H),(8,9,12,255)); d=ImageDraw.Draw(im)
    d.text((W//2,430),'BetterTDRender',font=inter(120,'Bold'),fill=(255,255,255,255),anchor='ms')
    d.text((W//2,500),'v0.7.3  ·  PolyForm Noncommercial 1.0.0  ·  TouchDesigner 2025',font=inter(32),fill=(255,255,255,190),anchor='ms')
    d.text((W//2,610),'github.com/Maxwel-Lei/BetterTDRender',font=inter(40,'SemiBold'),fill=(90,160,255,255),anchor='ms')
    d.text((W//2,690),'Xikai Lei',font=inter(34,'Medium'),fill=(255,255,255,220),anchor='ms')
    im.convert('RGB').save('ov/end.png')

def keyword(name, zh, en):
    # one keyword per segment, lower left, small: the picture carries the message
    im=blank()
    band=Image.new('L',(1,220))
    for y in range(220): band.putpixel((0,y), int(110*(y/219)**1.8))
    band=band.resize((W,220)); g=Image.new('RGBA',(W,220),(0,0,0,0)); g.putalpha(band); im.alpha_composite(g,(0,H-220))
    shadow_text(im,(96,H-104),zh,cjk(46,'Medium'),(255,255,255,250),'ls')
    shadow_text(im,(98,H-62),en,inter(24,'Medium'),(255,255,255,175),'ls')
    im.save('ov/cap_%s.png'%name)

def title():
    im=blank()
    shadow_text(im,(W//2,H//2+30),'BetterTDRender',inter(128,'Bold'),(255,255,255,255),'ms',blur=14,sh=150)
    shadow_text(im,(W//2,H//2+92),'for TouchDesigner',inter(32,'Medium'),(255,255,255,210),'ms',blur=6)
    im.save('ov/title.png')

def perf_note():
    im=blank(); d=ImageDraw.Draw(im)
    d.text((96,H-150),'RTX 5080 Laptop · 1080p · High',font=inter(24),fill=(255,255,255,160),anchor='ls')
    im.save('ov/perf_note.png')

keyword('k_native','原生 Render TOP','Native Render TOP')
keyword('k_btdr','BetterTDRender','')
keyword('k_param','参数','Parameters')
keyword('k_refl','反射','Reflections')
keyword('k_vol','体积光','Volumetric light')
keyword('k_chladni','克拉尼图形','Chladni figures')
keyword('k_perf','性能','Performance')
keyword('k_refr','折射','Refraction')
label('refl_off','Reflections  ·  OFF'); label('refl_on','Reflections  ·  ON')
title(); perf_note(); endcard()
print('ok')
