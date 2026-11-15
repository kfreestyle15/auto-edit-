import os
import subprocess
import tempfile
import unittest

from auto_edit import preprocess
from auto_edit.preprocess import SplitError, merge_close, pick_songs

CFG = {
    "silence": {"piano": {"noise_db": -35, "min_silence_s": 2.0}},
    "merge_gap_s": 3.0, "min_song_s": 30, "pad_start_s": 1.0, "pad_end_s": 2.5,
}


def make_audio(path, pieces):
    """pieces: list of (seconds, kind) with kind in {'tone', 'quiet', 'silence'}."""
    srcs = {"tone": "sine=frequency=440:sample_rate=48000:duration={}",
            "quiet": "sine=frequency=300:sample_rate=48000:duration={},volume=0.003",
            "silence": "anullsrc=r=48000:cl=mono:d={}"}
    inputs, labels = [], []
    for i, (sec, kind) in enumerate(pieces):
        inputs += ["-f", "lavfi", "-i", srcs[kind].format(sec)]
        labels.append(f"[{i}:a]")
    concat = "".join(labels) + f"concat=n={len(pieces)}:v=0:a=1[a]"
    subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", concat,
                    "-map", "[a]", "-c:a", "aac", path], check=True)


class PickSongsTest(unittest.TestCase):
    def test_keeps_playing_order_and_pads(self):
        regions = [(0, 10), (12, 100), (110, 120), (130, 200), (210, 290)]
        self.assertEqual(pick_songs(regions, 3, 30, 300, 1.0, 2.5),
                         [(11.0, 102.5), (129.0, 202.5), (209.0, 292.5)])

    def test_too_few_songs(self):
        with self.assertRaisesRegex(SplitError, "ghi 3 bài nhưng chỉ dò được 2"):
            pick_songs([(0, 60), (70, 130), (140, 150)], 3, 30, 200, 1, 1)

    def test_extra_candidate_as_long_as_a_song(self):
        with self.assertRaisesRegex(SplitError, "dò được 4"):
            pick_songs([(0, 60), (70, 130), (140, 200), (210, 250)], 3, 30, 300, 1, 1)

    def test_short_extra_candidate_is_ignored(self):
        songs = pick_songs([(0, 100), (110, 210), (220, 320), (330, 362)], 3, 30, 400, 0, 0)
        self.assertEqual(songs, [(0, 100), (110, 210), (220, 320)])

    def test_merge_close(self):
        self.assertEqual(merge_close([(0, 10), (12, 20), (30, 40)], 3.0), [(0, 20), (30, 40)])


class SplitSongsFileTest(unittest.TestCase):
    """Three tone 'songs' separated by silence, with chatter-level noise between."""

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

    def test_finds_three_songs_within_tolerance(self):
        songs = preprocess.split_songs(self.clip, 3, "piano", CFG)
        expected = [(4, 44), (60, 95), (101, 146)]
        self.assertEqual(len(songs), 3)
        for (a, b), (ea, eb) in zip(songs, expected):
            self.assertLess(abs((a + CFG["pad_start_s"]) - ea), 1.5)
            self.assertLess(abs((b - CFG["pad_end_s"]) - eb), 1.5)

    def test_mismatched_count_refuses(self):
        with self.assertRaises(SplitError):
            preprocess.split_songs(self.clip, 4, "piano", CFG)


if __name__ == "__main__":
    unittest.main()
