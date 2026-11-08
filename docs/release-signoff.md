# Ký duyệt phát hành (Release Sign-off) — Mini Crawler

Tài liệu này ghi lại quy trình kiểm duyệt và ký duyệt trước khi phát hành,
theo Definition of Done trong [08-quality-security-release.md](plan/08-quality-security-release.md).

## 1. Bảo mật (Security review sign-off)
- [ ] SSRF: ma trận kiểm tra scheme, user-info, IPv4/IPv6/private/link-local, DNS multi-record/rebinding, redirect chain, cổng chính sách.
- [ ] Nguồn chính sách: deny-by-default, chỉ nguồn `approved` mới được phép mạng, 증거 quyền phân phối.
- [ ] Phân quyền: ma trận caller/tên thuê/tài nguyên, lưu trữ đối tượng riêng, presigned URL có TTL/quyền.
- [ ] Log/trace/audit redaction: không thô réseau payload, token, cookie, signed URL, secret, nhãn URL cao cardinality.
- [ ] Cách ly quá trình/mạng: trình duyệt, trình tải, FFmpeg, công nhân torrent có giới hạn CPU/RAM/disk/thời gian/mạng.

Chủ sở hữu: ____________________  Ngày: ___________  Ký: ____________

## 2. Sao lưu/phục hồi drill (Backup/restore drill)
- [ ] Dump PostgreSQL / PITR đã được kiểm thử.
- [ ] Phục hồi MinIO từ bản sao lưu đã được kiểm thử.
- [ ] Bản ghi drilling đã được lưu và chủ sở hữu cảnh báo đã xác định.

Chủ sở hữu: ____________________  Ngày: ___________  Ký: ____________

## 3. Benchmark và SLO/threshold
- [ ] Cơ sở chuẩn benchmark đã được đo (bài viết tĩnh, bài viết JavaScript, media trực tiếp, batch ảnh, torrent mẫu).
- [ ] Ngưỡng SLO đã được phê duyệt trong `app/core/slo.py`.
- [ ] Chỉ tiêu độ trễ hàng đợi, thời lượng công việc, tỉ lệ thất bại, bộ nhớ trình duyệt, dung lượng tải xuống.

Chủ sở hữu: ____________________  Ngày: ___________  Ký: ____________

## 4. Tính năng và rollback (Feature flag & rollback)
- [ ] Không có vấn đề critical/high chưa giải quyết.
- [ ] Bật/tắt tính năng đã được diễn tập.
- [ ] Rollback bằng cách tắt tính năng/công nhân hàng đợi trước; không xóa dữ liệu/audit.
- [ ] Migration rollback chỉ sau khi kiểm chứng tính tương thích dữ liệu.

Chủ sở hữu: ____________________  Ngày: ___________  Ký: ____________

## 5. Tài liệu và hạn chế đối với người dùng
- [ ] API docs đã cập nhật đầy đủ.
- [ ] Changelog đã cập nhật (`CHANGELOG.md`).
- [ ] Hạn chế đối với người dùng đã được ghi rõ (trình duyệt dự phòng là stub, torrent chưa tải thật, Docker integration chưa chạy).

Chủ sở hữu: ____________________  Ngày: ___________  Ký: ____________
