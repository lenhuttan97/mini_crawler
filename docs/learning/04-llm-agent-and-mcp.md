# 04 — Trí tuệ nhân tạo, agent và kết nối AI client

> Học phần này dạy bạn cách dùng mô hình ngôn ngữ lớn (LLM) để trả lời dựa trên nội dung đã crawl, xây agent có công cụ rõ ràng, và kết nối AI client qua Model Context Protocol (MCP) sau khi MVP ổn định.

---

## Mục tiêu của học phần

- Hiểu LiteLLM là cổng kết nối thống nhất đến nhiều mô hình LLM.
- Xây câu trả lời có dẫn nguồn (citation) từ nội dung đã crawl.
- Dùng PydanticAI để tạo agent với công cụ (tool) có kiểu dữ liệu rõ ràng.
- Hiểu Model Context Protocol (MCP) và tại sao chỉ xây sau MVP.
- Áp dụng bảo mật: nội dung web là dữ liệu không tin cậy, không để LLM tự kích hoạt hành động nguy hiểm.
- Viết test cho trích dẫn dẫn nguồn và chính sách agent.

---

## Lộ trình năng lực trong bài này

| Mức | Bạn tập trung vào | Khi nào nên đi tiếp? |
|-----|-------------------|----------------------|
| Beginner | Gọi một mô hình với secret ở server và kiểm tra citation bằng hàm thuần. | Bạn hiểu LLM có thể sai và không được tự quyết định hành động. |
| Intermediate | Thêm tool chỉ đọc, dữ liệu mock và kiểm tra đầu vào/đầu ra có kiểu. | Bạn xác minh mọi citation dựa trên context đã cấp. |
| Advanced | Thiết kế policy, approval và audit log cho các action có side effect. | Bạn tách quyền đọc khỏi quyền tạo crawl/media job. |
| Master | Mở MCP sau khi API ổn định, với danh tính caller, phân quyền và quan sát đầy đủ. | Bạn có thể review rủi ro prompt injection và quyền công cụ trước deployment. |

Nội dung web và mọi chỉ dẫn xuất hiện trong đó luôn là dữ liệu không tin cậy, không phải lệnh cho agent.

---

## 1. Tổng quan: LLM trong mini crawler làm gì?

Sau khi crawler thu thập nội dung trang web và lưu vào database, bạn muốn người dùng có thể hỏi câu hỏi và nhận câu trả lời dựa trên những trang đó. Ví dụ:

```
Câu hỏi: "FastAPI khác Spring Boot như thế nào?"
     │
     ▼
Tìm các đoạn văn bản liên quan trong database
     │
     ▼
Gửi đoạn văn bản đó kèm câu hỏi đến LLM
     │
     ▼
LLM trả lời và ghi dẫn nguồn (URL) của mỗi đoạn dùng
```

LLM không được tự crawl web hoặc tự tải file. Nó chỉ nhận ngữ cảnh đã được chuẩn bị và trả lời.

---

## 2. LiteLLM — cổng kết nối mô hình LLM

### 2.1 LiteLLM là gì?

LiteLLM là thư viện Python cung cấp một giao diện thống nhất để gọi nhiều mô hình LLM khác nhau (OpenAI, Anthropic, Ollama, mô hình cục bộ…). Thay vì viết mã riêng cho mỗi nhà cung cấp, bạn dùng LiteLLM và đổi mô hình bằng cấu hình.

### 2.2 Tại sao dùng LiteLLM?

- Dễ thay đổi mô hình (ví dụ từ OpenAI sang mô hình cục bộ) mà không sửa khắp code.
- Quản lý khóa API ở một nơi duy nhất (server-side).
- Theo dõi chi phí token và latency.

### 2.3 Cài LiteLLM

```bash
uv add litellm
```

### 2.4 Ví dụ gọi mô hình qua LiteLLM

```python
import litellm

response = litellm.completion(
    model="gpt-3.5-turbo",
    messages=[{"role": "user", "content": "Chào bạn"}],
    api_key="sk-...",  # Trong thực tế đọc từ biến môi trường, không để cứng
)

print(response.choices[0].message.content)
```

### 2.5 Bảo mật với LiteLLM

- Không để `api_key` trực tiếp trong mã nguồn. Dùng biến môi trường hoặc secret manager.
- Không gửi khóa API đến client hay ghi vào log.
- Tách mô hình nhúng (embedding) và mô hình chat vì chi phí và tốc độ khác nhau.

---

## 3. Trả lời có dẫn nguồn (citation)

### 3.1 Tại sao cần dẫn nguồn?

Nội dung từ Internet có thể sai hoặc lỗi thời. Khi LLM trả lời, bạn cần cho người dùng biết thông tin đến từ trang nào để họ có thể kiểm tra. Dự án yêu cầu mọi trích dẫn phải hợp lệ với danh sách đoạn văn bản đã cung cấp.

### 3.2 Luồng trả lời có dẫn nguồn

```
Câu hỏi của người dùng
     │
     ▼
Tìm các đoạn văn bản liên quan (retrieve chunks)
     │
     ▼
Xây ngữ cảnh: mỗi đoạn có source_id và URL
     │
     ▼
Gửi ngữ cảnh + câu hỏi đến LLM
     │
     ▼
LLM trả lời kèm mã nguồn (ví dụ: [S1], [S2])
     │
     ▼
Kiểm tra lại mã nguồn trả về có nằm trong danh sách ngữ cảnh không
     │
     ▼
Trả lời cuối cùng kèm danh sách URL thực
```

### 3.3 Ví dụ kiểm tra trích dẫn (pure function)

```python
def validate_citations(answer_citations: list[str], valid_source_ids: set[str]) -> list[str]:
    """Chỉ giữ các trích dẫn có trong danh sách nguồn hợp lệ."""
    return [cid for cid in answer_citations if cid in valid_source_ids]

# Ví dụ sử dụng
valid = {"S1", "S2"}
answer_citations = ["S1", "S9"]  # S9 không có trong ngữ cảnh
safe = validate_citations(answer_citations, valid)
print(safe)  # In ra ["S1"]
```

Nếu LLM bịa trích dẫn, hàm này sẽ loại bỏ mã nguồn không tồn tại.

---

## 4. PydanticAI — agent có công cụ rõ ràng

### 4.1 PydanticAI là gì?

PydanticAI là SDK Python giúp xây agent (trợ lý AI tự thực hiện nhiệm vụ) với công cụ (tool) có kiểu dữ liệu rõ ràng (typed). Mỗi công cụ nhận đầu vào và trả đầu ra theo mô hình Pydantic, giúp bạn kiểm soát agent dễ dàng hơn.

### 4.2 Công cụ agent trong dự án

Agent chỉ được gọi các công cụ sau:

| Công cụ | Loại | Đầu vào tối thiểu | Đầu ra |
|---------|------|-------------------|--------|
| `search_web` | Chỉ đọc | `query`, `limit` | Danh sách URL, tiêu đề, mô tả ngắn |
| `get_crawl_job` | Chỉ đọc | `job_id` | Trạng thái và lỗi an toàn |
| `retrieve_documents` | Chỉ đọc | `query`, `limit` | Các đoạn văn bản có source_id, URL |
| `answer_with_citations` | Tính toán | `câu hỏi`, `source_ids` | Câu trả lời và mã trích dẫn đã kiểm tra |

Công cụ có side effect (gây tác động bên ngoài) như `request_crawl` và `request_media_download` cần phê duyệt (approval) trước khi thực hiện. Agent không tự chạy chúng mà không có sự đồng ý của con người hoặc token phê duyệt.

### 4.3 Ví dụ công cụ chỉ đọc

```python
from pydantic import BaseModel, Field
from pydantic_ai import Agent

class RetrieveInput(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=5, ge=1, le=20)

class RetrieveOutput(BaseModel):
    results: list[dict]

agent = Agent("openai:gpt-4o")  # Chọn model qua cấu hình trong ứng dụng thật.

@agent.tool_plain
async def retrieve_documents(input: RetrieveInput) -> RetrieveOutput:
    # Gọi service đã có trong dự án, không truy cập database trực tiếp
    ...
```

`@agent.tool_plain` đăng ký một tool không cần dependency context. PydanticAI cũng hỗ trợ `@agent.tool` khi tool cần `RunContext`, hoặc truyền hàm đã kiểm tra qua `Agent(tools=[...])`. Không để model tự đăng ký tool hay tự chọn endpoint bên ngoài danh sách cho phép.

### 4.4 Bảo mật với agent

- Nội dung từ trang web là dữ liệu không tin cậy. System prompt phải cấm agent tuân theo lệnh ngụy biện nằm trong trang web.
- Agent không được có quyền shell, truy cập trực tiếp database, hay gọi mạng tự do.
- Mọi công dụng side effect cần kiểm tra chính sách và ghi nhật ký kiểm tra (audit log).

---

## 5. Model Context Protocol (MCP) — kết nối AI client

### 5.1 MCP là gì?

MCP là tiêu chuẩn mở giúp ứng dụng cung cấp ngữ cảnh và công cụ cho mô hình LLM. Nó giống như "cổng USB" cho AI: thay vì mỗi AI client phát minh cách kết nối khác nhau, mọi người dùng cùng giao thức MCP.

### 5.2 Tại sao chỉ xây MCP sau MVP?

Trước khi xây MCP, bạn cần:

- REST API ổn định (tìm kiếm, crawl, trả lời).
- Chính sách bảo mật và phân quyền rõ ràng.
- Tác vụ nền (Celery) chạy được.

MCP chỉ là lớp kết nối, không thay thế logic nghiệp vụ. Nếu xây MCP sớm, bạn sẽ phải sửa nhiều lần khi API thay đổi.

### 5.3 Giao tiếp MCP

| Môi trường | Giao thức (transport) | Mục đích |
|------------|----------------------|----------|
| Phát triển local / ứng dụng AI trên máy tính | `stdio` | Không mở cổng mạng, dễ chạy cùng trình soạn thảo code. |
| Triển khai nội bộ / từ xa | Streamable HTTP qua HTTPS | Kết nối nhiều AI client, đi kèm xác thực và giới hạn tần suất. |

### 5.4 Công cụ MCP dự kiến

| Công cụ MCP | Loại | Kết quả |
|-------------|------|---------|
| `search_web` | Chỉ đọc | Danh sách kết quả SearXNG đã chuẩn hóa |
| `request_crawl` | Tác dụng bên ngoài | `crawl_job_id` sau khi kiểm tra URL và chính sách |
| `get_crawl_job` | Chỉ đọc | Trạng thái công việc crawl |
| `retrieve_documents` | Chỉ đọc | Các đoạn văn bản có source_id, URL |
| `answer_with_citations` | Tính toán | Câu trả lời và mã trích dẫn đã kiểm tra |
| `request_media_download` | Tác dụng bên ngoài, cần phê duyệt | `media_job_id` sau khi kiểm tra quyền và chính sách |
| `get_media_job` | Chỉ đọc | Trạng thái và tiến độ tải media |

### 5.5 Quy tắc an toàn của MCP

- MCP server không có quyền lớn hơn người gọi (caller). Mọi yêu cầu mang danh tính người gọi.
- Công cụ chỉ đọc được bật mặc định. Công dụng side effect (crawl, tải media) cần phê duyệt và trả về job ID để người dùng kiểm tra trạng thái sau.
- Không expose HTML thô, dữ liệu phản hồi mạng, cookie, token hoặc URL lưu trữ dài hạn qua MCP resource.
- Nội dung web trong phản hồi MCP vẫn là dữ liệu không tin cậy.

---

## 6. Luồng xử lý LLM/Agent trong dự án

```
Câu hỏi người dùng
     │
     ▼
Agent phân tích nhu cầu
     │
     ├─ Cần tìm thông tin mới → công cụ search_web → SearXNG
     │
     ├─ Cần nội dung trang đã crawl → công cụ retrieve_documents → PostgreSQL
     │
     ├─ Cần trả lời có dẫn nguồn → công cụ answer_with_citations → LLM qua LiteLLM
     │
     └─ Cần tải media → công cụ request_media_download → kiểm tra chính sách → Celery worker
```

---

## 7. Bài thực hành

### Bài 1: Gọi mô hình LLM qua LiteLLM

1. Cài `litellm`.
2. Viết hàm gọi mô hình với tin nhắn đơn giản.
3. Đọc khóa API từ biến môi trường, không để cứng trong code.
4. Xử lý lỗi khi mô hình không phản hồi (timeout, lỗi xác thực).

### Bài 2: Trả lời có dẫn nguồn

1. Tạo danh sách đoạn văn bản giả lập có `source_id` và URL.
2. Viết hàm kiểm tra trích dẫn (như ví dụ `validate_citations` ở trên).
3. Thử với LLM trả trích dẫn không tồn tại, đảm bảo hàm loại bỏ trích dẫn không hợp lệ.

### Bài 3: Công cụ agent chỉ đọc

1. Cài `pydantic-ai`.
2. Tạo công cụ `retrieve_documents` với đầu vào/đầu ra kiểu Pydantic.
3. Gọi công cụ với dữ liệu giả lập và kiểm tra đầu ra.

### Bài 4: Chính sách side effect

1. Viết hàm kiểm tra xem một yêu cầu tải media có được phép hay không (dùng allowlist domain).
2. Thử yêu cầu tải từ domain không được phép, đảm bảo hàm từ chối.
3. Ghi nhật ký kiểm tra (audit log) cho yêu cầu được phép và từ chối.

### Bài 5: MCP stdio (sau khi REST API ổn định)

1. Cài `mcp` (Python SDK).
2. Tạo MCP server `stdio` đơn giản expose công cụ `search_web` giả lập.
3. Viết client MCP gọi công cụ và kiểm tra schema đầu vào/đầu ra.

---

## 8. Checklist hoàn thành theo mức độ

| Mức độ | Tiêu chí |
|--------|----------|
| Beginner | Gọi được LLM qua LiteLLM; hiểu tại sao cần dẫn nguồn; viết được công cụ agent đơn giản. |
| Intermediate | Xây được luồng trả lời có dẫn nguồn; kiểm tra trích dẫn hợp lệ; dùng PydanticAI tool typed. |
| Advanced | Thiết kế agent với side effect cần phê duyệt; tích hợp LiteLLM gateway; viết test cho chính sách agent. |
| Master | Xây MCP server stdio và Streamable HTTP; thiết kế phân quyền caller; tối ưu chi phí token và latency. |

---

## 9. Liên kết tài liệu chính thức

- [LiteLLM getting started](https://docs.litellm.ai/docs/)
- [LiteLLM embeddings](https://docs.litellm.ai/docs/embedding/supported_embedding)
- [PydanticAI overview](https://ai.pydantic.dev/)
- [PydanticAI tools](https://ai.pydantic.dev/tools/)
- [MCP Python SDK](https://py.sdk.modelcontextprotocol.io/)
- [MCP transports specification](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports)
- [MCP tools specification](https://modelcontextprotocol.io/specification/2026-07-28/server/tools)
- [MCP Python authorization](https://py.sdk.modelcontextprotocol.io/run/authorization/)

---

**Khi hoàn thành học phần 04, hãy chuyển sang [05-video-discovery-and-download.md](05-video-discovery-and-download.md) để học về phát hiện và tải ảnh/video/audio.**
