# build_exe.py - PyInstaller를 사용한 exe 빌드 스크립트

import subprocess
import sys
import os
import shutil

def check_pyinstaller():
    """PyInstaller 설치 확인"""
    try:
        import PyInstaller
        print("[OK] PyInstaller 설치됨")
        return True
    except ImportError:
        print("[INFO] PyInstaller 설치 중...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        return True

def get_all_py_files():
    """모든 Python 파일 목록"""
    py_files = []
    exclude = ['build_exe.py', 'check_positions.py', 'emergency_config_fix.py']

    for file in os.listdir('.'):
        if file.endswith('.py') and file not in exclude:
            py_files.append(file)

    return py_files

def build_exe():
    """exe 파일 빌드"""
    print("="*60)
    print("CoinTrade Bot - EXE 빌드 시작")
    print("="*60)

    # PyInstaller 확인
    check_pyinstaller()

    # 빌드 명령어 구성
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",                    # 단일 exe 파일
        "--name", "CoinTradeBot",       # exe 이름
        "--console",                    # 콘솔 창 표시
        "--noconfirm",                  # 기존 빌드 덮어쓰기

        # 아이콘 (있으면 추가)
        # "--icon", "icon.ico",

        # pyupbit 및 의존성 수집
        "--collect-all", "pyupbit",
        "--collect-all", "pandas",
        "--collect-all", "numpy",
        "--collect-all", "sklearn",

        # 숨겨진 import 추가
        "--hidden-import", "pyupbit",
        "--hidden-import", "pyupbit.quotation_api",
        "--hidden-import", "pyupbit.exchange_api",
        "--hidden-import", "pandas",
        "--hidden-import", "numpy",
        "--hidden-import", "sklearn",
        "--hidden-import", "sklearn.ensemble",
        "--hidden-import", "sklearn.ensemble._forest",
        "--hidden-import", "sklearn.preprocessing",
        "--hidden-import", "sklearn.preprocessing._data",
        "--hidden-import", "sklearn.utils._cython_blas",
        "--hidden-import", "sklearn.neighbors._typedefs",
        "--hidden-import", "sklearn.neighbors._quad_tree",
        "--hidden-import", "sklearn.tree._utils",
        "--hidden-import", "requests",
        "--hidden-import", "websocket",
        "--hidden-import", "websockets",
        "--hidden-import", "jwt",
        "--hidden-import", "PyJWT",
        "--hidden-import", "uuid",
        "--hidden-import", "dateutil",
        "--hidden-import", "urllib3",

        # 데이터 파일 추가 (없어도 됨 - 외부에서 로드)
        # "--add-data", "settings.json;.",

        # 메인 스크립트
        "main_trading_bot.py"
    ]

    print("\n빌드 명령어:")
    print(" ".join(cmd))
    print("\n빌드 중... (약 1-3분 소요)")

    # 빌드 실행
    result = subprocess.run(cmd, capture_output=False)

    if result.returncode == 0:
        print("\n" + "="*60)
        print("[OK] 빌드 성공!")
        print("="*60)

        # dist 폴더에서 exe 찾기
        exe_path = os.path.join("dist", "CoinTradeBot.exe")
        if os.path.exists(exe_path):
            print(f"\n실행 파일: {os.path.abspath(exe_path)}")

            # 배포 폴더 생성
            create_distribution()
        else:
            print("[WARN] exe 파일을 찾을 수 없습니다.")
    else:
        print("\n[ERROR] 빌드 실패!")
        print("위의 오류 메시지를 확인하세요.")

def create_distribution():
    """배포용 폴더 생성"""
    dist_folder = "CoinTradeBot_Release"

    # 보존할 파일 목록
    preserve_files = [
        "settings.json",
        "active_positions.json",
        "trade_history.json",
        "ml_model_random_forest.pkl",
        "ml_scaler.pkl",
        "score_performance.json",
        "trading_bot.log"
    ]

    # 기존 파일들 백업
    backups = {}
    for filename in preserve_files:
        filepath = os.path.join(dist_folder, filename)
        if os.path.exists(filepath):
            try:
                with open(filepath, 'rb') as f:
                    backups[filename] = f.read()
                print(f"[INFO] 기존 {filename} 발견 - 보존됩니다")
            except Exception as e:
                print(f"[WARN] {filename} 백업 실패: {e}")

    # 기존 폴더 삭제
    if os.path.exists(dist_folder):
        shutil.rmtree(dist_folder)

    os.makedirs(dist_folder)

    # exe 복사
    shutil.copy("dist/CoinTradeBot.exe", dist_folder)

    # 백업된 파일들 복원
    for filename, content in backups.items():
        filepath = os.path.join(dist_folder, filename)
        try:
            with open(filepath, 'wb') as f:
                f.write(content)
            print(f"[OK] 기존 {filename} 복원 완료")
        except Exception as e:
            print(f"[WARN] {filename} 복원 실패: {e}")

    # settings.json이 없으면 새로 생성
    settings_path = os.path.join(dist_folder, "settings.json")
    if not os.path.exists(settings_path):
        create_clean_settings(settings_path)
        print(f"[OK] 새 settings.json 생성 완료")

    # README 생성
    create_readme(dist_folder)

    print("\n" + "="*60)
    print("배포 폴더 생성 완료!")
    print("="*60)
    print(f"\n폴더: {os.path.abspath(dist_folder)}")
    print("\n포함 파일:")
    for f in os.listdir(dist_folder):
        print(f"  - {f}")
    print("\n사용 방법:")
    print("1. settings.json 파일에 API 키 입력")
    print("2. CoinTradeBot.exe 실행")

def create_clean_settings(path):
    """API 키가 빈 settings.json 생성"""
    import json

    settings = {
        "_comment": "CoinTrade Bot 설정 파일 - 이 파일을 수정하여 봇 설정을 변경하세요",
        "_version": "2.1.0",

        "api": {
            "_comment": "업비트 API 키 (필수) - 아래에 본인의 API 키를 입력하세요",
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

        "adaptive_score": {
            "_comment": "적응형 점수 자동 조정 (히스토리 기반)",
            "enabled": True,
            "analysis_interval_hours": 4,
            "min_trades": 10,
            "lookback_days": 7,
            "target_win_rate": 0.50,
            "max_adjustment": 0.5,
            "score_min": 4.0,
            "score_max": 8.0
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
            "status_print_interval": 60
        }
    }

    with open(path, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)

def create_readme(folder):
    """README 파일 생성"""
    readme = """# CoinTrade Bot v2.1

업비트 자동 트레이딩 봇 (스윙 트레이딩 버전)

## 사용 방법

### 1. API 키 설정
1. `settings.json` 파일을 메모장으로 열기
2. 아래 부분에 업비트 API 키 입력:
   ```json
   "api": {
     "access_key": "여기에_액세스키_입력",
     "secret_key": "여기에_시크릿키_입력"
   }
   ```
3. 파일 저장

### 2. 실행
- `CoinTradeBot.exe` 더블클릭

### 3. 설정 변경
`settings.json` 파일에서 다음 설정을 변경할 수 있습니다:

#### 거래 대상 코인
```json
"trading": {
  "pairs": ["BTC", "ETH", "XRP", ...]
}
```

#### 리스크 관리
```json
"risk": {
  "stop_loss": 0.015,      // 손절 1.5%
  "max_positions": 1       // 최대 보유 종목 수
}
```

#### 진입 조건
```json
"entry": {
  "score_threshold": 5.5   // 진입 점수 기준
}
```

#### 스윙 홀딩
```json
"swing_holding": {
  "min_hold_hours": 12,    // 최소 보유 시간
  "min_profit_for_early_exit": 0.025  // 조기 익절 기준 2.5%
}
```

#### 프리셋 선택
```json
"preset": {
  "active": "conservative"  // conservative, balanced, aggressive
}
```

## 주요 기능

1. **스윙 트레이딩 최적화**
   - 최소 12시간 보유 강제
   - 조기 익절 방지

2. **멀티 타임프레임 분석**
   - 1시간, 4시간, 일봉 통합 분석

3. **머신러닝 예측**
   - Random Forest 기반 가격 예측

4. **리스크 관리**
   - 손절 자동 실행
   - 일일 손실 한도
   - 연속 손실 관리

## 주의사항

- 투자는 본인 책임입니다
- API 키는 절대 타인에게 공유하지 마세요
- 소액으로 테스트 후 사용을 권장합니다

## 문제 해결

### API 키 오류
- settings.json의 API 키가 정확한지 확인
- 업비트에서 IP 제한 설정 확인

### 거래가 안 됨
- 진입 점수(score_threshold)를 낮춰보세요 (5.5 → 5.0)
- 시장 상황이 좋지 않을 수 있습니다

### 프로그램이 바로 종료됨
- 명령 프롬프트에서 실행하여 오류 메시지 확인
- settings.json 형식 오류 확인

---
CoinTrade Bot v2.1 - Swing Trading Edition
"""

    with open(os.path.join(folder, "README.md"), 'w', encoding='utf-8') as f:
        f.write(readme)

if __name__ == "__main__":
    build_exe()
