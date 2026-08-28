# Log Analysis MCP Server

**Họ và tên:** Nguyễn Trường Ngọc Mai  
**MSSV:** 2A202601652

Đây là MCP Server hỗ trợ tra cứu log của ứng dụng. Server cung cấp các tool để tìm theo từ khóa, xem lỗi mới nhất và lọc log theo mức độ. Kết nối dùng Streamable HTTP; client cần gửi Bearer token trước khi sử dụng.

## Bài toán giải quyết

Khi cần tìm nguyên nhân một sự cố, cách làm thủ công thường là mở file log rồi dò từng dòng theo từ khóa hoặc mã giao dịch. Việc này mất thời gian, đặc biệt khi log có nhiều service và nhiều mức độ lỗi.

Server này đọc file `data/app.log` mỗi khi nhận yêu cầu và trả về các dòng log phù hợp. Nhờ đó, client có thể hỏi nhanh về lỗi gần đây hoặc một giao dịch cụ thể mà không cần xử lý file log bằng tay.

Mỗi dòng log có dạng:

```text
2026-08-28T08:04:09+07:00 ERROR orders - Failed to create order ORD-1008
```

## Các tool

| Tool | Dữ liệu đầu vào | Kết quả trả về |
| --- | --- | --- |
| `search_logs(keyword)` | `keyword`: từ khóa cần tìm | Danh sách các dòng có chứa từ khóa, không phân biệt hoa thường. Đây là phiên bản v1 để tương thích client cũ. |
| `get_recent_errors(limit=10)` | `limit`: số dòng cần lấy, từ 1 đến 100 | Các dòng có mức `ERROR` hoặc `CRITICAL`, sắp xếp từ mới đến cũ. |
| `search_logs_v2(keyword, level="all", limit=50)` | Từ khóa, mức log tùy chọn và giới hạn kết quả | JSON gồm điều kiện tìm kiếm, số kết quả và các log đã được tách thành timestamp, level, service và message. |

Tool `search_logs_v2` hỗ trợ các mức: `debug`, `info`, `warning`, `error`, `critical` hoặc `all`.

## Cài đặt và chạy

Yêu cầu Python 3.11 trở lên. Mở PowerShell tại thư mục `my-mcp-server` rồi chạy:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:MCP_AUTH_TOKEN = "change-this-token"
python server.py
```

Server mặc định lắng nghe tại `http://localhost:8080/mcp`.

Để dùng file log khác, đặt biến môi trường trước khi khởi động:

```powershell
$env:APP_LOG_PATH = "D:\logs\application.log"
python server.py
```

## Kết nối từ Claude Code

Giữ server đang chạy. Ở một terminal khác, đăng ký MCP Server bằng token đã đặt ở trên:

```powershell
claude.cmd mcp add --transport http --scope local log-analysis http://localhost:8080/mcp --header "Authorization: Bearer change-this-token"
```

Kiểm tra cấu hình đã được thêm:

```powershell
claude.cmd mcp list
```

Sau đó có thể dùng các câu hỏi như:

```text
Lấy 10 lỗi mới nhất trong log.
Tìm log có mã ORD-1008.
Tìm log của payment ở mức ERROR bằng tool phiên bản 2.
```

## Xác thực token

Server kiểm tra Bearer token thông qua `TokenVerifier`.

- Với token đúng, client có thể khởi tạo kết nối, xem danh sách tool và gọi tool.
- Không gửi token, server trả về `401 Unauthorized`.
- Token không hợp lệ bị từ chối với `401` hoặc `403`, tùy SDK/client đang dùng.

Token chỉ được truyền qua biến môi trường `MCP_AUTH_TOKEN`. Khi triển khai thực tế, token nên được lưu trong secret manager thay vì ghi vào source code.

## Phiên bản API

`search_logs` vẫn được giữ cho client đang dùng API cũ. `search_logs_v2` bổ sung bộ lọc level, giới hạn kết quả và dữ liệu có cấu trúc hơn.

Resource `server://info` cung cấp phiên bản server, trạng thái deprecation của tool và gợi ý chuyển từ v1 sang v2.

## Cấu trúc thư mục

```text
my-mcp-server/
|-- data/
|   `-- app.log
|-- requirements.txt
|-- server.py
`-- README.md
```

Không đưa `.env`, token thật, `.venv`, `__pycache__` hoặc log có dữ liệu nhạy cảm lên repository.
