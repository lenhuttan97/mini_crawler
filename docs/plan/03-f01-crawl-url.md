# P02 — F01: Crawl data từ URL

> **Mục tiêu:** chuyển một URL được phép thành document có Markdown/metadata, xử lý bất đồng bộ.  
> **Dependency:** P01 Shared Platform.

## 1. Yêu cầu chức năng

- Người dùng tạo crawl job cho một URL; nhận `crawl_job_id` ngay.
- Static fetch là mặc định; browser chỉ fallback khi policy cho phép và HTML không đủ nội dung.
- Kết quả gồm canonical URL, title, clean HTML/Markdown, content hash, thời điểm crawl và reason code khi thất bại.
- Khi URL là bài báo điện tử, nhận diện và trích xuất dữ liệu bài báo có cấu trúc: headline, subtitle/summary nếu có, published/updated time, author/byline nếu có, canonical URL, nội dung chính và media metadata được phép.
- Gán đúng một `document_type` chính theo [Document Type Classification spec](../document-classification.md); caller có thể gửi `document_type_hint` nhưng đó chỉ là tín hiệu.
- Lưu `classification_confidence`, `classification_reason` và `needs_review`; nếu không đủ tín hiệu, vẫn lưu Markdown chung với `generic_page` hoặc `unknown`.
- URL tương đương/nội dung không đổi không tạo document/chunk trùng.

## 2. API và trạng thái

| API | Input | Output | Quy tắc |
|---|---|---|---|
| Create crawl job | URL, idempotency key, optional `document_type_hint` | job ID/status | Gọi Policy Gate trước khi enqueue; hint không override classifier. |
| Get crawl job | job ID | progress/status/error code/document ID | Ownership bắt buộc. |
| Get document | document ID | Markdown, `document_type`, confidence/reason, `needs_review`, metadata theo quyền | Không trả raw secret/network capture. |
| Cancel job | job ID | cancellation status | Worker dừng ở checkpoint an toàn. |

## 3. Work breakdown

1. Migration `crawl_jobs`, `documents`, index canonical URL/content hash và foreign key tới `jobs`.
2. Implement crawl service tạo job qua P01; không để controller gọi HTTPX/browser trực tiếp.
3. Static adapter HTTPX: stream, timeout, max bytes, content-type policy, redirect manual validation.
4. Browser adapter: context sandboxed, `robots.txt`, timeout/memory limits, recipe server-side; không login/free JS.
5. Article extractor/normalizer: ưu tiên structured data (`Article` JSON-LD/Open Graph), sau đó main-content extraction theo DOM; loại navigation, quảng cáo, related links và footer; giữ headline/byline/time khi có dữ liệu đáng tin cậy.
6. Document classifier ưu tiên structured metadata → DOM/content pattern → URL pattern → optional caller hint; luôn chọn một type trong taxonomy MVP.
7. Gắn `document_type`, confidence/reason và `needs_review`; không bịa author/time hoặc metadata khi trang không công bố.
8. Persistence: raw/clean content object key server-side; lưu classification và metadata theo type transactionally.
9. Job worker: checkpoint cancellation, classify transient/permanent/policy failure, metrics/audit.

## 4. Test và acceptance

- Unit: URL normalization, content hash, static-vs-browser decision, error classification.
- HTTP integration (respx): success, timeout, oversize, bad MIME, redirect loop/private IP.
- Browser integration: fixture local có JavaScript; selector/JS từ request phải bị từ chối.
- Article/classification: fixture HTML/news JSON-LD do team kiểm soát cho `news_article`, `learning_material`, `technical_documentation`, `listing_page`, thiếu byline/time, caller hint mâu thuẫn và generic/unknown fallback.
- Persistence: cùng content hash không sinh duplicate; storage error không đánh job completed.
- Done khi fixture bài báo tạo structured article + Markdown đúng phần nội dung chính, classifier luôn trả một type/confidence/reason, hint không ép type, generic/unknown được `needs_review` khi cần, URL blocked không chạm adapter network, unit test không gọi Internet.

## 5. Risks/DoD

| Risk | Mitigation |
|---|---|
| SSRF redirect | Policy Gate trước từng hop, egress policy. |
| Browser tốn resource | Queue/concurrency/timeout riêng, fallback có điều kiện. |
| Nội dung trùng | Canonicalization + content hash + idempotency. |

- [ ] API, worker, document persistence và metrics/audit đã có test.
- [ ] Không crawl đồng bộ hoặc auto-follow redirect không kiểm tra.
- [ ] Crawler không thực thi input action/selector/JavaScript của caller/LLM.
