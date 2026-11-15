"""Python side of textpng.swift: compile it once, then draw PNGs from a dict spec."""
import json
import os
import subprocess
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(HERE, "textpng.swift")


def _binary(work_dir):
    exe = os.path.join(work_dir, "bin", "textpng")
    if not os.path.exists(exe) or os.path.getmtime(exe) < os.path.getmtime(SOURCE):
        os.makedirs(os.path.dirname(exe), exist_ok=True)
        subprocess.run(["swiftc", "-O", SOURCE, "-o", exe], check=True,
                       capture_output=True, text=True)
    return exe


def draw(spec, work_dir):
    """spec follows the header of textpng.swift; returns spec['out']."""
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                     encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False)
    try:
        subprocess.run([_binary(work_dir), f.name], check=True, capture_output=True, text=True)
    finally:
        os.unlink(f.name)
    return spec["out"]
