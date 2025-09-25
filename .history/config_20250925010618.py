# config.py - 개선된 파라미터

STRATEGY_CONFIG = {
    'min_profit_target': 0.01,       # 1.5% → 1% (더 현실적)
    'max_trades_per_day': 10,        
    'min_hold_time': 1800,           # 1시간 → 30분 (더 유연하게)
}

RISK_CONFIG = {
    'max_position_size': 0.2,        # 종목당 최대 포지션 20% (보수적)
    'stop_loss': 0.02,                # 손절선 2%
    'daily_loss_limit': 0.05,        # 일일 최대 손실 5%
    'max_positions': 2,               # 최대 동시 포지션 수
}

# 거래 대상 (변동성과 유동성 고려)
TRADING_PAIRS = ['ETH', 'SOL', 'XRP']  # BTC는 변동성이 낮아 제외, DOGE는 불안정

# 추가 설정
ADVANCED_CONFIG = {
    'use_trailing_stop': True,       # 추적 손절 사용
    'trailing_stop_trigger': 0.02,   # 2% 수익 후 추적 손절 활성화
    'trailing_stop_distance': 0.01,  # 최고가 대비 1% 하락 시 매도
    'cooldown_period': 1800,         # 종목별 재거래 쿨다운 (30분)
    'min_volume_ratio': 1.2,         # 최소 거래량 비율
    'entry_score_threshold': 7,      # 진입 최소 점수 (12점 만점)
}