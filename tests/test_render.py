import json
import os
import subprocess
import tempfile
import unittest
from unittest import mock

from auto_edit import brand
from auto_edit import render as render_mod
from auto_edit.preprocess import integrated_lufs, probe_duration
from auto_edit.render import Job, Overlay, render

SIZE = (360, 640)


def make_clip(path, seconds, landscape=False):
    w, h = (640, 360) if landscape else SIZE
    subprocess.run(["ffmpeg", "-v", "error", "-y",
                    "-f", "lavfi", "-i", f"testsrc2=s={w}x{h}:r=30:d={seconds}",
                    "-f", "lavfi", "-i", f"sine=frequency=330:sample_rate=44100:d={seconds},volume=0.1",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", path],
                   check=True)
    return path


class ProbeTest(unittest.TestCase):
    def test_rotation_found_in_any_side_data_entry(self):
        """iPhone files list the display matrix after an empty side-data entry."""
        fake = json.dumps({"streams": [{"width": 3840, "height": 2160,
                                        "color_transfer": "arib-std-b67",
                                        "side_data_list": [{}, {"rotation": -90}, {}]}]})
        with mock.patch.object(render_mod, "run", return_value=mock.Mock(stdout=fake)):
            self.assertEqual(render_mod.output_size("x.mov"), (1080, 1920))
            self.assertTrue(render_mod.probe("x.mov")["hlg"])


class RenderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        d = cls.tmp.name
        cls.cfg = {"work_dir": d, "brand": {"background": [0.04, 0.04, 0.05, 1],
                                            "outro_lines": ["facebook.com/khoaanhmusicshop"]}}
        src = make_clip(os.path.join(d, "src.mp4"), 12)
        wide = make_clip(os.path.join(d, "wide.mp4"), 5, landscape=True)
        caption = brand.lower_third(SIZE, "Phương Quỳnh", ["Piano · Kiểm tra cuối khóa"],
                                    os.path.join(d, "cap.png"), d)
        cls.job = Job(segments=[(src, 1, 5), (src, 7, 11), (wide, 0, 4)], size=SIZE,
                      out_path=os.path.join(d, "out.mp4"), work_dir=os.path.join(d, "job"),
                      intro=brand.make_intro(SIZE, cls.cfg), outro=brand.make_outro(SIZE, cls.cfg),
                      watermark=brand.make_watermark(SIZE, cls.cfg),
                      overlays=[Overlay(caption, 0.5, 3)])
        render(cls.job)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def streams(self):
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                              "stream=codec_type,width,height,color_primaries", "-of", "json",
                              self.job.out_path], capture_output=True, text=True, check=True)
        return json.loads(out.stdout)["streams"]

    def test_size_audio_and_colour_tags(self):
        v = [s for s in self.streams() if s["codec_type"] == "video"][0]
        self.assertEqual((v["width"], v["height"]), SIZE)
        self.assertEqual(v["color_primaries"], "bt709")
        self.assertTrue(any(s["codec_type"] == "audio" for s in self.streams()))

    def test_duration_is_clips_minus_crossfades(self):
        expected = 3.0 + 4 + 4 + 4 + 4.0 - 4 * self.job.xfade_s
        self.assertAlmostEqual(probe_duration(self.job.out_path), expected, delta=0.3)

    def test_loudness_on_target(self):
        self.assertAlmostEqual(integrated_lufs(self.job.out_path), -14, delta=1.0)


if __name__ == "__main__":
    unittest.main()
