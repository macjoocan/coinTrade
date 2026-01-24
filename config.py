# config.py - 외부 설정 파일 기반 버전
# settings.json에서 설정을 로드하여 사용합니다

import os
import json
import sys

# ==========================================
# 🔧 설정 파일 로드
# ==========================================

def get_base_path():
    """실행 파일 기준 경로 반환"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

BASE_PATH = get_base_path()
SETTINGS_FILE = os.path.join(BASE_PATH, 'settings.json')

def load_settings():
    """settings.json 로드"""
    if not os.path.exists(SETTINGS_FILE):
        print(f"[ERROR] settings.json 파일이 없습니다: {SETTINGS_FILE}")
        print("[INFO] settings.json 파일을 생성하고 API 키를 설정하세요.")
        return None

    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERROR] settings.json 로드 실패: {e}")
        return None

# 설정 로드
_settings = load_settings()

def get_setting(*keys, default=None):
    """중첩 딕셔너리에서 값 가져오기"""
    if _settings is None:
        return default
    value = _settings
    for key in keys:
        if isinstance(value, dict):
            value = value.get(key)
        else:
            return default
        if value is None:
            return default
    return value

# ==========================================
# 🔑 API 키 (settings.json에서 로드)
# ==========================================
API_ACCESS_KEY = get_setting('api', 'access_key', default='')
API_SECRET_KEY = get_setting('api', 'secret_key', default='')

# ==========================================
# 📈 거래 대상 코인 (settings.json에서 로드)
# ==========================================
TRADING_PAIRS = get_setting('trading', 'pairs', default=['BTC', 'ETH', 'XRP', 'SOL', 'DOGE'])
STABLE_PAIRS = get_setting('trading', 'stable_pairs', default=['BTC', 'ETH', 'XRP'])

# ==========================================
# ⚙️ 1. 기본 설정
# ==========================================

UPBIT_CONFIG = {
    'min_order_value': 5500,
    'min_order_amount': 5000,
    'fee_rate': 0.0005,
    'api_rate_limit': 10,
}

# 전략 기본 설정 - settings.json에서 로드
STRATEGY_CONFIG = {
    'min_profit_target': get_setting('strategy', 'min_profit_target', default=0.030),
    'max_trades_per_day': get_setting('strategy', 'max_trades_per_day', default=20),
    'min_hold_time': get_setting('strategy', 'min_hold_time_hours', default=12) * 3600,
    'status_print_interval': get_setting('advanced', 'status_print_interval', default=60),
    'position_save_interval': get_setting('advanced', 'position_save_interval', default=60),
    'trade_cooldown_minutes': get_setting('strategy', 'trade_cooldown_minutes', default=120),
}

# ==========================================
# 🔺 추매(Pyramiding) 설정
# ==========================================
PYRAMIDING_CONFIG = {
    'enabled': False,
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

# ==========================================
# 🎯 시장 연동 익절 조정 설정
# ==========================================
ADAPTIVE_TAKE_PROFIT_CONFIG = {
    'enabled': get_setting('adaptive_take_profit', 'enabled', default=True),
    'base_target': get_setting('strategy', 'min_profit_target', default=0.030),  # 기본 익절 목표 3%
    'market_adjustments': {
        'bullish': get_setting('adaptive_take_profit', 'bullish_target', default=0.035),   # 상승장: 3.5%
        'neutral': get_setting('adaptive_take_profit', 'neutral_target', default=0.025),   # 중립: 2.5%
        'bearish': get_setting('adaptive_take_profit', 'bearish_target', default=0.015),   # 하락장: 1.5%
    },
    'min_profit_floor': get_setting('adaptive_take_profit', 'min_profit_floor', default=0.010),  # 최소 1% 수익 확보
    'log_adjustments': True,  # 조정 시 로그 출력
}

# 리스크 관리 - settings.json에서 로드
RISK_CONFIG = {
    'max_position_size': get_setting('risk', 'max_position_size', default=0.20),
    'stop_loss': get_setting('risk', 'stop_loss', default=0.015),
    'daily_loss_limit': get_setting('risk', 'daily_loss_limit', default=0.03),
    'max_positions': get_setting('risk', 'max_positions', default=1),
}

# 고급 설정 - settings.json에서 로드
ADVANCED_CONFIG = {
    'entry_score_threshold': get_setting('entry', 'score_threshold', default=5.5),
    'min_score_for_small_position': 999,
    'aggressive_mode': False,
    'use_consecutive_loss_check': True,
    'max_consecutive_losses': 3,
}

# 동적 코인 스캔 설정
DYNAMIC_COIN_CONFIG = {
    'enabled': True,
    'max_dynamic_coins': 3,
    'refresh_interval': 900,
    'min_score': 5,
    'max_allocation': 0.15,
}

# ==========================================
# 📊 2. 분석 모듈 설정
# ==========================================

# 멀티 타임프레임 분석 - settings.json에서 로드
MTF_CONFIG = {
    'enabled': get_setting('features', 'mtf_analysis', default=True),
    'timeframes': {
        '1h': {'interval': 'minute60', 'weight': 0.3, 'count': 100},
        '4h': {'interval': 'minute240', 'weight': 0.4, 'count': 100},
        '1d': {'interval': 'day', 'weight': 0.3, 'count': 50}
    },
    'min_score': get_setting('entry', 'mtf_min_score', default=6.0),
    'min_consensus': get_setting('entry', 'mtf_min_consensus', default=0.70),
    'strong_signal_threshold': {'score': 8.0, 'consensus': 0.85},
    'allowed_trends': ['strong_uptrend', 'uptrend'],
    'cache_duration': 300,
}

# 머신러닝 설정 - settings.json에서 로드
ML_CONFIG = {
    'enabled': get_setting('features', 'ml_prediction', default=True),
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
        'min_buy_probability': get_setting('entry', 'ml_min_probability', default=0.65),
        'min_confidence': 0.60,
        'strong_signal_probability': 0.80,
    },
    'performance': {
        'min_accuracy': 0.55,
        'retrain_threshold': 0.50,
        'evaluation_days': 7,
    },
}

# 신호 통합 설정
SIGNAL_INTEGRATION_CONFIG = {
    'enabled': True,
    'weights': {
        'technical': 0.25,
        'mtf': 0.45,
        'ml': 0.30
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
# 💧 3. 물타기 설정 - settings.json에서 로드
# ==========================================
AVERAGING_DOWN_CONFIG = {
    'enabled': get_setting('averaging_down', 'enabled', default=False),
    'trigger_loss_rate': get_setting('averaging_down', 'trigger_loss_rate', default=-0.03),
    'max_averaging_count': get_setting('averaging_down', 'max_count', default=2),
    'averaging_size_ratio': get_setting('averaging_down', 'amount_ratio', default=0.5),
    'max_total_loss': -0.03,
    'min_balance_ratio': 0.3,
    'only_stable_coins': True,
    'disable_on_bear_market': True,
    'log_details': True,
}

# ==========================================
# 🤖 4. 자동 프리셋 전환 설정
# ==========================================
ADAPTIVE_PRESET_CONFIG = {
    'enabled': get_setting('features', 'adaptive_preset', default=True),
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
    'force_conservative_on': {
        'consecutive_losses': 1,
        'daily_loss_rate': 0.015,
        'high_volatility': 0.04,
    },
    'force_balanced_on': {
        'small_loss_streak': 2,
    },
    'log_analysis': True,
    'notify_on_switch': True,
}

# ==========================================
# 🎛️ 5. 전략 프리셋
# ==========================================
STRATEGY_PRESETS = {
    'conservative': {
        'entry_score_threshold': get_setting('entry', 'score_threshold', default=5.5),
        'mtf_min_score': get_setting('entry', 'mtf_min_score', default=6.0),
        'mtf_min_consensus': get_setting('entry', 'mtf_min_consensus', default=0.70),
        'ml_min_probability': get_setting('entry', 'ml_min_probability', default=0.65),
        'signal_weights': {'technical': 0.25, 'mtf': 0.45, 'ml': 0.30},
        'max_positions': get_setting('risk', 'max_positions', default=1),
        'max_position_size': get_setting('risk', 'max_position_size', default=0.15),
        'stop_loss': get_setting('risk', 'stop_loss', default=0.015),
    },
    'balanced': {
        'entry_score_threshold': get_setting('entry', 'score_threshold', default=5.0),
        'mtf_min_score': get_setting('entry', 'mtf_min_score', default=5.5),
        'mtf_min_consensus': get_setting('entry', 'mtf_min_consensus', default=0.60),
        'ml_min_probability': get_setting('entry', 'ml_min_probability', default=0.58),
        'signal_weights': {'technical': 0.40, 'mtf': 0.50, 'ml': 0.10},
        'max_positions': get_setting('risk', 'max_positions', default=1),
        'max_position_size': get_setting('risk', 'max_position_size', default=0.20),
        'stop_loss': get_setting('risk', 'stop_loss', default=0.015),
    },
    'aggressive': {
        'entry_score_threshold': 4.5,  # aggressive는 더 낮은 고정값
        'mtf_min_score': 5.0,
        'mtf_min_consensus': 0.55,
        'ml_min_probability': 0.45,
        'signal_weights': {'technical': 0.80, 'mtf': 0.20, 'ml': 0},
        'max_positions': 3,
        'max_position_size': 0.25,
        'stop_loss': 0.020,
    },
    'ml_focused': {
        'entry_score_threshold': 6.0,
        'mtf_min_score': 6.5,
        'mtf_min_consensus': 0.70,
        'ml_min_probability': 0.70,
        'signal_weights': {'technical': 0.25, 'mtf': 0.35, 'ml': 0.40},
        'max_positions': 3,
        'max_position_size': 0.20,
        'stop_loss': 0.010,
    }
}

# ==========================================
# ⚙️ 6. 활성 프리셋
# ==========================================
ACTIVE_PRESET = get_setting('preset', 'active', default='conservative')

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
        print(f"[WARN] 알 수 없는 프리셋: {preset_name}. 기본값 유지.")
        return

    preset = STRATEGY_PRESETS[preset_name]

    ADVANCED_CONFIG['entry_score_threshold'] = preset['entry_score_threshold']
    MTF_CONFIG['min_score'] = preset['mtf_min_score']
    MTF_CONFIG['min_consensus'] = preset['mtf_min_consensus']
    ML_CONFIG['prediction']['min_buy_probability'] = preset['ml_min_probability']
    SIGNAL_INTEGRATION_CONFIG['weights'] = preset['signal_weights']
    RISK_CONFIG['max_positions'] = preset['max_positions']
    RISK_CONFIG['max_position_size'] = preset['max_position_size']
    RISK_CONFIG['stop_loss'] = preset['stop_loss']

    print(f"[OK] '{preset_name}' 프리셋 적용 완료")
    print(f"     진입 점수: {preset['entry_score_threshold']}점 이상")
    print(f"     손절 기준: {preset['stop_loss']:.1%}")

# ==========================================
# 🛡️ 8. 과최적화 방지 설정
# ==========================================
SIMPLIFICATION_CONFIG = {
    'enabled': True,
    'core_parameters': ['entry_score_threshold', 'stop_loss', 'max_positions'],
    'adaptive_learning': {
        'enabled': True,
        'min_trades': 30,
        'learning_rate': 0.1,
        'max_adjustment': 0.2,
        'evaluation_window': 50,
    },
    'market_adaptive': {
        'enabled': True,
        'bull_market_bonus': 0.1,
        'bear_market_penalty': 0.3,
        'volatile_stop_multiplier': 1.5,
    }
}

# ==========================================
# 🌡️ 9. 슬리피지 및 변동성 설정
# ==========================================
SLIPPAGE_CONFIG = {
    'enabled': get_setting('features', 'slippage_protection', default=True),
    'max_slippage_rate': get_setting('advanced', 'slippage_max_rate', default=0.003),
    'use_limit_on_high_slippage': True,
    'slippage_buffer': 0.001,
}

VOLATILITY_CONFIG = {
    'enabled': get_setting('features', 'volatility_monitor', default=True),
    'update_interval': get_setting('advanced', 'volatility_update_interval', default=300),
    'lookback_periods': 24,
    'dynamic_adjustment': True,
    'pause_on_extreme': True,
}

# ==========================================
# 🎯 10. 스윙 홀딩 설정
# ==========================================
SWING_HOLDING_CONFIG = {
    'enabled': get_setting('swing_holding', 'enabled', default=True),
    'min_swing_hold_hours': get_setting('swing_holding', 'min_hold_hours', default=12),
    'ideal_swing_hold_hours': get_setting('swing_holding', 'ideal_hold_hours', default=24),
    'min_profit_for_early_exit': get_setting('swing_holding', 'min_profit_for_early_exit', default=0.025),
    'good_profit_threshold': get_setting('swing_holding', 'good_profit_threshold', default=0.030),
    'excellent_profit_threshold': get_setting('swing_holding', 'excellent_profit_threshold', default=0.050),
    'stop_loss_threshold': -get_setting('risk', 'stop_loss', default=0.015),
}

# ==========================================
# 🔄 11. 적응형 점수 관리 설정
# ==========================================
ADAPTIVE_SCORE_CONFIG = {
    'enabled': get_setting('adaptive_score', 'enabled', default=True),
    'analysis_interval_hours': get_setting('adaptive_score', 'analysis_interval_hours', default=4),
    'min_trades_for_analysis': get_setting('adaptive_score', 'min_trades', default=10),
    'lookback_days': get_setting('adaptive_score', 'lookback_days', default=7),
    'target_win_rate': get_setting('adaptive_score', 'target_win_rate', default=0.50),
    'max_adjustment': get_setting('adaptive_score', 'max_adjustment', default=0.5),
    'score_min': get_setting('adaptive_score', 'score_min', default=4.0),
    'score_max': get_setting('adaptive_score', 'score_max', default=8.0),
}

# ==========================================
# 🚀 12. 초기화
# ==========================================

def print_config_summary():
    """현재 설정 요약 출력"""
    print("\n" + "="*60)
    print("📋 현재 설정 요약 (settings.json)")
    print("="*60)
    print(f"거래 대상: {', '.join(TRADING_PAIRS)}")
    print(f"활성 프리셋: {ACTIVE_PRESET}")
    print(f"진입 점수: {ADVANCED_CONFIG['entry_score_threshold']}")
    print(f"손절: {RISK_CONFIG['stop_loss']:.1%}")
    print(f"최대 포지션: {RISK_CONFIG['max_positions']}개")
    print(f"스윙 홀딩: {'활성화' if SWING_HOLDING_CONFIG['enabled'] else '비활성화'}")
    print(f"최소 보유: {SWING_HOLDING_CONFIG['min_swing_hold_hours']}시간")
    print("="*60 + "\n")

# 파일 로드 시 자동 적용
if __name__ != "__main__":
    if _settings is not None:
        apply_preset(ACTIVE_PRESET)
    else:
        print("[WARN] 설정 파일 없음 - 기본값 사용")
