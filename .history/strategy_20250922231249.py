# strategy.py 또는 trading_bot.py 파일에 추가

import time
from datetime import datetime, timedelta
from collections import defaultdict

class ImprovedStrategy:
    def __init__(self):
        self.min_profit_target = 0.015  # 최소 1.5% 목표
        self.max_trades_per_day = 10    # 일일 최대 거래 제한
        self.min_hold_time = 3600        # 최소 1시간 보유 (초)
        
        # 거래 추적용
        self.daily_trades = defaultdict(int)
        self.position_entry_time = {}
        
    def can_trade_today(self):
        """오늘 거래 가능한지 확인"""
        today = datetime.now().strftime('%Y-%m-%d')
        return self.daily_trades[today] < self.max_trades_per_day
    
    def can_exit_position(self, symbol):
        """포지션 청산 가능한지 확인 (최소 보유시간 체크)"""
        if symbol not in self.position_entry_time:
            return True
        
        elapsed_time = time.time() - self.position_entry_time[symbol]
        return elapsed_time >= self.min_hold_time
    
    def record_trade(self, symbol, trade_type):
        """거래 기록"""
        today = datetime.now().strftime('%Y-%m-%d')
        self.daily_trades[today] += 1
        
        if trade_type == 'buy':
            self.position_entry_time[symbol] = time.time()
        elif trade_type == 'sell' and symbol in self.position_entry_time:
            del self.position_entry_time[symbol]