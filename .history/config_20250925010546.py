# config.py - 더 적극적인 설정

STRATEGY_CONFIG = {
    'min_profit_target': 0.01,       # 1.5% → 1% (더 현실적)
    'max_trades_per_day': 10,        
    'min_hold_time': 1800,           # 1시간 → 30분 (더 유연하게)
}

RISK_CONFIG = {
    'max_position_size': 0.15,       # 20% → 15% (리스크는 유지)
    'stop_loss': 0.015,              # 2% → 1.5% (더 타이트하게)
    'daily_loss_limit': 0.03,        # 5% → 3% (더 보수적으로)
    'max_positions': 3,              # 2 → 3 (기회 증가)
}

# 거래 대상 확대
TRADING_PAIRS = ['BTC', 'ETH', 'SOL', 'XRP', 'DOGE']  # 5개로 확대

ADVANCED_CONFIG = {
    'entry_score_threshold': 5,      # 7 → 5 (더 낮춤)
    'min_score_for_small_position': 4,  # 소액 포지션용 최소 점수
    'aggressive_mode': True,         # 적극적 모드
}