"""Generate the colour LUTs as .cube files, so the look is ours and needs no licence.

Two files per look:
- `<look>.cube` takes ordinary BT.709 video.
- `<look>-hlg.cube` takes iPhone HDR (HLG, BT.2020) and first maps it to BT.709
  SDR. The installed FFmpeg has no zscale, so the tone mapping lives in the LUT.

The "soft-film" look: lifted blacks, gentle midtone contrast, warm highlights,
slightly cool shadows and a little less saturation.
"""
import math
import os

SIZE = 33

# HLG constants, ITU-R BT.2100
_A, _B, _C = 0.17883277, 0.28466892, 0.55991073
# Linear BT.2020 -> BT.709 primaries, ITU-R BT.2087
_M2020_709 = ((1.6605, -0.5876, -0.0728),
              (-0.1246, 1.1329, -0.0083),
              (-0.0182, -0.1006, 1.1187))
HLG_PEAK_NITS, SDR_WHITE_NITS = 1000.0, 450.0  # 450 keeps white walls from clipping
KNEE = 0.6  # SDR level where the highlight roll-off starts


def _hlg_to_scene(e):
    return e * e / 3 if e <= 0.5 else (math.exp((e - _C) / _A) + _B) / 12


def _shoulder(x):
    """Identity below KNEE, then an exponential roll-off that approaches 1.0."""
    if x <= KNEE:
        return x
    room = 1 - KNEE
    return KNEE + room * (1 - math.exp(-(x - KNEE) / room))


def hlg_to_sdr(r, g, b):
    """HLG BT.2020 signal (0..1) -> BT.709 gamma-encoded signal (0..1)."""
    rgb = [_hlg_to_scene(v) for v in (r, g, b)]
    ys = 0.2627 * rgb[0] + 0.6780 * rgb[1] + 0.0593 * rgb[2]
    gain = (ys ** 0.2 if ys > 0 else 0) * HLG_PEAK_NITS / SDR_WHITE_NITS  # HLG OOTF, gamma 1.2
    lin = [v * gain for v in rgb]
    lin = [sum(m * v for m, v in zip(row, lin)) for row in _M2020_709]
    return tuple(max(0.0, _shoulder(v)) ** (1 / 2.4) for v in lin)


def _smoothstep(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def soft_film(r, g, b, strength=0.8):
    """Creative look on a BT.709 signal (0..1)."""
    out = []
    luma = 0.2126 * r + 0.7152 * g + 0.0722 * b
    hi, lo = _smoothstep((luma - 0.45) / 0.5), 1 - _smoothstep(luma / 0.4)
    tint = ((0.035 * hi - 0.010 * lo), (0.010 * hi + 0.004 * lo), (-0.030 * hi + 0.012 * lo))
    for v, t in zip((r, g, b), tint):
        s = v + 0.12 * math.sin(math.pi * (v - 0.5)) / math.pi * 2 * 0.5  # gentle S-curve
        s = 0.035 + s * (0.955 - 0.035)  # lift blacks, soften whites
        out.append(s + t)
    y = 0.2126 * out[0] + 0.7152 * out[1] + 0.0722 * out[2]
    out = [y + 0.88 * (v - y) for v in out]  # 12 % less saturation
    return tuple(min(1.0, max(0.0, o * strength + v * (1 - strength)))
                 for o, v in zip(out, (r, g, b)))


def write_cube(path, fn, title):
    with open(path, "w") as f:
        f.write(f'TITLE "{title}"\nLUT_3D_SIZE {SIZE}\n')
        for bi in range(SIZE):  # .cube order: red changes fastest
            for gi in range(SIZE):
                for ri in range(SIZE):
                    r, g, b = fn(ri / (SIZE - 1), gi / (SIZE - 1), bi / (SIZE - 1))
                    f.write(f"{r:.6f} {g:.6f} {b:.6f}\n")
    return path


def write_luts(out_dir, look="soft-film"):
    os.makedirs(out_dir, exist_ok=True)
    sdr = write_cube(os.path.join(out_dir, f"{look}.cube"), soft_film, look)
    hlg = write_cube(os.path.join(out_dir, f"{look}-hlg.cube"),
                     lambda r, g, b: soft_film(*hlg_to_sdr(r, g, b)), f"{look} from HLG")
    return sdr, hlg


if __name__ == "__main__":
    print(*write_luts(os.path.join(os.path.dirname(__file__), "..", "assets", "luts")))
