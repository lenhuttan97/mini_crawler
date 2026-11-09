# Roadmap thay thế Mini Services và tách feature về sau

> **Reference material only.** Đây là roadmap học tập/định hướng; không phải active worker implementation contract. Repository hiện tại giữ `app/services/`, `app/adapters/`, `app/workers/` and `app/api/` để giảm complexity.

## Trạng thái hiện tại

Mini Crawler tiếp tục xây Search, Crawl Data, Image và Video trong layout đơn
giản hiện có. Không tạo directory/module mới chỉ để phản ánh tên feature. Việc
tách về sau phải bảo toàn behavior, queue/version, test và rollback của từng
feature; nó không phải mục tiêu của phase tài liệu này.

| Capability | Khu vực hiện tại | Destination khi cần tách | Quy tắc migration |
|---|---|---|---|
| Search | `app/services/search_service.py` | `app/features/search/` | Chỉ tách trong migration được phê duyệt, reversible. |
| Crawl Data | crawl, normalize, classify, persistence services | `app/features/web_crawl/` | Chỉ tách trong migration được phê duyệt, reversible. |
| Image | media submission/processing services và media tasks | `app/features/image_download/` | Chỉ tách trong migration được phê duyệt, reversible. |
| Video | video discovery only (`VideoDiscoveryService`, no network fetch/download) | `app/features/video_download/` | Chỉ tách trong migration được phê duyệt, reversible; download capability is deferred. |

Video discovery does not fetch or download video. It only checks approved source state and normalizes supplied `raw_items`; page-driven or direct download is a deferred target and must not be documented as current capability.

## Provider thay thế của hai mini project

Chỉ Mini Search và Mini Nextcloud có đường thay thế provider trong roadmap này.
Crawl Data, Image và Video tiếp tục được xây trực tiếp trên implementation hiện
có; không suy đoán tool/provider thay thế khi chưa có quyết định product và
dependency được duyệt.

| Mục tiêu standalone | Provider trước khi mục tiêu tồn tại | Provider sau đó | Boundary không đổi |
|---|---|---|---|
| Mini Search | SearXNG → Mini Search | Mini Search tại call site Search hiện có | Search vẫn discovery-only; workflow mới quyết định crawl explicit. |
| Mini Nextcloud | Self-hosted Nextcloud → Mini Nextcloud | Mini Nextcloud trong standalone project | Metadata/binary tách biệt, object key do server tạo. |

**MinIO/S3-compatible storage remains the current crawler storage.** Nextcloud
không thay crawler storage ở phase này; mọi data migration có binary object là
project riêng cần approval, backup/restore và rollback.

## Khi nào tách module

Chỉ bắt đầu migration một feature khi có ít nhất một bằng chứng vận hành rõ ràng:

1. feature cần independent deployment hoặc queue ownership;
2. feature cần contract được version độc lập; hoặc
3. thay đổi feature liên tục phải đi qua nhiều thư mục hiện tại và gây coupling
   có thể đo/nhìn thấy.

Migration phải làm từng feature, từng bước reversible—inventory caller/queue,
giữ test behavior, chạy controlled traffic rồi mới chuyển hẳn. Không thực hiện
directory-only refactor: đổi tên/chuyển file mà không có boundary vận hành rõ
ràng chỉ làm tăng complexity.

## Không làm trong phase này

- No module folders.
- No provider abstraction.
- No dual write.
- No automatic storage migration.
- Không thay đổi behavior Search/Crawl/Image/Video, queue, workflow hay runtime configuration.
- Không thêm dependency, container hoặc service mới.

## Tài liệu liên quan

- [Mini Search học từ SearXNG](MINI_SEARXNG_PYTHON.md)
- [Mini Nextcloud architecture](mini_nextcloud_architecture.md)
- [Worker rearchitecture đích về sau](../architecture/worker-crawler-rearchitecture.md)
- [Search worker contract](../features/search.md)
- [Storage contract](../platform/storage.md)
