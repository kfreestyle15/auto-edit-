"""Assemble a finished video: graded clips joined by crossfades, captions, logo.

Each clip is cut and graded on its own first, so the final filtergraph only
joins same-format 1080p clips; that keeps it short and easy to debug.
"""
import json
import os
import subprocess
from dataclasses import dataclass, field

from . import luts
from .preprocess import probe_duration, run

FPS = 25
LUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "assets", "luts")


@dataclass
class Overlay:
    png: str          # full-frame transparent PNG
    start: float      # seconds on the output timeline
    duration: float
    fade_s: float = 0.6


@dataclass
class Job:
    segments: list                    # [(src, start, end)]
    size: tuple                       # (width, height) of the output
    out_path: str
    work_dir: str
    intro: str = None                 # finished clips at the same size and FPS
    outro: str = None
    watermark: str = None             # full-frame PNG shown over the body only
    overlays: list = field(default_factory=list)  # times relative to the body start
    look: str = "soft-film"
    xfade_s: float = 0.5
    target_lufs: float = -14


def probe(path):
    out = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
               "stream=width,height,color_transfer:stream_side_data=rotation",
               "-of", "json", path]).stdout
    s = json.loads(out)["streams"][0]
    rot = abs(int(next((d["rotation"] for d in s.get("side_data_list", []) if "rotation" in d), 0)))
    w, h = (s["height"], s["width"]) if rot in (90, 270) else (s["width"], s["height"])
    return {"width": w, "height": h, "hlg": s.get("color_transfer") == "arib-std-b67"}


def output_size(src, long_side=1920, short_side=1080):
    """Keep the orientation the recording was made in."""
    p = probe(src)
    return (short_side, long_side) if p["height"] >= p["width"] else (long_side, short_side)


def _lut_path(look, hlg):
    path = os.path.join(LUT_DIR, f"{look}{'-hlg' if hlg else ''}.cube")
    if not os.path.exists(path):
        luts.write_luts(LUT_DIR, look)
    return path


def grade_filter(src, size, look):
    """Fit into size, convert HDR to SDR when needed, apply the look, end as BT.709."""
    w, h = size
    hlg = probe(src)["hlg"]
    matrix = "bt2020" if hlg else "bt709"
    lut = _lut_path(look, hlg).replace(":", r"\:")
    return (f"scale={w}:{h}:force_original_aspect_ratio=decrease:in_color_matrix={matrix}"
            f":out_range=pc,format=gbrp16le,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black,"
            f"lut3d=file='{lut}':interp=tetrahedral,"
            f"scale=out_color_matrix=bt709:out_range=tv,format=yuv420p,fps={FPS},"
            "setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709")


ENC_TAGS = ["-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709"]


def cut_clip(src, start, end, size, look, out):
    """One graded clip with clean AAC audio at 48 kHz."""
    run(["ffmpeg", "-nostdin", "-hide_banner", "-y", "-hwaccel", "videotoolbox",
         "-ss", f"{start:.3f}", "-t", f"{end - start:.3f}", "-i", src,
         "-vf", grade_filter(src, size, look),
         "-af", "aresample=48000,aformat=channel_layouts=stereo",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", *ENC_TAGS,
         "-c:a", "aac", "-b:a", "256k", out])
    return out


def _chain(durations, xfade):
    """Join inputs with xfade/acrossfade. Returns (video graph, audio graph, start of
    each input on the output timeline, total length)."""
    vparts = [f"[{i}:v]settb=AVTB,fps={FPS},format=yuv420p[v{i}]" for i in range(len(durations))]
    aparts = [f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo[a{i}]"
              for i in range(len(durations))]
    starts, t, vprev, aprev = [0.0], durations[0], "v0", "a0"
    for i in range(1, len(durations)):
        off = t - xfade
        starts.append(off)
        vparts.append(f"[{vprev}][v{i}]xfade=transition=fade:duration={xfade}:offset={off:.3f}[vx{i}]")
        aparts.append(f"[{aprev}][a{i}]acrossfade=d={xfade}:c1=tri:c2=tri[ax{i}]")
        vprev, aprev, t = f"vx{i}", f"ax{i}", off + durations[i]
    return ";".join(vparts), vprev, ";".join(aparts), aprev, starts, t


def _loudnorm_pass1(inputs, agraph, alabel, target):
    err = subprocess.run(
        ["ffmpeg", "-nostdin", "-hide_banner", "-nostats", *inputs, "-filter_complex",
         f"{agraph};[{alabel}]loudnorm=I={target}:TP=-1.5:LRA=11:print_format=json[aout]",
         "-map", "[aout]", "-f", "null", "-"],
        capture_output=True, text=True, check=True).stderr
    return json.loads(err[err.rindex("{"):err.rindex("}") + 1])


def render(job):
    os.makedirs(job.work_dir, exist_ok=True)
    clips = []
    for i, (src, a, b) in enumerate(job.segments):
        clips.append(cut_clip(src, a, b, job.size, job.look,
                              os.path.join(job.work_dir, f"clip_{i:02d}.mp4")))
    files = [f for f in [job.intro, *clips, job.outro] if f]
    durations = [probe_duration(f) for f in files]
    inputs = sum((["-i", f] for f in files), [])
    vgraph, vlab, agraph, alab, starts, total = _chain(durations, job.xfade_s)

    m = _loudnorm_pass1(inputs, agraph, alab, job.target_lufs)
    loud = (f"loudnorm=I={job.target_lufs}:TP=-1.5:LRA=11:measured_I={m['input_i']}"
            f":measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}"
            f":measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")

    body_start = starts[1] if job.intro else 0.0
    body_end = starts[-1] + job.xfade_s if job.outro else total
    graph, extra, n = f"{vgraph};{agraph}", [], len(files)
    if job.watermark:
        extra.append(("-loop", "1", "-t", f"{total:.3f}", "-i", job.watermark))
        graph += (f";[{n}:v]format=rgba,colorchannelmixer=aa=0.8[wm];"
                  f"[{vlab}][wm]overlay=0:0:enable='between(t,{body_start:.3f},{body_end:.3f})'[vw]")
        vlab, n = "vw", n + 1
    for k, ov in enumerate(job.overlays):
        t0 = body_start + ov.start
        extra.append(("-loop", "1", "-t", f"{ov.duration:.3f}", "-i", ov.png))
        graph += (f";[{n}:v]format=rgba,fade=in:st=0:d={ov.fade_s}:alpha=1,"
                  f"fade=out:st={ov.duration - ov.fade_s:.3f}:d={ov.fade_s}:alpha=1,"
                  f"setpts=PTS-STARTPTS+{t0:.3f}/TB[ov{k}];"
                  f"[{vlab}][ov{k}]overlay=0:0:eof_action=pass[vo{k}]")
        vlab, n = f"vo{k}", n + 1
    graph += (f";[{vlab}]setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709"
              f":range=tv[vout];[{alab}]{loud},aresample=48000[aout]")

    run(["ffmpeg", "-nostdin", "-hide_banner", "-y", *inputs, *sum(map(list, extra), []),
         "-filter_complex", graph, "-map", "[vout]", "-map", "[aout]",
         "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", *ENC_TAGS,
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", job.out_path])
    return job.out_path
