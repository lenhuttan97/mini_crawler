# Network Policy

## Scope

`network_policy` là cổng duy nhất trước mọi network call của worker features. Nó trả `PolicyDecision`; không enqueue job, fetch content hay persist asset.

## Contract

```text
PolicyCommand
- feature_code
- requested_url
- caller_context (redacted)
- source_context (optional)
- redirect_from (optional)

PolicyDecision
- allowed
- reason_code
- policy_reference
```

## Required gates

1. Chỉ allow scheme/port được cấu hình; từ chối user-info và hostname không hợp lệ.
2. Resolve toàn bộ DNS A/AAAA; chặn loopback, private, link-local, multicast, reserved và internal address.
3. Revalidate URL, DNS và connection target trước từng redirect.
4. Áp dụng allowlist/source state, caller/domain quota và `robots.txt` khi Web Crawl.
5. Video yêu cầu approved source, reviewed recipe, entitlement và DRM gate trước download.
6. Image phải kiểm tra policy cho **mỗi** URL manifest trước network call.

## Feature use

| Feature | Policy use |
|---|---|
| Search | Validate provider endpoint/configuration and query quota; search result URL is not approved for crawl. |
| Web Crawl | Gate initial URL and every redirect; enforce robots/content policy. |
| Image Download | Gate every image URL before streaming. |
| Video Download | Gate source URL, source registry, reviewed recipe and entitlement/DRM path. |

## Security boundaries

- Worker never accepts cookie, token, arbitrary JavaScript, CSS selector or shell argument from job payload.
- Policy/audit/log/metric data never contain raw query strings, secrets, signed URLs or captured network payloads.
- `blocked_*` is terminal and non-retryable unless a new, audited job is created after policy changes.

## Tests

Test scheme, user-info, port, IPv4/IPv6 ranges, DNS multi-record, redirect-to-private target, allowlist/source state, robots decision, per-image validation and video DRM/entitlement block.
