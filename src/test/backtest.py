"""
Backtest System with MACD + Bollinger Bands Strategy Visualization
Uses mplfinance for advanced charting
"""
import pandas as pd
import numpy as np
import mplfinance as mpf
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from models.candle import Candle
from models.position import Position, PositionSide, PositionStatus
from indicator.macd import MACDIndicator
from indicator.bollingerband import BollingerBandsIndicator
from strategies.macd_bb_strategy import MACDBBStrategy, StrategySignal


@dataclass
class Trade:
    """Kết quả một giao dịch"""
    entry_time: datetime
    exit_time: datetime
    side: str
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float
    pnl_percent: float
    fees: float
    reason: str
    
    @property
    def duration(self) -> timedelta:
        return self.exit_time - self.entry_time


@dataclass
class BacktestResult:
    """Kết quả backtest tổng thể"""
    initial_capital: float
    final_capital: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    total_pnl_percent: float
    max_drawdown: float
    max_drawdown_percent: float
    sharpe_ratio: float
    profit_factor: float
    avg_win: float
    avg_loss: float
    largest_win: float
    largest_loss: float
    trades: List[Trade] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)
    
    def print_summary(self):
        """In tóm tắt kết quả"""
        print("\n" + "="*60)
        print("📊 BACKTEST RESULTS SUMMARY")
        print("="*60)
        print(f"Initial Capital:        ${self.initial_capital:,.2f}")
        print(f"Final Capital:          ${self.final_capital:,.2f}")
        print(f"Total P&L:              ${self.total_pnl:,.2f} ({self.total_pnl_percent:+.2f}%)")
        print(f"Max Drawdown:           ${self.max_drawdown:,.2f} ({self.max_drawdown_percent:.2f}%)")
        print(f"\nTotal Trades:           {self.total_trades}")
        print(f"Winning Trades:         {self.winning_trades} ({self.win_rate:.1f}%)")
        print(f"Losing Trades:          {self.losing_trades}")
        print(f"\nAverage Win:            ${self.avg_win:,.2f}")
        print(f"Average Loss:           ${self.avg_loss:,.2f}")
        print(f"Largest Win:            ${self.largest_win:,.2f}")
        print(f"Largest Loss:           ${self.largest_loss:,.2f}")
        print(f"\nProfit Factor:          {self.profit_factor:.2f}")
        print(f"Sharpe Ratio:           {self.sharpe_ratio:.2f}")
        print("="*60)


class BacktestEngine:
    """Engine để chạy backtest"""
    
    def __init__(
        self,
        strategy: MACDBBStrategy,
        initial_capital: float = 10000.0,
        position_size_percent: float = 0.95,
        commission: float = 0.001,  # 0.1%
        slippage: float = 0.0005,  # 0.05%
    ):
        """
        Args:
            strategy: Strategy để test
            initial_capital: Vốn ban đầu
            position_size_percent: % vốn sử dụng cho mỗi lệnh
            commission: Phí giao dịch (%)
            slippage: Slippage (%)
        """
        self.strategy = strategy
        self.initial_capital = initial_capital
        self.position_size_percent = position_size_percent
        self.commission = commission
        self.slippage = slippage
        
        # State variables
        self.capital = initial_capital
        self.current_position: Optional[Position] = None
        self.trades: List[Trade] = []
        self.equity_curve: List[float] = []
        self.peak_capital = initial_capital
        self.max_drawdown = 0.0
        
    def run(self, candles: List[Candle]) -> BacktestResult:
        """
        Chạy backtest trên dữ liệu lịch sử
        
        Args:
            candles: Danh sách nến giá lịch sử
        
        Returns:
            BacktestResult
        """
        print(f"🚀 Starting backtest with {len(candles)} candles...")
        print(f"Strategy: {self.strategy}")
        print(f"Initial Capital: ${self.initial_capital:,.2f}\n")
        
        for i in range(len(candles)):
            current_candles = candles[:i+1]
            current_candle = candles[i]
            current_price = current_candle.close
            
            # Cập nhật equity curve
            current_equity = self._calculate_current_equity(current_price)
            self.equity_curve.append(current_equity)
            
            # Cập nhật peak và drawdown
            if current_equity > self.peak_capital:
                self.peak_capital = current_equity
            
            drawdown = self.peak_capital - current_equity
            if drawdown > self.max_drawdown:
                self.max_drawdown = drawdown
            
            # Kiểm tra stop loss / take profit
            if self.current_position and self.current_position.is_open:
                if self._check_stop_loss_take_profit(current_candle):
                    continue  # Position đã đóng, chuyển sang candle tiếp
            
            # Lấy tín hiệu từ strategy
            signal = self.strategy.analyze(current_candles, self.current_position)
            
            # Xử lý tín hiệu
            if signal.action == "BUY":
                if self.current_position and self.current_position.side == PositionSide.SHORT:
                    # Đóng SHORT position
                    self._close_position(current_candle, "Exit SHORT: " + signal.reason)
                
                if not self.current_position:
                    # Mở LONG position
                    self._open_position(current_candle, PositionSide.LONG, signal)
            
            elif signal.action == "SELL":
                if self.current_position and self.current_position.side == PositionSide.LONG:
                    # Đóng LONG position
                    self._close_position(current_candle, "Exit LONG: " + signal.reason)
                
                if not self.current_position:
                    # Mở SHORT position
                    self._open_position(current_candle, PositionSide.SHORT, signal)
        
        # Đóng position cuối cùng nếu còn mở
        if self.current_position and self.current_position.is_open:
            self._close_position(candles[-1], "End of backtest")
        
        # Tính toán kết quả
        return self._calculate_results()
    
    def _calculate_current_equity(self, current_price: float) -> float:
        """Tính equity hiện tại (bao gồm unrealized P&L)"""
        equity = self.capital
        
        if self.current_position and self.current_position.is_open:
            unrealized_pnl = self._calculate_pnl(
                self.current_position.entry_price,
                current_price,
                self.current_position.quantity,
                self.current_position.side
            )
            equity += unrealized_pnl
        
        return equity
    
    def _check_stop_loss_take_profit(self, candle: Candle) -> bool:
        """Kiểm tra stop loss và take profit"""
        if not self.current_position or not self.current_position.is_open:
            return False
        
        position = self.current_position
        
        # Kiểm tra LONG position
        if position.side == PositionSide.LONG:
            # Stop Loss
            if position.stop_loss_price and candle.low <= position.stop_loss_price:
                exit_price = position.stop_loss_price
                self._close_position_at_price(candle, exit_price, "Stop Loss")
                return True
            
            # Take Profit
            if position.take_profit_price and candle.high >= position.take_profit_price:
                exit_price = position.take_profit_price
                self._close_position_at_price(candle, exit_price, "Take Profit")
                return True
        
        # Kiểm tra SHORT position
        elif position.side == PositionSide.SHORT:
            # Stop Loss
            if position.stop_loss_price and candle.high >= position.stop_loss_price:
                exit_price = position.stop_loss_price
                self._close_position_at_price(candle, exit_price, "Stop Loss")
                return True
            
            # Take Profit
            if position.take_profit_price and candle.low <= position.take_profit_price:
                exit_price = position.take_profit_price
                self._close_position_at_price(candle, exit_price, "Take Profit")
                return True
        
        return False
    
    def _open_position(
        self,
        candle: Candle,
        side: PositionSide,
        signal: StrategySignal
    ):
        """Mở position mới"""
        entry_price = self._apply_slippage(candle.close, side, is_entry=True)
        
        # Tính quantity dựa trên % vốn
        position_value = self.capital * self.position_size_percent
        quantity = position_value / entry_price
        
        # Tính phí
        entry_fee = position_value * self.commission
        
        # Trừ phí khỏi vốn
        self.capital -= entry_fee
        
        # Tạo position
        self.current_position = Position(
            symbol="BACKTEST",
            side=side,
            status=PositionStatus.OPEN,
            entry_price=entry_price,
            quantity=quantity,
            entry_time=candle.datetime,
            stop_loss_price=signal.stop_loss,
            take_profit_price=signal.take_profit,
            entry_fee=entry_fee,
            strategy_name=self.strategy.name
        )
        
        print(f"{'🟢 LONG' if side == PositionSide.LONG else '🔴 SHORT'} @ ${entry_price:.2f} | "
              f"Qty: {quantity:.4f} | SL: ${signal.stop_loss:.2f} | TP: ${signal.take_profit:.2f}")
    
    def _close_position(self, candle: Candle, reason: str):
        """Đóng position tại giá close của candle"""
        self._close_position_at_price(candle, candle.close, reason)
    
    def _close_position_at_price(self, candle: Candle, exit_price: float, reason: str):
        """Đóng position tại giá cụ thể"""
        if not self.current_position or not self.current_position.is_open:
            return
        
        position = self.current_position
        
        # Apply slippage
        exit_price = self._apply_slippage(exit_price, position.side, is_entry=False)
        
        # Tính P&L
        pnl = self._calculate_pnl(
            position.entry_price,
            exit_price,
            position.quantity,
            position.side
        )
        
        # Tính phí exit
        position_value = position.quantity * exit_price
        exit_fee = position_value * self.commission
        
        # P&L sau phí
        net_pnl = pnl - exit_fee
        pnl_percent = (net_pnl / (position.entry_price * position.quantity)) * 100
        
        # Cập nhật vốn
        self.capital += position.quantity * exit_price + net_pnl
        
        # Cập nhật position
        position.exit_price = exit_price
        position.exit_time = candle.datetime
        position.exit_fee = exit_fee
        position.exit_reason = reason
        position.status = PositionStatus.CLOSED
        
        # Lưu trade
        trade = Trade(
            entry_time=position.entry_time,
            exit_time=position.exit_time,
            side=position.side.value,
            entry_price=position.entry_price,
            exit_price=exit_price,
            quantity=position.quantity,
            pnl=net_pnl,
            pnl_percent=pnl_percent,
            fees=position.entry_fee + exit_fee,
            reason=reason
        )
        self.trades.append(trade)
        
        # Reset position
        self.current_position = None
        
        emoji = "✅" if net_pnl > 0 else "❌"
        print(f"{emoji} CLOSE @ ${exit_price:.2f} | P&L: ${net_pnl:,.2f} ({pnl_percent:+.2f}%) | {reason}")
    
    def _calculate_pnl(
        self,
        entry_price: float,
        exit_price: float,
        quantity: float,
        side: PositionSide
    ) -> float:
        """Tính P&L (chưa trừ phí)"""
        if side == PositionSide.LONG:
            return (exit_price - entry_price) * quantity
        else:  # SHORT
            return (entry_price - exit_price) * quantity
    
    def _apply_slippage(self, price: float, side: PositionSide, is_entry: bool) -> float:
        """Áp dụng slippage vào giá"""
        if is_entry:
            # Entry: LONG mua cao hơn, SHORT bán thấp hơn
            if side == PositionSide.LONG:
                return price * (1 + self.slippage)
            else:
                return price * (1 - self.slippage)
        else:
            # Exit: LONG bán thấp hơn, SHORT mua cao hơn
            if side == PositionSide.LONG:
                return price * (1 - self.slippage)
            else:
                return price * (1 + self.slippage)
    
    def _calculate_results(self) -> BacktestResult:
        """Tính toán kết quả backtest"""
        if not self.trades:
            return BacktestResult(
                initial_capital=self.initial_capital,
                final_capital=self.capital,
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate=0.0,
                total_pnl=0.0,
                total_pnl_percent=0.0,
                max_drawdown=0.0,
                max_drawdown_percent=0.0,
                sharpe_ratio=0.0,
                profit_factor=0.0,
                avg_win=0.0,
                avg_loss=0.0,
                largest_win=0.0,
                largest_loss=0.0,
                trades=self.trades,
                equity_curve=self.equity_curve
            )
        
        # Tính các metrics
        winning_trades = [t for t in self.trades if t.pnl > 0]
        losing_trades = [t for t in self.trades if t.pnl < 0]
        
        total_trades = len(self.trades)
        num_winning = len(winning_trades)
        num_losing = len(losing_trades)
        win_rate = (num_winning / total_trades * 100) if total_trades > 0 else 0
        
        total_pnl = sum(t.pnl for t in self.trades)
        total_pnl_percent = (total_pnl / self.initial_capital) * 100
        
        gross_profit = sum(t.pnl for t in winning_trades) if winning_trades else 0
        gross_loss = abs(sum(t.pnl for t in losing_trades)) if losing_trades else 0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        avg_win = gross_profit / num_winning if num_winning > 0 else 0
        avg_loss = gross_loss / num_losing if num_losing > 0 else 0
        
        largest_win = max((t.pnl for t in winning_trades), default=0)
        largest_loss = min((t.pnl for t in losing_trades), default=0)
        
        # Tính Sharpe Ratio
        if len(self.equity_curve) > 1:
            returns = np.diff(self.equity_curve) / self.equity_curve[:-1]
            sharpe_ratio = (np.mean(returns) / np.std(returns) * np.sqrt(252)) if np.std(returns) > 0 else 0
        else:
            sharpe_ratio = 0
        
        max_drawdown_percent = (self.max_drawdown / self.peak_capital * 100) if self.peak_capital > 0 else 0
        
        return BacktestResult(
            initial_capital=self.initial_capital,
            final_capital=self.capital,
            total_trades=total_trades,
            winning_trades=num_winning,
            losing_trades=num_losing,
            win_rate=win_rate,
            total_pnl=total_pnl,
            total_pnl_percent=total_pnl_percent,
            max_drawdown=self.max_drawdown,
            max_drawdown_percent=max_drawdown_percent,
            sharpe_ratio=sharpe_ratio,
            profit_factor=profit_factor,
            avg_win=avg_win,
            avg_loss=avg_loss,
            largest_win=largest_win,
            largest_loss=largest_loss,
            trades=self.trades,
            equity_curve=self.equity_curve
        )


def create_backtest_chart(
    candles: List[Candle],
    strategy: MACDBBStrategy,
    trades: List[Trade],
    result: BacktestResult,
    save_path: str = "backtest_chart.png"
):
    """
    Tạo biểu đồ backtest với mplfinance
    
    Args:
        candles: Dữ liệu nến
        strategy: Strategy được sử dụng
        trades: Danh sách giao dịch
        result: Kết quả backtest
        save_path: Đường dẫn lưu file
    """
    print(f"\n📊 Generating backtest chart...")
    
    # Tạo DataFrame cho mplfinance
    df = pd.DataFrame([
        {
            'Date': c.datetime,
            'Open': c.open,
            'High': c.high,
            'Low': c.low,
            'Close': c.close,
            'Volume': c.volume
        }
        for c in candles
    ])
    df.set_index('Date', inplace=True)
    
    # Tính indicators
    close_prices = [c.close for c in candles]
    
    # MACD
    macd_df = strategy.macd.calculate(close_prices, return_dataframe=True)
    if macd_df is not None:
        df['MACD'] = macd_df['macd'].values
        df['MACD_Signal'] = macd_df['signal'].values
        df['MACD_Hist'] = macd_df['histogram'].values
    
    # Bollinger Bands
    bb_df = strategy.bb.calculate(close_prices, return_dataframe=True)
    if bb_df is not None:
        df['BB_Upper'] = bb_df['upper'].values
        df['BB_Middle'] = bb_df['middle'].values
        df['BB_Lower'] = bb_df['lower'].values
    
    # Tạo markers cho buy/sell signals
    buy_signals = []
    sell_signals = []
    
    for trade in trades:
        # Entry signal
        entry_idx = df.index.searchsorted(trade.entry_time)
        if entry_idx < len(df):
            if trade.side == "LONG":
                buy_signals.append(entry_idx)
            else:
                sell_signals.append(entry_idx)
    
    # Tạo additional plots
    apds = []
    
    # MACD subplot
    if 'MACD' in df.columns:
        apds.append(
            mpf.make_addplot(df['MACD'], panel=2, color='blue', width=1.5, ylabel='MACD')
        )
        apds.append(
            mpf.make_addplot(df['MACD_Signal'], panel=2, color='red', width=1.5)
        )
        apds.append(
            mpf.make_addplot(df['MACD_Hist'], panel=2, type='bar', color='gray', alpha=0.5)
        )
    
    # Bollinger Bands overlay
    if 'BB_Upper' in df.columns:
        apds.append(
            mpf.make_addplot(df['BB_Upper'], color='purple', linestyle='--', width=1)
        )
        apds.append(
            mpf.make_addplot(df['BB_Middle'], color='orange', linestyle='--', width=1)
        )
        apds.append(
            mpf.make_addplot(df['BB_Lower'], color='purple', linestyle='--', width=1)
        )
    
    # Buy/Sell markers
    if buy_signals:
        marker_data = [np.nan] * len(df)
        for idx in buy_signals:
            if idx < len(marker_data):
                marker_data[idx] = df.iloc[idx]['Low'] * 0.995
        apds.append(
            mpf.make_addplot(marker_data, type='scatter', markersize=100, 
                            marker='^', color='green', panel=0)
        )
    
    if sell_signals:
        marker_data = [np.nan] * len(df)
        for idx in sell_signals:
            if idx < len(marker_data):
                marker_data[idx] = df.iloc[idx]['High'] * 1.005
        apds.append(
            mpf.make_addplot(marker_data, type='scatter', markersize=100, 
                            marker='v', color='red', panel=0)
        )
    
    # Tạo style và plot
    style = mpf.make_mpf_style(
        base_mpf_style='charles',
        marketcolors=mpf.make_marketcolors(
            up='green', down='red',
            edge='inherit',
            wick='inherit',
            volume='in'
        )
    )
    
    # Tạo title với kết quả
    title = (f"Backtest: {strategy.name}\n"
             f"P&L: ${result.total_pnl:,.2f} ({result.total_pnl_percent:+.2f}%) | "
             f"Trades: {result.total_trades} | Win Rate: {result.win_rate:.1f}%")
    
    # Plot
    fig, axes = mpf.plot(
        df,
        type='candle',
        style=style,
        title=title,
        volume=True,
        addplot=apds if apds else None,
        figsize=(16, 12),
        panel_ratios=(3, 1, 2),
        returnfig=True,
        warn_too_much_data=len(df) + 1
    )
    
    # Lưu file
    fig.savefig(save_path, dpi=150, bbox_inches='tight')
    print(f"✅ Chart saved to: {save_path}")
    
    return fig


def create_equity_curve_chart(
    result: BacktestResult,
    candles: List[Candle],
    save_path: str = "equity_curve.png"
):
    """Tạo biểu đồ equity curve"""
    import matplotlib.pyplot as plt
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8))
    
    # Equity curve
    timestamps = [c.datetime for c in candles[:len(result.equity_curve)]]
    ax1.plot(timestamps, result.equity_curve, linewidth=2, color='blue', label='Equity')
    ax1.axhline(y=result.initial_capital, color='gray', linestyle='--', label='Initial Capital')
    ax1.fill_between(timestamps, result.initial_capital, result.equity_curve, 
                      where=np.array(result.equity_curve) >= result.initial_capital,
                      alpha=0.3, color='green', label='Profit')
    ax1.fill_between(timestamps, result.initial_capital, result.equity_curve,
                      where=np.array(result.equity_curve) < result.initial_capital,
                      alpha=0.3, color='red', label='Loss')
    ax1.set_title(f'Equity Curve - Final: ${result.final_capital:,.2f} ({result.total_pnl_percent:+.2f}%)', 
                  fontsize=14, fontweight='bold')
    ax1.set_ylabel('Capital ($)', fontsize=12)
    ax1.grid(True, alpha=0.3)
    ax1.legend()
    
    # Drawdown
    peak = np.maximum.accumulate(result.equity_curve)
    drawdown = peak - result.equity_curve
    drawdown_pct = (drawdown / peak) * 100
    
    ax2.fill_between(timestamps, 0, drawdown_pct, color='red', alpha=0.3)
    ax2.plot(timestamps, drawdown_pct, color='darkred', linewidth=1)
    ax2.set_title(f'Drawdown - Max: {result.max_drawdown_percent:.2f}%', fontsize=12)
    ax2.set_ylabel('Drawdown (%)', fontsize=12)
    ax2.set_xlabel('Time', fontsize=12)
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    print(f"✅ Equity curve saved to: {save_path}")
    plt.close()


def generate_sample_data(
    symbol: str = "BTCUSDT",
    days: int = 90,
    interval: str = "1h"
) -> List[Candle]:
    """
    Tạo dữ liệu mẫu hoặc tải từ Binance
    
    Args:
        symbol: Cặp giao dịch
        days: Số ngày lịch sử
        interval: Timeframe (1m, 5m, 15m, 1h, 4h, 1d)
    
    Returns:
        List[Candle]
    """
    print(f"📥 Loading historical data for {symbol} ({days} days, {interval})...")
    
    try:
        # Thử tải từ Binance
        import requests
        
        end_time = int(datetime.now().timestamp() * 1000)
        start_time = end_time - (days * 24 * 60 * 60 * 1000)
        
        url = "https://api.binance.com/api/v3/klines"
        params = {
            'symbol': symbol,
            'interval': interval,
            'startTime': start_time,
            'endTime': end_time,
            'limit': 1000
        }
        
        candles = []
        current_start = start_time
        
        while current_start < end_time:
            params['startTime'] = current_start
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code != 200:
                print(f"⚠️ Failed to fetch data: {response.status_code}")
                break
            
            data = response.json()
            
            if not data:
                break
            
            for kline in data:
                candle = Candle(
                    timestamp=kline[0],
                    open=float(kline[1]),
                    high=float(kline[2]),
                    low=float(kline[3]),
                    close=float(kline[4]),
                    volume=float(kline[5]),
                    quote_volume=float(kline[7]),
                    number_of_trades=kline[8]
                )
                candles.append(candle)
            
            # Cập nhật start time cho request tiếp theo
            current_start = data[-1][0] + 1
            
            # Giới hạn số request
            if len(candles) >= days * 24:
                break
        
        print(f"✅ Loaded {len(candles)} candles from Binance")
        return candles
    
    except Exception as e:
        print(f"⚠️ Error loading from Binance: {e}")
        print("📊 Generating synthetic data instead...")
        
        # Tạo dữ liệu mẫu
        candles = []
        base_price = 50000.0
        current_time = datetime.now() - timedelta(days=days)
        
        # Interval mapping
        interval_minutes = {
            '1m': 1, '5m': 5, '15m': 15, '30m': 30,
            '1h': 60, '4h': 240, '1d': 1440
        }
        minutes = interval_minutes.get(interval, 60)
        
        for i in range(days * 24 * 60 // minutes):
            # Random walk với trend
            trend = np.sin(i / 100) * 0.001
            volatility = np.random.randn() * 0.02
            
            price_change = base_price * (trend + volatility)
            new_price = base_price + price_change
            
            # Tạo OHLC
            high = new_price * (1 + abs(np.random.randn()) * 0.01)
            low = new_price * (1 - abs(np.random.randn()) * 0.01)
            open_price = base_price
            close_price = new_price
            
            candle = Candle(
                timestamp=int(current_time.timestamp() * 1000),
                open=open_price,
                high=high,
                low=low,
                close=close_price,
                volume=np.random.uniform(100, 1000)
            )
            candles.append(candle)
            
            base_price = new_price
            current_time += timedelta(minutes=minutes)
        
        print(f"✅ Generated {len(candles)} synthetic candles")
        return candles


def main():
    """Main function để chạy backtest"""
    print("\n" + "="*70)
    print("🚀 MACD + BOLLINGER BANDS BACKTEST SYSTEM")
    print("="*70)
    
    # Cấu hình
    SYMBOL = "BTCUSDT"
    DAYS = 90
    INTERVAL = "1h"
    INITIAL_CAPITAL = 10000.0
    
    # Tải dữ liệu
    candles = generate_sample_data(SYMBOL, DAYS, INTERVAL)
    
    if not candles or len(candles) < 100:
        print("❌ Không đủ dữ liệu để backtest")
        return
    
    # Tạo strategy (có thể thử các strategy khác nhau)
    print("\n📋 Strategy Configuration:")
    strategy = MACDBBStrategy(
        macd_fast=12,
        macd_slow=26,
        macd_signal=9,
        bb_period=20,
        bb_std_dev=2.0,
        min_confidence=0.6,
        require_crossover=False,
        use_divergence=True,
        risk_reward_ratio=2.0
    )
    
    strategy_info = strategy.get_strategy_info()
    print(f"  Strategy: {strategy_info['name']} v{strategy_info['version']}")
    print(f"  MACD: ({strategy_info['indicators']['macd']['fast']}, "
          f"{strategy_info['indicators']['macd']['slow']}, "
          f"{strategy_info['indicators']['macd']['signal']})")
    print(f"  BB: (period={strategy_info['indicators']['bollinger_bands']['period']}, "
          f"std={strategy_info['indicators']['bollinger_bands']['std_dev']})")
    print(f"  Min Confidence: {strategy_info['parameters']['min_confidence']}")
    
    # Chạy backtest
    print("\n" + "-"*70)
    engine = BacktestEngine(
        strategy=strategy,
        initial_capital=INITIAL_CAPITAL,
        position_size_percent=0.95,
        commission=0.001,
        slippage=0.0005
    )
    
    result = engine.run(candles)
    
    # In kết quả
    result.print_summary()
    
    # Tạo biểu đồ
    print("\n" + "-"*70)
    create_backtest_chart(
        candles=candles,
        strategy=strategy,
        trades=result.trades,
        result=result,
        save_path="backtest_chart.png"
    )
    
    create_equity_curve_chart(
        result=result,
        candles=candles,
        save_path="equity_curve.png"
    )
    
    print("\n" + "="*70)
    print("✅ BACKTEST COMPLETED SUCCESSFULLY!")
    print("="*70)


if __name__ == "__main__":
    main()

