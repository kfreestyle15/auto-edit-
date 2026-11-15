"""Gate test: can a script schedule a normal video and a Reel on the Page via Graph API?

Token is read from macOS Keychain (service "auto-edit-fb", account "page") and is
never printed. Stdlib only, so it runs before the project has dependencies.

Usage:
  python3 spike/post_scheduled.py whoami
  python3 spike/post_scheduled.py video spike/test-16x9.mp4 --days 2
  python3 spike/post_scheduled.py reel  spike/test-9x16.mp4 --days 2
  add --dry-run to print what would be sent without calling the API.
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

GRAPH_VERSION = os.environ.get("FB_GRAPH_VERSION", "v23.0")
GRAPH = f"https://graph.facebook.com/{GRAPH_VERSION}"
GRAPH_VIDEO = f"https://graph-video.facebook.com/{GRAPH_VERSION}"
RUPLOAD = f"https://rupload.facebook.com/video-upload/{GRAPH_VERSION}"
CAPTION = "[auto-edit thử nghiệm] Video kiểm tra hẹn giờ, sẽ được xóa."


def page_token():
    try:
        return subprocess.run(
            ["security", "find-generic-password", "-s", "auto-edit-fb", "-a", "page", "-w"],
            check=True, capture_output=True, text=True).stdout.strip()
    except subprocess.CalledProcessError:
        sys.exit("Chưa có token trong Keychain (service auto-edit-fb, account page).")


def call(req):
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            err = json.loads(body).get("error", {})
            msg = f"HTTP {e.code} code={err.get('code')} subcode={err.get('error_subcode')}: {err.get('message')}"
        except ValueError:
            msg = f"HTTP {e.code}: {body[:300]}"
        sys.exit(msg)


def post_form(url, fields):
    data = urllib.parse.urlencode(fields).encode()
    return call(urllib.request.Request(url, data=data, method="POST"))


def post_multipart(url, fields, file_field, path):
    boundary = uuid.uuid4().hex
    parts = []
    for k, v in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    with open(path, "rb") as f:
        blob = f.read()
    parts.append((f'--{boundary}\r\nContent-Disposition: form-data; name="{file_field}"; '
                  f'filename="{os.path.basename(path)}"\r\nContent-Type: video/mp4\r\n\r\n').encode())
    parts.append(blob + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    req = urllib.request.Request(url, data=b"".join(parts), method="POST",
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    return call(req)


def whoami(token):
    q = urllib.parse.urlencode({"fields": "id,name", "access_token": token})
    return call(urllib.request.Request(f"{GRAPH}/me?{q}"))


def schedule_video(token, page_id, path, ts):
    return post_multipart(f"{GRAPH_VIDEO}/{page_id}/videos", {
        "access_token": token, "description": CAPTION,
        "published": "false", "scheduled_publish_time": str(ts)}, "source", path)


def schedule_reel(token, page_id, path, ts):
    start = post_form(f"{GRAPH}/{page_id}/video_reels",
                      {"access_token": token, "upload_phase": "start"})
    video_id = start["video_id"]
    with open(path, "rb") as f:
        blob = f.read()
    call(urllib.request.Request(f"{RUPLOAD}/{video_id}", data=blob, method="POST", headers={
        "Authorization": f"OAuth {token}", "offset": "0", "file_size": str(len(blob))}))
    finish = post_form(f"{GRAPH}/{page_id}/video_reels", {
        "access_token": token, "upload_phase": "finish", "video_id": video_id,
        "video_state": "SCHEDULED", "scheduled_publish_time": str(ts), "description": CAPTION})
    return {"video_id": video_id, **finish}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=["whoami", "video", "reel"])
    ap.add_argument("path", nargs="?")
    ap.add_argument("--days", type=float, default=2.0)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    ts = int(time.time() + a.days * 86400)
    if a.dry_run:
        print(json.dumps({"kind": a.kind, "path": a.path, "graph": GRAPH_VERSION,
                          "scheduled_publish_time": ts,
                          "scheduled_local": time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))},
                         ensure_ascii=False))
        return
    token = page_token()
    me = whoami(token)
    if a.kind == "whoami":
        print(json.dumps(me, ensure_ascii=False))
        return
    if not a.path or not os.path.isfile(a.path):
        sys.exit("Thiếu file video.")
    fn = schedule_video if a.kind == "video" else schedule_reel
    out = fn(token, me["id"], a.path, ts)
    print(json.dumps({"page": me.get("name"), "scheduled_local":
                      time.strftime("%Y-%m-%d %H:%M", time.localtime(ts)), **out}, ensure_ascii=False))


if __name__ == "__main__":
    main()
