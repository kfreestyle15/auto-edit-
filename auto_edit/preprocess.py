"""FFmpeg steps: find the playing by sound, trim it, clean and level the audio.

Ported from capcut-auto, where trimming one performance per file was proven on
real recordings; this version keeps every stretch of playing in an exam recording
and drops the silences between them.
"""
import json
import re
import subprocess


class SplitError(RuntimeError):
    """The recording does not split cleanly into the expected number of songs."""


def run(cmd):
    return subprocess.run(cmd, check=True, capture_output=True, text=True)


def probe_duration(path):
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "csv=p=0", path]).stdout
    return float(out.strip())


def sound_regions(path, noise_db, min_silence_s):
    """Return [(start, end)] stretches that are not silence, in time order."""
    proc = subprocess.run(
        ["ffmpeg", "-nostdin", "-hide_banner", "-nostats", "-i", path, "-vn",
         "-af", f"silencedetect=noise={noise_db}dB:d={min_silence_s}", "-f", "null", "-"],
        capture_output=True, text=True, check=True)
    total = probe_duration(path)
    starts = [float(x) for x in re.findall(r"silence_start: (-?[0-9.]+)", proc.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: ([0-9.]+)", proc.stderr)]
    regions, cursor = [], 0.0
    for i, s in enumerate(starts):
        if s > cursor:
            regions.append((cursor, s))
        cursor = ends[i] if i < len(ends) else total
    if cursor < total:
        regions.append((cursor, total))
    return [(max(0.0, a), b) for a, b in regions if b - a > 0.05]


def merge_close(regions, max_gap):
    """Join stretches separated by a short pause, e.g. a rest inside a song."""
    merged = []
    for a, b in regions:
        if merged and a - merged[-1][1] < max_gap:
            merged[-1] = (merged[-1][0], b)
        else:
            merged.append((a, b))
    return merged


def pick_segments(regions, n_songs, min_block_s, total, pad_start, pad_end):
    """Keep every stretch of playing, padded, so the silences between them can be cut.

    A pause can be a change of song or a page turn mid-song, and the audio cannot
    tell them apart, so all playing is kept rather than guessing song edges. Fewer
    stretches than songs means a song is missing, so a person checks.
    """
    blocks = [r for r in regions if r[1] - r[0] >= min_block_s]
    if len(blocks) < n_songs:
        raise SplitError(f"tên file ghi {n_songs} bài nhưng chỉ dò được {len(blocks)} "
                         f"đoạn đàn")
    segments = []
    for a, b in blocks:
        a, b = max(0.0, a - pad_start), min(total, b + pad_end)
        if segments and a <= segments[-1][1]:
            segments[-1] = (segments[-1][0], b)
        else:
            segments.append((a, b))
    return segments


def music_segments(path, n_songs, subject, cfg):
    """Return [(start, end)] of the playing in the recording, in time order."""
    s = cfg["silence"][subject]
    regions = merge_close(sound_regions(path, s["noise_db"], s["min_silence_s"]),
                          cfg["merge_gap_s"])
    return pick_segments(regions, n_songs, cfg["min_block_s"], probe_duration(path),
                         cfg["pad_start_s"], cfg["pad_end_s"])


def _scale_filter(out_w, out_h):
    """Fit portrait clips into out_w x out_h and landscape clips into out_h x out_w.
    Decided on the frames after FFmpeg applies phone rotation metadata."""
    return (f"scale=w='if(gte(ih,iw),{out_w},{out_h})':h='if(gte(ih,iw),{out_h},{out_w})'"
            ":force_original_aspect_ratio=decrease:force_divisible_by=2")


def normalize(path, start, end, out_path, target_lufs, out_size):
    """Cut [start, end], denoise lightly and bring loudness to target_lufs."""
    span = ["-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", path]
    clean = "afftdn=nf=-25"
    loud = f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11"
    measure = subprocess.run(
        ["ffmpeg", "-nostdin", "-hide_banner", "-nostats", *span, "-vn",
         "-af", f"{clean},{loud}:print_format=json", "-f", "null", "-"],
        capture_output=True, text=True, check=True).stderr
    m = json.loads(measure[measure.rindex("{"):measure.rindex("}") + 1])
    second = (f"{loud}:measured_I={m['input_i']}:measured_TP={m['input_tp']}"
              f":measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}"
              f":offset={m['target_offset']}:linear=true")
    run(["ffmpeg", "-nostdin", "-hide_banner", "-y", *span,
         "-vf", _scale_filter(*out_size),
         "-af", f"{clean},{second}",
         "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart",
         out_path])
    return out_path


def integrated_lufs(path):
    err = subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-nostats", "-i", path, "-vn",
                          "-af", "ebur128", "-f", "null", "-"],
                         capture_output=True, text=True, check=True).stderr
    return float(re.findall(r"I:\s+(-?[0-9.]+) LUFS", err)[-1])
