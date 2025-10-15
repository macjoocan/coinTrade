STRATEGY_CONFIG = {
    'min_profit_target': 0.015,       # 1.5% → 1% (현실적으로)
    'max_trades_per_day': 30,        
    'min_hold_time': 3600,           # 2시간 → 1시간
}

RISK_CONFIG = {
    'max_position_size': 0.20,       # 20% → 25% 
    'stop_loss': 0.010,              # 1.5% → 1.2% (더 타이트)
    'daily_loss_limit': 0.015,        
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
    'entry_score_threshold': 6.5,    # 7 → 5.5 (완화)
    'min_score_for_small_position': 999,
    'aggressive_mode': False,        
    'use_consecutive_loss_check': True,
    'max_consecutive_losses': 2,     # 2 → 3 (여유 추가)
}

DYNAMIC_COIN_CONFIG = {
    'enabled': True,  # 동적 선택 활성화
    'max_dynamic_coins': 2,  # 최대 3개 추가
    'refresh_interval': 3600 * 6,  # 3시간마다 갱신
    'min_score': 5,  # 최소 모멘텀 점수
    'max_allocation': 0.15,  # 동적 코인당 최대 15%
}

# ==========================================
# ✅ 멀티 타임프레임 분석 설정 (신규)
# ==========================================
MTF_CONFIG = {
    'enabled': True,  # MTF 분석 활성화
    
    # 타임프레임 설정
    'timeframes': {
        '1h': {
            'interval': 'minute60',
            'weight': 0.3,      # 가중치 (합계 1.0)
            'count': 100        # 데이터 개수
        },
        '4h': {
            'interval': 'minute240',
            'weight': 0.4,      # 중기 추세에 더 큰 가중치
            'count': 100
        },
        '1d': {
            'interval': 'day',
            'weight': 0.3,
            'count': 50
        }
    },
    
    # 진입 기준
    'min_score': 6.5,           # 최소 MTF 점수 (0~10)
    'min_consensus': 0.70,      # 최소 합의 수준 (65%)
    'strong_signal_threshold': {
        'score': 8.0,           # 강한 신호 점수
        'consensus': 0.85       # 강한 신호 합의
    },
    
    # 추세 필터
    'allowed_trends': [
        'strong_uptrend',
        'uptrend',
        # 'sideways',  # 주석 처리 = 횡보장에서는 거래 안함
        # 'downtrend'  # 하락장 제외
    ],
    
    # 캐싱
    'cache_duration': 300,      # 5분 캐싱 (API 절약)
}

# ==========================================
# 🤖 머신러닝 예측 설정 (신규)
# ==========================================
ML_CONFIG = {
    'enabled': True,  # ML 예측 활성화
    
    # 모델 설정
    'model_type': 'random_forest',  # 'random_forest' 또는 'gradient_boosting'
    'model_file': 'ml_model_random_forest.pkl',
    'scaler_file': 'ml_scaler.pkl',
    
    # 학습 파라미터
    'training': {
        'lookback_hours': 168,      # 학습 데이터: 1주일 (168시간)
        'prediction_horizon': 6,    # 6시간 후 예측
        'min_profit_threshold': 0.015,  # 1.5% 이상을 성공으로 간주
        'auto_retrain_days': 7,     # 7일마다 자동 재학습
        'min_samples': 200,         # 최소 학습 샘플 수
    },
    
    # 예측 기준
    'prediction': {
        'min_buy_probability': 0.70,    # 최소 매수 확률 (65%)
        'min_confidence': 0.65,         # 최소 신뢰도 (60%)
        'strong_signal_probability': 0.80,  # 강한 신호 확률
    },
    
    # 성능 임계값
    'performance': {
        'min_accuracy': 0.55,       # 최소 정확도 (55%)
        'retrain_threshold': 0.50,  # 이 이하면 재학습
        'evaluation_days': 7,       # 최근 7일 성능 평가
    },
    
    # 특성 선택
    'features': {
        'use_price_features': True,     # 가격 특성 (returns, momentum)
        'use_technical_indicators': True,  # 기술적 지표 (RSI, MACD, BB)
        'use_volume_features': True,    # 볼륨 특성
        'use_volatility_features': True,  # 변동성 특성
        'use_time_features': True,      # 시간 특성 (hour, day_of_week)
        'use_candle_patterns': True,    # 캔들 패턴
    },
    
    # Random Forest 파라미터
    'rf_params': {
        'n_estimators': 100,
        'max_depth': 10,
        'min_samples_split': 20,
        'min_samples_leaf': 10,
        'random_state': 42,
    },
    
    # Gradient Boosting 파라미터
    'gb_params': {
        'n_estimators': 100,
        'max_depth': 5,
        'learning_rate': 0.1,
        'random_state': 42,
    }
}

# ==========================================
# 🎯 신호 통합 설정 (신규)
# ==========================================
SIGNAL_INTEGRATION_CONFIG = {
    'enabled': True,  # 신호 통합 활성화
    
    # 신호별 가중치 (합계 1.0)
    'weights': {
        'technical': 0.30,   # 기존 기술적 분석
        'mtf': 0.40,         # 멀티 타임프레임
        'ml': 0.30           # 머신러닝
    },
    
    # 진입 모드
    'entry_mode': 'weighted',  # 'weighted', 'consensus', 'any', 'all'
    # weighted: 가중 평균 점수
    # consensus: 2개 이상 신호 일치
    # any: 1개 이상 신호
    # all: 3개 모두 신호
    
    # 모드별 설정
    'mode_settings': {
        'weighted': {
            'min_score': 5.5,           # 가중 평균 최소 점수
            'conservative_score': 6.5,  # 보수적 모드 점수
            'aggressive_score': 5.0,    # 공격적 모드 점수
        },
        'consensus': {
            'min_signals': 2,           # 최소 신호 개수
            'min_individual_score': 0.6,  # 개별 신호 최소 점수
        },
        'any': {
            'min_signal_score': 0.7,    # 1개 신호의 최소 점수
        },
        'all': {
            'min_signal_score': 0.6,    # 모든 신호의 최소 점수
        }
    },
    
    # 시장 상황별 조정
    'market_adjustment': {
        'bullish': -1.0,    # 강세장: 기준 완화
        'neutral': -0.5,     # 중립: 기준 유지
        'bearish': +2.5,    # 약세장: 기준 강화
    },
    
    # 신호 무시 조건
    'ignore_signals': {
        'on_consecutive_losses': 2,     # 연속 3회 손실 시 모든 신호 무시
        'on_daily_loss_exceed': 0.015,  # 일일 1.5% 손실 시 무시
        'ignore_weak_signals': True,    # 약한 신호 자동 무시
    }
}

# ==========================================
# 📊 대시보드 설정 (신규)
# ==========================================
DASHBOARD_CONFIG = {
    'enabled': True,
    
    # 업데이트 주기
    'refresh_interval': 10,     # 초 단위 (10초마다 갱신)
    'api_call_interval': 30,    # 가격 API 호출 간격 (30초)
    
    # 표시 설정
    'display': {
        'max_watchlist_coins': 8,   # 가격 리스트 최대 표시
        'max_position_display': 5,  # 포지션 최대 표시
        'show_mtf_analysis': True,  # MTF 분석 표시
        'show_ml_prediction': True, # ML 예측 표시
        'show_24h_stats': True,     # 24시간 통계
        'show_7d_stats': True,      # 7일 통계
        'show_30d_stats': True,     # 30일 통계
    },
    
    # 알림 설정
    'alerts': {
        'enabled': False,           # 알림 기능 (추후 구현)
        'mtf_strong_signal': 8.0,   # MTF 강한 신호 점수
        'ml_high_probability': 0.75, # ML 높은 확률
        'price_change_alert': 0.05,  # 5% 변동 알림
    },
    
    # 성능
    'performance': {
        'cache_prices': True,
        'cache_duration': 30,
        'max_api_calls_per_minute': 500,
    }
}

# ==========================================
# 🎛️ 전략 프리셋 (선택 가능)
# ==========================================
STRATEGY_PRESETS = {
    # 보수적 전략
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
    
    # 균형 전략 (기본)
    'balanced': {
        'entry_score_threshold': 6.5,
        'mtf_min_score': 6.5,
        'mtf_min_consensus': 0.70,
        'ml_min_probability': 0.70,
        'signal_weights': {'technical': 0.30, 'mtf': 0.40, 'ml': 0.30},
        'max_positions': 3,
        'max_position_size': 0.20,
        'stop_loss': 0.010,
    },
    
    # 공격적 전략
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
# 📈 추매(Pyramiding) 설정 - 조건부 활성화
# ==========================================
PYRAMIDING_CONFIG = {
    'enabled': False,  # ⚠️ 처음엔 False로 시작 추천
    
    # 기본 조건
    'max_pyramids': 1,              # 최대 1회만 (총 2번 매수)
    'min_score_increase': 1.0,      # 이전보다 1.0점 높아야
    'min_profit_for_pyramid': 0.02, # +2% 수익 상태에서만 ⚠️
    
    # 시장 조건
    'allowed_markets': ['bullish'],  # 상승장에서만
    'min_market_strength': 0.7,      # 시장 강도 70%+
    
    # 포지션 크기
    'pyramid_size_ratio': 0.5,       # 기존의 50% 크기
    'max_total_position': 0.30,      # 한 코인 최대 30%
    
    # 안전장치
    'stop_on_reversal': True,        # 추세 반전 시 중단
    'require_all_signals': True,     # 3가지 신호 모두 OK
    'min_volume_increase': 1.3,      # 거래량 30%↑
    
    # 추매 후 관리
    'use_breakeven_stop': True,      # 평균단가 손절
    'tighten_stop_loss': 0.008,      # 손절 0.8%로
}

# 현재 사용 중인 프리셋
ACTIVE_PRESET = 'balanced'  # 'conservative', 'balanced', 'aggressive'

# ==========================================
# 🔧 디버그 설정
# ==========================================
DEBUG_CONFIG = {
    'verbose_logging': False,       # 상세 로깅
    'log_mtf_details': False,       # MTF 상세 로그
    'log_ml_predictions': False,    # ML 예측 로그
    'log_signal_scoring': True,     # 신호 점수 로그
    'save_predictions': False,      # 예측 결과 파일 저장
    'performance_monitoring': True, # 성능 모니터링
}

# 기본 안정 코인
# STABLE_PAIRS = ['BTC', 'ETH', 'SOL']
STABLE_PAIRS = ['BTC', 'ETH', 'SOL', 'XRP', 'DOGE', 'ADA']

# 안정적인 메이저 코인만
TRADING_PAIRS = STABLE_PAIRS


# ==========================================
# 🚀 프리셋 적용 함수 (자동)
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