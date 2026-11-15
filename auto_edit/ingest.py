"""Register new KTCK recordings from the Drive folders.

Every video is registered so it can be edited; only files in KTCK/duoc-dang/
get consent=1, and publishing refuses anything without it.
"""
import logging
import os
import shutil
import time

from . import state
from .naming import FileNameError, is_video, parse_ktck

log = logging.getLogger(__name__)
SETTLE_S = 120  # a file still being uploaded by Drive keeps changing; wait it out


def _files(folder):
    if not os.path.isdir(folder):
        return []
    return sorted(os.path.join(folder, n) for n in os.listdir(folder)
                  if not n.startswith(".") and os.path.isfile(os.path.join(folder, n)))


def _reject(path, reason, error_dir):
    os.makedirs(error_dir, exist_ok=True)
    name = os.path.basename(path)
    shutil.move(path, os.path.join(error_dir, name))
    with open(os.path.join(error_dir, name + ".loi.txt"), "w", encoding="utf-8") as f:
        f.write(reason + "\n")
    log.warning("bỏ qua %s: %s (đã chuyển vào loi/)", name, reason)


def ingest_ktck(cfg, db, now=None):
    now = now or time.time()
    summary = {"new": [], "consent_granted": [], "rejected": [], "waiting_upload": []}
    for folder, consent in ((cfg["ktck_dir"], False), (cfg["ktck_consent_dir"], True)):
        for path in _files(folder):
            name = os.path.basename(path)
            if not is_video(path):
                continue
            if now - os.path.getmtime(path) < SETTLE_S:
                summary["waiting_upload"].append(name)
                continue
            try:
                info = parse_ktck(path)
            except FileNameError as e:
                _reject(path, str(e), cfg["error_dir"])
                summary["rejected"].append({"file": name, "reason": str(e)})
                continue
            fp = state.fingerprint(path)
            row = state.find(db, fp)
            if row:
                if consent and not row["consent"]:
                    state.update(db, row["id"], consent=1, src_path=path)
                    summary["consent_granted"].append(name)
                continue
            meta = {"subject": info.subject, "student": info.student,
                    "songs": list(info.songs), "exam_date": info.exam_date.isoformat(),
                    "stem": info.stem}
            item_id = state.add(db, "ktck", path, fp, consent, meta)
            summary["new"].append({"id": item_id, "file": name, "consent": consent})
            log.info("đã nhận %s (id %s, đồng ý đăng: %s)", name, item_id, consent)
    return summary
