"""
MACD + Bollinger Bands Combined Strategy

Chiến lược kết hợp MACD và Bollinger Bands để tạo tín hiệu giao dịch
- MACD: Xác định momentum và trend
- Bollinger Bands: Xác định vùng quá mua/quá bán và volatility
"""
from dataclasses import dataclass
from typing import Optional, Literal, Dict, List
from datetime import datetime

from ..indicator.macd import MACDIndicator, MACDSignal
from ..indicator.bollingerband import BollingerBandsIndicator, BollingerBandsSignal
from ..models.candle import Candle
from ..models.position import Position, PositionSide


@dataclass
class StrategySignal:
    """Tín hiệu giao dịch từ strategy"""
    action: Literal["BUY", "SELL", "HOLD"]
    confidence: float  # 0.0 - 1.0
    entry_price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    reason: str = ""
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
    
    @property
    def is_entry_signal(self) -> bool:
        """Kiểm tra có phải tín hiệu vào lệnh"""
        return self.action in ["BUY", "SELL"]
    
    @property
    def risk_reward_ratio(self) -> Optional[float]:
        """Tính tỷ lệ risk/reward"""
        if not self.stop_loss or not self.take_profit:
            return None
        
        risk = abs(self.entry_price - self.stop_loss)
        reward = abs(self.take_profit - self.entry_price)
        
        if risk == 0:
            return None
        
        return reward / risk
    
    def __str__(self) -> str:
        emoji = {"BUY": "🟢", "SELL": "🔴", "HOLD": "⚪"}.get(self.action, "")
        result = f"{emoji} {self.action} | Price: {self.entry_price:.2f} | Confidence: {self.confidence:.0%}"
        
        if self.stop_loss:
            result += f" | SL: {self.stop_loss:.2f}"
        if self.take_profit:
            result += f" | TP: {self.take_profit:.2f}"
        if self.risk_reward_ratio:
            result += f" | RR: 1:{self.risk_reward_ratio:.2f}"
        
        result += f"\n   Reason: {self.reason}"
        return result


class MACDBBStrategy:
    """
    Chiến lược kết hợp MACD và Bollinger Bands
    
    Logic chính:
    1. Tín hiệu MUA (LONG):
       - MACD bullish crossover HOẶC MACD đang bullish
       - Giá ở lower BB hoặc oversold (dưới lower band)
       - Không trong giai đoạn squeeze
       
    2. Tín hiệu BÁN (SHORT):
       - MACD bearish crossover HOẶC MACD đang bearish
       - Giá ở upper BB hoặc overbought (trên upper band)
       - Không trong giai đoạn squeeze
       
    3. Bộ lọc bổ sung:
       - Divergence: tăng confidence
       - BB Squeeze breakout: tín hiệu mạnh
       - Volume confirmation (nếu có)
    """
    
    def __init__(
        self,
        # MACD parameters
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9,
        
        # Bollinger Bands parameters
        bb_period: int = 20,
        bb_std_dev: float = 2.0,
        
        # Strategy parameters
        min_confidence: float = 0.6,
        require_crossover: bool = False,
        use_divergence: bool = True,
        risk_reward_ratio: float = 2.0,
        stop_loss_atr_multiplier: float = 1.5,
    ):
        """
        Args:
            macd_fast: MACD EMA nhanh
            macd_slow: MACD EMA chậm
            macd_signal: MACD signal line
            bb_period: Bollinger Bands period
            bb_std_dev: Bollinger Bands độ lệch chuẩn
            min_confidence: Confidence tối thiểu để vào lệnh (0.0-1.0)
            require_crossover: Bắt buộc phải có MACD crossover
            use_divergence: Sử dụng divergence để tăng confidence
            risk_reward_ratio: Tỷ lệ Risk/Reward mong muốn
            stop_loss_atr_multiplier: Multiplier cho ATR để tính stop loss
        """
        # Khởi tạo indicators
        self.macd = MACDIndicator(
            fast_period=macd_fast,
            slow_period=macd_slow,
            signal_period=macd_signal
        )
        
        self.bb = BollingerBandsIndicator(
            period=bb_period,
            std_dev=bb_std_dev
        )
        
        # Strategy parameters
        self.min_confidence = min_confidence
        self.require_crossover = require_crossover
        self.use_divergence = use_divergence
        self.risk_reward_ratio = risk_reward_ratio
        self.stop_loss_atr_multiplier = stop_loss_atr_multiplier
        
        # Metadata
        self.name = "MACD_BB_Strategy"
        self.version = "1.0.0"
        
    def analyze(
        self,
        candles: List[Candle],
        current_position: Optional[Position] = None
    ) -> StrategySignal:
        """
        Phân tích và tạo tín hiệu giao dịch
        
        Args:
            candles: Danh sách nến giá (mới nhất ở cuối)
            current_position: Vị thế hiện tại (nếu có)
        
        Returns:
            StrategySignal
        """
        # Kiểm tra đủ dữ liệu
        if len(candles) < max(self.macd.slow_period + self.macd.signal_period, self.bb.period) + 10:
            return StrategySignal(
                action="HOLD",
                confidence=0.0,
                entry_price=candles[-1].close,
                reason="Không đủ dữ liệu để phân tích"
            )
        
        # Lấy danh sách giá đóng cửa
        close_prices = [c.close for c in candles]
        current_price = close_prices[-1]
        
        # Tính các indicators
        macd_signal = self.macd.get_latest_signal(close_prices)
        bb_signal = self.bb.get_latest_signal(close_prices)
        
        if not macd_signal or not bb_signal:
            return StrategySignal(
                action="HOLD",
                confidence=0.0,
                entry_price=current_price,
                reason="Không thể tính indicators"
            )
        
        # Phát hiện các patterns
        has_crossover, crossover_type = self.macd.detect_crossover(close_prices)
        has_divergence, divergence_type = None, None
        if self.use_divergence:
            has_divergence, divergence_type = self.macd.is_divergence(close_prices)
        
        bb_bounce = self.bb.detect_bounce(close_prices)
        bb_breakout = self.bb.detect_breakout(close_prices)
        bb_squeeze = self.bb.detect_squeeze(close_prices)
        
        # Nếu đang có position, kiểm tra exit signals
        if current_position and current_position.is_open:
            exit_signal = self._check_exit_signal(
                current_position,
                current_price,
                macd_signal,
                bb_signal,
                has_crossover,
                crossover_type
            )
            if exit_signal:
                return exit_signal
        
        # Phân tích tín hiệu entry
        return self._generate_entry_signal(
            current_price=current_price,
            candles=candles,
            macd_signal=macd_signal,
            bb_signal=bb_signal,
            has_crossover=has_crossover,
            crossover_type=crossover_type,
            has_divergence=has_divergence,
            divergence_type=divergence_type,
            bb_bounce=bb_bounce,
            bb_breakout=bb_breakout,
            bb_squeeze=bb_squeeze
        )
    
    def _generate_entry_signal(
        self,
        current_price: float,
        candles: List[Candle],
        macd_signal: MACDSignal,
        bb_signal: BollingerBandsSignal,
        has_crossover: bool,
        crossover_type: Optional[str],
        has_divergence: bool,
        divergence_type: Optional[str],
        bb_bounce: Optional[str],
        bb_breakout: Optional[str],
        bb_squeeze: bool
    ) -> StrategySignal:
        """Tạo tín hiệu vào lệnh (entry signal)"""
        
        # Khởi tạo điểm confidence và lý do
        confidence = 0.0
        reasons = []
        action = "HOLD"
        
        # === PHÂN TÍCH TÍN HIỆU MUA (LONG) ===
        buy_score = 0.0
        buy_reasons = []
        
        # MACD conditions
        if has_crossover and crossover_type == "bullish":
            buy_score += 0.35
            buy_reasons.append("MACD bullish crossover")
        elif macd_signal.is_bullish and not self.require_crossover:
            buy_score += 0.20
            buy_reasons.append("MACD bullish")
        
        # Bollinger Bands conditions
        if bb_signal.is_oversold:
            buy_score += 0.25
            buy_reasons.append("Giá oversold (dưới lower BB)")
        elif bb_signal.price_position == "below_middle":
            buy_score += 0.15
            buy_reasons.append("Giá dưới middle BB")
        
        # BB Bounce
        if bb_bounce == "lower_bounce":
            buy_score += 0.20
            buy_reasons.append("Bounce từ lower BB")
        
        # Divergence
        if has_divergence and divergence_type == "bullish":
            buy_score += 0.15
            buy_reasons.append("Bullish divergence")
        
        # BB Squeeze breakout
        if bb_squeeze and macd_signal.histogram_increasing:
            buy_score += 0.10
            buy_reasons.append("Squeeze breakout potential")
        
        # === PHÂN TÍCH TÍN HIỆU BÁN (SHORT) ===
        sell_score = 0.0
        sell_reasons = []
        
        # MACD conditions
        if has_crossover and crossover_type == "bearish":
            sell_score += 0.35
            sell_reasons.append("MACD bearish crossover")
        elif macd_signal.is_bearish and not self.require_crossover:
            sell_score += 0.20
            sell_reasons.append("MACD bearish")
        
        # Bollinger Bands conditions
        if bb_signal.is_overbought:
            sell_score += 0.25
            sell_reasons.append("Giá overbought (trên upper BB)")
        elif bb_signal.price_position == "above_middle":
            sell_score += 0.15
            sell_reasons.append("Giá trên middle BB")
        
        # BB Bounce
        if bb_bounce == "upper_bounce":
            sell_score += 0.20
            sell_reasons.append("Bounce từ upper BB")
        
        # Divergence
        if has_divergence and divergence_type == "bearish":
            sell_score += 0.15
            sell_reasons.append("Bearish divergence")
        
        # BB Squeeze breakout
        if bb_squeeze and macd_signal.histogram_decreasing:
            sell_score += 0.10
            sell_reasons.append("Squeeze breakout potential")
        
        # === XÁC ĐỊNH TÍN HIỆU CUỐI CÙNG ===
        if buy_score > sell_score and buy_score >= self.min_confidence:
            action = "BUY"
            confidence = min(buy_score, 1.0)
            reasons = buy_reasons
        elif sell_score > buy_score and sell_score >= self.min_confidence:
            action = "SELL"
            confidence = min(sell_score, 1.0)
            reasons = sell_reasons
        else:
            return StrategySignal(
                action="HOLD",
                confidence=max(buy_score, sell_score),
                entry_price=current_price,
                reason=f"Không đủ confidence (BUY: {buy_score:.2f}, SELL: {sell_score:.2f})"
            )
        
        # Tính Stop Loss và Take Profit
        stop_loss, take_profit = self._calculate_risk_management(
            action=action,
            entry_price=current_price,
            candles=candles,
            bb_signal=bb_signal
        )
        
        return StrategySignal(
            action=action,
            confidence=confidence,
            entry_price=current_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            reason=" + ".join(reasons)
        )
    
    def _check_exit_signal(
        self,
        position: Position,
        current_price: float,
        macd_signal: MACDSignal,
        bb_signal: BollingerBandsSignal,
        has_crossover: bool,
        crossover_type: Optional[str]
    ) -> Optional[StrategySignal]:
        """Kiểm tra tín hiệu thoát lệnh"""
        
        # Kiểm tra exit conditions cho LONG position
        if position.side == PositionSide.LONG:
            # Exit nếu MACD bearish crossover
            if has_crossover and crossover_type == "bearish":
                return StrategySignal(
                    action="SELL",
                    confidence=0.9,
                    entry_price=current_price,
                    reason="Exit LONG: MACD bearish crossover"
                )
            
            # Exit nếu giá chạm upper BB (take profit)
            if bb_signal.is_overbought:
                return StrategySignal(
                    action="SELL",
                    confidence=0.8,
                    entry_price=current_price,
                    reason="Exit LONG: Giá overbought tại upper BB"
                )
            
            # Exit nếu MACD chuyển bearish và giá trên middle BB
            if macd_signal.is_bearish and bb_signal.price_position in ["above_upper", "above_middle"]:
                return StrategySignal(
                    action="SELL",
                    confidence=0.7,
                    entry_price=current_price,
                    reason="Exit LONG: MACD bearish + giá trên middle BB"
                )
        
        # Kiểm tra exit conditions cho SHORT position
        elif position.side == PositionSide.SHORT:
            # Exit nếu MACD bullish crossover
            if has_crossover and crossover_type == "bullish":
                return StrategySignal(
                    action="BUY",
                    confidence=0.9,
                    entry_price=current_price,
                    reason="Exit SHORT: MACD bullish crossover"
                )
            
            # Exit nếu giá chạm lower BB (take profit)
            if bb_signal.is_oversold:
                return StrategySignal(
                    action="BUY",
                    confidence=0.8,
                    entry_price=current_price,
                    reason="Exit SHORT: Giá oversold tại lower BB"
                )
            
            # Exit nếu MACD chuyển bullish và giá dưới middle BB
            if macd_signal.is_bullish and bb_signal.price_position in ["below_lower", "below_middle"]:
                return StrategySignal(
                    action="BUY",
                    confidence=0.7,
                    entry_price=current_price,
                    reason="Exit SHORT: MACD bullish + giá dưới middle BB"
                )
        
        return None
    
    def _calculate_risk_management(
        self,
        action: str,
        entry_price: float,
        candles: List[Candle],
        bb_signal: BollingerBandsSignal
    ) -> tuple[Optional[float], Optional[float]]:
        """
        Tính Stop Loss và Take Profit
        
        Returns:
            (stop_loss, take_profit)
        """
        if action not in ["BUY", "SELL"]:
            return None, None
        
        # Tính ATR cho stop loss động
        atr = self._calculate_atr(candles, period=14)
        
        if action == "BUY":
            # Stop Loss cho LONG
            # Option 1: Sử dụng lower BB
            stop_loss_bb = bb_signal.lower
            
            # Option 2: Sử dụng ATR
            stop_loss_atr = entry_price - (atr * self.stop_loss_atr_multiplier) if atr else None
            
            # Chọn stop loss an toàn hơn (thấp hơn)
            if stop_loss_atr and stop_loss_bb:
                stop_loss = min(stop_loss_bb, stop_loss_atr)
            else:
                stop_loss = stop_loss_bb if stop_loss_bb else stop_loss_atr
            
            # Take Profit: sử dụng upper BB hoặc risk/reward ratio
            if stop_loss:
                risk = entry_price - stop_loss
                take_profit_rr = entry_price + (risk * self.risk_reward_ratio)
                take_profit_bb = bb_signal.upper
                
                # Chọn take profit gần hơn (realistic)
                take_profit = min(take_profit_rr, take_profit_bb) if take_profit_bb > entry_price else take_profit_rr
            else:
                take_profit = bb_signal.upper
        
        else:  # SELL (SHORT)
            # Stop Loss cho SHORT
            # Option 1: Sử dụng upper BB
            stop_loss_bb = bb_signal.upper
            
            # Option 2: Sử dụng ATR
            stop_loss_atr = entry_price + (atr * self.stop_loss_atr_multiplier) if atr else None
            
            # Chọn stop loss an toàn hơn (cao hơn)
            if stop_loss_atr and stop_loss_bb:
                stop_loss = max(stop_loss_bb, stop_loss_atr)
            else:
                stop_loss = stop_loss_bb if stop_loss_bb else stop_loss_atr
            
            # Take Profit: sử dụng lower BB hoặc risk/reward ratio
            if stop_loss:
                risk = stop_loss - entry_price
                take_profit_rr = entry_price - (risk * self.risk_reward_ratio)
                take_profit_bb = bb_signal.lower
                
                # Chọn take profit gần hơn (realistic)
                take_profit = max(take_profit_rr, take_profit_bb) if take_profit_bb < entry_price else take_profit_rr
            else:
                take_profit = bb_signal.lower
        
        return stop_loss, take_profit
    
    def _calculate_atr(self, candles: List[Candle], period: int = 14) -> Optional[float]:
        """
        Tính Average True Range (ATR) để đo độ biến động
        
        Args:
            candles: Danh sách nến
            period: Chu kỳ ATR
        
        Returns:
            ATR value hoặc None nếu không đủ dữ liệu
        """
        if len(candles) < period + 1:
            return None
        
        true_ranges = []
        
        for i in range(1, len(candles)):
            high = candles[i].high
            low = candles[i].low
            prev_close = candles[i-1].close
            
            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            true_ranges.append(tr)
        
        # Tính ATR (simple moving average của True Range)
        if len(true_ranges) >= period:
            atr = sum(true_ranges[-period:]) / period
            return atr
        
        return None
    
    def get_strategy_info(self) -> Dict:
        """Lấy thông tin về strategy"""
        return {
            "name": self.name,
            "version": self.version,
            "indicators": {
                "macd": {
                    "fast": self.macd.fast_period,
                    "slow": self.macd.slow_period,
                    "signal": self.macd.signal_period
                },
                "bollinger_bands": {
                    "period": self.bb.period,
                    "std_dev": self.bb.std_dev
                }
            },
            "parameters": {
                "min_confidence": self.min_confidence,
                "require_crossover": self.require_crossover,
                "use_divergence": self.use_divergence,
                "risk_reward_ratio": self.risk_reward_ratio,
                "stop_loss_atr_multiplier": self.stop_loss_atr_multiplier
            }
        }
    
    def __str__(self) -> str:
        return f"{self.name} v{self.version}"


# === UTILITY FUNCTIONS ===

def create_default_strategy() -> MACDBBStrategy:
    """Tạo strategy với cấu hình mặc định"""
    return MACDBBStrategy(
        macd_fast=12,
        macd_slow=26,
        macd_signal=9,
        bb_period=20,
        bb_std_dev=2.0,
        min_confidence=0.6,
        require_crossover=False,
        use_divergence=True,
        risk_reward_ratio=2.0,
        stop_loss_atr_multiplier=1.5
    )


def create_aggressive_strategy() -> MACDBBStrategy:
    """
    Tạo strategy aggressive (nhiều tín hiệu hơn, rủi ro cao hơn)
    """
    return MACDBBStrategy(
        macd_fast=8,
        macd_slow=21,
        macd_signal=5,
        bb_period=15,
        bb_std_dev=1.5,
        min_confidence=0.5,
        require_crossover=False,
        use_divergence=True,
        risk_reward_ratio=1.5,
        stop_loss_atr_multiplier=1.0
    )


def create_conservative_strategy() -> MACDBBStrategy:
    """
    Tạo strategy conservative (ít tín hiệu hơn, rủi ro thấp hơn)
    """
    return MACDBBStrategy(
        macd_fast=12,
        macd_slow=26,
        macd_signal=9,
        bb_period=20,
        bb_std_dev=2.5,
        min_confidence=0.75,
        require_crossover=True,
        use_divergence=True,
        risk_reward_ratio=3.0,
        stop_loss_atr_multiplier=2.0
    )
