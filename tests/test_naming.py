import datetime
import unicodedata
import unittest

from auto_edit.naming import FileNameError, is_video, parse_ktck


class ParseKtckTest(unittest.TestCase):
    def test_pattern_with_hyphens_and_accents(self):
        info = parse_ktck("/x/KTCK_Piano_Nguyễn-Văn-A_Für-Elise+Canon+River-Flows_15-11-2026.mp4")
        self.assertEqual(info.subject, "piano")
        self.assertEqual(info.subject_label, "Piano")
        self.assertEqual(info.student, "Nguyễn Văn A")
        self.assertEqual(info.songs, ("Für Elise", "Canon", "River Flows"))
        self.assertEqual(info.exam_date, datetime.date(2026, 11, 15))
        self.assertEqual(info.stem, "2026-11-15_KTCK_Nguyễn-Văn-A")

    def test_real_world_upper_case_spaces_and_double_extension(self):
        info = parse_ktck("KTCK_PIANO_PHƯƠNG QUỲNH_BAI-1+BAI-2+BAI-3_15-11-2026.MOV.MOV")
        self.assertEqual(info.student, "Phương Quỳnh")
        self.assertEqual(info.songs, ("Bai 1", "Bai 2", "Bai 3"))

    def test_decomposed_unicode_is_normalized(self):
        nfd = unicodedata.normalize("NFD", "KTCK_Guitar_Bảo Lam_Hà Nội+Một Nhà_01-02-2026.mov")
        info = parse_ktck(nfd)
        self.assertEqual(info.student, unicodedata.normalize("NFC", "Bảo Lam"))
        self.assertEqual(info.subject, "guitar")
        self.assertEqual(len(info.songs), 2)

    def test_single_song(self):
        self.assertEqual(parse_ktck("KTCK_Piano_An_Canon_01-01-2026.mp4").songs, ("Canon",))

    def test_errors(self):
        bad = {
            "KTCK_Violin_An_Canon_01-01-2026.mp4": "môn",
            "KTCK_Piano_An_Canon_31-02-2026.mp4": "ngày",
            "KTCK_Piano_An_Canon.mp4": "5 phần",
            "THI_Piano_An_Canon_01-01-2026.mp4": "KTCK_",
            "KTCK_Piano__Canon_01-01-2026.mp4": "tên học viên",
            "KTCK_Piano_An_Canon+_01-01-2026.mp4": "tên bài",
            "KTCK_Piano_An_Canon_01-01-2026.png": "video",
        }
        for name, hint in bad.items():
            with self.subTest(name=name):
                with self.assertRaises(FileNameError) as ctx:
                    parse_ktck(name)
                self.assertIn(hint, str(ctx.exception))

    def test_is_video(self):
        self.assertTrue(is_video("a.MOV.MOV"))
        self.assertTrue(is_video("a.mp4"))
        self.assertFalse(is_video("LOGO KHOA ANH PNG-02.png"))


if __name__ == "__main__":
    unittest.main()
