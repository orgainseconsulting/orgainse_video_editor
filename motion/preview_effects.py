"""Render the original effect functions on a moving studio test card and publish verified previews."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import math
from pathlib import Path
import subprocess
import sys

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / ".local/effects-python"))
sys.path.insert(0, str(PROJECT))
from PIL import Image, ImageChops, ImageDraw
from core import ROOT, LOCAL, binary, ff, save
from effects import CATALOG, render_layers


def source_clip(target):
    w,h = 320,400
    ffmpeg = subprocess.Popen([binary("ffmpeg"),"-v","error","-y","-f","rawvideo","-pix_fmt","rgb24",
        "-s","320x400","-r","15","-i","pipe:0","-c:v","libx264","-pix_fmt","yuv420p",str(target)],stdin=subprocess.PIPE)
    try:
        for n in range(36):
            im=Image.new("RGB",(w,h),"#172c37")
            d=ImageDraw.Draw(im)
            for y in range(0,h,20):
                d.line((0,y,w,y),fill="#23414a")
            for x in range(-20,w+40,28):
                shift=round(6*math.sin(n/13))
                d.line((x+shift,0,x+shift,h),fill="#23414a")
            d.ellipse((38,35,290,287),fill="#7fc8b2")
            x=round(7*math.sin(n/10))
            d.ellipse((43+x,250,278+x,476),fill="#d8a256")
            d.rounded_rectangle((131+x,213,189+x,283),radius=18,fill="#a96548")
            d.ellipse((99+x,111,215+x,245),fill="#d9966c")
            d.pieslice((92+x,89,223+x,211),165,347,fill="#312e37")
            d.ellipse((125+x,173,132+x,181),fill="#312e37")
            d.ellipse((176+x,173,183+x,181),fill="#312e37")
            d.arc((141+x,194,172+x,215),12,158,fill="#78453a",width=3)
            d.line((167+x,172,162+x,190,169+x,191),fill="#b57151",width=2)
            d.line((156+x,292,156+x,399),fill="#bd8441",width=2)
            ffmpeg.stdin.write(im.tobytes())
        ffmpeg.stdin.close()
        if ffmpeg.wait(): raise ValueError("Could not create the test clip")
    finally:
        if ffmpeg.poll() is None: ffmpeg.kill()


def check(args):
    work=LOCAL/"effects-proof"
    work.mkdir(exist_ok=True)
    dest=ROOT/"web/previews"
    dest.mkdir(exist_ok=True)
    src=work/"presenter.mp4"
    source_clip(src)
    headroom=work/"presenter-headroom.mp4"
    ff("ffmpeg","-v","error","-y","-i",src,"-vf","scale=224:280,pad=320:400:48:120:color=0x172c37",headroom)
    for source in (src,headroom):
        ff("ffmpeg","-v","error","-y","-i",source,"-vf","fps=5,scale=256:-1","-loop","0",source.with_suffix(".webp"))
    def one(item):
        key=item["id"]
        out=dest/(key+".webp")
        proof=work/key
        proof.mkdir(exist_ok=True)
        clip=proof/"render.mp4"
        if not clip.exists() or not out.exists() or args.force:
            source = headroom if key == "countdown-flip" else src
            render_layers(proof,source,clip,[{"id":key}],2.4)
            temp=proof/"sample.webp"
            ff("ffmpeg","-v","error","-y","-i",clip,"-vf","fps=5,scale=256:-1","-loop","0",temp)
            with Image.open(source.with_suffix(".webp")) as control, Image.open(temp) as rendered:
                if rendered.n_frames < 10: raise ValueError(key+" lost frames")
                changed = False
                for i in range(1,10):
                    control.seek(i); rendered.seek(i)
                    delta=ImageChops.difference(control.convert("RGB"),rendered.convert("RGB")).convert("L")
                    if sum(delta.histogram()[18:]) > rendered.width*rendered.height*.004:
                        changed=True; break
                if not changed: raise ValueError(key+" did not change the sample")
            temp.replace(out)
        return key
    todo=[i for i in CATALOG if i["kind"]=="effect" and (not args.only or i["id"] in args.only)]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        errors=[]
        tasks={i["id"]:pool.submit(one,i) for i in todo}
        for key,future in tasks.items():
            try: print(future.result(),flush=True)
            except Exception as e: errors.append([key,str(e)]); print(key,str(e)[-300:],flush=True)
    save(work/"failed-effects.json",errors)
    if errors: raise SystemExit(1)


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--force",action="store_true")
    p.add_argument("--only",nargs="+")
    p.add_argument("--workers",type=int,default=2,choices=range(1,5))
    check(p.parse_args())
