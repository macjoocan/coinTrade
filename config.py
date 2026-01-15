# config.py - 정리 및 충돌 해결 버전

# ==========================================
# ⚙️ 1. 기본 설정 (프리셋이 적용되기 전 기본값)
# ==========================================

# 업비트 API 관련 설정
UPBIT_CONFIG = {
    'min_order_value': 5500,         # 최소 주문 금액 (KRW)
    'min_order_amount': 5000,        # 최소 주문 금액 (수수료 고려)
    'fee_rate': 0.0005,              # 거래 수수료 (0.05%)
    'api_rate_limit': 10,            # 초당 API 호출 제한
}

# 전략 기본 설정
STRATEGY_CONFIG = {
    'min_profit_target': 0.025,     # 목표 수익률 2.5% (기존 2% → 개선)
    'max_trades_per_day': 50,        # 일일 최대 거래 횟수
    'min_hold_time': 600,            # 최소 보유 시간 (초)
    'status_print_interval': 300,    # 상태 출력 간격 (5분)
    'position_save_interval': 60,    # 포지션 저장 간격 (1분)
    'trade_cooldown_minutes': 60,
}

# ==========================================
# 🔺 추매(Pyramiding/불타기) 설정 (누락된 부분 추가)
# ==========================================
PYRAMIDING_CONFIG = {
    'enabled': False,            # 기본적으로는 꺼둠 (안전 제일)
    'max_pyramids': 3,           # 최대 추매 횟수
    'min_score_increase': 1.0,   # 점수가 이만큼 더 올라야 추매
    'min_profit_for_pyramid': 0.02, # 수익률 2% 이상일 때만
    
    'allowed_markets': ['bullish'], # 상승장에서만 허용
    'min_market_strength': 0.7,
    
    'pyramid_size_ratio': 0.5,   # 최초 진입 물량의 50%만 추매
    'max_total_position': 0.30,  # 최대 비중 제한
    
    'stop_on_reversal': True,
    'require_all_signals': True,
    'min_volume_increase': 1.3,  # 거래량 증가 확인
    
    'use_breakeven_stop': True,  # 추매 시 손절라인을 본전 위로 올림
    'tighten_stop_loss': 0.008,
}

# 리스크 관리 기본 설정 (주의: 프리셋에 의해 덮어쓰여질 수 있음)
RISK_CONFIG = {
    'max_position_size': 0.20,       # 최대 포지션 비중 20%
    'stop_loss': 0.015,              # 기본 손절 -1.5%
    'daily_loss_limit': 0.03,        # 일일 손실 한도 -3%
    'max_positions': 3,              # 최대 보유 종목 수
}

# 고급 설정
ADVANCED_CONFIG = {
    'entry_score_threshold': 6.0,    # 진입 점수 기준 (프리셋에 의해 변경됨)
    'min_score_for_small_position': 999,
    'aggressive_mode': False,        
    'use_consecutive_loss_check': True,
    'max_consecutive_losses': 3,
}

# 동적 코인 스캔 설정
DYNAMIC_COIN_CONFIG = {
    'enabled': True,
    'max_dynamic_coins': 3,
    'refresh_interval': 900,        # 2시간
    'min_score': 5,
    'max_allocation': 0.15,
}

# ==========================================
# 📊 2. 분석 모듈 설정
# ==========================================

# 멀티 타임프레임 분석 설정
MTF_CONFIG = {
    'enabled': True,
    
    'timeframes': {
        '1h': {'interval': 'minute60', 'weight': 0.3, 'count': 100},
        '4h': {'interval': 'minute240', 'weight': 0.4, 'count': 100},
        '1d': {'interval': 'day', 'weight': 0.3, 'count': 50}
    },
    
    'min_score': 6.0,                # 프리셋에 의해 변경됨
    'min_consensus': 0.70,           # 프리셋에 의해 변경됨
    'strong_signal_threshold': {'score': 8.0, 'consensus': 0.85},
    'allowed_trends': ['strong_uptrend', 'uptrend'],
    'cache_duration': 300,
}

# 머신러닝 설정
ML_CONFIG = {
    'enabled': True,
    'model_type': 'random_forest',
    'model_file': 'ml_model_random_forest.pkl',
    'scaler_file': 'ml_scaler.pkl',
    
    'training': {
        'lookback_hours': 168,
        'prediction_horizon': 6,
        'min_profit_threshold': 0.015,
        'auto_retrain_days': 7,
        'min_samples': 200,
    },
    
    'prediction': {
        'min_buy_probability': 0.30, # 프리셋에 의해 변경됨
        'min_confidence': 0.60,
        'strong_signal_probability': 0.80,
    },
    
    'performance': {
        'min_accuracy': 0.55,
        'retrain_threshold': 0.50,
        'evaluation_days': 7,
    },
}

# 신호 통합 설정 (중복 제거 및 통합됨)
SIGNAL_INTEGRATION_CONFIG = {
    'enabled': True,
    
    # 기본 가중치 (프리셋이 없을 때 사용)
    'weights': {
        'technical': 0.40,
        'mtf': 0.40,
        'ml': 0.20
    },
    
    'entry_mode': 'weighted',
    
    'mode_settings': {
        'weighted': {
            'min_score': 3.0,
            'conservative_score': 6.5,
            'aggressive_score': 2.5,
        },
        'consensus': {'min_signals': 2, 'min_individual_score': 0.6},
        'any': {'min_signal_score': 0.7},
        'all': {'min_signal_score': 0.6}
    },
    
    'market_adjustment': {
        'bullish': 0.0,
        'neutral': 0.2,
        'bearish': 1.5,
    },
    
    'ignore_signals': {
        'on_consecutive_losses': 1,
        'on_daily_loss_exceed': 0.0,
        'ignore_weak_signals': True,
    }
}

# ==========================================
# 💧 3. 물타기 (Averaging Down) 설정
# ==========================================
AVERAGING_DOWN_CONFIG = {
    'enabled': False,              # 🚨 손익비 개선을 위해 물타기 비활성화 (손실 확대 방지)
    'trigger_loss_rate': -0.004,     # -0.4% 손실 시 발동 (더 빠르게)
    'max_averaging_count': 1,        # 최대 1회로 제한 (기존 3회 → 개선)
    'averaging_size_ratio': 0.5,     # 0.5배수 물타기 (기존 1.0배 → 개선)
    'max_total_loss': -0.03,         # -3% 초과 하락 시 물타기 중단 (기존 -5% → 강화)
    'min_balance_ratio': 0.3,
    'only_stable_coins': True,       # 안정 코인만 물타기 허용 (리스크 축소)
    'disable_on_bear_market': True,  # 하락장에서는 물타기 금지
    'log_details': True,
}

# ==========================================
# 🤖 4. 자동 프리셋 전환 설정
# ==========================================
ADAPTIVE_PRESET_CONFIG = {
    'enabled': True,
    'check_interval': 600,
    'min_switch_interval': 1800,
    
    'thresholds': {
        'high_volatility': 0.04,
        'medium_volatility': 0.02,
        'low_volatility': 0.02,
        'high_win_rate': 0.60,
        'medium_win_rate': 0.45,
        'low_win_rate': 0.45,
        'consecutive_losses': 2,
        'consecutive_wins': 4,
    },
    
    'min_confidence': 0.6,
    'min_trades_for_analysis': 10,
    
    # 강제 전환 (방어 모드) - 🚨 더 빠르게 방어 모드 진입
    'force_conservative_on': {
        'consecutive_losses': 1,            # 🚨 2 → 1 (1회 손실만 방어)
        'daily_loss_rate': 0.015,           # 🚨 0.03 → 0.015 (-1.5%만 방어)
        'high_volatility': 0.04,            # 🚨 0.05 → 0.04 (더 빨리 방어)
    },
    
    'force_balanced_on': {
        'small_loss_streak': 2,
    },
    
    'log_analysis': True,
    'notify_on_switch': True,
}

# ==========================================
# 🎛️ 5. 전략 프리셋 (여기가 실제 설정을 지배합니다!)
# ==========================================
STRATEGY_PRESETS = {
    # 🛡️ 보수적 전략 (방어 중심) - 🎯 현실적 조정: 실제 거래 가능하도록
    'conservative': {
        'entry_score_threshold': 6.0,       # 🎯 현실적: 7.5 → 6.0 (너무 높으면 거래 없음)
        'mtf_min_score': 6.5,               # 🎯 현실적: 8.0 → 6.5
        'mtf_min_consensus': 0.75,          # 🎯 현실적: 0.85 → 0.75
        'ml_min_probability': 0.70,         # 🎯 현실적: 0.80 → 0.70

        'signal_weights': {
            'technical': 0.25,
            'mtf': 0.45,
            'ml': 0.30
        },

        'max_positions': 1,                 # 🚨 한 종목만 집중
        'max_position_size': 0.15,
        'stop_loss': 0.015,                 # 🚨 손절 완화: 1.5% (정상 변동 허용)
    },
    
    # ⚖️ 균형 전략 (일반 상황) - 🎯 현실적 조정
    'balanced': {
        'entry_score_threshold': 5.5,       # 🎯 현실적: 6.5 → 5.5
        'mtf_min_score': 6.0,               # 🎯 현실적: 7.0 → 6.0
        'mtf_min_consensus': 0.70,          # 🎯 현실적: 0.75 → 0.70
        'ml_min_probability': 0.55,         # 🎯 현실적: 0.60 → 0.55

        'signal_weights': {
            'technical': 0.40,
            'mtf': 0.50,
            'ml': 0.10
        },

        'max_positions': 2,                 # 🚨 집중 투자
        'max_position_size': 0.20,
        'stop_loss': 0.015,                 # 🚨 손절 완화: 1.5%
    },
    
    # ⚔️ 공격적 전략 (상승장용) - 🎯 현실적 조정
    'aggressive': {
        'entry_score_threshold': 5.0,       # 🎯 현실적: 6.0 → 5.0
        'mtf_min_score': 5.5,               # 🎯 현실적: 6.5 → 5.5
        'mtf_min_consensus': 0.65,          # 🎯 현실적: 0.70 → 0.65
        'ml_min_probability': 0.45,         # 🎯 현실적: 0.50 → 0.45

        'signal_weights': {
            'technical': 0.80,
            'mtf': 0.20,
            'ml': 0
        },

        'max_positions': 2,                 # 🚨 집중 투자
        'max_position_size': 0.25,          # 🚨 리스크 축소
        'stop_loss': 0.020,                 # 🚨 손절 완화: 2.0%
    },
    
    # 🧠 ML 중심 전략
    'ml_focused': {
        'entry_score_threshold': 6.0,
        'mtf_min_score': 6.5,
        'mtf_min_consensus': 0.70,
        'ml_min_probability': 0.70,
        
        'signal_weights': {
            'technical': 0.25,
            'mtf': 0.35,
            'ml': 0.40
        },
        
        'max_positions': 3,
        'max_position_size': 0.20,
        'stop_loss': 0.010,
    }
}

# ==========================================
# ⚙️ 6. 활성 프리셋 및 기타 설정
# ==========================================

# ⚠️ 여기서 설정한 프리셋의 값들이 위의 기본 설정들을 덮어씁니다!
ACTIVE_PRESET = 'conservative'  # 🚨 긴급: 승률 5% → Conservative로 전환

STABLE_PAIRS = ['BTC', 'ETH', 'SOL', 'XRP', 'DOGE', 'ADA']
TRADING_PAIRS = STABLE_PAIRS

DASHBOARD_CONFIG = {
    'enabled': True,
    'refresh_interval': 10,
    'api_call_interval': 30,
    'display': {'max_watchlist_coins': 8, 'max_position_display': 5},
    'performance': {'cache_prices': True, 'cache_duration': 10}
}

DEBUG_CONFIG = {
    'verbose_logging': False,
    'log_mtf_details': False,
    'log_ml_predictions': False,
    'log_signal_scoring': True,
}

# ==========================================
# 🚀 7. 프리셋 적용 로직
# ==========================================
def apply_preset(preset_name='balanced'):
    """선택한 프리셋을 현재 설정에 적용"""
    if preset_name not in STRATEGY_PRESETS:
        print(f"⚠️ 알 수 없는 프리셋: {preset_name}. 기본값 유지.")
        return
    
    preset = STRATEGY_PRESETS[preset_name]
    
    # 1. 전략 설정 덮어쓰기
    ADVANCED_CONFIG['entry_score_threshold'] = preset['entry_score_threshold']
    
    # 2. MTF 설정 덮어쓰기
    MTF_CONFIG['min_score'] = preset['mtf_min_score']
    MTF_CONFIG['min_consensus'] = preset['mtf_min_consensus']
    
    # 3. ML 설정 덮어쓰기
    ML_CONFIG['prediction']['min_buy_probability'] = preset['ml_min_probability']
    
    # 4. 가중치 덮어쓰기
    SIGNAL_INTEGRATION_CONFIG['weights'] = preset['signal_weights']
    
    # 5. 리스크 설정 덮어쓰기
    RISK_CONFIG['max_positions'] = preset['max_positions']
    RISK_CONFIG['max_position_size'] = preset['max_position_size']
    RISK_CONFIG['stop_loss'] = preset['stop_loss']
    
    print(f"✅ '{preset_name}' 프리셋 적용 완료")
    print(f"   진입 점수: {preset['entry_score_threshold']}점 이상")
    print(f"   손절 기준: {preset['stop_loss']:.1%}")
    print(f"   가중치: Tech {preset['signal_weights']['technical']:.0%}, "
          f"MTF {preset['signal_weights']['mtf']:.0%}, "
          f"ML {preset['signal_weights']['ml']:.0%}")

# ==========================================
# 🛡️ 8. 과최적화 방지 설정
# ==========================================

# 파라미터 단순화 모드
SIMPLIFICATION_CONFIG = {
    'enabled': True,  # 과최적화 방지 활성화

    # 핵심 파라미터만 사용 (나머지는 고정)
    'core_parameters': [
        'entry_score_threshold',  # 진입 점수
        'stop_loss',              # 손절
        'max_positions',          # 최대 포지션 수
    ],

    # 적응형 학습 (실전 데이터 기반 자동 조정)
    'adaptive_learning': {
        'enabled': True,
        'min_trades': 30,              # 최소 30회 거래 후 조정 시작
        'learning_rate': 0.1,          # 조정 속도 (보수적)
        'max_adjustment': 0.2,         # 최대 20% 변경까지만
        'evaluation_window': 50,       # 최근 50회 거래 기반
    },

    # 시장 적응형 (시장 상황에 따라 자동 조정)
    'market_adaptive': {
        'enabled': True,
        'bull_market_bonus': 0.1,      # 상승장: 진입 점수 10% 완화
        'bear_market_penalty': 0.3,    # 하락장: 진입 점수 30% 강화
        'volatile_stop_multiplier': 1.5,  # 고변동성: 손절 1.5배
    }
}

# ==========================================
# 🌡️ 9. 슬리피지 및 변동성 설정
# ==========================================

SLIPPAGE_CONFIG = {
    'enabled': True,
    'max_slippage_rate': 0.003,     # 최대 허용 슬리피지 0.3%
    'use_limit_on_high_slippage': True,  # 슬리피지 높으면 지정가 사용
    'slippage_buffer': 0.001,       # 슬리피지 버퍼 0.1%
}

VOLATILITY_CONFIG = {
    'enabled': True,
    'update_interval': 300,         # 5분마다 변동성 업데이트
    'lookback_periods': 24,         # 24시간 기준
    'dynamic_adjustment': True,     # 변동성에 따라 파라미터 자동 조정
    'pause_on_extreme': True,       # 극단 변동성 시 거래 일시 중단
}

# 파일 로드 시 자동으로 프리셋 적용
if __name__ != "__main__":
    apply_preset(ACTIVE_PRESET)