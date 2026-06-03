"""
Position Size Calculator - Tính toán kích thước vị thế giao dịch

Module này tính toán số lượng giao dịch dựa trên:
- Tài khoản hiện tại
- % rủi ro cho phép
- Giá vào lệnh và stop loss
- Leverage (nếu có)
"""
from dataclasses import dataclass
from typing import Optional, Literal
from decimal import Decimal, ROUND_DOWN
import logging

logger = logging.getLogger(__name__)


@dataclass
class PositionSizeResult:
    """Kết quả tính toán position size"""
    quantity: float  # Số lượng base asset
    notional_value: float  # Giá trị danh nghĩa (quantity * price)
    risk_amount: float  # Số tiền rủi ro thực tế
    risk_percent: float  # % rủi ro thực tế
    leverage: int  # Đòn bẩy sử dụng
    margin_required: float  # Margin cần thiết
    max_loss: float  # Lỗ tối đa nếu hit stop loss
    
    # Validation flags
    is_valid: bool = True
    warnings: list[str] = None
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []
    
    def __str__(self) -> str:
        result = (
            f"Position Size: {self.quantity:.8f}\n"
            f"Notional Value: ${self.notional_value:.2f}\n"
            f"Risk: ${self.risk_amount:.2f} ({self.risk_percent:.2f}%)\n"
            f"Margin Required: ${self.margin_required:.2f}\n"
            f"Max Loss: ${self.max_loss:.2f}"
        )
        if self.leverage > 1:
            result += f"\nLeverage: {self.leverage}x"
        if self.warnings:
            result += f"\n⚠️  Warnings: {', '.join(self.warnings)}"
        return result


class PositionSizer:
    """
    Position Size Calculator
    
    Tính toán kích thước vị thế dựa trên nhiều phương pháp:
    1. Fixed Fractional (Risk % per trade)
    2. Fixed Amount
    3. Kelly Criterion
    4. Percent of Equity
    """
    
    def __init__(
        self,
        account_balance: float,
        risk_per_trade_percent: float = 1.0,
        max_position_size_percent: float = 10.0,
        leverage: int = 1,
        commission_rate: float = 0.001,  # 0.1% (Binance)
        min_notional: float = 10.0,  # Minimum order size
    ):
        """
        Args:
            account_balance: Số dư tài khoản (USDT)
            risk_per_trade_percent: % rủi ro mỗi lệnh (1-10%)
            max_position_size_percent: % vốn tối đa cho 1 vị thế (1-100%)
            leverage: Đòn bẩy (1-125x)
            commission_rate: Phí giao dịch (0.1% = 0.001)
            min_notional: Giá trị đơn hàng tối thiểu
        """
        if account_balance <= 0:
            raise ValueError("Account balance phải > 0")
        if not (0.1 <= risk_per_trade_percent <= 10):
            raise ValueError("Risk per trade phải trong khoảng 0.1-10%")
        if not (1 <= max_position_size_percent <= 100):
            raise ValueError("Max position size phải trong khoảng 1-100%")
        if not (1 <= leverage <= 125):
            raise ValueError("Leverage phải trong khoảng 1-125")
        
        self.account_balance = account_balance
        self.risk_per_trade_percent = risk_per_trade_percent
        self.max_position_size_percent = max_position_size_percent
        self.leverage = leverage
        self.commission_rate = commission_rate
        self.min_notional = min_notional
    
    def calculate_fixed_risk(
        self,
        entry_price: float,
        stop_loss_price: float,
        side: Literal["LONG", "SHORT"] = "LONG",
        override_risk_percent: Optional[float] = None
    ) -> PositionSizeResult:
        """
        Tính position size dựa trên fixed risk per trade
        
        Formula:
        - Risk Amount = Account Balance × Risk %
        - Risk per Unit = |Entry Price - Stop Loss Price|
        - Quantity = Risk Amount / Risk per Unit
        
        Args:
            entry_price: Giá vào lệnh
            stop_loss_price: Giá stop loss
            side: LONG hoặc SHORT
            override_risk_percent: Override risk % (optional)
        
        Returns:
            PositionSizeResult
        """
        if entry_price <= 0 or stop_loss_price <= 0:
            raise ValueError("Giá phải > 0")
        
        # Validate stop loss
        if side == "LONG" and stop_loss_price >= entry_price:
            raise ValueError("Stop loss LONG phải < entry price")
        if side == "SHORT" and stop_loss_price <= entry_price:
            raise ValueError("Stop loss SHORT phải > entry price")
        
        # Risk amount
        risk_percent = override_risk_percent or self.risk_per_trade_percent
        risk_amount = self.account_balance * (risk_percent / 100)
        
        # Risk per unit (tính theo absolute value)
        risk_per_unit = abs(entry_price - stop_loss_price)
        
        # Calculate quantity
        # Quantity = Risk Amount / Risk per Unit
        quantity = risk_amount / risk_per_unit
        
        # Calculate notional value (before leverage)
        notional_value = quantity * entry_price
        
        # Apply max position size constraint
        max_notional = self.account_balance * (self.max_position_size_percent / 100)
        
        warnings = []
        
        if notional_value > max_notional:
            # Reduce quantity to fit max position size
            quantity = max_notional / entry_price
            notional_value = quantity * entry_price
            warnings.append(f"Position size giảm xuống max {self.max_position_size_percent}%")
        
        # Calculate margin required (with leverage)
        margin_required = notional_value / self.leverage
        
        # Check if enough balance for margin
        if margin_required > self.account_balance:
            # Reduce to available balance
            margin_required = self.account_balance * 0.95  # Giữ lại 5% buffer
            notional_value = margin_required * self.leverage
            quantity = notional_value / entry_price
            warnings.append("Không đủ balance, giảm position size")
        
        # Check minimum notional
        if notional_value < self.min_notional:
            warnings.append(f"Position size < minimum ({self.min_notional} USDT)")
        
        # Calculate actual risk with new quantity
        actual_risk = quantity * risk_per_unit
        actual_risk_percent = (actual_risk / self.account_balance) * 100
        
        # Calculate max loss including fees
        commission_cost = notional_value * self.commission_rate * 2  # Entry + Exit
        max_loss = actual_risk + commission_cost
        
        return PositionSizeResult(
            quantity=quantity,
            notional_value=notional_value,
            risk_amount=actual_risk,
            risk_percent=actual_risk_percent,
            leverage=self.leverage,
            margin_required=margin_required,
            max_loss=max_loss,
            is_valid=len([w for w in warnings if "minimum" not in w]) == 0,
            warnings=warnings
        )
    
    def calculate_fixed_amount(
        self,
        entry_price: float,
        position_value: float,
        stop_loss_price: Optional[float] = None
    ) -> PositionSizeResult:
        """
        Tính position size với giá trị cố định
        
        Args:
            entry_price: Giá vào lệnh
            position_value: Giá trị vị thế mong muốn (USDT)
            stop_loss_price: Giá stop loss (optional, để tính risk)
        
        Returns:
            PositionSizeResult
        """
        if position_value <= 0:
            raise ValueError("Position value phải > 0")
        
        # Calculate quantity
        quantity = position_value / entry_price
        notional_value = quantity * entry_price
        
        # Check constraints
        warnings = []
        max_notional = self.account_balance * (self.max_position_size_percent / 100)
        
        if notional_value > max_notional:
            quantity = max_notional / entry_price
            notional_value = quantity * entry_price
            warnings.append(f"Position size giảm xuống max {self.max_position_size_percent}%")
        
        # Calculate margin
        margin_required = notional_value / self.leverage
        
        if margin_required > self.account_balance:
            margin_required = self.account_balance * 0.95
            notional_value = margin_required * self.leverage
            quantity = notional_value / entry_price
            warnings.append("Không đủ balance, giảm position size")
        
        # Calculate risk if stop loss provided
        risk_amount = 0.0
        risk_percent = 0.0
        max_loss = 0.0
        
        if stop_loss_price:
            risk_per_unit = abs(entry_price - stop_loss_price)
            risk_amount = quantity * risk_per_unit
            risk_percent = (risk_amount / self.account_balance) * 100
            
            commission_cost = notional_value * self.commission_rate * 2
            max_loss = risk_amount + commission_cost
            
            # Warn if risk too high
            if risk_percent > self.risk_per_trade_percent * 2:
                warnings.append(f"⚠️ Risk cao ({risk_percent:.2f}%) vượt ngưỡng")
        
        return PositionSizeResult(
            quantity=quantity,
            notional_value=notional_value,
            risk_amount=risk_amount,
            risk_percent=risk_percent,
            leverage=self.leverage,
            margin_required=margin_required,
            max_loss=max_loss,
            is_valid=True,
            warnings=warnings
        )
    
    def calculate_percent_of_equity(
        self,
        entry_price: float,
        percent: float,
        stop_loss_price: Optional[float] = None
    ) -> PositionSizeResult:
        """
        Tính position size theo % vốn
        
        Args:
            entry_price: Giá vào lệnh
            percent: % vốn muốn đầu tư (1-100%)
            stop_loss_price: Giá stop loss (optional)
        
        Returns:
            PositionSizeResult
        """
        if not (1 <= percent <= 100):
            raise ValueError("Percent phải trong khoảng 1-100%")
        
        position_value = self.account_balance * (percent / 100)
        return self.calculate_fixed_amount(entry_price, position_value, stop_loss_price)
    
    def update_balance(self, new_balance: float):
        """Cập nhật số dư tài khoản"""
        if new_balance <= 0:
            raise ValueError("Balance phải > 0")
        self.account_balance = new_balance
        logger.info(f"Account balance updated: ${new_balance:.2f}")


def round_quantity(quantity: float, step_size: float) -> float:
    """
    Làm tròn quantity theo step size của exchange
    
    Args:
        quantity: Số lượng cần làm tròn
        step_size: Bước nhảy (VD: 0.001 cho BTC)
    
    Returns:
        Số lượng đã làm tròn
    """
    if step_size == 0:
        return quantity
    
    # Sử dụng Decimal để tính toán chính xác
    qty_decimal = Decimal(str(quantity))
    step_decimal = Decimal(str(step_size))
    
    # Làm tròn xuống
    rounded = (qty_decimal // step_decimal) * step_decimal
    
    return float(rounded)


def validate_position_size(
    quantity: float,
    price: float,
    min_qty: float,
    max_qty: float,
    min_notional: float,
    step_size: float
) -> tuple[bool, Optional[str]]:
    """
    Validate position size theo quy định của exchange
    
    Returns:
        (is_valid, error_message)
    """
    # Check min quantity
    if quantity < min_qty:
        return False, f"Quantity {quantity} < min {min_qty}"
    
    # Check max quantity
    if quantity > max_qty:
        return False, f"Quantity {quantity} > max {max_qty}"
    
    # Check notional value
    notional = quantity * price
    if notional < min_notional:
        return False, f"Notional ${notional:.2f} < min ${min_notional}"
    
    # Check step size
    rounded = round_quantity(quantity, step_size)
    if abs(quantity - rounded) > step_size * 0.01:  # Tolerance
        return False, f"Quantity không khớp step size {step_size}"
    
    return True, None
