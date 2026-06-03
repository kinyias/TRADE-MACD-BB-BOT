# AGENT.md — botmacdbb

Tài liệu hướng dẫn cho AI Agent khi làm việc với dự án này.

---

## Mục tiêu dự án

Bot Telegram tự động theo dõi thị trường Binance Futures (USDS-M), phát hiện tín hiệu giao dịch dựa trên **sự kết hợp của MACD đảo chiều + giá chạm Bollinger Band**, sau đó gửi thông báo Telegram kèm TP/SL rõ ràng.

---

## Cấu trúc thư mục

```
src/
├── config/
│   └── settings.py          # Cấu hình toàn cục: API keys, symbol, timeframe, thông số indicator
├── exchange/
│   ├── binance_rest.py       # Lấy dữ liệu nến (kline) qua REST API
│   └── binance_ws.py         # Stream nến realtime qua WebSocket
├── indicator/
│   ├── macd.py               # Tính toán MACD (line, signal, histogram)
│   └── bollingerband.py      # Tính toán Bollinger Band (upper, middle, lower)
├── models/
│   ├── candle.py             # Dataclass cho một cây nến
│   └── position.py           # Dataclass cho tín hiệu lệnh (entry, TP, SL, side)
├── notifications/
│   └── telegram.py           # Gửi tin nhắn Telegram qua python-telegram-bot
├── order/
│   ├── executor.py           # (tuỳ chọn) Đặt lệnh thật trên Binance
│   └── order_manager.py      # Quản lý trạng thái lệnh đang mở, tránh spam tín hiệu
├── risk/
│   ├── position_size.py      # Tính khối lượng vào lệnh theo % vốn và đòn bẩy
│   └── stop_loss.py          # Tính SL theo ATR hoặc khoảng cách Bollinger Band
├── strategies/
│   └── macd_bb_strategy.py   # Chiến lược chính: phát hiện tín hiệu MACD + BB
├── utils/
│   ├── helpers.py            # Các hàm tiện ích (làm tròn giá, format số, ...)
│   └── logger.py             # Cấu hình logging ra file và stdout
└── main.py                   # Entry point: khởi chạy vòng lặp chính
```

---

## Chiến lược giao dịch (Strategy Logic)

### Điều kiện tín hiệu LONG (Buy)

Tất cả các điều kiện sau phải đồng thời thoả mãn trên cùng một cây nến:

1. **MACD đảo chiều từ giảm → tăng**: Histogram chuyển từ âm sang dương (histogram[i-1] < 0 và histogram[i] > 0), HOẶC MACD line cắt lên trên Signal line.
2. **Giá chạm hoặc xuyên qua Bollinger Band dưới**: `candle.low <= bb_lower` trong khoảng `lookback` nến gần nhất (mặc định 3 nến).
3. **Không có lệnh LONG nào đang mở** trên cùng symbol/timeframe (chống spam).

### Điều kiện tín hiệu SHORT (Sell)

1. **MACD đảo chiều từ tăng → giảm**: Histogram chuyển từ dương sang âm (histogram[i-1] > 0 và histogram[i] < 0), HOẶC MACD line cắt xuống dưới Signal line.
2. **Giá chạm hoặc xuyên qua Bollinger Band trên**: `candle.high >= bb_upper` trong khoảng `lookback` nến gần nhất.
3. **Không có lệnh SHORT nào đang mở** trên cùng symbol/timeframe.

### Tính TP / SL

| Tham số | LONG | SHORT |
|---|---|---|
| **Entry** | `close` của nến tín hiệu | `close` của nến tín hiệu |
| **Stop Loss** | `bb_lower - atr_multiplier * ATR` | `bb_upper + atr_multiplier * ATR` |
| **Take Profit 1** | `bb_middle` (50% vị thế) | `bb_middle` (50% vị thế) |
| **Take Profit 2** | `bb_upper` (50% vị thế còn lại) | `bb_lower` (50% vị thế còn lại) |

- `atr_multiplier` mặc định = `0.5` (cấu hình trong `settings.py`).
- SL tối thiểu cách entry ít nhất `min_sl_pct` (mặc định 0.3%) để tránh SL quá sát.

---

## Cài đặt tham số mặc định (`settings.py`)

```python
# Binance
SYMBOL          = "BTCUSDT"
TIMEFRAME       = "15m"       # Khung thời gian chính
LOOKBACK_CANDLES = 500        # Số nến tải về lúc khởi động

# MACD
MACD_FAST       = 12
MACD_SLOW       = 26
MACD_SIGNAL     = 9

# Bollinger Band
BB_PERIOD       = 20
BB_STD          = 2.0

# Risk Management
ATR_PERIOD      = 14
ATR_MULTIPLIER  = 0.5         # Hệ số nhân ATR cho SL
MIN_SL_PCT      = 0.003       # SL tối thiểu 0.3% từ entry
TP1_RATIO       = 0.5         # 50% vị thế chốt tại TP1
TP2_RATIO       = 0.5         # 50% còn lại chốt tại TP2

# BB Touch Lookback
BB_TOUCH_LOOKBACK = 3         # Số nến nhìn lại để xác nhận BB touch

# Telegram
TELEGRAM_BOT_TOKEN = ""       # Đặt trong .env
TELEGRAM_CHAT_ID   = ""       # Đặt trong .env
```

---

## Định dạng tin nhắn Telegram

```
🚀 LONG SIGNAL — BTCUSDT 15m

📍 Entry   : 67,450.00
🎯 TP1     : 68,120.00  (+1.0%)
🎯 TP2     : 68,800.00  (+2.0%)
🛑 SL      : 66,900.00  (-0.8%)
📊 R/R     : 1 : 1.25

🔍 Lý do:
  • MACD đảo chiều tăng (histogram: -42 → +18)
  • Giá chạm BB dưới (BB_lower: 67,100.00)

⏰ 2025-06-03 14:30:00 UTC
```

```
🔴 SHORT SIGNAL — BTCUSDT 15m

📍 Entry   : 68,950.00
🎯 TP1     : 68,120.00  (-1.2%)
🎯 TP2     : 67,300.00  (-2.4%)
🛑 SL      : 69,500.00  (+0.8%)
📊 R/R     : 1 : 1.50

🔍 Lý do:
  • MACD đảo chiều giảm (histogram: +55 → -10)
  • Giá chạm BB trên (BB_upper: 69,200.00)

⏰ 2025-06-03 14:45:00 UTC
```

---

## Luồng hoạt động chính (`main.py`)

```
Khởi động
    │
    ├─► Tải cấu hình từ settings.py + .env
    ├─► Kết nối Binance REST, tải LOOKBACK_CANDLES nến lịch sử
    ├─► Tính MACD + Bollinger Band cho toàn bộ lịch sử
    │
    └─► Vòng lặp WebSocket (nhận nến realtime)
            │
            ├─► Khi nến ĐÓNG (is_closed = True):
            │       ├─► Cập nhật buffer nến
            │       ├─► Tính lại MACD + BB
            │       ├─► Gọi strategy.check_signal()
            │       │       ├─► Nếu có tín hiệu LONG/SHORT:
            │       │       │       ├─► Tính TP/SL
            │       │       │       ├─► Kiểm tra order_manager (chống spam)
            │       │       │       └─► Gửi thông báo Telegram
            │       │       └─► Không có tín hiệu → bỏ qua
            │       └─► Ghi log
            │
            └─► Khi nến CHƯA ĐÓNG: bỏ qua (không tính tín hiệu giữa nến)
```

---

## Quy tắc quan trọng cho Agent

### Khi viết code mới

- **Chỉ phát tín hiệu trên nến đóng** (`is_closed = True`) — không bao giờ tính tín hiệu giữa chừng nến đang chạy.
- **Kiểm tra `order_manager`** trước khi gửi thông báo để tránh gửi 2 tín hiệu cùng chiều liên tiếp.
- **Không đặt lệnh thật** trừ khi `LIVE_TRADING = True` trong settings và người dùng xác nhận rõ ràng.
- **Log đầy đủ** mỗi lần nến đóng: giá trị MACD, BB, kết quả check signal.
- **Xử lý exception** cho mọi lời gọi API (Binance và Telegram) với retry tối đa 3 lần.

### Khi sửa chiến lược (`macd_bb_strategy.py`)

- Không thay đổi logic TP/SL mà không cập nhật lại phần **Tính TP / SL** trong file này.
- Mỗi thay đổi tham số (MACD, BB) phải được ghi lại trong **Changelog** cuối file này.
- Kiểm tra tín hiệu bằng dữ liệu backtest tối thiểu 30 ngày trước khi chạy thật.

### Khi thêm symbol hoặc timeframe mới

- Mỗi cặp (symbol, timeframe) cần một instance `order_manager` riêng biệt.
- Thêm vào `WATCHLIST` trong `settings.py`, không hardcode trong `main.py`.

### Bảo mật

- **Không bao giờ** commit API key, bot token, chat ID lên git.
- Luôn dùng file `.env` và `python-dotenv`.
- File `.env` đã có trong `.gitignore`.

---

## Dependencies chính

| Thư viện | Mục đích |
|---|---|
| `binance-sdk-derivatives-trading-usds-futures` | WebSocket + REST Binance Futures |
| `python-telegram-bot` | Gửi thông báo Telegram |
| `pandas` | Xử lý dữ liệu nến dạng DataFrame |
| `pandas-ta` | Tính MACD, BB, ATR |
| `python-dotenv` | Đọc biến môi trường từ `.env` |
| `loguru` | Logging tiện lợi |

---

## Môi trường chạy

- Python `>=3.14, <3.15` (xem `pyproject.toml`)
- Quản lý dependency bằng **Poetry**
- Chạy: `poetry run python src/main.py`
- Chạy nền: `nohup poetry run python src/main.py &` hoặc dùng `systemd` / `supervisor`

---

## Changelog

| Ngày | Thay đổi |
|---|---|
| 2025-06-03 | Khởi tạo AGENT.md, định nghĩa chiến lược MACD + BB ban đầu |