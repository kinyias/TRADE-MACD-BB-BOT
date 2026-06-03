"""
Model cho vị thế giao dịch (Position)
"""
from pydantic import BaseModel, Field, validator
from datetime import datetime
from typing import Optional, Literal
from enum import Enum


class PositionSide(str, Enum):
    """Loại vị thế"""
    LONG = "LONG"
    SHORT = "SHORT"


class PositionStatus(str, Enum):
    """Trạng thái vị thế"""
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    PENDING = "PENDING"
    CANCELLED = "CANCELLED"


class Position(BaseModel):
    """Model đại diện cho một vị thế giao dịch"""
    
    # Thông tin cơ bản
    id: Optional[str] = Field(None, description="ID duy nhất của vị thế")
    symbol: str = Field(..., description="Cặp giao dịch (VD: BTCUSDT)")
    side: PositionSide = Field(..., description="LONG hoặc SHORT")
    status: PositionStatus = Field(default=PositionStatus.PENDING)
    
    # Thông tin vào lệnh
    entry_price: float = Field(..., gt=0, description="Giá vào lệnh")
    quantity: float = Field(..., gt=0, description="Số lượng (base asset)")
    entry_time: datetime = Field(default_factory=datetime.now)
    entry_order_id: Optional[str] = Field(None, description="Order ID khi vào lệnh")
    
    # Stop Loss & Take Profit
    stop_loss_price: Optional[float] = Field(None, gt=0)
    take_profit_price: Optional[float] = Field(None, gt=0)
    trailing_stop_percent: Optional[float] = Field(None, gt=0)
    highest_price_since_entry: Optional[float] = Field(None, description="Giá cao nhất kể từ khi vào (LONG)")
    lowest_price_since_entry: Optional[float] = Field(None, description="Giá thấp nhất kể từ khi vào (SHORT)")
    
    # Thông tin đóng lệnh
    exit_price: Optional[float] = Field(None, gt=0)
    exit_time: Optional[datetime] = None
    exit_order_id: Optional[str] = None
    exit_reason: Optional[str] = Field(None, description="Lý do đóng: TP, SL, Manual, Signal")
    
    # Phí giao dịch
    entry_fee: float = Field(default=0.0, ge=0)
    exit_fee: float = Field(default=0.0, ge=0)
    
    # Metadata
    strategy_name: Optional[str] = Field(None, description="Tên chiến lược")
    notes: Optional[str] = Field(None, description="Ghi chú")
    leverage: int = Field(default=1, ge=1, le=125)
    
    @validator('stop_loss_price')
    def validate_stop_loss(cls, v, values):
        """Kiểm tra stop loss hợp lý"""
        if v is None:
            return v
        
        side = values.get('side')
        entry_price = values.get('entry_price')
        
        if side == PositionSide.LONG and v >= entry_price:
            raise ValueError("Stop loss LONG phải < entry price")
        if side == PositionSide.SHORT and v <= entry_price:
            raise ValueError("Stop loss SHORT phải > entry price")
        
        return v
    
    @validator('take_profit_price')
    def validate_take_profit(cls, v, values):
        """Kiểm tra take profit hợp lý"""
        if v is None:
            return v
        
        side = values.get('side')
        entry_price = values.get('entry_price')
        
        if side == PositionSide.LONG and v <= entry_price:
            raise ValueError("Take profit LONG phải > entry price")
        if side == PositionSide.SHORT and v >= entry_price:
            raise ValueError("Take profit SHORT phải < entry price")
        
        return v
    
    @property
    def is_open(self) -> bool:
        """Kiểm tra vị thế đang mở"""
        return self.status == PositionStatus.OPEN
    
    @property
    def is_closed(self) -> bool:
        """Kiểm tra vị thế đã đóng"""
        return self.status == PositionStatus.CLOSED
    
    @property
    def position_value(self) -> float:
        """Giá trị vị thế (entry_price * quantity)"""
        return self.entry_price * self.quantity
    
    @property
    def position_value_with_leverage(self) -> float:
        """Giá trị vị thế có tính leverage"""
        return self.position_value * self.leverage
    
    def calculate_pnl(self, current_price: float) -> float:
        """Tính P&L dựa trên giá hiện tại"""
        if self.side == PositionSide.LONG:
            pnl = (current_price - self.entry_price) * self.quantity
        else:  # SHORT
            pnl = (self.entry_price - current_price) * self.quantity
        
        # Trừ phí
        pnl -= (self.entry_fee + self.exit_fee)
        
        return pnl
    
    def calculate_pnl_percent(self, current_price: float) -> float:
        """Tính P&L theo % (dựa trên giá trị vị thế)"""
        pnl = self.calculate_pnl(current_price)
        return (pnl / self.position_value) * 100
    
    def calculate_roe_percent(self, current_price: float) -> float:
        """Tính ROE (Return on Equity) - % lợi nhuận trên vốn thực tế"""
        pnl = self.calculate_pnl(current_price)
        actual_capital = self.position_value / self.leverage
        return (pnl / actual_capital) * 100 if actual_capital > 0 else 0
    
    @property
    def realized_pnl(self) -> Optional[float]:
        """P&L thực tế khi đã đóng lệnh"""
        if not self.is_closed or self.exit_price is None:
            return None
        return self.calculate_pnl(self.exit_price)
    
    @property
    def realized_pnl_percent(self) -> Optional[float]:
        """P&L % thực tế khi đã đóng lệnh"""
        if not self.is_closed or self.exit_price is None:
            return None
        return self.calculate_pnl_percent(self.exit_price)
    
    @property
    def holding_time(self) -> Optional[float]:
        """Thời gian giữ vị thế (giây)"""
        if self.exit_time:
            return (self.exit_time - self.entry_time).total_seconds()
        return (datetime.now() - self.entry_time).total_seconds()
    
    @property
    def holding_time_formatted(self) -> str:
        """Thời gian giữ vị thế (định dạng dễ đọc)"""
        seconds = self.holding_time
        if seconds is None:
            return "N/A"
        
        days = int(seconds // 86400)
        hours = int((seconds % 86400) // 3600)
        minutes = int((seconds % 3600) // 60)
        
        if days > 0:
            return f"{days}d {hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"
    
    def update_trailing_stop(self, current_price: float):
        """Cập nhật trailing stop loss"""
        if self.trailing_stop_percent is None:
            return
        
        if self.side == PositionSide.LONG:
            # Cập nhật giá cao nhất
            if self.highest_price_since_entry is None or current_price > self.highest_price_since_entry:
                self.highest_price_since_entry = current_price
            
            # Tính trailing stop mới
            new_stop = self.highest_price_since_entry * (1 - self.trailing_stop_percent / 100)
            
            # Chỉ cập nhật nếu stop mới cao hơn stop hiện tại
            if self.stop_loss_price is None or new_stop > self.stop_loss_price:
                self.stop_loss_price = new_stop
        
        else:  # SHORT
            # Cập nhật giá thấp nhất
            if self.lowest_price_since_entry is None or current_price < self.lowest_price_since_entry:
                self.lowest_price_since_entry = current_price
            
            # Tính trailing stop mới
            new_stop = self.lowest_price_since_entry * (1 + self.trailing_stop_percent / 100)
            
            # Chỉ cập nhật nếu stop mới thấp hơn stop hiện tại
            if self.stop_loss_price is None or new_stop < self.stop_loss_price:
                self.stop_loss_price = new_stop
    
    def should_trigger_stop_loss(self, current_price: float) -> bool:
        """Kiểm tra có nên trigger stop loss không"""
        if self.stop_loss_price is None:
            return False
        
        if self.side == PositionSide.LONG:
            return current_price <= self.stop_loss_price
        else:  # SHORT
            return current_price >= self.stop_loss_price
    
    def should_trigger_take_profit(self, current_price: float) -> bool:
        """Kiểm tra có nên trigger take profit không"""
        if self.take_profit_price is None:
            return False
        
        if self.side == PositionSide.LONG:
            return current_price >= self.take_profit_price
        else:  # SHORT
            return current_price <= self.take_profit_price
    
    def close_position(self, exit_price: float, exit_reason: str, exit_order_id: Optional[str] = None):
        """Đóng vị thế"""
        self.exit_price = exit_price
        self.exit_time = datetime.now()
        self.exit_reason = exit_reason
        self.exit_order_id = exit_order_id
        self.status = PositionStatus.CLOSED
    
    def __str__(self) -> str:
        direction = "📈" if self.side == PositionSide.LONG else "📉"
        status_emoji = "🟢" if self.status == PositionStatus.OPEN else "⚪"
        
        info = f"{status_emoji} {direction} {self.symbol} | Entry: {self.entry_price:.2f} | Qty: {self.quantity:.4f}"
        
        if self.is_closed and self.exit_price:
            pnl = self.realized_pnl
            pnl_pct = self.realized_pnl_percent
            pnl_emoji = "✅" if pnl and pnl > 0 else "❌"
            info += f" | Exit: {self.exit_price:.2f} | {pnl_emoji} PnL: {pnl:.2f} ({pnl_pct:.2f}%)"
        
        return info
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
