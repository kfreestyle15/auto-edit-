"""Turn one end-of-course exam recording into a finished video.

Usage: python -m auto_edit.ktck <recording> [--out DIR]
"""
import argparse
import os
import sys
import time

from . import brand
from .config import load_config
from .naming import parse_ktck
from .preprocess import music_segments
from .render import Job, Overlay, output_size, render


def caption_lines(info):
    return [f"{info.subject_label} · Kiểm tra cuối khóa · {info.exam_date:%d/%m/%Y}",
            " · ".join(info.songs)]


def build_job(path, cfg, out_dir=None):
    info = parse_ktck(path)
    segs = music_segments(path, len(info.songs), info.subject, cfg)
    size = output_size(path)
    work = os.path.join(cfg["work_dir"], info.stem)
    os.makedirs(work, exist_ok=True)
    caption = brand.lower_third(size, info.student, caption_lines(info),
                                os.path.join(work, "caption.png"), cfg["work_dir"])
    out_dir = out_dir or cfg["output_dir"]
    os.makedirs(out_dir, exist_ok=True)
    return Job(segments=[(path, a, b) for a, b in segs], size=size,
               out_path=os.path.join(out_dir, info.stem + ".mp4"), work_dir=work,
               intro=brand.make_intro(size, cfg), outro=brand.make_outro(size, cfg),
               watermark=brand.make_watermark(size, cfg),
               overlays=[Overlay(caption, start=0.8, duration=7.0)],
               look=cfg["look"]["ktck"], target_lufs=cfg["target_lufs"])


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("recording")
    ap.add_argument("--out")
    args = ap.parse_args(argv)
    cfg = load_config()
    t = time.time()
    job = build_job(args.recording, cfg, args.out)
    print(f"{len(job.segments)} đoạn đàn, khung {job.size[0]}x{job.size[1]}", flush=True)
    render(job)
    print(f"xong sau {time.time() - t:.0f} giây: {job.out_path}")


if __name__ == "__main__":
    sys.exit(main())
