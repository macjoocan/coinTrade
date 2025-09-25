# config.py

STRATEGY_CONFIG = {
    'min_profit_target': 0.012,      # 1.2% (살짝 높임)
    'max_trades_per_day': 15,        # 유지
    'min_hold_time': 5400,           # 30분 → 1.5시간 (더 길게)
}

RISK_CONFIG = {
    'max_position_size': 0.1,        # 15% → 10% (더 작게)
    'stop_loss': 0.012,              # 1.5% → 1.2% (더 타이트)
    'daily_loss_limit': 0.02,        # 3% → 2% (더 보수적)
    'max_positions': 2,              # 4 → 2 (집중)
}

ADVANCED_CONFIG = {
    'entry_score_threshold': 6,      # 5 → 6 (기준 높임)
    'min_score_for_small_position': 7,  # 4 → 7 (소액도 엄격)
    'aggressive_mode': False,        # 비활성화
}

# 변동성 높은 DOGE 제외
TRADING_PAIRS = ['BTC', 'ETH', 'SOL']

# ADVANCED_CONFIG = {
#     'use_trailing_stop': True,       # 추적 손절 사용
#     'trailing_stop_trigger': 0.02,   # 2% 수익 후 추적 손절 활성화
#     'trailing_stop_distance': 0.01,  # 최고가 대비 1% 하락 시 매도
#     'cooldown_period': 1800,         # 종목별 재거래 쿨다운 (30분)
#     'min_volume_ratio': 1.2,         # 최소 거래량 비율
#     'entry_score_threshold': 5,      # 진입 최소 점수 (12점 만점)
# }