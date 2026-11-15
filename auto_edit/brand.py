"""Intro and outro clips, watermark and caption images built from the logo."""
import os

from . import textpng
from .render import ENC_TAGS, FPS
from .preprocess import run

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGO_LIGHT = os.path.join(ROOT, "assets", "logo-light.png")
WHITE = [1, 1, 1, 1]


def _card(size, lines, out, work_dir, bg):
    """Full-frame still: white logo in the middle, optional lines below it.
    Drawn at twice the size so the slow zoom stays sharp."""
    w, h = size[0] * 2, size[1] * 2
    logo = int(min(w, h) * 0.55)
    top = (h - logo) // 2 - (len(lines) * w // 30)
    texts = [{"text": t, "size": w / 26, "weight": "medium", "color": [1, 1, 1, 0.85],
              "x": w / 2, "y": top + logo + i * w / 18, "align": "center", "maxWidth": w * 0.85}
             for i, t in enumerate(lines)]
    return textpng.draw({"width": w, "height": h, "out": out, "background": bg,
                         "images": [{"path": LOGO_LIGHT, "x": (w - logo) / 2, "y": top,
                                     "w": logo, "h": logo}],
                         "texts": texts}, work_dir)


def _animate(still, size, seconds, out, fade_in, fade_out):
    """Slow 4 % zoom with fades, plus silent stereo audio for the crossfades."""
    frames = int(seconds * FPS)
    w, h = size
    vf = (f"zoompan=z='1+0.04*on/{frames}':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2'"
          f":d={frames}:s={w}x{h}:fps={FPS},format=yuv420p")
    if fade_in:
        vf += ",fade=in:st=0:d=0.8"
    if fade_out:
        vf += f",fade=out:st={seconds - 0.8:.2f}:d=0.8"
    run(["ffmpeg", "-nostdin", "-hide_banner", "-y", "-i", still,
         "-f", "lavfi", "-t", f"{seconds}", "-i", "anullsrc=r=48000:cl=stereo",
         "-vf", vf, "-frames:v", str(frames), "-c:v", "libx264", "-preset", "medium",
         "-crf", "18", *ENC_TAGS, "-c:a", "aac", "-shortest", out])
    return out


def _cached(work_dir, name, size):
    d = os.path.join(work_dir, "brand", f"{size[0]}x{size[1]}")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, name)


def make_intro(size, cfg, seconds=3.0):
    out = _cached(cfg["work_dir"], "intro.mp4", size)
    if not os.path.exists(out):
        still = _card(size, [], out[:-4] + ".png", cfg["work_dir"], cfg["brand"]["background"])
        _animate(still, size, seconds, out, fade_in=True, fade_out=False)
    return out


def make_outro(size, cfg, seconds=4.0):
    out = _cached(cfg["work_dir"], "outro.mp4", size)
    if not os.path.exists(out):
        still = _card(size, cfg["brand"]["outro_lines"], out[:-4] + ".png", cfg["work_dir"],
                      cfg["brand"]["background"])
        _animate(still, size, seconds, out, fade_in=False, fade_out=True)
    return out


def make_watermark(size, cfg):
    """White logo, top right, with a soft shadow so it reads on white walls.
    Its width is brand.watermark_scale of the short side of the frame."""
    scale = cfg["brand"].get("watermark_scale", 0.26)
    out = _cached(cfg["work_dir"], f"watermark-{scale:g}.png", size)
    if not os.path.exists(out):
        w, h = size
        logo, margin = int(min(w, h) * scale), int(min(w, h) * 0.03)
        textpng.draw({"width": w, "height": h, "out": out,
                      "images": [{"path": LOGO_LIGHT, "x": w - logo - margin, "y": margin,
                                  "w": logo, "h": logo, "shadow": True}]}, cfg["work_dir"])
    return out


def lower_third(size, title, lines, out, work_dir):
    """Name in large type with smaller lines under it, near the bottom left."""
    w, h = size
    unit = min(w, h)
    x, y = unit * 0.06, h - unit * 0.06 - unit * (0.11 + 0.06 * len(lines))
    texts = [{"text": title, "size": unit * 0.075, "weight": "bold", "color": WHITE,
              "x": x, "y": y, "shadow": True, "maxWidth": w - 2 * x}]
    for i, line in enumerate(lines):
        texts.append({"text": line, "size": unit * 0.04, "weight": "medium",
                      "color": [1, 0.93, 0.82, 1], "x": x, "y": y + unit * (0.1 + 0.06 * i),
                      "shadow": True, "maxWidth": w - 2 * x})
    return textpng.draw({"width": w, "height": h, "out": out, "texts": texts}, work_dir)
