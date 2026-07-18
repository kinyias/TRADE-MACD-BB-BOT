import os
import json
import requests
from typing import Dict, List, Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def call_openrouter_api(prompt: str, model: str = "openrouter/owl-alpha") -> dict:
    """
    Call OpenRouter AI API to get chat completion.
    Automatically switches to backup API key if primary fails.
    
    Args:
        prompt: The user's prompt/question
        model: The model to use (default: openrouter/owl-alpha)
    
    Returns:
        dict: API response containing the completion
    """
    url = "https://openrouter.ai/api/v1/chat/completions"
    
    # Get API keys from environment variables
    api_key_1 = os.getenv("OPENROUTER_API_KEY", "")
    api_key_2 = os.getenv("OPENROUTER_API_KEY_2", "")
    
    if not api_key_1 and not api_key_2:
        raise ValueError("No OPENROUTER_API_KEY found in environment variables")
    
    # List of API keys to try
    api_keys = []
    if api_key_1:
        api_keys.append(("OPENROUTER_API_KEY", api_key_1))
    if api_key_2:
        api_keys.append(("OPENROUTER_API_KEY_2", api_key_2))
    
    last_error = None
    
    # Try each API key
    for key_name, api_key in api_keys:
        try:
            print(f"Trying {key_name}...")
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
            
            payload = {
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            }
            
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()  # Raise exception for HTTP errors
            
            print(f"✅ Successfully used {key_name}")
            return response.json()
            
        except requests.exceptions.RequestException as e:
            print(f"❌ {key_name} failed: {e}")
            last_error = e
            continue
    
    # If all keys failed, raise the last error
    raise Exception(f"All API keys failed. Last error: {last_error}")


def build_market_analysis_prompt(
    klines_data: List[List],
    order_book_data: Dict,
    volume_profile_data: Dict,
    recent_trades_data: List[Dict],
    taker_volume_data: List[Dict],
    funding_rate_data: List[Dict],
    current_price: float,
    symbol: str,
    timeframe: str
) -> str:
    """
    Xây dựng prompt để phân tích thị trường dựa trên dữ liệu từ Binance API
    
    Args:
        klines_data: Dữ liệu nến từ /fapi/v1/klines
        order_book_data: Dữ liệu order book (bids/asks)
        volume_profile_data: Dữ liệu phân tích volume profile (POC, value area, etc.)
        recent_trades_data: Dữ liệu giao dịch gần đây
        taker_volume_data: Dữ liệu taker buy/sell volume
        funding_rate_data: Dữ liệu funding rate
        current_price: Giá hiện tại
        symbol: Cặp giao dịch (VD: BTCUSDT)
        timeframe: Khung thời gian (VD: 1m, 5m, 1h)
    
    Returns:
        str: Prompt được format để gửi đến AI
    """
    
    prompt = f"""Bạn là một chuyên gia phân tích thị trường crypto với kinh nghiệm sâu về Price Action, Volume Analysis và Market Microstructure.

**THÔNG TIN THỊ TRƯỜNG:**
- Symbol: {symbol}
- Timeframe: {timeframe}
- Giá hiện tại: {current_price}

**DỮ LIỆU PHÂN TÍCH:**

1. KLINES DATA (Nến gần đây):
```json
{json.dumps(klines_data[-80:], indent=2)}
```

2. ORDER BOOK (Sổ lệnh):
```json
{json.dumps(order_book_data, indent=2)}
```

3. VOLUME PROFILE ANALYSIS:
```json
{json.dumps(volume_profile_data, indent=2)}
```

4. RECENT TRADES (Giao dịch gần đây):
```json
{json.dumps(recent_trades_data[:100], indent=2)}
```

5. TAKER BUY/SELL VOLUME:
```json
{json.dumps(taker_volume_data, indent=2)}
```

6. FUNDING RATE:
```json
{json.dumps(funding_rate_data, indent=2)}
```

---

**YÊU CẦU PHÂN TÍCH:**

**PHẦN 1: PHÂN TÍCH VÙNG GIÁ QUAN TRỌNG (Key Price Zones)**

Dựa trên ORDER BOOK và VOLUME PROFILE, hãy xác định:

1.1. **Vùng Support/Resistance mạnh:**
   - Xác định các mức giá có volume tập trung cao (từ Volume Profile: POC, Value Area High/Low, High Volume Nodes)
   - Phân tích độ dày của order book tại các mức giá quan trọng
   - Xác định vùng imbalance (chênh lệch lớn giữa bids/asks)

1.2. **Đánh giá độ tin cậy:**
   - Vùng nào có khả năng giữ giá cao nhất?
   - Vùng nào dễ bị phá vỡ?
   - Khoảng cách từ giá hiện tại đến các vùng này?

1.3. **Kết luận vùng giá:**
   - Liệt kê top 3-5 vùng giá cần lưu ý nhất (từ gần đến xa)
   - Gợi ý entry/exit zone tiềm năng

---

**PHẦN 2: PHÂN TÍCH ĐỘNG LỰC & ĐẢO CHIỀU (Momentum & Reversal Analysis)**

Dựa trên RECENT TRADES, TAKER VOLUME, ORDER BOOK và FUNDING RATE:

2.1. **Phân tích động lực hiện tại:**
   - Xu hướng hiện tại là gì? (Tăng/Giảm/Sideway)
   - Lực mua/bán đang chiếm ưu thế? (dựa vào taker buy/sell volume ratio)
   - Áp lực từ order book: Bid pressure vs Ask pressure
   - Tốc độ giao dịch và kích thước lệnh trung bình từ recent trades

2.2. **Dấu hiệu đảo chiều:**
   - Có sự phân kỳ giữa price và volume không?
   - Funding rate cho thấy điều gì? (Quá cao/thấp = tín hiệu đảo chiều)
   - Order book có dấu hiệu spoofing hoặc accumulation/distribution không?
   - Taker volume có thay đổi xu hướng gần đây không?

2.3. **Độ mạnh của động lực:**
   - Đánh giá độ mạnh từ 1-10 (1=rất yếu, 10=rất mạnh)
   - Dự đoán xu hướng ngắn hạn (5-15 phút tiếp theo)
   - Xác suất đảo chiều trong khung thời gian này (%)

---

**OUTPUT FORMAT (Trả về text có cấu trúc, tối ưu cho Telegram):**

```
📊 PHÂN TÍCH THỊ TRƯỜNG {symbol} | `{timeframe}`
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 Giá hiện tại: `${current_price}`
⏰ Thời gian: [timestamp]

📈 TÍN HIỆU GIAO DỊCH

🎯 HÀNH ĐỘNG: [BUY 🟢/SELL 🔴/WAIT ⏸️]

📍 ENTRY ZONE: `$XX,XXX - $XX,XXX`
🛑 STOP LOSS: `$XX,XXX` (-X.XX%)

🎯 TP1: `$XX,XXX` (+X.XX%) - Chốt 50%
🎯 TP2: `$XX,XXX` (+X.XX%) - Chốt 50%

💡 LÝ DO: [Giải thích ngắn gọn tại sao đưa ra tín hiệu này]

🗺️ VÙNG GIÁ QUAN TRỌNG

📌 POC: `$XX,XXX`
📊 VA High: `$XX,XXX` | VA Low: `$XX,XXX`

🟢 SUPPORT MẠNH:
  • `$XX,XXX` - [HIGH/MED/LOW] - Cách X.XX%
    _[Lý do]_
  • `$XX,XXX` - [HIGH/MED/LOW] - Cách X.XX%
    _[Lý do]_

🔴 RESISTANCE MẠNH:
  • `$XX,XXX` - [HIGH/MED/LOW] - Cách X.XX%
    _[Lý do]_
  • `$XX,XXX` - [HIGH/MED/LOW] - Cách X.XX%
    _[Lý do]_

⚡ PHÂN TÍCH ĐỘNG LỰC

📈 Xu hướng: [BULLISH 🐂/BEARISH 🐻/SIDEWAYS ↔️]
💪 Độ mạnh: [X/10] ⭐⭐⭐
⚖️ Lực lượng: [BUYERS 🟢/SELLERS 🔴/NEUTRAL ⚪]
📊 Buy/Sell: `X.XX`

🔄 Order Book: [BUY_PRESSURE 🟢/SELL_PRESSURE 🔴/BALANCED ⚖️]
📉 Funding: [BULL 🟢/BEAR 🔴/NEUTRAL ⚪]

⚠️ Đảo chiều: XX%
🚨 Dấu hiệu:
  • [Dấu hiệu 1]
  • [Dấu hiệu 2]

🔮 Dự đoán 5-15p: [BULL/BEAR/SIDE]
🎯 Độ tin cậy: XX%

📝 TÓM TẮT

[Viết 3-5 câu tóm tắt toàn bộ tình hình thị trường, các yếu tố chính ảnh hưởng, và khuyến nghị giao dịch. Sử dụng ngôn ngữ dễ hiểu, tránh thuật ngữ phức tạp.]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ _Không phải lời khuyên tài chính. DYOR!_
```

**LƯU Ý QUAN TRỌNG:**
- Phân tích phải dựa trên dữ liệu thực tế, không đoán mò
- Ưu tiên các tín hiệu có độ tin cậy cao
- Cân nhắc nhiều yếu tố trước khi đưa ra kết luận
- Trả về text theo đúng format trên, điền đầy đủ thông tin vào các vị trí [...]
- Sử dụng emoji để dễ nhìn, format rõ ràng
"""
    
    return prompt


def analyze_market_with_ai(
    klines_data: List[List],
    order_book_data: Dict,
    volume_profile_data: Dict,
    recent_trades_data: List[Dict],
    taker_volume_data: List[Dict],
    funding_rate_data: List[Dict],
    current_price: float,
    symbol: str,
    timeframe: str,
    model: str = "openrouter/owl-alpha"
) -> Optional[str]:
    """
    Gọi AI để phân tích thị trường
    
    Returns:
        str: Kết quả phân tích dưới dạng text có format hoặc None nếu lỗi
    """
    try:
        prompt = build_market_analysis_prompt(
            klines_data=klines_data,
            order_book_data=order_book_data,
            volume_profile_data=volume_profile_data,
            recent_trades_data=recent_trades_data,
            taker_volume_data=taker_volume_data,
            funding_rate_data=funding_rate_data,
            current_price=current_price,
            symbol=symbol,
            timeframe=timeframe
        )
        
        response = call_openrouter_api(prompt, model)
        
        # Parse response and return formatted text
        if response and "choices" in response and len(response["choices"]) > 0:
            content = response["choices"][0]["message"]["content"]
            
            # Remove markdown code blocks if present
            if "```" in content:
                # Extract content from code block
                parts = content.split("```")
                if len(parts) >= 3:
                    content = parts[1]
                    # Remove language identifier if present (e.g., "text" or "markdown")
                    if content.startswith(("text", "markdown", "\n")):
                        content = content.split("\n", 1)[1] if "\n" in content else content
            
            return content.strip()
        
        return None
        
    except Exception as e:
        print(f"Error analyzing market with AI: {e}")
        return None


def build_quick_signal_prompt(
    klines_data: List[List],
    order_book_data: Dict,
    volume_profile_data: Dict,
    recent_trades_data: List[Dict],
    taker_volume_data: List[Dict],
    funding_rate_data: List[Dict],
    current_price: float,
    symbol: str,
    timeframe: str
) -> str:
    """
    Xây dựng prompt NGẮN GỌN để AI quyết định nhanh: LONG / SHORT / NEUTRAL

    Chỉ yêu cầu AI trả lời động lực hiện tại nên LONG, SHORT hay đợi (NEUTRAL).
    Nếu có khả năng LONG/SHORT thì đưa ra Entry, TP, SL kèm 3 câu tóm tắt lý do.
    """

    prompt = f"""Bạn là chuyên gia scalping crypto. Hãy quyết định NHANH dựa trên dữ liệu thị trường.

**THÔNG TIN:**
- Symbol: {symbol}
- Timeframe: {timeframe}
- Giá hiện tại: {current_price}

**DỮ LIỆU:**

1. KLINES (nến gần đây):
```json
{json.dumps(klines_data[-50:], indent=2)}
```

2. ORDER BOOK:
```json
{json.dumps(order_book_data, indent=2)}
```

3. VOLUME PROFILE:
```json
{json.dumps(volume_profile_data, indent=2)}
```

4. TAKER BUY/SELL VOLUME:
```json
{json.dumps(taker_volume_data, indent=2)}
```

5. FUNDING RATE:
```json
{json.dumps(funding_rate_data, indent=2)}
```

---

**YÊU CẦU:**
Chỉ cần đánh giá động lực hiện tại nên đặt LONG, SHORT hay đợi (NEUTRAL).
- Nếu động lực chưa rõ ràng => NEUTRAL và không cần Entry/TP/SL.
- Nếu có khả năng LONG hoặc SHORT => đưa ra Entry, TP, SL cụ thể.
- Luôn kèm đúng 3 câu tóm tắt lý do đưa ra quyết định.

**OUTPUT FORMAT (trả về đúng format sau, tối ưu cho Telegram, không thêm gì khác):**

```
🎯 QUYẾT ĐỊNH: [LONG 🟢/SHORT 🔴/NEUTRAL ⚪]

📍 ENTRY: `$XXXX`
🎯 TP: `$XXXX`
🛑 SL: `$XXXX`

📝 LÝ DO:
1. [Câu 1]
2. [Câu 2]
3. [Câu 3]
```

**LƯU Ý:**
- Nếu NEUTRAL thì bỏ phần ENTRY/TP/SL, chỉ giữ QUYẾT ĐỊNH và 3 câu LÝ DO.
- Phân tích dựa trên dữ liệu thực, không đoán mò.
- Chỉ trả về đúng format trên, ngắn gọn.
"""

    return prompt


def analyze_market_quick_signal(
    klines_data: List[List],
    order_book_data: Dict,
    volume_profile_data: Dict,
    recent_trades_data: List[Dict],
    taker_volume_data: List[Dict],
    funding_rate_data: List[Dict],
    current_price: float,
    symbol: str,
    timeframe: str,
    model: str = "openrouter/owl-alpha"
) -> Optional[str]:
    """
    Gọi AI để đưa ra quyết định nhanh LONG/SHORT/NEUTRAL (đơn giản hơn analyze_market_with_ai)

    Returns:
        str: Kết quả quyết định dạng text có format hoặc None nếu lỗi
    """
    try:
        prompt = build_quick_signal_prompt(
            klines_data=klines_data,
            order_book_data=order_book_data,
            volume_profile_data=volume_profile_data,
            recent_trades_data=recent_trades_data,
            taker_volume_data=taker_volume_data,
            funding_rate_data=funding_rate_data,
            current_price=current_price,
            symbol=symbol,
            timeframe=timeframe
        )

        response = call_openrouter_api(prompt, model)

        # Parse response and return formatted text
        if response and "choices" in response and len(response["choices"]) > 0:
            content = response["choices"][0]["message"]["content"]

            # Remove markdown code blocks if present
            if "```" in content:
                parts = content.split("```")
                if len(parts) >= 3:
                    content = parts[1]
                    if content.startswith(("text", "markdown", "\n")):
                        content = content.split("\n", 1)[1] if "\n" in content else content

            return content.strip()

        return None

    except Exception as e:
        print(f"Error getting quick signal from AI: {e}")
        return None


if __name__ == "__main__":
    # Example usage
    try:
        # Sample data (thay bằng dữ liệu thực từ các API)
        sample_klines = [
            [1640000000000, "50000", "51000", "49000", "50500", "1000", 1640003600000, "50000000", 500, "600", "30000000", "0"],
            [1640003600000, "50500", "51500", "50000", "51200", "1200", 1640007200000, "60000000", 600, "700", "35000000", "0"]
        ]
        sample_order_book = {
            "bids": [["50000", "10"], ["49900", "20"], ["49800", "15"]], 
            "asks": [["50100", "15"], ["50200", "25"], ["50300", "20"]]
        }
        sample_volume_profile = {
            "poc": 50250, 
            "value_area_high": 50500, 
            "value_area_low": 50000,
            "total_volume": 5000,
            "volume_by_price": {
                "50000": 800,
                "50100": 1200,
                "50250": 1500,
                "50400": 900,
                "50500": 600
            }
        }
        sample_trades = [
            {"price": "50100", "qty": "0.5", "isBuyerMaker": False, "time": 1640000000000},
            {"price": "50150", "qty": "0.8", "isBuyerMaker": True, "time": 1640000060000}
        ]
        sample_taker_volume = [
            {"buySellRatio": 1.2, "buyVol": "600", "sellVol": "500", "timestamp": 1640000000000}
        ]
        sample_funding = [
            {"fundingRate": "0.0001", "fundingTime": 1640000000000}
        ]
        
        print("Đang gọi AI để phân tích thị trường...")
        print("=" * 70)
        
        result = analyze_market_with_ai(
            klines_data=sample_klines,
            order_book_data=sample_order_book,
            volume_profile_data=sample_volume_profile,
            recent_trades_data=sample_trades,
            taker_volume_data=sample_taker_volume,
            funding_rate_data=sample_funding,
            current_price=50100,
            symbol="BTCUSDT",
            timeframe="5m"
        )
        
        if result:
            print(result)
        else:
            print("❌ Không thể lấy kết quả phân tích")
            
    except Exception as e:
        print(f"❌ Error: {e}")
