import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRIVE_DIRS = {
    "ktck": "KTCK",
    "ktck_consent": os.path.join("KTCK", "duoc-dang"),
    "trend": "trend-clips",
    "review": "cho-duyet",
    "approved": "da-duyet",
    "posted": "da-dang",
    "error": "loi",
}


def load_config(path=None, drive_root=None):
    """Read config.json and resolve every folder the pipeline touches."""
    path = path or os.path.join(ROOT, "config.json")
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    cfg["drive_root"] = os.path.expanduser(drive_root or cfg["drive_root"])
    for key, rel in DRIVE_DIRS.items():
        cfg[f"{key}_dir"] = os.path.join(cfg["drive_root"], rel)
    cfg["root"] = ROOT
    for name in ("work", "output", "logs"):
        cfg[f"{name}_dir"] = os.path.join(ROOT, name)
    cfg["db_path"] = os.path.join(ROOT, "state.sqlite")
    return cfg
