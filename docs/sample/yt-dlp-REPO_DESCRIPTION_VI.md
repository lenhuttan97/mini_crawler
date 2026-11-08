# 📄 Mô tả Repository yt-dlp

## 1. Repo này là gì?

**yt-dlp** là một trình tải xuống âm thanh/ video dòng lệnh (CLI), phong phú tính năng, hỗ trợ nghìn trăm trang web khác nhau.

- Đây là một **fork** của dự án [youtube-dl](https://github.com/ytdl-org/youtube-dl), dựa trên [youtube-dlc](https://github.com/blackjack4494/yt-dlc) (đã không còn được duy trì).
- Mục tiêu chính là cung cấp một công cụ tải video mạnh mẽ, được cập nhật thường xuyên, hỗ trợ nhiều trang web hơn và sửa lỗi nhanh hơn so với youtube-dl gốc.
- Giấy phép: **Unlicense** (public domain — tự do sử dụng, chỉnh sửa, phân phối).

> Thông tin từ `pyproject.toml`:  
> `name = "yt-dlp"`  
> `description = "A feature-rich command-line audio/video downloader"`  
> `requires-python = ">=3.11"`

---

## 2. Mục đích

| Mục đích | Chi tiết |
|----------|----------|
| Tải video/audio từ web | Hỗ trợ nghìn trăm trang web (YouTube, Facebook, Instagram, TikTok, v.v.) |
| Dòng lệnh mạnh mẽ | Cung cấp hàng trăm tuỳ chọn để kiểm soát chất lượng, định dạng, phụ đề, metadata, xác thực, v.v. |
| Tùy chỉnh cao | Hỗ trợ mẫu đầu ra (output template), pós xử lý (ffmpeg), plugin,proxy, cookie, xác thực, v.v. |
| Dễ mở rộng | Có cấu trúc module rõ ràng (`yt_dlp/extractor`, `yt_dlp/downloader`, `yt_dlp/postprocessor`) |

---

## 3. Cách tiếp cận (Architecture)

Repository chia thành các thành phần chính:

```
yt-dlp/
├── yt_dlp/             # Mã nguồn chính (Python package)
│   ├── __main__.py     # Điểm vào CLI (python -m yt_dlp)
│   ├── YoutubeDL.py    # Lớp chính điều phối quá trình tải
│   ├── options.py      # Định nghĩa tất cả tùy chọn dòng lệnh
│   ├── extractor/      # Trích xuất thông tin video từ từng trang web
│   ├── downloader/     # Tải xuống nội dung (HTTP, HLS, DASH, v.v.)
│   ├── postprocessor/  # Xử lý sau khi tải (ffmpeg, chuyển đổi, ghép phụ đề...)
│   ├── utils/          # Tiện ích chung (mã hóa, băm, network...)
│   └── networking/     # Lớp mạng, yêu cầu HTTP
├── test/               # Bộ kiểm thử đơn vị và tích hợp
├── devscripts/         # Script dành cho desenvol viên (tạo changelog, lazy extractors, completion...)
├── bundle/             # Tệp đóng gói (Dockerfile, PyInstaller spec, requirements...)
└── pyproject.toml      # Cấu hình xây dựng (hatchling)
```

**Luồng hoạt động chính:**

1. Ngôn người dùng gọi `yt-dlp <URL>` → `yt_dlp/__main__.py` khởi động.
2. `YoutubeDL` phân tích tùy chọn, chọn `Extractor` phù hợp với trang web.
3. Extractor trích xuất metadata (tiêu đề, thời lượng, định dạng có sẵn...).
4. Ngọn người dùng chọn định dạng → `Downloader` tải dữ liệu về.
5. `PostProcessor` thực hiện hậu xử lý (chuyển đổi định dạng, nhúng phụ đề, v.v.) nếu cần.

---

## 4. Công nghệ được sử dụng

### Ngôn ngữ chính
- **Python 3.11+** (1.122 tệp Python, chiếm đa phần mã nguồn)

### Hệ sinh thái & thư viện
| Thuộc tính | Công nghệ |
|------------|-----------|
| Build backend | [hatchling](https://hatch.pypa.io/latest/) |
| Quản lý phụ thuộc | `uv` (`uv.lock`), `pip` |
| Định dạng dữ liệu | JSON, TOML, YAML, XML |
| Mạng | `requests`, `urllib3`, `websockets` |
| Mã hóa/bảo mật | `certifi`, `pycryptodomex`, `cryptography` |
| Nhận dạng charset | `charset-normalizer` |
| Nhập dữ liệu multimedia | `mutagen` |
| Nén | `brotli`, `brotlicffi` |
| JavaScript interop | `yt-dlp-ejs` |
| Môi trường ảo | `deno` (tùy chọn) |

### Công cụ phát triển
- **Kiểm thử:** `pytest` (thư mục `test/`)
- **Lint/Format:** ruff (qua pre-commit)
- **Tài liệu:** Markdown, man page
- **CI/CD:** GitHub Actions (`.github/workflows/`)

### Tệp cấu hình quan trọng
- `pyproject.toml` — metadata & xây dựng
- `.pre-commit-config.yaml` — hooks trước khi commit
- `Makefile` — lệnh xây dựng, phát hành
- `yt-dlp.sh` / `yt-dlp.cmd` — script khởi động cho Linux/macOS và Windows

---

## 5. Nếu muốn tạo 1 "bản mini" (yt-dlp-lite), cần thực hiện gì?

Nếu bạn muốn xây dựng một phiên bản gọn nhẹ của yt-dlp (chỉ tải YouTube hoặc một số trang nhất định), dưới đây là lộ trình thực hiện:

### Bước 1: Xác định phạm vi (Scope)
- Chọn 1–3 trang web mục tiêu (ví dụ: chỉ YouTube).
- Loại bỏ các extractor không cần thiết trong `yt_dlp/extractor/`.
- Giữ lại chỉ những tùy chọn CLI thực sự cần thiết trong `options.py`.

### Bước 2: Thu gọn mã nguồn
| Thành phần | Hành động đề xuất |
|------------|-------------------|
| `yt_dlp/extractor/` | Giữ chỉ extractor của trang mục tiêu, xóa phần còn lại (~100+ tệp) |
| `yt_dlp/downloader/` | Giữ downloader HTTP cơ bản, có thể bỏ HLS/DASH nếu không cần |
| `yt_dlp/postprocessor/` | Giữ chỉ ffmpeg postprocessor cơ bản (chuyển đổi định dạng) |
| `yt_dlp/utils/` | Giữ tiện ích nền tảng, xóa hàm không dùng |
| `test/` | Có thể bỏ qua ở phiên bản đầu tiên |
| `devscripts/`, `bundle/` | Không cần thiết cho bản mini |

### Bước 3: Giảm phụ thuộc
- Loại bỏ các thư viện không dùng (ví dụ: `websockets`, `mutagen`, `pycryptodomex` nếu không cần mã hóa/phụ đề phức tạp).
- Giữ lại: `requests` hoặc `urllib3`, `certifi`, `charset-normalizer`.

### Bước 4: Tái cấu trúc điểm vào
- Tạo file `main.py` đơn giản thay cho `YoutubeDL.py` phức tạp.
- Loại bỏ hệ thống plugin và tùy chọn nâng cao (cookie, proxy, xác thực...).

### Bước 5: Xây dựng và đóng gói
- Sửa `pyproject.toml`: thay `name`, `description`, `requires-python`.
- Tùy chọn: đóng gói thành một thực thi đơn duy nhất với PyInstaller hoặc `shiv`/`pex`.

### Bước 6: Kiểm thử
- Viết ít nhất 1–2 kiểm thử cho trang web mục tiêu.
- Đảm bảo tải thành công và lưu file đúng định dạng.

---

### Ví dụ cấu trúc bản mini

```
yt-dlp-lite/
├── yt_dlp_lite/
│   ├── __main__.py
│   ├── downloader.py      # Tải HTTP đơn giản
│   ├── extractor/
│   │   └── youtube.py     # Chỉ extractor YouTube
│   └── cli.py             # Parse argumentos dòng lệnh
├── pyproject.toml
├── requirements.txt       # requests, certifi
└── README.md
```

---

## 6. Tóm tắt nhanh

| Mục | Chi tiết |
|-----|----------|
| **Tên** | yt-dlp |
| **Loại** | CLI audio/video downloader |
| **Ngôn ngữ** | Python 3.11+ |
| **Kích thước** | 1.224 tệp, ~8.750 nút kiến thức (sau khi phân tích) |
| **Giấy phép** | Unlicense |
| **Điểm vào** | `yt_dlp/__main__.py` |
| **Lớp chính** | `YoutubeDL` |

File này được tạo tự động từ quá trình phân tích kiến thức của repository (`/understand` skill). Nếu bạn cần chi tiết thêm về một module cụ thể, hãy cho tôi biết.
