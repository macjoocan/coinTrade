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

EXIT_PRIORITY = {
    'stop_loss': {
        'priority': 1,  # 최고 우선순위
        'ignore_hold_time': True  # 보유시간 무시
    },
    'trailing_stop': {
        'priority': 2,
        'ignore_hold_time': False  # 수익 중이니 시간 체크
    },
    'take_profit': {
        'priority': 3,
        'ignore_hold_time': False
    }
}

ADVANCED_CONFIG = {
    'entry_score_threshold': 5.5,    # 7 → 5.5 (완화)
    'min_score_for_small_position': 999,
    'aggressive_mode': False,        
    'use_consecutive_loss_check': True,
    'max_consecutive_losses': 3,     # 2 → 3 (여유 추가)
}

DYNAMIC_COIN_CONFIG = {
    'enabled': True,  # 동적 선택 활성화
    'max_dynamic_coins': 2,  # 최대 2개 추가
    'refresh_interval': 3600 * 6,  # 6시간마다 갱신
    'min_score': 6,  # 최소 모멘텀 점수
    'max_allocation': 0.15,  # 동적 코인당 최대 15%
}

# 기본 안정 코인
STABLE_PAIRS = ['BTC', 'ETH', 'SOL']

# 안정적인 메이저 코인만
TRADING_PAIRS = STABLE_PAIRS