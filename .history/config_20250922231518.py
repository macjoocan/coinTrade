# config.py - 쉽게 조정 가능한 파라미터

STRATEGY_CONFIG = {
    'min_profit_target': 0.015,      # 최소 목표 수익률 1.5%
    'max_trades_per_day': 10,        # 일일 최대 거래 수
    'min_hold_time': 3600,           # 최소 보유 시간 (초)
}

RISK_CONFIG = {
    'max_position_size': 0.3,        # 종목당 최대 포지션 30%
    'stop_loss': 0.02,                # 손절선 2%
    'daily_loss_limit': 0.05,        # 일일 최대 손실 5%
    'max_positions': 2,               # 최대 동시 포지션 수
}

TRADING_PAIRS = ['BTC', 'ETH', 'SOL', 'XRP', 'DOGE']  # 거래 대상