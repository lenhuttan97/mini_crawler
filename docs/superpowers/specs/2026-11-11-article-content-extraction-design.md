# Article Content Extraction — Design

## Intent

Web Crawl hiện chuyển gần như toàn bộ DOM đã lọc một blacklist ngắn thành
Markdown. Điều này làm header, aside, share, comments và khối gợi ý lọt vào
document. Người dùng đã chọn phương án B: chọn đúng một vùng nội dung chính,
trích metadata bài viết có cấu trúc, và không thêm dependency.

Mục tiêu là biến một trang bài báo thành một `Document` chứa nội dung bài và
metadata thực có; không suy đoán giá trị thiếu.

## Evidence from current runtime

Một document runtime mẫu có 4.104 từ, 219 Markdown link và dấu hiệu khối
share/comment. HTML sạch tương ứng vẫn có nhiều `article`, `header`, `aside`
và nội dung related. Hiện tại:

- `normalizer.py` xoá một số selector trên toàn trang, rồi chuyển toàn bộ DOM
  còn lại sang Markdown.
- title chỉ lấy từ `<title>`; `CrawlService` truyền `json_ld=None` cho
  classifier.
- `Document` chưa giữ author, thời điểm xuất bản/cập nhật, section/field,
  summary hoặc key của article HTML; HTML đã upload hiện không có key để truy
  hồi từ bản ghi.

## Goals

- Chọn và lưu một article body có thể dùng làm dữ liệu đọc/LLM, không gồm
  chrome của trang.
- Trích xuất an toàn các metadata hiện diện: title, summary, authors,
  published/updated time, section, canonical URL và language khi có.
- Giữ các phần ngữ nghĩa trong bài: heading, đoạn văn, danh sách, bảng, code,
  blockquote, figure/image, caption và time.
- Tính `content_hash` từ Markdown của article body đã chuẩn hoá, để dynamic
  header/footer không làm thay đổi dedupe.
- Lưu article HTML đã làm sạch với key có thể truy hồi, thay vì upload một
  object không được tham chiếu.
- Giữ workflow ảnh đúng boundary: `crawl_url` không trả raw image URL;
  `extract_images` mới tạo `ImageCandidateManifest` với candidate ID và policy
  gate riêng.

## Non-goals / anti-goals

- Không thêm Readability, Trafilatura hoặc dependency mới.
- Không browser fallback, không selector/JavaScript do request cung cấp,
  không crawl link con và không download ảnh.
- Không bịa author, ngày tháng, lĩnh vực hoặc ảnh khi nguồn không cung cấp.
- Không lưu/trả raw candidate URL, signed URL, cookies, token hay raw full-page
  capture trong result event, log hoặc UI-facing response.
- Không thay queue/job/workflow contract hay tự tạo downstream image job.

## Approaches considered

| Approach | Trade-off | Decision |
| --- | --- | --- |
| Mở rộng blacklist toàn trang | Diff nhỏ nhưng vẫn giữ nhiều boilerplate và dễ xoá nhầm theo từng site. | Rejected |
| Chọn content root + trích metadata bằng `selectolax` hiện có | Deterministic, kiểm thử được bằng fixture, không thêm dependency; cần fallback rõ ràng. | Selected |
| Dùng Readability/Trafilatura | Có thể bao phủ website lạ rộng hơn nhưng thêm dependency và khó kiểm soát output. | Deferred |

## Extraction design

### 1. Parse and metadata collection

Parse HTML một lần. Trước khi prune body, thu thập JSON-LD hợp lệ, Open Graph
và meta tags. Với mỗi field chọn nguồn theo thứ tự:

| Field | Source priority |
| --- | --- |
| title | JSON-LD `headline` → `og:title` → `h1` → `<title>` |
| summary | JSON-LD `description` → `og:description` / meta description → lead paragraph |
| authors | JSON-LD `author` → meta author → `rel=author` / byline trong article |
| published / updated | JSON-LD → `article:published_time` / `article:modified_time` → `time[datetime]` |
| section | JSON-LD `articleSection` → `article:section` |
| canonical URL | canonical link, resolved against fetched URL |
| language | `<html lang>` khi có giá trị hợp lệ |

Chuẩn hoá ngày theo ISO timezone-aware nếu parse được. Giá trị không hợp lệ,
trống hoặc mâu thuẫn không được suy đoán; field được để `null`/rỗng và quality
gate có thể yêu cầu review.

### 2. Choose exactly one content root

Chọn theo thứ tự: `<article>` → `<main>` → `[role="main"]` → candidate có text
density cao nhất. Candidate chỉ hợp lệ khi có đủ text/paragraph theo ngưỡng
cấu hình nội bộ cố định. Nếu không có candidate đủ chất lượng, fallback body
đã prune và gắn `generic_page`/`unknown`, `needs_review=true`; không cố gắng
đoán bài báo.

### 3. Prune within that root

Loại bỏ node cấu trúc không phải nội dung (`header`, `nav`, `footer`, `aside`,
form, iframe, popup/cookie/banner) và descendant có class/id/aria-label token
chỉ boilerplate: ad, share/social, subscribe/newsletter, related/recommended,
comments, pagination, breadcrumb và tag cloud. Rule phải match token, không
match substring tuỳ tiện.

Giữ link/text, image và caption nằm trong article. Chỉ URL ảnh được đưa vào
durable `ImageCandidateManifest` của workflow `extract_images`; `crawl_url`
không thêm image URL vào `Document` result.

Markdown và HTML đều sinh từ root đã prune. Mọi reference URL được retained
trong storage nội bộ phải qua canonicalization/redaction policy thích hợp;
không được log hay trả query string nhạy cảm.

### 4. Classification and quality gate

Đưa JSON-LD đã parse vào `DocumentClassifier` thay vì `None`; classifier vẫn
chỉ trả một type, confidence, reason và `needs_review` theo contract hiện có.
Nếu article candidate thiếu body đáng tin cậy hoặc metadata mâu thuẫn, giữ
fallback classification và đánh `needs_review`, thay vì nâng thành
`news_article` chỉ dựa URL.

## Persistence and data boundary

Giữ `Document.title` tương thích. Bổ sung migration mở rộng, nullable cho:

- `summary`, `authors` (list JSON), `published_at`, `updated_at`, `section`,
  `language`;
- `article_html_key` để tham chiếu HTML đã clean.

`markdown_key` tiếp tục chứa Markdown article body. Persist layer nhận một
internal normalized model, map tường minh sang ORM và object storage. Khi
upload hoặc transaction lỗi, cleanup object mới tạo để tránh orphan; migration
không backfill nội dung cũ vì không thể xác định article root một cách đáng tin
cậy từ record hiện có.

Tạm thời không mở rộng legacy document-list API: đó là API chuyển tiếp, còn
target worker result chỉ trả document reference. Nếu cần API đọc metadata sau
này, tạo response schema explicit, additive và chỉ trả safe fields — không
leak storage key hay raw image URL.

## Scope map

| Area | Expected paths |
| --- | --- |
| Extraction/normalized model | `app/features/web_crawl/application/normalizer.py` |
| Classification input | `app/features/web_crawl/application/service.py`, `classifier.py` |
| Persistence/model | `app/platform/document_storage/service.py`, `app/platform/persistence/models.py`, Alembic migration |
| Tests | normalizer, crawl service, document persistence fixtures |
| Active contract docs | `docs/features/web-crawl.md`, `docs/document-classification.md` if field contract changes |

## Verification

- Fixtures: news article có full metadata; article nhiều aside/related/comment;
  generic/listing page; malformed JSON-LD; thiếu metadata; nhiều author/image.
- Assert Markdown/clean HTML không chứa boilerplate và vẫn giữ figure/caption,
  code/table và nội dung bài.
- Assert source precedence, date validation, no invented metadata, one
  classification and fallback `needs_review`.
- Assert persistence lưu đúng metadata/article HTML key, dedupe body hash và
  cleanup object nếu transaction/upload thất bại.
- Chạy focused tests, `uv run ruff check .`, `uv run ruff format --check .`,
  rồi review diff.

## Risks and implementation decisions

- Heuristic static extraction không thể đúng với mọi website; fallback quality
  gate là an toàn hơn lấy cả trang. Các domain kém cấu trúc sẽ cần review hoặc
  recipe đã được phê duyệt ở giai đoạn browser hậu MVP.
- Dedupe hiện theo `content_hash`; nếu body không đổi nhưng metadata nguồn đổi,
  record cũ vẫn có thể được tái sử dụng. Việc refresh metadata là một policy
  riêng, không nằm trong thay đổi này.
- Không backfill records/object cũ; dữ liệu mới được áp dụng khi crawl lại.
