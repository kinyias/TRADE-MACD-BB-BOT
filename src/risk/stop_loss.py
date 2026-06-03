"""
Stop Loss Manager - Quản lý Stop Loss động

Module này quản lý stop loss cho vị thế giao dịch:
- Fixed stop loss (% hoặc giá tuyệt đối)
- ATR-based stop loss
- Trailing stop loss
- Break-even stop loss
"""
from dataclasses import dataclass
from typing import Optional, Literal, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class StopLossLevel:
    """Thông tin về mức stop loss"""
    price: float  # Giá stop loss
    type: Literal["fixed", "trailing", "break_even", "atr_based"]
    reason: str  # Lý do đặt stop loss này
    updated_at: datetime = None
    
    def __post_init__(self):
        if self.updated_at is None:
            self.updated_at = datetime.now()
    
    def __str__(self) -> str:
        return f"SL {self.type}: ${self.price:.2f} - {self.reason}"


class StopLossManager:
    """
    Stop Loss Manager
    
    Quản lý và cập nhật stop loss dựa trên nhiều phương pháp:
    1. Fixed Stop Loss (% hoặc giá tuyệt đối)
    2. ATR-based Stop Loss (dựa trên volatility)
    3. Trailing Stop Loss (theo dấu giá)
    4. Break-even Stop Loss (bảo vệ vốn)
    """
    
    def __init__(
        self,
        default_stop_loss_percent: float = 2.0,
        trailing_stop_percent: float = 1.5,
        break_even_trigger_percent: float = 1.0,
        atr_multiplier: float = 2.0,
    ):
        """
        Args:
            default_stop_loss_percent: % stop loss mặc định (1-10%)
            trailing_stop_percent: % trailing stop (0.5-5%)
            break_even_trigger_percent: % lời để kích hoạt break-even (0.5-5%)
            atr_multiplier: Multiplier cho ATR stop loss (1-5)
        """
        if not (0.5 <= default_stop_loss_percent <= 10):
            raise ValueError("Default stop loss phải trong khoảng 0.5-10%")
        if not (0.2 <= trailing_stop_percent <= 5):
            raise ValueError("Trailing stop phải trong khoảng 0.2-5%")
        if not (0.5 <= break_even_trigger_percent <= 5):
            raise ValueError("Break-even trigger phải trong khoảng 0.5-5%")
        if not (1 <= atr_multiplier <= 5):
            raise ValueError("ATR multiplier phải trong khoảng 1-5")
        
        self.default_stop_loss_percent = default_stop_loss_percent
        self.trailing_stop_percent = trailing_stop_percent
        self.break_even_trigger_percent = break_even_trigger_percent
        self.atr_multiplier = atr_multiplier
        
        # Tracking
        self._stop_loss_history: List[StopLossLevel] = []
    
    def calculate_fixed_stop_loss(
        self,
        entry_price: float,
        side: Literal["LONG", "SHORT"],
        stop_loss_percent: Optional[float] = None
    ) -> StopLossLevel:
        """
        Tính stop loss cố định dựa trên %
        
        Args:
            entry_price: Giá vào lệnh
            side: LONG hoặc SHORT
            stop_loss_percent: % stop loss (override default)
        
        Returns:
            StopLossLevel
        """
        if entry_price <= 0:
            raise ValueError("Entry price phải > 0")
        
        percent = stop_loss_percent or self.default_stop_loss_percent
        
        if side == "LONG":
            # Stop loss dưới entry price
            stop_price = entry_price * (1 - percent / 100)
        else:  # SHORT
            # Stop loss trên entry price
            stop_price = entry_price * (1 + percent / 100)
        
        level = StopLossLevel(
            price=stop_price,
            type="fixed",
            reason=f"Fixed {percent}% từ entry ${entry_price:.2f}"
        )
        
        self._stop_loss_history.append(level)
        logger.info(f"Fixed stop loss calculated: {level}")
        
        return level
    
    def calculate_atr_stop_loss(
        self,
        entry_price: float,
        atr: float,
        side: Literal["LONG", "SHORT"],
        multiplier: Optional[float] = None
    ) -> StopLossLevel:
        """
        Tính stop loss dựa trên ATR (Average True Range)
        
        ATR stop loss thích ứng với volatility của thị trường
        
        Args:
            entry_price: Giá vào lệnh
            atr: Average True Range value
            side: LONG hoặc SHORT
            multiplier: ATR multiplier (override default)
        
        Returns:
            StopLossLevel
        """
        if entry_price <= 0 or atr <= 0:
            raise ValueError("Entry price và ATR phải > 0")
        
        mult = multiplier or self.atr_multiplier
        stop_distance = atr * mult
        
        if side == "LONG":
            stop_price = entry_price - stop_distance
        else:  # SHORT
            stop_price = entry_price + stop_distance
        
        # Calculate percent for logging
        percent = (stop_distance / entry_price) * 100
        
        level = StopLossLevel(
            price=stop_price,
            type="atr_based",
            reason=f"ATR {mult}x (${atr:.2f}) = {percent:.2f}% từ entry"
        )
        
        self._stop_loss_history.append(level)
        logger.info(f"ATR stop loss calculated: {level}")
        
        return level
    
    def update_trailing_stop(
        self,
        entry_price: float,
        current_price: float,
        current_stop_loss: float,
        side: Literal["LONG", "SHORT"],
        trailing_percent: Optional[float] = None
    ) -> Optional[StopLossLevel]:
        """
        Cập nhật trailing stop loss
        
        Trailing stop di chuyển theo giá để bảo vệ lợi nhuận
        
        Args:
            entry_price: Giá vào lệnh
            current_price: Giá hiện tại
            current_stop_loss: Stop loss hiện tại
            side: LONG hoặc SHORT
            trailing_percent: % trailing (override default)
        
        Returns:
            StopLossLevel mới nếu cần update, None nếu giữ nguyên
        """
        if any(p <= 0 for p in [entry_price, current_price, current_stop_loss]):
            raise ValueError("Tất cả giá phải > 0")
        
        percent = trailing_percent or self.trailing_stop_percent
        
        if side == "LONG":
            # Trailing stop cho LONG: chỉ di chuyển lên
            new_stop = current_price * (1 - percent / 100)
            
            if new_stop > current_stop_loss:
                level = StopLossLevel(
                    price=new_stop,
                    type="trailing",
                    reason=f"Trailing {percent}% từ ${current_price:.2f}"
                )
                self._stop_loss_history.append(level)
                logger.info(f"Trailing stop updated: ${current_stop_loss:.2f} → ${new_stop:.2f}")
                return level
        
        else:  # SHORT
            # Trailing stop cho SHORT: chỉ di chuyển xuống
            new_stop = current_price * (1 + percent / 100)
            
            if new_stop < current_stop_loss:
                level = StopLossLevel(
                    price=new_stop,
                    type="trailing",
                    reason=f"Trailing {percent}% từ ${current_price:.2f}"
                )
                self._stop_loss_history.append(level)
                logger.info(f"Trailing stop updated: ${current_stop_loss:.2f} → ${new_stop:.2f}")
                return level
        
        return None  # Không cần update
    
    def check_break_even(
        self,
        entry_price: float,
        current_price: float,
        current_stop_loss: float,
        side: Literal["LONG", "SHORT"],
        trigger_percent: Optional[float] = None,
        buffer_percent: float = 0.1
    ) -> Optional[StopLossLevel]:
        """
        Kiểm tra và đặt break-even stop loss
        
        Break-even: Di chuyển stop loss về entry price khi đã có lời nhất định
        
        Args:
            entry_price: Giá vào lệnh
            current_price: Giá hiện tại
            current_stop_loss: Stop loss hiện tại
            side: LONG hoặc SHORT
            trigger_percent: % lời để kích hoạt (override default)
            buffer_percent: % buffer trên entry (để cover phí)
        
        Returns:
            StopLossLevel mới nếu đạt điều kiện, None nếu chưa
        """
        if any(p <= 0 for p in [entry_price, current_price, current_stop_loss]):
            raise ValueError("Tất cả giá phải > 0")
        
        percent = trigger_percent or self.break_even_trigger_percent
        
        if side == "LONG":
            # Kiểm tra đã đạt % lời chưa
            profit_percent = ((current_price - entry_price) / entry_price) * 100
            
            if profit_percent >= percent and current_stop_loss < entry_price:
                # Đặt stop ở entry + buffer
                new_stop = entry_price * (1 + buffer_percent / 100)
                
                level = StopLossLevel(
                    price=new_stop,
                    type="break_even",
                    reason=f"Break-even tại ${entry_price:.2f} (profit {profit_percent:.2f}%)"
                )
                self._stop_loss_history.append(level)
                logger.info(f"Break-even activated: ${current_stop_loss:.2f} → ${new_stop:.2f}")
                return level
        
        else:  # SHORT
            # Kiểm tra đã đạt % lời chưa
            profit_percent = ((entry_price - current_price) / entry_price) * 100
            
            if profit_percent >= percent and current_stop_loss > entry_price:
                # Đặt stop ở entry - buffer
                new_stop = entry_price * (1 - buffer_percent / 100)
                
                level = StopLossLevel(
                    price=new_stop,
                    type="break_even",
                    reason=f"Break-even tại ${entry_price:.2f} (profit {profit_percent:.2f}%)"
                )
                self._stop_loss_history.append(level)
                logger.info(f"Break-even activated: ${current_stop_loss:.2f} → ${new_stop:.2f}")
                return level
        
        return None  # Chưa đạt điều kiện
    
    def should_trigger_stop_loss(
        self,
        current_price: float,
        stop_loss_price: float,
        side: Literal["LONG", "SHORT"]
    ) -> bool:
        """
        Kiểm tra giá có chạm stop loss không
        
        Args:
            current_price: Giá hiện tại
            stop_loss_price: Giá stop loss
            side: LONG hoặc SHORT
        
        Returns:
            True nếu cần đóng lệnh
        """
        if side == "LONG":
            return current_price <= stop_loss_price
        else:  # SHORT
            return current_price >= stop_loss_price
    
    def get_stop_loss_history(self) -> List[StopLossLevel]:
        """Lấy lịch sử các lần điều chỉnh stop loss"""
        return self._stop_loss_history.copy()
    
    def clear_history(self):
        """Xóa lịch sử stop loss (dùng khi đóng vị thế)"""
        self._stop_loss_history.clear()


def calculate_risk_from_stop_loss(
    entry_price: float,
    stop_loss_price: float,
    quantity: float
) -> dict:
    """
    Tính toán risk từ stop loss
    
    Args:
        entry_price: Giá vào lệnh
        stop_loss_price: Giá stop loss
        quantity: Số lượng
    
    Returns:
        Dict với risk_amount, risk_per_unit, risk_percent
    """
    if entry_price <= 0 or stop_loss_price <= 0 or quantity <= 0:
        raise ValueError("Tất cả tham số phải > 0")
    
    risk_per_unit = abs(entry_price - stop_loss_price)
    risk_amount = risk_per_unit * quantity
    risk_percent = (risk_per_unit / entry_price) * 100
    
    return {
        "risk_amount": risk_amount,
        "risk_per_unit": risk_per_unit,
        "risk_percent": risk_percent
    }
