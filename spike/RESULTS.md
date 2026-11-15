# Phase 1: Kết quả thử nghiệm cổng

Ngày bắt đầu: 15/11/2026

## Chuẩn bị (đã xong)

- Script `spike/post_scheduled.py` chỉ dùng thư viện chuẩn của Python. Token được đọc từ Keychain (service `auto-edit-fb`, account `page`) và không bao giờ được in ra.
- Hai video thử, mỗi video dài 20 giây và có tiếng:
  - `spike/test-16x9.mp4`: 1920×1080.
  - `spike/test-9x16.mp4`: 1080×1920.
- Đã chạy `--dry-run` cho cả hai loại và đều đạt. Lịch được tính đúng +2 ngày theo giờ Asia/Saigon.
- Python dùng `/opt/homebrew/bin/python3` (bản 3.15). Python của hệ thống chỉ là bản 3.9.
- Graph API đang đặt phiên bản `v23.0`. Nếu API báo phiên bản đã cũ, đặt biến `FB_GRAPH_VERSION` sang phiên bản mới hơn.

## Bài học: lưu token vào Keychain

Nếu dán token vào ô nhập sau lệnh `security add-generic-password ... -w` (không kèm giá trị), Keychain chỉ giữ **128 ký tự đầu** và không báo lỗi gì. Graph API khi đó trả về lỗi `code=190`: "The access token could not be decrypted". Hiện tượng này đã gặp ngày 15/11/2026.

Cách lưu đúng là lấy token thẳng từ clipboard:

```bash
security add-generic-password -U -s auto-edit-fb -a page -w "$(pbpaste | tr -d '[:space:]\"')"
```

## A1: Đăng video thường có hẹn giờ

- Trạng thái: **ĐẠT** (15/11/2026, 21:42).
- Token trang được lưu trong Keychain. Lệnh `whoami` trả về đúng trang "Khoa Anh Music" (id 890360664349269).
- Gọi `POST graph-video.facebook.com/v23.0/{page}/videos` với `published=false` và `scheduled_publish_time` hẹn sau 2 ngày, upload kiểu multipart. Kết quả trả về id 1792532655151903, `publish_status: scheduled`, `published: false`.

## A2: Đăng Reel có hẹn giờ

- Trạng thái: **ĐẠT** (15/11/2026, 21:42).
- Upload qua `video_reels` theo ba bước `start`, `rupload`, `finish`, với `video_state=SCHEDULED`. Kết quả: video_id 1147375454562291, post_id 1159635039900272.
- Sau khi upload, video ở trạng thái `processing` khoảng 1 phút, sau đó chuyển sang `ready` và `publish_status: scheduled`. Bước kiểm tra bản quyền (`copyright_check_status`) vẫn đang `in_progress` lúc video đã vào lịch. Vì vậy khâu đăng của phase 4 cần kiểm tra lại trạng thái video sau khi upload.
- Hai video thử được hẹn đăng lúc 17/11/2026 21:42. Người dùng đã xóa cả hai trong Meta Business Suite. Ngày 15/11, lúc 21:49, đã gọi API kiểm tra lại: cả hai ID đều trả về "does not exist".

## A3: Google Drive for desktop (chế độ Mirror)

- Trạng thái: đã cài Google Drive 133.0.2.0. Thư mục mount đã xuất hiện, nhưng lúc 21:49 ngày 15/11 lệnh `ls` vẫn báo "Operation timed out". Có thể Drive đang đồng bộ lần đầu hoặc macOS đang chờ cấp quyền.
- Đường dẫn local: `~/Library/CloudStorage/GoogleDrive-kfreestyle15@gmail.com/My Drive/auto-edit`
- Lúc 21:50 ngày 15/11, đọc lại thư mục vẫn báo "timed out". Log của Drive (`drive_fs.txt`) ghi: "Google Drive has encountered a macOS File Provider error. This might be resolved by restarting your computer." Trường `mirrored_my_drive_watch_path` đang rỗng, tức là Drive chưa ở chế độ Mirror. Hướng xử lý: khởi động lại máy rồi thử lại. Nếu vẫn lỗi thì chuyển sang `rclone` (đường lui đã ghi trong phase 1).
- Sau khi khởi động lại máy (21:54), thư mục đọc được bình thường. Drive vẫn ở chế độ Stream (chưa chọn Mirror). Chế độ này vẫn chạy được: file chỉ tải về khi có chương trình đọc tới.
- 21:57:12: script tạo cấu trúc `auto-edit/` (`KTCK/duoc-dang`, `trend-clips`, `cho-duyet`, `da-duyet`, `da-dang`, `loi`), rồi tạo file `TEST-dong-bo.txt` trong `cho-duyet/` và chuyển sang `da-duyet/`.
- Thời gian đồng bộ sau một lần `mv`: người dùng thấy file nằm trong `da-duyet/` trên Drive web gần như ngay lập tức (ghi nhận 21:57:12, đúng lúc chuyển). **A3 ĐẠT.** File thử sau đó đã được xóa.

## Kết luận phase 1

**Cổng ĐẠT.** Hệ thống đăng được video thường và Reel có hẹn giờ qua Graph API (app ở chế độ Development, không cần App Review). Thư mục Drive đọc và ghi được qua File Provider ở chế độ Stream. Phase 2 bắt đầu với đường dẫn Drive local: `~/Library/CloudStorage/GoogleDrive-kfreestyle15@gmail.com/My Drive/auto-edit`.

Cần nhớ cho các phase sau:
- Python phải chạy bằng `/opt/homebrew/bin/python3`.
- Lưu token bằng `pbpaste`, không dán vào ô nhập của lệnh `security`.
- Upload Reel xong cần kiểm tra lại trạng thái video.
- Nếu Drive lại báo lỗi File Provider, khởi động lại máy.

## Giới hạn API ghi nhận được

- Thời lượng tối đa của Reel:
- Khoảng thời gian hẹn giờ cho phép:
- Số bài đăng qua API mỗi ngày:
