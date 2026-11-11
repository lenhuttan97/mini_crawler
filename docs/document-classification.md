# Document Type Classification — MVP Specification

> **Feature:** Web Crawl Worker — document processing
> **Phạm vi MVP:** nội dung HTML/JSON được chuyển thành Markdown; chưa hỗ trợ PDF, Office, presentation hoặc spreadsheet.

## 1. Mục tiêu

Sau khi crawl một URL được phép, hệ thống gán **một `document_type` chính** để chọn extractor, metadata và cách hiển thị phù hợp. Caller có thể gửi type gợi ý, nhưng hệ thống vẫn phân loại độc lập và lưu kết quả thực tế.

## 2. Taxonomy MVP

| `document_type` | Mô tả |
|---|---|
| `news_article` | Bài báo điện tử có nội dung/tác giả/thời điểm hoặc article metadata. |
| `learning_material` | Bài học, hướng dẫn, giáo trình hoặc tài nguyên học tập. |
| `course_page` | Trang mô tả khóa học/module/bài học. |
| `technical_documentation` | Tài liệu kỹ thuật, hướng dẫn sản phẩm/phần mềm. |
| `api_reference` | Tham chiếu endpoint, schema hoặc API. |
| `academic_article` | Bài viết/hồ sơ học thuật có metadata phù hợp. |
| `blog_article` | Bài viết blog/essay. |
| `book_chapter` | Một chương/sách điện tử có cấu trúc văn bản dài. |
| `listing_page` | Danh sách kết quả, category, tag hoặc archive. |
| `navigation_page` | Trang điều hướng/landing page, không có nội dung chính đủ dùng. |
| `media_page` | Trang chủ yếu chứa media/player. |
| `generic_page` | Trang có nội dung văn bản nhưng không khớp type chuyên biệt. |
| `unknown` | Không đủ tín hiệu để phân loại đáng tin cậy. |

## 3. Inputs và quyết định

1. **Caller hint (tùy chọn):** chỉ là tín hiệu, không override policy hay classifier.
2. **Content signals:** `Content-Type`, URL/canonical URL, JSON-LD, Open Graph, HTML semantic/DOM và nội dung chính đã extract.
3. **Ưu tiên signal:** structured metadata đáng tin cậy → DOM/content pattern → URL pattern → caller hint.
4. **Output:** một `document_type`, `classification_confidence` (`high`, `medium`, `low`), `classification_reason` và `needs_review`.
5. **Fallback:** nếu confidence thấp, lưu Markdown chung với `generic_page` hoặc `unknown`; không suy đoán author, ngày tháng, loại tài liệu hoặc metadata thiếu.

## 4. Metadata theo loại

| Loại | Metadata ưu tiên |
|---|---|
| `news_article` | headline, subtitle/summary, author/byline, published/updated time, canonical URL, body, media metadata được phép |
| `learning_material`/`course_page` | title, lesson/module, learning objectives, body, canonical URL |
| `technical_documentation`/`api_reference` | title, product/version nếu có, section headings, code blocks, canonical URL |
| `academic_article` | title, author, abstract, published date, citation identifier nếu công khai, body |
| `blog_article`/`book_chapter` | title, author nếu có, section headings, body |
| `listing_page`/`navigation_page`/`media_page` | title, canonical URL, classification reason; chỉ lưu body khi policy cho phép |

Nguồn metadata cho bài viết: JSON-LD Article-family → Open Graph/meta → DOM. Nếu nguồn ưu tiên cao nhất có nhiều giá trị mâu thuẫn cho cùng field, field đó để trống (không fallback, không suy đoán). Chỉ lưu field thực có; author/date/section thiếu hoặc không parse được thì bỏ trống.

## 5. Ranh giới và quality gate

- Classification không thay thế Policy Gate, SSRF/redirect validation hoặc quyền nội dung.
- Nội dung không đủ (dưới 200 ký tự không khoảng trắng hoặc dưới hai text block) không được phân loại là bài báo từ URL; fallback `generic_page`/`unknown`, confidence `low`, `needs_review=true`.
- Không dùng type để tự động crawl link con, download media hoặc thực thi action browser.
- Không log raw HTML, cookie, token hoặc URL query nhạy cảm làm classification evidence.
- Dùng fixture HTML/JSON-LD do team kiểm soát; không cần gọi website bên ngoài trong unit/integration test.

## 6. Ranh giới với media workflow

**Classification does not trigger downloads.** `media_page` chỉ là nhãn phân loại; nó không tạo Image/Video candidate hay download job. Classification never creates a candidate or download job by itself. Candidate discovery chỉ xảy ra trong workflow media được caller yêu cầu rõ ràng, với ownership và budget theo [media candidate workflows](platform/media-candidate-workflows.md).

## 7. Acceptance criteria

- Classifier luôn trả đúng một type trong taxonomy cùng confidence/reason.
- Caller hint được lưu riêng và không ép classifier chọn type.
- Fixture news article trích xuất được metadata có mặt; fixture thiếu metadata không bịa field.
- Fixture generic/listing/media page fallback an toàn với `generic_page` hoặc `unknown` và `needs_review=true` khi cần.
