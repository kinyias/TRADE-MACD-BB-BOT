import os
from dotenv import load_dotenv  
load_dotenv()
# Binance
SYMBOL          = os.getenv("SYMBOL", "SOLUSDC")
TIMEFRAME       = os.getenv("TIMEFRAME", "1m")       # Khung thời gian chính
LOOKBACK_CANDLES = int(os.getenv("LOOKBACK_CANDLES", 200))        # Số nến tải về lúc khởi động

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
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")       # Đặt trong .env
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "")       # Đặt trong .env
