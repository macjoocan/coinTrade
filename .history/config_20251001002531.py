STRATEGY_CONFIG = {
    'min_profit_target': 0.01,       # 1.5% → 1% (현실적으로)
    'max_trades_per_day': 10,        
    'min_hold_time': 3600,           # 2시간 → 1시간
}

RISK_CONFIG = {
    'max_position_size': 0.25,       # 20% → 25% 
    'stop_loss': 0.012,              # 1.5% → 1.2% (더 타이트)
    'daily_loss_limit': 0.02,        
    'max_positions': 3,              
}

ADVANCED_CONFIG = {
    'entry_score_threshold': 5.5,    # 7 → 5.5 (완화)
    'min_score_for_small_position': 999,
    'aggressive_mode': False,        
    'use_consecutive_loss_check': True,
    'max_consecutive_losses': 3,     # 2 → 3 (여유 추가)
}

# 안정적인 메이저 코인만
TRADING_PAIRS = ['BTC', 'ETH', 'SOL']  # 변동성 큰 코인 제외