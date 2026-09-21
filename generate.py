import os, json, textwrap, datetime, requests
from io import BytesIO
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT=Path(__file__).parent
CFG=json.loads((ROOT/'config.json').read_text(encoding='utf-8'))
TOKEN=os.environ.get('TMDB_API_TOKEN') or os.environ.get('TMDB_API_KEY')
if not TOKEN: raise SystemExit('Ajoutez TMDB_API_TOKEN dans les secrets GitHub.')
HEAD={'Authorization': f'Bearer {TOKEN}', 'accept':'application/json'}
API='https://api.themoviedb.org/3'
IMG='https://image.tmdb.org/t/p/original'
OUT=ROOT/'wallpapers'; OUT.mkdir(exist_ok=True)

def get(path, **params):
    r=requests.get(API+path, headers=HEAD, params=params, timeout=30); r.raise_for_status(); return r.json()

def font(size,bold=False):
    paths=['/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']
    return ImageFont.truetype(paths[0],size)

def providers(kind, mid):
    data=get(f'/{kind}/{mid}/watch/providers').get('results',{}).get('FR',{})
    names=[]
    for bucket in ('flatrate','free','ads'):
        for p in data.get(bucket,[]):
            if p['provider_name'] not in names: names.append(p['provider_name'])
    return names

def discover(kind):
    today=datetime.date.today(); start=today-datetime.timedelta(days=CFG['days_back'])
    datefield='primary_release_date' if kind=='movie' else 'first_air_date'
    return get(f'/discover/{kind}', language='fr-FR', region='FR', sort_by='popularity.desc',
               **{f'{datefield}.gte':str(start), f'{datefield}.lte':str(today)}, page=1).get('results',[])

def wrap(draw,text,f,maxw,maxlines=3):
    words=text.split(); lines=[]; cur=''
    for w in words:
        test=(cur+' '+w).strip()
        if draw.textbbox((0,0),test,font=f)[2] <= maxw: cur=test
        else:
            if cur: lines.append(cur)
            cur=w
            if len(lines)>=maxlines: break
    if cur and len(lines)<maxlines: lines.append(cur)
    if len(lines)==maxlines and len(' '.join(lines))<len(text): lines[-1]=lines[-1].rstrip(' .')+'…'
    return lines

def make(item,kind,prov):
    path=item.get('backdrop_path');
    if not path: return None
    im=Image.open(BytesIO(requests.get(IMG+path,timeout=30).content)).convert('RGB')
    W,H=CFG['width'],CFG['height']; scale=max(W/im.width,H/im.height); im=im.resize((int(im.width*scale),int(im.height*scale)),Image.Resampling.LANCZOS)
    left=(im.width-W)//2; top=(im.height-H)//2; im=im.crop((left,top,left+W,top+H))
    # dark top-left readability gradient, leaving center/menu visually clean
    overlay=Image.new('RGBA',(W,H),(0,0,0,0)); od=ImageDraw.Draw(overlay)
    for x in range(0,2300,20):
        a=int(210*max(0,1-x/2300)); od.rectangle((x,0,x+20,900),fill=(0,0,0,a))
    for y in range(0,950,20):
        a=int(80*max(0,1-y/950)); od.rectangle((0,y,2200,y+20),fill=(0,0,0,a))
    im=Image.alpha_composite(im.convert('RGBA'),overlay)
    d=ImageDraw.Draw(im); x,y=180,115
    title=item.get('title') or item.get('name') or 'Sans titre'; date=item.get('release_date') or item.get('first_air_date') or ''
    year=date[:4] if date else ''
    d.text((x,y),title,font=font(112,True),fill='white',stroke_width=2,stroke_fill=(0,0,0,180)); y+=145
    meta=f"{year}   •   {'FILM' if kind=='movie' else 'SÉRIE'}   •   ★ {item.get('vote_average',0):.1f}/10"
    d.text((x,y),meta,font=font(46,True),fill=(245,245,245)); y+=85
    overview=item.get('overview') or 'Synopsis français indisponible.'
    f=font(44)
    for line in wrap(d,overview,f,1650,3): d.text((x,y),line,font=f,fill=(245,245,245)); y+=58
    y+=30
    ptxt=' • '.join(prov[:4]) if prov else 'Disponibilité streaming non renseignée'
    d.text((x,y),'DISPONIBLE EN FRANCE',font=font(34,True),fill=(255,210,70)); y+=48
    d.text((x,y),ptxt,font=font(40,True),fill='white')
    d.text((x,835),'Disponibilités : données TMDB / JustWatch',font=font(24),fill=(210,210,210))
    fn=f"{'film' if kind=='movie' else 'serie'}-{item['id']}.jpg"; im.convert('RGB').save(OUT/fn,'JPEG',quality=92,optimize=True)
    return fn,title

def main():
    chosen=[]
    for kind in ('movie','tv'):
        for it in discover(kind):
            try: prov=providers(kind,it['id'])
            except Exception: prov=[]
            if CFG['providers'] and prov and not any(any(k.lower() in p.lower() for k in CFG['providers']) for p in prov): continue
            chosen.append((it,kind,prov))
    chosen.sort(key=lambda t:t[0].get('popularity',0),reverse=True); chosen=chosen[:CFG['max_wallpapers']]
    entries=[]
    base=os.environ.get('PUBLIC_BASE_URL','').rstrip('/')
    for it,kind,prov in chosen:
        try: result=make(it,kind,prov)
        except Exception as e: print('skip',it.get('id'),e); continue
        if not result: continue
        fn,title=result
        entries.append({'location':'France','title':title,'author':'TMDB / JustWatch','url_img':f'{base}/wallpapers/{fn}' if base else f'wallpapers/{fn}'})
    (ROOT/'wallpapers.json').write_text(json.dumps(entries,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'{len(entries)} wallpapers générés')
if __name__=='__main__': main()
