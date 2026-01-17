# settings_loader.py - 외부 설정 파일 로더

import json
import os
import sys
import shutil
from datetime import datetime

# exe 실행 시 경로 처리
def get_base_path():
    """실행 파일 기준 경로 반환"""
    if getattr(sys, 'frozen', False):
        # PyInstaller로 빌드된 exe 실행 시
        return os.path.dirname(sys.executable)
    else:
        # 일반 Python 실행 시
        return os.path.dirname(os.path.abspath(__file__))

BASE_PATH = get_base_path()
SETTINGS_FILE = os.path.join(BASE_PATH, 'settings.json')
SETTINGS_TEMPLATE = os.path.join(BASE_PATH, 'settings_template.json')


def load_settings():
    """
    settings.json 파일 로드

    Returns:
        dict: 설정 딕셔너리
    """
    # 설정 파일이 없으면 템플릿에서 복사
    if not os.path.exists(SETTINGS_FILE):
        if os.path.exists(SETTINGS_TEMPLATE):
            shutil.copy(SETTINGS_TEMPLATE, SETTINGS_FILE)
            print(f"[INFO] settings.json 파일이 생성되었습니다.")
            print(f"[INFO] API 키를 설정하고 다시 실행하세요: {SETTINGS_FILE}")
        else:
            create_default_settings()
            print(f"[INFO] 기본 settings.json 파일이 생성되었습니다.")
            print(f"[INFO] API 키를 설정하고 다시 실행하세요: {SETTINGS_FILE}")

    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            settings = json.load(f)

        # API 키 검증
        if not validate_api_keys(settings):
            print("\n" + "="*60)
            print("[ERROR] API 키가 설정되지 않았습니다!")
            print(f"[INFO] 설정 파일을 열어 API 키를 입력하세요:")
            print(f"       {SETTINGS_FILE}")
            print("="*60 + "\n")
            sys.exit(1)

        return settings

    except json.JSONDecodeError as e:
        print(f"[ERROR] settings.json 파싱 오류: {e}")
        print("[INFO] 설정 파일 형식을 확인하세요.")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] 설정 로드 실패: {e}")
        sys.exit(1)


def validate_api_keys(settings):
    """API 키 유효성 검사"""
    api = settings.get('api', {})
    access_key = api.get('access_key', '')
    secret_key = api.get('secret_key', '')

    if not access_key or access_key == 'YOUR_ACCESS_KEY_HERE':
        return False
    if not secret_key or secret_key == 'YOUR_SECRET_KEY_HERE':
        return False

    return True


def create_default_settings():
    """기본 설정 파일 생성"""
    default_settings = {
        "_comment": "CoinTrade Bot 설정 파일 - 이 파일을 수정하여 봇 설정을 변경하세요",
        "_version": "1.0.0",
        "_last_updated": datetime.now().strftime("%Y-%m-%d"),

        "api": {
            "_comment": "업비트 API 키 (필수)",
            "access_key": "YOUR_ACCESS_KEY_HERE",
            "secret_key": "YOUR_SECRET_KEY_HERE"
        },

        "trading": {
            "_comment": "거래 대상 코인 목록",
            "pairs": ["BTC", "ETH", "XRP", "SOL", "DOGE", "ADA", "AVAX", "LINK", "DOT", "MATIC"],
            "stable_pairs": ["BTC", "ETH", "XRP"]
        },

        "strategy": {
            "_comment": "전략 설정",
            "min_profit_target": 0.030,
            "max_trades_per_day": 20,
            "min_hold_time_hours": 12,
            "trade_cooldown_minutes": 120
        },

        "risk": {
            "_comment": "리스크 관리",
            "max_position_size": 0.20,
            "stop_loss": 0.015,
            "daily_loss_limit": 0.03,
            "max_positions": 1
        },

        "entry": {
            "_comment": "진입 조건",
            "score_threshold": 5.5,
            "mtf_min_score": 6.0,
            "mtf_min_consensus": 0.70,
            "ml_min_probability": 0.65
        },

        "swing_holding": {
            "_comment": "스윙 홀딩 설정",
            "enabled": True,
            "min_hold_hours": 12,
            "ideal_hold_hours": 24,
            "min_profit_for_early_exit": 0.025,
            "good_profit_threshold": 0.030,
            "excellent_profit_threshold": 0.050
        },

        "features": {
            "_comment": "기능 활성화/비활성화",
            "mtf_analysis": True,
            "ml_prediction": True,
            "slippage_protection": True,
            "volatility_monitor": True,
            "averaging_down": True,
            "adaptive_preset": True
        },

        "averaging_down": {
            "_comment": "물타기 설정",
            "enabled": True,
            "trigger_loss_rate": -0.03,
            "max_count": 2,
            "amount_ratio": 0.5
        },

        "preset": {
            "_comment": "활성 프리셋: conservative, balanced, aggressive",
            "active": "conservative"
        },

        "advanced": {
            "_comment": "고급 설정 (주의해서 변경)",
            "slippage_max_rate": 0.003,
            "volatility_update_interval": 300,
            "position_save_interval": 60,
            "status_print_interval": 300
        }
    }

    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(default_settings, f, indent=2, ensure_ascii=False)


def get_setting(settings, *keys, default=None):
    """
    중첩 딕셔너리에서 값 가져오기

    Usage:
        get_setting(settings, 'api', 'access_key')
        get_setting(settings, 'risk', 'stop_loss', default=0.015)
    """
    value = settings
    for key in keys:
        if isinstance(value, dict):
            value = value.get(key)
        else:
            return default
        if value is None:
            return default
    return value


class Settings:
    """설정 접근 클래스"""

    def __init__(self):
        self._settings = load_settings()
        self._apply_settings()

    def _apply_settings(self):
        """설정값을 속성으로 변환"""
        s = self._settings

        # API
        self.access_key = get_setting(s, 'api', 'access_key')
        self.secret_key = get_setting(s, 'api', 'secret_key')

        # Trading
        self.trading_pairs = get_setting(s, 'trading', 'pairs', default=[])
        self.stable_pairs = get_setting(s, 'trading', 'stable_pairs', default=[])

        # Strategy
        self.min_profit_target = get_setting(s, 'strategy', 'min_profit_target', default=0.030)
        self.max_trades_per_day = get_setting(s, 'strategy', 'max_trades_per_day', default=20)
        self.min_hold_time = get_setting(s, 'strategy', 'min_hold_time_hours', default=12) * 3600
        self.trade_cooldown = get_setting(s, 'strategy', 'trade_cooldown_minutes', default=120)

        # Risk
        self.max_position_size = get_setting(s, 'risk', 'max_position_size', default=0.20)
        self.stop_loss = get_setting(s, 'risk', 'stop_loss', default=0.015)
        self.daily_loss_limit = get_setting(s, 'risk', 'daily_loss_limit', default=0.03)
        self.max_positions = get_setting(s, 'risk', 'max_positions', default=1)

        # Entry
        self.entry_score_threshold = get_setting(s, 'entry', 'score_threshold', default=5.5)
        self.mtf_min_score = get_setting(s, 'entry', 'mtf_min_score', default=6.0)
        self.mtf_min_consensus = get_setting(s, 'entry', 'mtf_min_consensus', default=0.70)
        self.ml_min_probability = get_setting(s, 'entry', 'ml_min_probability', default=0.65)

        # Swing Holding
        self.swing_enabled = get_setting(s, 'swing_holding', 'enabled', default=True)
        self.swing_min_hours = get_setting(s, 'swing_holding', 'min_hold_hours', default=12)
        self.swing_ideal_hours = get_setting(s, 'swing_holding', 'ideal_hold_hours', default=24)
        self.swing_early_exit = get_setting(s, 'swing_holding', 'min_profit_for_early_exit', default=0.025)
        self.swing_good_profit = get_setting(s, 'swing_holding', 'good_profit_threshold', default=0.030)
        self.swing_excellent = get_setting(s, 'swing_holding', 'excellent_profit_threshold', default=0.050)

        # Features
        self.mtf_enabled = get_setting(s, 'features', 'mtf_analysis', default=True)
        self.ml_enabled = get_setting(s, 'features', 'ml_prediction', default=True)
        self.slippage_enabled = get_setting(s, 'features', 'slippage_protection', default=True)
        self.volatility_enabled = get_setting(s, 'features', 'volatility_monitor', default=True)
        self.averaging_enabled = get_setting(s, 'features', 'averaging_down', default=True)
        self.adaptive_preset_enabled = get_setting(s, 'features', 'adaptive_preset', default=True)

        # Averaging Down
        self.avg_trigger_rate = get_setting(s, 'averaging_down', 'trigger_loss_rate', default=-0.03)
        self.avg_max_count = get_setting(s, 'averaging_down', 'max_count', default=2)
        self.avg_amount_ratio = get_setting(s, 'averaging_down', 'amount_ratio', default=0.5)

        # Preset
        self.active_preset = get_setting(s, 'preset', 'active', default='conservative')

        # Advanced
        self.slippage_max = get_setting(s, 'advanced', 'slippage_max_rate', default=0.003)
        self.volatility_interval = get_setting(s, 'advanced', 'volatility_update_interval', default=300)
        self.position_save_interval = get_setting(s, 'advanced', 'position_save_interval', default=60)
        self.status_print_interval = get_setting(s, 'advanced', 'status_print_interval', default=300)

    def reload(self):
        """설정 다시 로드"""
        self._settings = load_settings()
        self._apply_settings()

    def get_raw(self):
        """원본 설정 딕셔너리 반환"""
        return self._settings

    def print_summary(self):
        """설정 요약 출력"""
        print("\n" + "="*60)
        print("📋 현재 설정 요약")
        print("="*60)
        print(f"거래 대상: {', '.join(self.trading_pairs)}")
        print(f"활성 프리셋: {self.active_preset}")
        print(f"진입 점수: {self.entry_score_threshold}")
        print(f"손절: {self.stop_loss:.1%}")
        print(f"최대 포지션: {self.max_positions}개")
        print(f"스윙 홀딩: {'활성화' if self.swing_enabled else '비활성화'}")
        print(f"최소 보유: {self.swing_min_hours}시간")
        print("="*60 + "\n")


# 전역 설정 인스턴스
_settings_instance = None

def get_settings():
    """전역 설정 인스턴스 반환"""
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance


# 테스트용
if __name__ == "__main__":
    print(f"설정 파일 경로: {SETTINGS_FILE}")
    settings = get_settings()
    settings.print_summary()
