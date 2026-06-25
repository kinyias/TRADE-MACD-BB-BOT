"""
EMA (Exponential Moving Average) Indicator
Tính toán theo công thức chuẩn của Binance
"""
import pandas as pd
from typing import Optional, Literal
from dataclasses import dataclass

@dataclass
class EMASignal:
    """Tín hiệu EMA"""
    ema_value: float
    current_price: float
    period: int
    
    @property
    def is_bullish(self) -> bool:
        """Giá ở trên EMA (xu hướng tăng)"""
        return self.current_price > self.ema_value
    
    @property
    def is_bearish(self) -> bool:
        """Giá ở dưới EMA (xu hướng giảm)"""
        return self.current_price < self.ema_value
    
    @property
    def distance_to_ema(self) -> float:
        """Khoảng cách từ giá hiện tại đến EMA (%)"""
        return ((self.current_price - self.ema_value) / self.ema_value) * 100
    
    @property
    def distance_absolute(self) -> float:
        """Khoảng cách tuyệt đối từ giá đến EMA"""
        return abs(self.current_price - self.ema_value)
    
    @property
    def price_position(self) -> Literal["above", "below", "at"]:
        """Vị trí giá so với EMA"""
        if self.current_price > self.ema_value:
            return "above"
        elif self.current_price < self.ema_value:
            return "below"
        else:
            return "at"
    
    @property
    def is_far_from_ema(self) -> bool:
        """Giá cách xa EMA (>5%)"""
        return abs(self.distance_to_ema) > 5.0
    
    def __str__(self) -> str:
        position_emoji = {
            "above": "🟢⬆️",
            "below": "🔴⬇️",
            "at": "🟡➡️"
        }
        emoji = position_emoji.get(self.price_position, "⚪")
        
        return (f"{emoji} EMA{self.period} | EMA: {self.ema_value:.2f} | "
                f"Price: {self.current_price:.2f} | "
                f"Distance: {self.distance_to_ema:+.2f}%")

class EMAIndicator:
    """
    EMA (Exponential Moving Average) Indicator Calculator
    
    EMA = Price(t) × k + EMA(y) × (1 − k)
    k = 2 / (N + 1)
    
    EMA phản ứng nhanh hơn SMA với thay đổi giá gần đây
    """
    
    def __init__(self, period: int = 200):
        """
        Args:
            period: Số nến cho EMA (mặc định 200)
        """
        if period < 1:
            raise ValueError("period phải >= 1")
        
        self.period = period
        
        # Lưu trữ giá trị trước để phát hiện crossover
        self._previous_price: Optional[float] = None
        self._previous_ema: Optional[float] = None
    
    def _calculate_ema_manual(self, prices: list[float]) -> list[float]:
        """
        Tính EMA thủ công theo công thức chuẩn của Binance
        
        EMA(t) = Price(t) * k + EMA(t-1) * (1 - k)
        k = 2 / (period + 1)
        EMA đầu tiên = SMA của period đầu tiên
        
        Args:
            prices: Danh sách giá đóng cửa
        
        Returns:
            Danh sách giá trị EMA (NaN cho các giá trị trước period)
        """
        if len(prices) < self.period:
            return [float('nan')] * len(prices)
        
        k = 2.0 / (self.period + 1)
        ema_values = [float('nan')] * len(prices)
        
        # EMA đầu tiên = SMA của period đầu tiên
        sma = sum(prices[:self.period]) / self.period
        ema_values[self.period - 1] = sma
        
        # Tính EMA cho các nến tiếp theo
        for i in range(self.period, len(prices)):
            ema_values[i] = prices[i] * k + ema_values[i - 1] * (1 - k)
        
        return ema_values
    
    def calculate(
        self,
        prices: list[float],
        return_dataframe: bool = False
    ) -> Optional[pd.DataFrame]:
        """
        Tính EMA từ danh sách giá
        
        Args:
            prices: Danh sách giá đóng cửa
            return_dataframe: Trả về DataFrame thay vì chỉ giá trị cuối
        
        Returns:
            DataFrame chứa EMA hoặc None nếu không đủ dữ liệu
        """
        if len(prices) < self.period:
            return None
        
        # Tính EMA thủ công
        ema_values = self._calculate_ema_manual(prices)
        
        # Tạo DataFrame kết quả
        result = pd.DataFrame({
            'ema': ema_values,
            'price': prices
        })
        
        return result if return_dataframe else result
    
    def get_latest_signal(
        self,
        prices: list[float]
    ) -> Optional[EMASignal]:
        """
        Lấy tín hiệu EMA mới nhất
        
        Args:
            prices: Danh sách giá đóng cửa
        
        Returns:
            EMASignal hoặc None nếu không đủ dữ liệu
        """
        df = self.calculate(prices, return_dataframe=True)
        
        if df is None or df.empty:
            return None
        
        # Lấy giá trị cuối cùng (non-NaN)
        last_row = df.iloc[-1]
        
        if pd.isna(last_row['ema']):
            return None
        
        current_price = prices[-1]
        
        # Lưu giá trị cho lần detect crossover sau
        self._previous_price = current_price
        self._previous_ema = float(last_row['ema'])
        
        return EMASignal(
            ema_value=float(last_row['ema']),
            current_price=current_price,
            period=self.period
        )
    
    def detect_crossover(
        self,
        prices: list[float]
    ) -> tuple[bool, Optional[Literal["bullish", "bearish"]]]:
        """
        Phát hiện giá cắt EMA
        
        Args:
            prices: Danh sách giá đóng cửa
        
        Returns:
            (has_crossover, crossover_type)
            crossover_type: "bullish" (giá cắt lên EMA) hoặc "bearish" (giá cắt xuống EMA)
        """
        df = self.calculate(prices, return_dataframe=True)
        
        if df is None or len(df) < 2:
            return False, None
        
        # Lấy 2 giá trị cuối
        current = df.iloc[-1]
        previous = df.iloc[-2]
        
        # Kiểm tra có NaN không
        if any(pd.isna([current['ema'], current['price'], 
                        previous['ema'], previous['price']])):
            return False, None
        
        current_price = float(current['price'])
        current_ema = float(current['ema'])
        previous_price = float(previous['price'])
        previous_ema = float(previous['ema'])
        
        # Bullish crossover: Giá cắt lên EMA
        if previous_price <= previous_ema and current_price > current_ema:
            return True, "bullish"
        
        # Bearish crossover: Giá cắt xuống EMA
        if previous_price >= previous_ema and current_price < current_ema:
            return True, "bearish"
        
        return False, None
    
    def is_strong_trend(
        self,
        prices: list[float],
        threshold: float = 3.0
    ) -> tuple[bool, Optional[Literal["bullish", "bearish"]]]:
        """
        Xác định xu hướng mạnh dựa trên khoảng cách giá với EMA
        
        Args:
            prices: Danh sách giá
            threshold: Ngưỡng % để coi là xu hướng mạnh (mặc định 3%)
        
        Returns:
            (is_strong, trend_type)
        """
        signal = self.get_latest_signal(prices)
        
        if signal is None:
            return False, None
        
        distance = signal.distance_to_ema
        
        # Xu hướng tăng mạnh
        if distance > threshold:
            return True, "bullish"
        
        # Xu hướng giảm mạnh
        if distance < -threshold:
            return True, "bearish"
        
        return False, None
    
    def get_slope(
        self,
        prices: list[float],
        lookback: int = 5
    ) -> Optional[Literal["rising", "falling", "flat"]]:
        """
        Tính độ dốc của EMA (hướng của EMA)
        
        Args:
            prices: Danh sách giá
            lookback: Số nến nhìn lại để tính slope
        
        Returns:
            "rising", "falling", hoặc "flat"
        """
        df = self.calculate(prices, return_dataframe=True)
        
        if df is None or len(df) < lookback + 1:
            return None
        
        # Lấy EMA values gần nhất
        recent_ema = df['ema'].tail(lookback + 1).dropna()
        
        if len(recent_ema) < lookback + 1:
            return None
        
        ema_values = recent_ema.values
        first_ema = ema_values[0]
        last_ema = ema_values[-1]
        
        # Tính % thay đổi
        change_percent = ((last_ema - first_ema) / first_ema) * 100
        
        # Threshold để coi là flat (±0.5%)
        if abs(change_percent) < 0.5:
            return "flat"
        elif change_percent > 0:
            return "rising"
        else:
            return "falling"
    
    def is_price_bouncing_off_ema(
        self,
        prices: list[float],
        lookback: int = 3,
        bounce_threshold: float = 0.5
    ) -> Optional[Literal["bounce_up", "bounce_down"]]:
        """
        Phát hiện giá chạm EMA và bounce (nảy lại)
        
        Args:
            prices: Danh sách giá
            lookback: Số nến nhìn lại
            bounce_threshold: Ngưỡng % để coi là bounce
        
        Returns:
            "bounce_up" (giá chạm EMA từ trên và nảy lên) hoặc 
            "bounce_down" (giá chạm EMA từ dưới và nảy xuống) hoặc None
        """
        if len(prices) < self.period + lookback + 1:
            return None
        
        df = self.calculate(prices, return_dataframe=True)
        
        if df is None or len(df) < lookback + 1:
            return None
        
        # Lấy dữ liệu gần nhất
        recent_df = df.tail(lookback + 1).dropna()
        
        if len(recent_df) < lookback + 1:
            return None
        
        ema_values = recent_df['ema'].values
        price_values = recent_df['price'].values
        
        current_price = price_values[-1]
        current_ema = ema_values[-1]
        
        # Tính khoảng cách % trong quá khứ
        for i in range(lookback):
            past_price = price_values[i]
            past_ema = ema_values[i]
            past_distance = ((past_price - past_ema) / past_ema) * 100
            
            # Giá đã ở gần EMA (trong threshold) và bây giờ đã đi xa hơn
            current_distance = ((current_price - current_ema) / current_ema) * 100
            
            # Bounce up: giá đã gần/dưới EMA, giờ lên trên
            if abs(past_distance) < bounce_threshold and current_distance > bounce_threshold:
                return "bounce_up"
            
            # Bounce down: giá đã gần/trên EMA, giờ xuống dưới
            if abs(past_distance) < bounce_threshold and current_distance < -bounce_threshold:
                return "bounce_down"
        
        return None
    
    def get_support_resistance_level(
        self,
        prices: list[float]
    ) -> Optional[dict[str, float]]:
        """
        EMA có thể hoạt động như support/resistance động
        
        Returns:
            Dict chứa thông tin về level
        """
        signal = self.get_latest_signal(prices)
        
        if signal is None:
            return None
        
        return {
            'level': signal.ema_value,
            'current_price': signal.current_price,
            'distance_percent': signal.distance_to_ema,
            'role': 'support' if signal.is_bullish else 'resistance'
        }
