import os
import subprocess
import tempfile
import unittest

from auto_edit import preprocess
from auto_edit.preprocess import SplitError, merge_close, pick_segments

CFG = {
    "silence": {"piano": {"noise_db": -50, "min_silence_s": 3.0}},
    "merge_gap_s": 3.0, "min_block_s": 2.0, "pad_start_s": 0.5, "pad_end_s": 1.0,
}


def make_audio(path, pieces):
    """pieces: list of (seconds, kind) with kind in {'tone', 'quiet', 'silence'}."""
    srcs = {"tone": "sine=frequency=440:sample_rate=48000:duration={}",
            "quiet": "sine=frequency=300:sample_rate=48000:duration={},volume=0.001",
            "silence": "anullsrc=r=48000:cl=mono:d={}"}
    inputs, labels = [], []
    for i, (sec, kind) in enumerate(pieces):
        inputs += ["-f", "lavfi", "-i", srcs[kind].format(sec)]
        labels.append(f"[{i}:a]")
    concat = "".join(labels) + f"concat=n={len(pieces)}:v=0:a=1[a]"
    subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", concat,
                    "-map", "[a]", "-c:a", "aac", path], check=True)


class PickSegmentsTest(unittest.TestCase):
    def test_keeps_every_block_with_padding(self):
        regions = [(10, 50), (70, 90), (110, 150), (170, 200)]
        self.assertEqual(pick_segments(regions, 3, 2, 300, 0.5, 1.0),
                         [(9.5, 51.0), (69.5, 91.0), (109.5, 151.0), (169.5, 201.0)])

    def test_drops_clicks_shorter_than_min_block(self):
        segs = pick_segments([(10, 50), (60, 61), (70, 90), (110, 150)], 3, 2, 300, 0, 0)
        self.assertEqual(segs, [(10, 50), (70, 90), (110, 150)])

    def test_padding_that_overlaps_is_merged(self):
        segs = pick_segments([(10, 50), (51, 90), (110, 150)], 2, 2, 300, 0.5, 1.0)
        self.assertEqual(segs, [(9.5, 90.0 + 1.0), (109.5, 151.0)])

    def test_padding_stays_inside_the_file(self):
        segs = pick_segments([(0.2, 50), (60, 99.8)], 2, 2, 100, 0.5, 1.0)
        self.assertEqual(segs, [(0.0, 51.0), (59.5, 100)])

    def test_fewer_blocks_than_songs_refuses(self):
        with self.assertRaisesRegex(SplitError, "ghi 3 bài nhưng chỉ dò được 2"):
            pick_segments([(0, 60), (70, 130), (140, 141)], 3, 2, 200, 1, 1)

    def test_merge_close(self):
        self.assertEqual(merge_close([(0, 10), (12, 20), (30, 40)], 3.0), [(0, 20), (30, 40)])


class MusicSegmentsFileTest(unittest.TestCase):
    """Three tone 'songs' separated by silence, with near-silent noise between."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.clip = os.path.join(cls.tmp.name, "exam.m4a")
        make_audio(cls.clip, [(4, "silence"), (40, "tone"), (5, "silence"), (6, "quiet"),
                              (5, "silence"), (35, "tone"), (6, "silence"), (45, "tone"),
                              (4, "silence")])

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_finds_the_playing_within_tolerance(self):
        segs = preprocess.music_segments(self.clip, 3, "piano", CFG)
        expected = [(4, 44), (60, 95), (101, 146)]
        self.assertEqual(len(segs), 3)
        for (a, b), (ea, eb) in zip(segs, expected):
            self.assertLess(abs((a + CFG["pad_start_s"]) - ea), 1.5)
            self.assertLess(abs((b - CFG["pad_end_s"]) - eb), 1.5)

    def test_more_songs_than_blocks_refuses(self):
        with self.assertRaises(SplitError):
            preprocess.music_segments(self.clip, 4, "piano", CFG)


if __name__ == "__main__":
    unittest.main()
