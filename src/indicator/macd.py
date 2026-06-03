"""
MACD (Moving Average Convergence Divergence) Indicator
Sử dụng pandas-ta để tính toán
"""
import pandas as pd
import pandas_ta as ta
from typing import Optional, Dict, Tuple
from dataclasses import dataclass


@dataclass
class MACDSignal:
    """Tín hiệu MACD"""
    macd: float
    signal: float
    histogram: float
    
    @property
    def is_bullish_crossover(self) -> bool:
        """MACD cắt lên signal line (tín hiệu mua)"""
        return self.macd > self.signal and self.histogram > 0
    
    @property
    def is_bearish_crossover(self) -> bool:
        """MACD cắt xuống signal line (tín hiệu bán)"""
        return self.macd < self.signal and self.histogram < 0
    
    @property
    def is_bullish(self) -> bool:
        """MACD ở trên signal line"""
        return self.macd > self.signal
    
    @property
    def is_bearish(self) -> bool:
        """MACD ở dưới signal line"""
        return self.macd < self.signal
    
    @property
    def histogram_increasing(self) -> bool:
        """Histogram đang tăng (momentum tăng)"""
        return self.histogram > 0
    
    @property
    def histogram_decreasing(self) -> bool:
        """Histogram đang giảm (momentum giảm)"""
        return self.histogram < 0
    
    def __str__(self) -> str:
        direction = "🟢" if self.is_bullish else "🔴"
        return f"{direction} MACD: {self.macd:.4f} | Signal: {self.signal:.4f} | Hist: {self.histogram:.4f}"


class MACDIndicator:
    """
    MACD Indicator Calculator
    
    MACD = EMA(fast) - EMA(slow)
    Signal = EMA(MACD, signal_period)
    Histogram = MACD - Signal
    """
    
    def __init__(
        self,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9
    ):
        """
        Args:
            fast_period: EMA nhanh (mặc định 12)
            slow_period: EMA chậm (mặc định 26)
            signal_period: EMA signal line (mặc định 9)
        """
        if fast_period >= slow_period:
            raise ValueError("fast_period phải nhỏ hơn slow_period")
        
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period
        
        # Lưu trữ giá trị trước đó để phát hiện crossover
        self._previous_macd: Optional[float] = None
        self._previous_signal: Optional[float] = None
        self._previous_histogram: Optional[float] = None
    
    def calculate(
        self,
        prices: list[float],
        return_dataframe: bool = False
    ) -> Optional[pd.DataFrame]:
        """
        Tính MACD từ danh sách giá
        
        Args:
            prices: Danh sách giá đóng cửa
            return_dataframe: Trả về DataFrame thay vì chỉ giá trị cuối
        
        Returns:
            DataFrame chứa MACD, Signal, Histogram hoặc None nếu không đủ dữ liệu
        """
        if len(prices) < self.slow_period + self.signal_period:
            return None
        
        # Tạo DataFrame
        df = pd.DataFrame({'close': prices})
        
        # Tính MACD sử dụng pandas-ta
        macd_df = ta.macd(
            df['close'],
            fast=self.fast_period,
            slow=self.slow_period,
            signal=self.signal_period
        )
        
        if macd_df is None or macd_df.empty:
            return None
        
        # Đổi tên cột để dễ sử dụng
        macd_df.columns = ['macd', 'histogram', 'signal']
        
        # Sắp xếp lại thứ tự cột
        result = macd_df[['macd', 'signal', 'histogram']]
        
        return result if return_dataframe else result
    
    def get_latest_signal(self, prices: list[float]) -> Optional[MACDSignal]:
        """
        Lấy tín hiệu MACD mới nhất
        
        Args:
            prices: Danh sách giá đóng cửa
        
        Returns:
            MACDSignal hoặc None nếu không đủ dữ liệu
        """
        df = self.calculate(prices, return_dataframe=True)
        
        if df is None or df.empty:
            return None
        
        # Lấy giá trị cuối cùng (non-NaN)
        last_row = df.iloc[-1]
        
        if pd.isna(last_row['macd']) or pd.isna(last_row['signal']):
            return None
        
        return MACDSignal(
            macd=float(last_row['macd']),
            signal=float(last_row['signal']),
            histogram=float(last_row['histogram'])
        )
    
    def detect_crossover(
        self,
        prices: list[float]
    ) -> Tuple[bool, Optional[str]]:
        """
        Phát hiện MACD crossover
        
        Args:
            prices: Danh sách giá đóng cửa
        
        Returns:
            (has_crossover, crossover_type) 
            crossover_type: "bullish" hoặc "bearish" hoặc None
        """
        df = self.calculate(prices, return_dataframe=True)
        
        if df is None or len(df) < 2:
            return False, None
        
        # Lấy 2 giá trị cuối
        current = df.iloc[-1]
        previous = df.iloc[-2]
        
        # Kiểm tra có NaN không
        if any(pd.isna([current['macd'], current['signal'], 
                        previous['macd'], previous['signal']])):
            return False, None
        
        current_macd = float(current['macd'])
        current_signal = float(current['signal'])
        previous_macd = float(previous['macd'])
        previous_signal = float(previous['signal'])
        
        # Bullish crossover: MACD cắt lên Signal
        if previous_macd <= previous_signal and current_macd > current_signal:
            return True, "bullish"
        
        # Bearish crossover: MACD cắt xuống Signal
        if previous_macd >= previous_signal and current_macd < current_signal:
            return True, "bearish"
        
        return False, None
    
    def get_trend_strength(self, prices: list[float]) -> Optional[Dict[str, float]]:
        """
        Đánh giá độ mạnh của trend dựa trên MACD
        
        Returns:
            Dict chứa các metrics về trend strength
        """
        df = self.calculate(prices, return_dataframe=True)
        
        if df is None or df.empty:
            return None
        
        # Lấy n giá trị gần nhất để tính trend
        n = min(10, len(df))
        recent_df = df.tail(n)
        
        # Loại bỏ NaN
        recent_df = recent_df.dropna()
        
        if recent_df.empty:
            return None
        
        histogram_values = recent_df['histogram'].values
        macd_values = recent_df['macd'].values
        
        return {
            'avg_histogram': float(histogram_values.mean()),
            'histogram_trend': 'increasing' if histogram_values[-1] > histogram_values[0] else 'decreasing',
            'macd_above_zero': bool(macd_values[-1] > 0),
            'histogram_above_zero': bool(histogram_values[-1] > 0),
            'strength': abs(float(histogram_values[-1]))
        }
    
    def is_divergence(
        self,
        prices: list[float],
        lookback: int = 10
    ) -> Tuple[bool, Optional[str]]:
        """
        Phát hiện divergence giữa giá và MACD
        
        Args:
            prices: Danh sách giá
            lookback: Số nến nhìn lại
        
        Returns:
            (has_divergence, divergence_type)
            divergence_type: "bullish" (giá xuống, MACD lên) hoặc "bearish" (giá lên, MACD xuống)
        """
        if len(prices) < lookback + self.slow_period + self.signal_period:
            return False, None
        
        df = self.calculate(prices, return_dataframe=True)
        
        if df is None or len(df) < lookback:
            return False, None
        
        # Lấy dữ liệu gần nhất
        recent_prices = prices[-lookback:]
        recent_macd = df['macd'].tail(lookback).values
        
        # Loại bỏ NaN
        mask = ~pd.isna(recent_macd)
        recent_prices = [p for p, m in zip(recent_prices, mask) if m]
        recent_macd = recent_macd[mask]
        
        if len(recent_prices) < 5 or len(recent_macd) < 5:
            return False, None
        
        # Tính trend của giá và MACD
        price_trend = recent_prices[-1] - recent_prices[0]
        macd_trend = recent_macd[-1] - recent_macd[0]
        
        # Bullish divergence: giá giảm nhưng MACD tăng
        if price_trend < 0 and macd_trend > 0:
            return True, "bullish"
        
        # Bearish divergence: giá tăng nhưng MACD giảm
        if price_trend > 0 and macd_trend < 0:
            return True, "bearish"
        
        return False, None
    
    def __str__(self) -> str:
        return f"MACD({self.fast_period}, {self.slow_period}, {self.signal_period})"


def calculate_macd(
    prices: list[float],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9
) -> Optional[MACDSignal]:
    """
    Hàm tiện ích để tính MACD nhanh
    
    Args:
        prices: Danh sách giá đóng cửa
        fast: EMA nhanh
        slow: EMA chậm
        signal: EMA signal
    
    Returns:
        MACDSignal hoặc None
    """
    indicator = MACDIndicator(fast, slow, signal)
    return indicator.get_latest_signal(prices)
