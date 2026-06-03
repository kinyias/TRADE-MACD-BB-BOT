"""
Bollinger Bands Indicator
Sử dụng pandas-ta để tính toán
"""
import pandas as pd
import pandas_ta as ta
from typing import Optional, Dict, Literal
from dataclasses import dataclass


@dataclass
class BollingerBandsSignal:
    """Tín hiệu Bollinger Bands"""
    upper: float
    middle: float
    lower: float
    current_price: float
    bandwidth: float
    percent_b: float
    
    @property
    def price_position(self) -> Literal["above_upper", "above_middle", "below_middle", "below_lower", "at_middle"]:
        """Vị trí giá so với các bands"""
        if self.current_price > self.upper:
            return "above_upper"
        elif self.current_price > self.middle:
            return "above_middle"
        elif self.current_price < self.lower:
            return "below_lower"
        elif self.current_price < self.middle:
            return "below_middle"
        else:
            return "at_middle"
    
    @property
    def is_overbought(self) -> bool:
        """Giá ở vùng quá mua (trên upper band)"""
        return self.current_price >= self.upper
    
    @property
    def is_oversold(self) -> bool:
        """Giá ở vùng quá bán (dưới lower band)"""
        return self.current_price <= self.lower
    
    @property
    def is_squeeze(self) -> bool:
        """Bandwidth thấp - thị trường đang ép (low volatility)"""
        # Bandwidth < 10% được coi là squeeze
        return self.bandwidth < 10.0
    
    @property
    def is_expansion(self) -> bool:
        """Bandwidth cao - thị trường đang bùng nổ (high volatility)"""
        # Bandwidth > 30% được coi là expansion
        return self.bandwidth > 30.0
    
    @property
    def distance_to_upper(self) -> float:
        """Khoảng cách từ giá hiện tại đến upper band (%)"""
        return ((self.upper - self.current_price) / self.current_price) * 100
    
    @property
    def distance_to_lower(self) -> float:
        """Khoảng cách từ giá hiện tại đến lower band (%)"""
        return ((self.current_price - self.lower) / self.current_price) * 100
    
    def __str__(self) -> str:
        position_emoji = {
            "above_upper": "🔴⬆️",
            "above_middle": "🟡⬆️",
            "at_middle": "🟢➡️",
            "below_middle": "🟡⬇️",
            "below_lower": "🔴⬇️"
        }
        emoji = position_emoji.get(self.price_position, "⚪")
        
        return (f"{emoji} BB | Upper: {self.upper:.2f} | Mid: {self.middle:.2f} | "
                f"Lower: {self.lower:.2f} | Price: {self.current_price:.2f} | "
                f"%B: {self.percent_b:.2f} | BW: {self.bandwidth:.2f}%")


class BollingerBandsIndicator:
    """
    Bollinger Bands Indicator Calculator
    
    Middle Band = SMA(n)
    Upper Band = Middle + (k × σ)
    Lower Band = Middle - (k × σ)
    
    %B = (Price - Lower) / (Upper - Lower)
    Bandwidth = (Upper - Lower) / Middle × 100
    """
    
    def __init__(
        self,
        period: int = 20,
        std_dev: float = 2.0
    ):
        """
        Args:
            period: Số nến cho SMA (mặc định 20)
            std_dev: Số độ lệch chuẩn (mặc định 2.0)
        """
        if period < 2:
            raise ValueError("period phải >= 2")
        if std_dev <= 0:
            raise ValueError("std_dev phải > 0")
        
        self.period = period
        self.std_dev = std_dev
    
    def calculate(
        self,
        prices: list[float],
        return_dataframe: bool = False
    ) -> Optional[pd.DataFrame]:
        """
        Tính Bollinger Bands từ danh sách giá
        
        Args:
            prices: Danh sách giá đóng cửa
            return_dataframe: Trả về DataFrame thay vì chỉ giá trị cuối
        
        Returns:
            DataFrame chứa upper, middle, lower, bandwidth, percent_b
        """
        if len(prices) < self.period:
            return None
        
        # Tạo DataFrame
        df = pd.DataFrame({'close': prices})
        
        # Tính Bollinger Bands sử dụng pandas-ta
        bbands = ta.bbands(
            df['close'],
            length=self.period,
            std=self.std_dev
        )
        
        if bbands is None or bbands.empty:
            return None
        
        # Đổi tên cột để dễ sử dụng
        # pandas-ta trả về: BBL_period_std, BBM_period_std, BBU_period_std, BBB_period_std, BBP_period_std
        cols = bbands.columns
        result = pd.DataFrame({
            'lower': bbands[cols[0]],    # BBL (Lower Band)
            'middle': bbands[cols[1]],   # BBM (Middle Band / SMA)
            'upper': bbands[cols[2]],    # BBU (Upper Band)
            'bandwidth': bbands[cols[3]], # BBB (Bandwidth)
            'percent_b': bbands[cols[4]]  # BBP (Percent B)
        })
        
        return result if return_dataframe else result
    
    def get_latest_signal(
        self,
        prices: list[float]
    ) -> Optional[BollingerBandsSignal]:
        """
        Lấy tín hiệu Bollinger Bands mới nhất
        
        Args:
            prices: Danh sách giá đóng cửa
        
        Returns:
            BollingerBandsSignal hoặc None nếu không đủ dữ liệu
        """
        df = self.calculate(prices, return_dataframe=True)
        
        if df is None or df.empty:
            return None
        
        # Lấy giá trị cuối cùng (non-NaN)
        last_row = df.iloc[-1]
        
        if pd.isna(last_row['upper']) or pd.isna(last_row['lower']):
            return None
        
        current_price = prices[-1]
        
        return BollingerBandsSignal(
            upper=float(last_row['upper']),
            middle=float(last_row['middle']),
            lower=float(last_row['lower']),
            current_price=current_price,
            bandwidth=float(last_row['bandwidth']),
            percent_b=float(last_row['percent_b'])
        )
    
    def detect_bounce(
        self,
        prices: list[float],
        lookback: int = 3
    ) -> Optional[Literal["upper_bounce", "lower_bounce"]]:
        """
        Phát hiện giá chạm band và bounce (nảy lại)
        
        Args:
            prices: Danh sách giá
            lookback: Số nến nhìn lại để xác nhận bounce
        
        Returns:
            "upper_bounce", "lower_bounce" hoặc None
        """
        if len(prices) < self.period + lookback:
            return None
        
        df = self.calculate(prices, return_dataframe=True)
        
        if df is None or len(df) < lookback + 1:
            return None
        
        # Lấy dữ liệu gần nhất
        recent_df = df.tail(lookback + 1)
        recent_prices = prices[-(lookback + 1):]
        
        # Loại bỏ NaN
        recent_df = recent_df.dropna()
        
        if len(recent_df) < lookback + 1:
            return None
        
        upper_band = recent_df['upper'].values
        lower_band = recent_df['lower'].values
        
        # Kiểm tra upper band bounce
        # Giá chạm/vượt upper trong quá khứ gần, và hiện tại đã quay lại trong bands
        for i in range(lookback):
            if recent_prices[i] >= upper_band[i] and recent_prices[-1] < upper_band[-1]:
                return "upper_bounce"
        
        # Kiểm tra lower band bounce
        for i in range(lookback):
            if recent_prices[i] <= lower_band[i] and recent_prices[-1] > lower_band[-1]:
                return "lower_bounce"
        
        return None
    
    def detect_breakout(
        self,
        prices: list[float]
    ) -> Optional[Literal["upper_breakout", "lower_breakout"]]:
        """
        Phát hiện breakout (giá vượt band)
        
        Args:
            prices: Danh sách giá
        
        Returns:
            "upper_breakout", "lower_breakout" hoặc None
        """
        if len(prices) < self.period + 2:
            return None
        
        df = self.calculate(prices, return_dataframe=True)
        
        if df is None or len(df) < 2:
            return None
        
        # Lấy 2 giá trị cuối
        current = df.iloc[-1]
        previous = df.iloc[-2]
        
        if any(pd.isna([current['upper'], current['lower'], 
                        previous['upper'], previous['lower']])):
            return None
        
        current_price = prices[-1]
        previous_price = prices[-2]
        
        # Upper breakout: giá vừa vượt upper band
        if previous_price <= previous['upper'] and current_price > current['upper']:
            return "upper_breakout"
        
        # Lower breakout: giá vừa vượt lower band
        if previous_price >= previous['lower'] and current_price < current['lower']:
            return "lower_breakout"
        
        return None
    
    def detect_squeeze(
        self,
        prices: list[float],
        lookback: int = 10,
        threshold_percentile: float = 20
    ) -> bool:
        """
        Phát hiện Bollinger Squeeze (bandwidth thấp bất thường)
        
        Args:
            prices: Danh sách giá
            lookback: Số nến nhìn lại để so sánh
            threshold_percentile: Bandwidth hiện tại phải < percentile này
        
        Returns:
            True nếu đang trong squeeze
        """
        if len(prices) < self.period + lookback:
            return False
        
        df = self.calculate(prices, return_dataframe=True)
        
        if df is None or len(df) < lookback:
            return False
        
        # Lấy bandwidth gần nhất
        recent_bandwidth = df['bandwidth'].tail(lookback).dropna()
        
        if len(recent_bandwidth) < lookback:
            return False
        
        current_bandwidth = recent_bandwidth.iloc[-1]
        
        # So sánh với percentile
        percentile_value = recent_bandwidth.quantile(threshold_percentile / 100)
        
        return current_bandwidth <= percentile_value
    
    def get_volatility_state(
        self,
        prices: list[float],
        lookback: int = 20
    ) -> Optional[Dict[str, any]]:
        """
        Phân tích trạng thái volatility dựa trên bandwidth
        
        Returns:
            Dict chứa thông tin về volatility state
        """
        if len(prices) < self.period + lookback:
            return None
        
        df = self.calculate(prices, return_dataframe=True)
        
        if df is None or len(df) < lookback:
            return None
        
        recent_bandwidth = df['bandwidth'].tail(lookback).dropna()
        
        if recent_bandwidth.empty:
            return None
        
        current_bandwidth = float(recent_bandwidth.iloc[-1])
        avg_bandwidth = float(recent_bandwidth.mean())
        min_bandwidth = float(recent_bandwidth.min())
        max_bandwidth = float(recent_bandwidth.max())
        
        # Xác định state
        if current_bandwidth <= recent_bandwidth.quantile(0.2):
            state = "squeeze"
        elif current_bandwidth >= recent_bandwidth.quantile(0.8):
            state = "expansion"
        else:
            state = "normal"
        
        return {
            'state': state,
            'current_bandwidth': current_bandwidth,
            'avg_bandwidth': avg_bandwidth,
            'min_bandwidth': min_bandwidth,
            'max_bandwidth': max_bandwidth,
            'bandwidth_percentile': float((recent_bandwidth <= current_bandwidth).sum() / len(recent_bandwidth) * 100)
        }
    
    def __str__(self) -> str:
        return f"BollingerBands(period={self.period}, std={self.std_dev})"


def calculate_bollinger_bands(
    prices: list[float],
    period: int = 20,
    std_dev: float = 2.0
) -> Optional[BollingerBandsSignal]:
    """
    Hàm tiện ích để tính Bollinger Bands nhanh
    
    Args:
        prices: Danh sách giá đóng cửa
        period: Chu kỳ SMA
        std_dev: Số độ lệch chuẩn
    
    Returns:
        BollingerBandsSignal hoặc None
    """
    indicator = BollingerBandsIndicator(period, std_dev)
    return indicator.get_latest_signal(prices)
