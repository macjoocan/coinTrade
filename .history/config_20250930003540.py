STRATEGY_CONFIG = {
    'min_profit_target': 0.012,      # 1.2% 목표
    'max_trades_per_day': 15,        
    'min_hold_time': 7200,           # 1.5시간 최소 보유
}

RISK_CONFIG = {
    'max_position_size': 0.2,        # 10%로 축소
    'stop_loss': 0.015,               # 1% 손절 (타이트)
    'daily_loss_limit': 0.02,        # 2% 일일 최대 손실
    'max_positions': 2,              # 최대 2개 포지션
}

ADVANCED_CONFIG = {
    # 'entry_score_threshold': 6,      # 6점 이상만 진입
    'entry_score_threshold':5.5,      # 5.5 한번 테스트
    'min_score_for_small_position': 999,  # 사실상 비활성화
    'aggressive_mode': False,        
    'use_consecutive_loss_check': True,  # 연속 손실 체크 활성화
    'max_consecutive_losses': 2,     # 2회 연속 손실 시 중단
}

# 안정적인 코인만
TRADING_PAIRS = ['BTC', 'ETH', 'SOL', 'AVAX', 'ADA', 'XLM']