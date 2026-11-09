# Storage

## Scope

Worker persistence tách `document_storage` và `asset_storage`. Database giữ state/metadata/index; object storage giữ HTML, Markdown và binary assets. Storage không quyết định policy, MIME validity hoặc feature business flow.

## Document storage

Chỉ `web_crawl` tạo document:

```text
NormalizedDocument
→ canonical URL + content hash deduplication
→ raw/clean HTML + Markdown object keys generated server-side
→ document metadata, type, confidence, reason, timestamps
→ Document reference in WebCrawlJobCompleted
```

Nếu content hash không đổi, update metadata/status theo policy thay vì tạo duplicate document/object.

## Asset storage

Chỉ `image_download` và `video_download` tạo asset:

```text
ValidatedAsset
→ server-generated object key
→ streaming upload
→ checksum, MIME type, byte size, feature metadata
→ ImageManifest/VideoAsset result reference
```

Image/video validation diễn ra trước persist. Object storage không public; access URL, retention và delete workflow do system sở hữu contract quyết định, không nằm trong worker message.

## Transaction and failure handling

- Commit durable job/document/asset state only after storage result is known.
- Dùng compensating cleanup cho orphan object khi database transaction thất bại.
- Result event đi qua outbox sau durable commit.
- Không log raw content, signed URL, cookie, token hay request query.

## Required ports

```text
DocumentRepository.find_by_hash(canonical_url, content_hash)
DocumentRepository.save(document)
AssetRepository.save(asset)
ObjectStorage.put_stream(key, stream, metadata)
ObjectStorage.delete(key)
```

## Tests

Test document dedupe, storage failure không hoàn thành job, checksum/mime/size persistence, partial image manifest, orphan cleanup, retention command audit và object key không suy ra từ user title/URL.
