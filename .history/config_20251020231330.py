STRATEGY_CONFIG = {
    'min_profit_target': 0.015,       # 1.5%
    'max_trades_per_day': 30,        
    'min_hold_time': 3600,           # 1시간
}

RISK_CONFIG = {
    'max_position_size': 0.20,       # 20%
    'stop_loss': 0.010,              # 1.0%
    'daily_loss_limit': 0.015,        
    'max_positions': 3,              
}

EXIT_PRIORITY = {
    'stop_loss': {
        'priority': 1,
        'ignore_hold_time': True
    },
    'trailing_stop': {
        'priority': 2,
        'ignore_hold_time': False
    },
    'take_profit': {
        'priority': 3,
        'ignore_hold_time': False
    }
}

ADVANCED_CONFIG = {
    'entry_score_threshold': 4.0,    # ✅ 5.0 → 4.0 (추가 완화)
    'min_score_for_small_position': 999,
    'aggressive_mode': False,        
    'use_consecutive_loss_check': True,
    'max_consecutive_losses': 2,
}

DYNAMIC_COIN_CONFIG = {
    'enabled': True,
    'max_dynamic_coins': 2,
    'refresh_interval': 3600 * 6,
    'min_score': 5,
    'max_allocation': 0.15,
}

# ==========================================
# ✅ 멀티 타임프레임 분석 설정
# ==========================================
MTF_CONFIG = {
    'enabled': True,
    
    'timeframes': {
        '1h': {
            'interval': 'minute60',
            'weight': 0.3,
            'count': 100
        },
        '4h': {
            'interval': 'minute240',
            'weight': 0.4,
            'count': 100
        },
        '1d': {
            'interval': 'day',
            'weight': 0.3,
            'count': 50
        }
    },
    
    'min_score': 5.5,           # ✅ 6.5 → 5.5 (완화)
    'min_consensus': 0.65,      # ✅ 0.70 → 0.65 (완화)
    'strong_signal_threshold': {
        'score': 8.0,
        'consensus': 0.85
    },
    
    'allowed_trends': [
        'strong_uptrend',
        'uptrend',
    ],
    
    'cache_duration': 300,
}

# ==========================================
# 🤖 머신러닝 예측 설정
# ==========================================
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
        'min_buy_probability': 0.65,    # ✅ 0.70 → 0.65 (완화)
        'min_confidence': 0.60,         # ✅ 0.65 → 0.60 (완화)
        'strong_signal_probability': 0.80,
    },
    
    'performance': {
        'min_accuracy': 0.55,
        'retrain_threshold': 0.50,
        'evaluation_days': 7,
    },
    
    'features': {
        'use_price_features': True,
        'use_technical_indicators': True,
        'use_volume_features': True,
        'use_volatility_features': True,
        'use_time_features': True,
        'use_candle_patterns': True,
    },
    
    'rf_params': {
        'n_estimators': 100,
        'max_depth': 10,
        'min_samples_split': 20,
        'min_samples_leaf': 10,
        'random_state': 42,
    },
    
    'gb_params': {
        'n_estimators': 100,
        'max_depth': 5,
        'learning_rate': 0.1,
        'random_state': 42,
    }
}

# ==========================================
# 🎯 신호 통합 설정
# ==========================================
SIGNAL_INTEGRATION_CONFIG = {
    'enabled': True,
    
    'weights': {
        'technical': 0.30,   # 기술적 분석
        'mtf': 0.40,         # 멀티 타임프레임
        'ml': 0.30           # 머신러닝
    },
    
    'entry_mode': 'weighted',
    
    'mode_settings': {
        'weighted': {
            'min_score': 4.0,           # ✅ 5.0 → 4.0 (추가 완화)
            'conservative_score': 6.5,
            'aggressive_score': 5.0,
        },
        'consensus': {
            'min_signals': 2,
            'min_individual_score': 0.6,
        },
        'any': {
            'min_signal_score': 0.7,
        },
        'all': {
            'min_signal_score': 0.6,
        }
    },
    
    # ✅ 시장 상황별 조정 추가 완화
    'market_adjustment': {
        'bullish': -1.5,    # ✅ -1.0 → -1.5 (상승장에서 2.5점이면 진입)
        'neutral': -0.5,    # ✅ 0.0 → -0.5 (중립장에서 3.5점이면 진입)
        'bearish': +1.5,    # ✅ +2.0 → +1.5 (약세장에서 5.5점 필요)
    },
    
    'ignore_signals': {
        'on_consecutive_losses': 2,
        'on_daily_loss_exceed': 0.015,
        'ignore_weak_signals': True,
    }
}

# ==========================================
# 📊 대시보드 설정
# ==========================================
DASHBOARD_CONFIG = {
    'enabled': True,
    
    'refresh_interval': 10,
    'api_call_interval': 30,
    
    'display': {
        'max_watchlist_coins': 8,
        'max_position_display': 5,
        'show_mtf_analysis': True,
        'show_ml_prediction': True,
        'show_24h_stats': True,
        'show_7d_stats': True,
        'show_30d_stats': True,
    },
    
    'alerts': {
        'enabled': False,
        'mtf_strong_signal': 8.0,
        'ml_high_probability': 0.75,
        'price_change_alert': 0.05,
    },
    
    'performance': {
        'cache_prices': True,
        'cache_duration': 30,
        'max_api_calls_per_minute': 500,
    }
}

# ==========================================
# 🎛️ 전략 프리셋
# ==========================================
STRATEGY_PRESETS = {
    'conservative': {
        'entry_score_threshold': 7.5,
        'mtf_min_score': 7.0,
        'mtf_min_consensus': 0.80,
        'ml_min_probability': 0.75,
        'signal_weights': {'technical': 0.25, 'mtf': 0.45, 'ml': 0.30},
        'max_positions': 2,
        'max_position_size': 0.15,
        'stop_loss': 0.008,
    },
    
    'balanced': {
        'entry_score_threshold': 4.0,   # ✅ 5.0 → 4.0 (추가 완화)
        'mtf_min_score': 5.5,
        'mtf_min_consensus': 0.65,
        'ml_min_probability': 0.65,
        'signal_weights': {'technical': 0.30, 'mtf': 0.40, 'ml': 0.30},
        'max_positions': 3,
        'max_position_size': 0.20,
        'stop_loss': 0.010,
    },
    
    'aggressive': {
        'entry_score_threshold': 6.0,
        'mtf_min_score': 6.0,
        'mtf_min_consensus': 0.65,
        'ml_min_probability': 0.65,
        'signal_weights': {'technical': 0.30, 'mtf': 0.40, 'ml': 0.30},
        'max_positions': 4,
        'max_position_size': 0.25,
        'stop_loss': 0.012,
    }
}

# ==========================================
# 📈 추매(Pyramiding) 설정
# ==========================================
PYRAMIDING_CONFIG = {
    'enabled': False,  # ✅ True → False (안정될 때까지)
    
    'max_pyramids': 3,
    'min_score_increase': 1.0,
    'min_profit_for_pyramid': 0.02,
    
    'allowed_markets': ['bullish'],
    'min_market_strength': 0.7,
    
    'pyramid_size_ratio': 0.5,
    'max_total_position': 0.30,
    
    'stop_on_reversal': True,
    'require_all_signals': True,
    'min_volume_increase': 1.3,
    
    'use_breakeven_stop': True,
    'tighten_stop_loss': 0.008,
}

# 현재 사용 중인 프리셋
ACTIVE_PRESET = 'balanced'  # ✅ 완화된 balanced 설정

# ==========================================
# 🔧 디버그 설정
# ==========================================
DEBUG_CONFIG = {
    'verbose_logging': False,
    'log_mtf_details': False,
    'log_ml_predictions': False,
    'log_signal_scoring': True,
    'save_predictions': False,
    'performance_monitoring': True,
}

# 기본 안정 코인
STABLE_PAIRS = ['BTC', 'ETH', 'SOL', 'XRP', 'DOGE', 'ADA']

# 거래 대상
TRADING_PAIRS = STABLE_PAIRS


# ==========================================
# 🚀 프리셋 적용 함수
# ==========================================
def apply_preset(preset_name='balanced'):
    """선택한 프리셋을 현재 설정에 적용"""
    global ADVANCED_CONFIG, MTF_CONFIG, ML_CONFIG, SIGNAL_INTEGRATION_CONFIG
    global RISK_CONFIG
    
    if preset_name not in STRATEGY_PRESETS:
        print(f"⚠️ 알 수 없는 프리셋: {preset_name}. 기본값 사용.")
        return
    
    preset = STRATEGY_PRESETS[preset_name]
    
    # 설정 적용
    ADVANCED_CONFIG['entry_score_threshold'] = preset['entry_score_threshold']
    MTF_CONFIG['min_score'] = preset['mtf_min_score']
    MTF_CONFIG['min_consensus'] = preset['mtf_min_consensus']
    ML_CONFIG['prediction']['min_buy_probability'] = preset['ml_min_probability']
    SIGNAL_INTEGRATION_CONFIG['weights'] = preset['signal_weights']
    RISK_CONFIG['max_positions'] = preset['max_positions']
    RISK_CONFIG['max_position_size'] = preset['max_position_size']
    RISK_CONFIG['stop_loss'] = preset['stop_loss']
    
    print(f"✅ '{preset_name}' 프리셋 적용 완료")   
    

if __name__ != "__main__":  # ✅ import될 때만 실행
    apply_preset(ACTIVE_PRESET)