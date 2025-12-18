# config.py - 정리 및 충돌 해결 버전

# ==========================================
# ⚙️ 1. 기본 설정 (프리셋이 적용되기 전 기본값)
# ==========================================

# 전략 기본 설정
STRATEGY_CONFIG = {
    'min_profit_target': 0.015,      # 목표 수익률 1.5%
    'max_trades_per_day': 50,        # 일일 최대 거래 횟수
    'min_hold_time': 600,            # 최소 보유 시간 (10분)
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
        'bullish': -0.2,
        'neutral': 0.0,
        'bearish': 0.5,
    },
    
    'ignore_signals': {
        'on_consecutive_losses': 2,
        'on_daily_loss_exceed': 0.015,
        'ignore_weak_signals': True,
    }
}

# ==========================================
# 💧 3. 물타기 (Averaging Down) 설정
# ==========================================
AVERAGING_DOWN_CONFIG = {
    'enabled': True,
    'trigger_loss_rate': -0.008,     # -0.8% 손실 시 발동
    'max_averaging_count': 3,        # 최대 3회
    'averaging_size_ratio': 1.0,     # 1배수 물타기
    'max_total_loss': -0.05,         # -5% 초과 하락 시 물타기 중단
    'min_balance_ratio': 0.3,
    'only_stable_coins': False,
    'disable_on_bear_market': True,  # 하락장에서는 물타기 금지
    'log_details': True,
}

# ==========================================
# 🤖 4. 자동 프리셋 전환 설정
# ==========================================
ADAPTIVE_PRESET_CONFIG = {
    'enabled': True,
    'check_interval': 600,
    'min_switch_interval': 7200,
    
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
    
    # 강제 전환 (방어 모드)
    'force_conservative_on': {
        'consecutive_losses': 2,
        'daily_loss_rate': 0.03,
        'high_volatility': 0.05,
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
    # 🛡️ 보수적 전략 (방어 중심)
    'conservative': {
        'entry_score_threshold': 6.5,       # 진입 장벽 높음
        'mtf_min_score': 7.0,
        'mtf_min_consensus': 0.80,
        'ml_min_probability': 0.75,
        
        'signal_weights': {
            'technical': 0.25,
            'mtf': 0.45,
            'ml': 0.30
        },
        
        'max_positions': 2,
        'max_position_size': 0.15,
        'stop_loss': 0.008,                 # 짧은 손절 (0.8%)
    },
    
    # ⚖️ 균형 전략 (일반 상황)
    'balanced': {
        'entry_score_threshold': 4.5,       # 적절한 진입 장벽
        'mtf_min_score': 6.0,
        'mtf_min_consensus': 0.70,
        'ml_min_probability': 0.25,
        
        'signal_weights': {
            'technical': 0.40,
            'mtf': 0.50,
            'ml': 0.10
        },
        
        'max_positions': 5,
        'max_position_size': 0.20,
        'stop_loss': 0.010,                 # 표준 손절 (1.0%)
    },
    
    # ⚔️ 공격적 전략 (상승장용)
    'aggressive': {
        'entry_score_threshold': 3.8,       # 낮은 진입 장벽
        'mtf_min_score': 5.5,
        'mtf_min_consensus': 0.65,
        'ml_min_probability': 0.25,
        
        'signal_weights': {
            'technical': 0.80,
            'mtf': 0.20,
            'ml': 0
        },
        
        'max_positions': 4,
        'max_position_size': 0.5,
        'stop_loss': 0.012,
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
ACTIVE_PRESET = 'balanced'

STABLE_PAIRS = ['BTC', 'ETH', 'SOL', 'XRP', 'DOGE', 'ADA']
TRADING_PAIRS = STABLE_PAIRS

DASHBOARD_CONFIG = {
    'enabled': True,
    'refresh_interval': 10,
    'api_call_interval': 30,
    'display': {'max_watchlist_coins': 8, 'max_position_display': 5},
    'performance': {'cache_prices': True, 'cache_duration': 30}
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

# 파일 로드 시 자동으로 프리셋 적용
if __name__ != "__main__":
    apply_preset(ACTIVE_PRESET)