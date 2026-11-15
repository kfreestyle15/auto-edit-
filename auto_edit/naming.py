"""Read exam info from a KTCK file name.

Pattern: KTCK_<Piano|Guitar>_<Tên học viên>_<Bài 1>+<Bài 2>+<Bài 3>_<dd-mm-yyyy>.mov
A hyphen or a space both mean a space; case does not matter; a doubled
extension such as `.MOV.MOV` is accepted because phones and Drive produce it.
"""
import datetime
import os
import unicodedata
from dataclasses import dataclass

SUBJECTS = {"piano": "Piano", "guitar": "Guitar"}
VIDEO_EXTS = (".mov", ".mp4", ".m4v")
PATTERN_HINT = "KTCK_Piano_Ten-Hoc-Vien_Bai-1+Bai-2+Bai-3_dd-mm-yyyy.mp4"


class FileNameError(ValueError):
    """The file name does not follow the agreed pattern."""


@dataclass(frozen=True)
class KtckInfo:
    subject: str          # "piano" | "guitar"
    student: str          # display form, e.g. "Phương Quỳnh"
    songs: tuple          # display forms, in playing order
    exam_date: datetime.date

    @property
    def subject_label(self):
        return SUBJECTS[self.subject]

    @property
    def stem(self):
        """Readable name for outputs, e.g. `2026-11-15_KTCK_Phuong-Quynh`."""
        return f"{self.exam_date.isoformat()}_KTCK_{self.student.replace(' ', '-')}"


def is_video(path):
    return os.path.basename(path).lower().endswith(VIDEO_EXTS)


def _strip_exts(base):
    stem = base
    while stem.lower().endswith(VIDEO_EXTS):
        stem = os.path.splitext(stem)[0]
    return stem


def _display(part, what):
    text = " ".join(part.replace("-", " ").split())
    if not text:
        raise FileNameError(f"{what} bị trống")
    return text.title() if text.isupper() else text


def _date(part):
    raw = part.strip().replace(".", "-")
    try:
        return datetime.datetime.strptime(raw, "%d-%m-%Y").date()
    except ValueError:
        raise FileNameError(f"ngày thi '{part}' không hợp lệ, cần dạng dd-mm-yyyy") from None


def parse_ktck(path):
    base = unicodedata.normalize("NFC", os.path.basename(path))
    if not is_video(base):
        raise FileNameError(f"'{base}' không phải file video .mov/.mp4")
    parts = _strip_exts(base).split("_")
    if len(parts) != 5:
        raise FileNameError(f"tên file cần đúng 5 phần ngăn bằng '_', mẫu: {PATTERN_HINT}")
    tag, subject, student, songs, date = parts
    if tag.strip().upper() != "KTCK":
        raise FileNameError("tên file phải bắt đầu bằng KTCK_")
    subject = subject.strip().lower()
    if subject not in SUBJECTS:
        raise FileNameError(f"môn '{parts[1]}' không hợp lệ, chỉ nhận Piano hoặc Guitar")
    song_list = tuple(_display(s, "tên bài") for s in songs.split("+"))
    return KtckInfo(subject, _display(student, "tên học viên"), song_list, _date(date))
