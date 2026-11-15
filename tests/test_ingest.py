import os
import shutil
import tempfile
import time
import unittest

from auto_edit import state
from auto_edit.config import load_config
from auto_edit.ingest import ingest_ktck

GOOD = "KTCK_Piano_Bảo Lam_Bai-1+Bai-2+Bai-3_15-11-2026.MOV"


class IngestTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.cfg = load_config(drive_root=self.tmp)
        os.makedirs(self.cfg["ktck_consent_dir"])
        self.db = state.connect(":memory:")
        self.later = time.time() + 3600  # pretend every file finished uploading

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def put(self, folder, name, data=b"video-bytes"):
        path = os.path.join(self.cfg[folder], name)
        with open(path, "wb") as f:
            f.write(data)
        return path

    def test_consent_only_from_duoc_dang(self):
        self.put("ktck_consent_dir", GOOD, b"a")
        self.put("ktck_dir", GOOD.replace("Bảo Lam", "An"), b"b")
        out = ingest_ktck(self.cfg, self.db, now=self.later)
        consents = {n["file"]: n["consent"] for n in out["new"]}
        self.assertTrue(consents[GOOD])
        self.assertFalse(consents[GOOD.replace("Bảo Lam", "An")])

    def test_rerun_does_not_duplicate(self):
        self.put("ktck_consent_dir", GOOD)
        ingest_ktck(self.cfg, self.db, now=self.later)
        out = ingest_ktck(self.cfg, self.db, now=self.later)
        self.assertEqual(out["new"], [])
        self.assertEqual(len(state.by_status(self.db, "new")), 1)

    def test_moving_into_duoc_dang_grants_consent(self):
        src = self.put("ktck_dir", GOOD)
        ingest_ktck(self.cfg, self.db, now=self.later)
        shutil.move(src, os.path.join(self.cfg["ktck_consent_dir"], GOOD))
        out = ingest_ktck(self.cfg, self.db, now=self.later)
        self.assertEqual(out["consent_granted"], [GOOD])
        self.assertEqual(state.by_status(self.db, "new")[0]["consent"], 1)

    def test_bad_name_moves_to_loi_with_reason(self):
        self.put("ktck_consent_dir", "KTCK_Violin_An_Canon_01-01-2026.mp4")
        out = ingest_ktck(self.cfg, self.db, now=self.later)
        self.assertEqual(len(out["rejected"]), 1)
        moved = os.path.join(self.cfg["error_dir"], "KTCK_Violin_An_Canon_01-01-2026.mp4")
        self.assertTrue(os.path.exists(moved))
        with open(moved + ".loi.txt", encoding="utf-8") as f:
            self.assertIn("môn", f.read())

    def test_ignores_images_and_files_still_uploading(self):
        self.put("ktck_consent_dir", "LOGO KHOA ANH PNG-02.png")
        self.put("ktck_consent_dir", GOOD)
        out = ingest_ktck(self.cfg, self.db, now=time.time())
        self.assertEqual(out["new"], [])
        self.assertEqual(out["waiting_upload"], [GOOD])
        self.assertTrue(os.path.exists(os.path.join(self.cfg["ktck_consent_dir"],
                                                    "LOGO KHOA ANH PNG-02.png")))

    def test_fingerprint_reads_head_and_tail_only(self):
        big = self.put("ktck_dir", "big.mov", b"x" * (9 * 1024 * 1024))
        same = self.put("ktck_consent_dir", "copy.mov", b"x" * (9 * 1024 * 1024))
        self.assertEqual(state.fingerprint(big), state.fingerprint(same))
        other = self.put("ktck_dir", "other.mov", b"x" * (9 * 1024 * 1024 - 1) + b"y")
        self.assertNotEqual(state.fingerprint(big), state.fingerprint(other))


if __name__ == "__main__":
    unittest.main()
