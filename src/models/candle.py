"""
Model cho dữ liệu nến (candlestick)
"""
from pydantic import BaseModel, Field, validator
from datetime import datetime
from typing import Optional


class Candle(BaseModel):
    """Model đại diện cho một nến giá (OHLCV)"""
    
    timestamp: int = Field(..., description="Unix timestamp (milliseconds)")
    open: float = Field(..., gt=0, description="Giá mở cửa")
    high: float = Field(..., gt=0, description="Giá cao nhất")
    low: float = Field(..., gt=0, description="Giá thấp nhất")
    close: float = Field(..., gt=0, description="Giá đóng cửa")
    volume: float = Field(..., ge=0, description="Khối lượng giao dịch")
    
    # Các trường tùy chọn
    quote_volume: Optional[float] = Field(None, ge=0, description="Khối lượng giao dịch theo quote asset")
    number_of_trades: Optional[int] = Field(None, ge=0, description="Số lượng giao dịch")
    taker_buy_base_volume: Optional[float] = Field(None, ge=0)
    taker_buy_quote_volume: Optional[float] = Field(None, ge=0)
    
    @validator('high')
    def validate_high(cls, v, values):
        """Giá cao nhất phải >= giá mở và đóng"""
        if 'open' in values and v < values['open']:
            raise ValueError("High phải >= Open")
        if 'low' in values and v < values['low']:
            raise ValueError("High phải >= Low")
        return v
    
    @validator('low')
    def validate_low(cls, v, values):
        """Giá thấp nhất phải <= giá mở và đóng"""
        if 'open' in values and v > values['open']:
            raise ValueError("Low phải <= Open")
        return v
    
    @validator('close')
    def validate_close(cls, v, values):
        """Giá đóng phải trong khoảng low-high"""
        if 'low' in values and v < values['low']:
            raise ValueError("Close phải >= Low")
        if 'high' in values and v > values['high']:
            raise ValueError("Close phải <= High")
        return v
    
    @property
    def datetime(self) -> datetime:
        """Chuyển timestamp thành datetime object"""
        return datetime.fromtimestamp(self.timestamp / 1000)
    
    @property
    def is_bullish(self) -> bool:
        """Kiểm tra nến tăng (close > open)"""
        return self.close > self.open
    
    @property
    def is_bearish(self) -> bool:
        """Kiểm tra nến giảm (close < open)"""
        return self.close < self.open
    
    @property
    def body_size(self) -> float:
        """Kích thước thân nến (absolute value)"""
        return abs(self.close - self.open)
    
    @property
    def body_size_percent(self) -> float:
        """Kích thước thân nến theo %"""
        return (self.body_size / self.open) * 100
    
    @property
    def range(self) -> float:
        """Phạm vi dao động (high - low)"""
        return self.high - self.low
    
    @property
    def range_percent(self) -> float:
        """Phạm vi dao động theo %"""
        return (self.range / self.open) * 100
    
    @property
    def upper_wick(self) -> float:
        """Độ dài râu trên"""
        return self.high - max(self.open, self.close)
    
    @property
    def lower_wick(self) -> float:
        """Độ dài râu dưới"""
        return min(self.open, self.close) - self.low
    
    @property
    def typical_price(self) -> float:
        """Giá điển hình (HLC/3)"""
        return (self.high + self.low + self.close) / 3
    
    @property
    def weighted_price(self) -> float:
        """Giá trọng số (HLCC/4)"""
        return (self.high + self.low + self.close + self.close) / 4
    
    def __str__(self) -> str:
        direction = "🟢" if self.is_bullish else "🔴"
        return (f"{direction} {self.datetime.strftime('%Y-%m-%d %H:%M')} | "
                f"O:{self.open:.2f} H:{self.high:.2f} L:{self.low:.2f} C:{self.close:.2f} | "
                f"Vol:{self.volume:.2f}")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class CandleList(BaseModel):
    """Danh sách các nến giá với các phương thức tiện ích"""
    
    candles: list[Candle] = Field(default_factory=list)
    
    def __len__(self) -> int:
        return len(self.candles)
    
    def __getitem__(self, index: int) -> Candle:
        return self.candles[index]
    
    def append(self, candle: Candle):
        """Thêm nến mới vào cuối"""
        self.candles.append(candle)
    
    def get_closes(self) -> list[float]:
        """Lấy danh sách giá đóng cửa"""
        return [candle.close for candle in self.candles]
    
    def get_highs(self) -> list[float]:
        """Lấy danh sách giá cao nhất"""
        return [candle.high for candle in self.candles]
    
    def get_lows(self) -> list[float]:
        """Lấy danh sách giá thấp nhất"""
        return [candle.low for candle in self.candles]
    
    def get_opens(self) -> list[float]:
        """Lấy danh sách giá mở cửa"""
        return [candle.open for candle in self.candles]
    
    def get_volumes(self) -> list[float]:
        """Lấy danh sách khối lượng"""
        return [candle.volume for candle in self.candles]
    
    def get_typical_prices(self) -> list[float]:
        """Lấy danh sách giá điển hình"""
        return [candle.typical_price for candle in self.candles]
    
    def get_latest(self, n: int = 1) -> list[Candle]:
        """Lấy n nến mới nhất"""
        return self.candles[-n:] if n <= len(self.candles) else self.candles
    
    def clear(self):
        """Xóa tất cả nến"""
        self.candles.clear()
    
    @property
    def latest_candle(self) -> Optional[Candle]:
        """Lấy nến mới nhất"""
        return self.candles[-1] if self.candles else None
    
    @property
    def latest_close(self) -> Optional[float]:
        """Lấy giá đóng cửa mới nhất"""
        return self.candles[-1].close if self.candles else None
