# GitHub Actions CI — Design

## Intent

Khôi phục GitHub Actions CI để workflow tạo và chạy job trên nhánh mặc định
`master`; sau mỗi lần chạy, toàn bộ GitHub Actions cache của repository phải
được xóa, kể cả khi quality checks thất bại.

## Goals

- Chạy test, Ruff check và Ruff format check với Python 3.12 cùng lockfile.
- Không khai báo service container vì CI này không cần external service.
- Chạy cho push và pull request nhắm vào `master`.
- Xóa toàn bộ repository Actions cache sau khi job quality kết thúc, cả khi
  quality job thất bại.
- Cấp quyền tối thiểu: đọc source cho quality job; ghi Actions chỉ cho cleanup.

## Non-goals

- Không sửa hoặc bỏ qua các test ứng dụng đang fail.
- Không thêm dependency, cache strategy, service container, artifact hay deploy.
- Không thay đổi `.gitignore` đang được chỉnh sửa ngoài task này.

## Root cause

Các GitHub Actions run gần nhất (`42490678811`, `42669714929`,
`42841090431`) kết thúc ngay khi tạo, không có job hoặc log. Workflow có
`services: none`, nhưng `jobs.<id>.services` phải là object service container;
đây là configuration không hợp lệ. Workflow cũng lọc `main` dù nhánh repository
hiện tại là `master`.

## Approaches considered

| Approach | Trade-off | Decision |
| --- | --- | --- |
| Cleanup step ở cuối quality job như workflow tham chiếu `saku-sched` | Ngắn hơn, nhưng post-job cache save có thể chạy sau cleanup và để lại cache. | Rejected. |
| Cleanup job riêng, phụ thuộc quality và dùng `if: always()` | Chạy sau toàn bộ post-job hooks; đảm bảo xóa sau cả success và failure. | Selected. |
| Bỏ luôn caching và không cleanup | Không tạo cache mới, nhưng không xóa cache repository đã tồn tại. | Rejected. |

## Workflow behavior

`quality` checkout source, cài Python 3.12 và `uv`, đồng bộ theo `uv.lock`, rồi
chạy `pytest`, `ruff check .`, và `ruff format --check .`. Workflow không thiết
lập GitHub Actions dependency cache.

`cleanup` luôn chạy sau `quality`, nhận `actions: write` và dùng GitHub CLI với
`GH_TOKEN: ${{ github.token }}` để chạy:

```sh
gh cache delete --all --succeed-on-no-caches --repo "$GITHUB_REPOSITORY"
```

Lệnh này xóa cache Actions của toàn repository và không fail nếu repository
không có cache.
