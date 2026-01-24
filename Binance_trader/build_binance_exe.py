# build_binance_exe.py - 바이낸스 트레이더 exe 빌드 스크립트

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

def build_binance_exe():
    """바이낸스 트레이더 exe 파일 빌드"""
    print("=" * 60)
    print("Binance Trader - EXE 빌드 시작")
    print("=" * 60)

    check_pyinstaller()

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--name", "BinanceTrader",
        "--console",
        "--noconfirm",

        # 의존성 수집
        "--collect-all", "ccxt",
        "--collect-all", "pandas",
        "--collect-all", "numpy",
        "--collect-all", "sklearn",

        # 숨겨진 import
        "--hidden-import", "ccxt",
        "--hidden-import", "ccxt.binance",
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
        "--hidden-import", "urllib3",
        "--hidden-import", "certifi",
        "--hidden-import", "json",
        "--hidden-import", "logging",
        "--hidden-import", "datetime",

        # 메인 스크립트
        "binance_trader.py"
    ]

    print("\n빌드 명령어:")
    print(" ".join(cmd))
    print("\n빌드 중... (약 2-5분 소요)")

    result = subprocess.run(cmd, capture_output=False)

    if result.returncode == 0:
        print("\n" + "=" * 60)
        print("[OK] 빌드 성공!")
        print("=" * 60)

        exe_path = os.path.join("dist", "BinanceTrader.exe")
        if os.path.exists(exe_path):
            print(f"\n실행 파일: {os.path.abspath(exe_path)}")
            create_release()
        else:
            print("[WARN] exe 파일을 찾을 수 없습니다.")
    else:
        print("\n[ERROR] 빌드 실패!")
        print("위의 오류 메시지를 확인하세요.")

def create_release():
    """배포 폴더 생성"""
    release_folder = "BinanceTrader_Release"

    # 보존할 파일 목록
    preserve_files = [
        "binance_settings.json",
        "binance_trading.log",
        "binance_history.json",
        "binance_positions.json"
    ]

    # 기존 파일들 백업
    backups = {}
    for filename in preserve_files:
        filepath = os.path.join(release_folder, filename)
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                backups[filename] = f.read()
            print(f"[INFO] 기존 {filename} 발견 - 보존됩니다")

    if os.path.exists(release_folder):
        shutil.rmtree(release_folder)

    os.makedirs(release_folder)

    # exe 복사
    shutil.copy("dist/BinanceTrader.exe", release_folder)

    # 백업된 파일들 복원
    for filename, content in backups.items():
        filepath = os.path.join(release_folder, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"[OK] 기존 {filename} 복원 완료")

    # binance_settings.json이 없으면 새로 생성
    settings_path = os.path.join(release_folder, "binance_settings.json")
    if not os.path.exists(settings_path):
        create_settings_template(settings_path)
        print(f"[OK] 새 binance_settings.json 생성 완료")

    # README 생성
    create_readme(release_folder)

    print("\n" + "=" * 60)
    print("배포 폴더 생성 완료!")
    print("=" * 60)
    print(f"\n폴더: {os.path.abspath(release_folder)}")
    print("\n포함 파일:")
    for f in os.listdir(release_folder):
        print(f"  - {f}")

def create_settings_template(path):
    """binance_settings.json 템플릿 생성"""
    import json

    settings = {
        "_comment": "Binance Trader 설정 파일",
        "_version": "1.0.0",

        "api": {
            "_comment": "바이낸스 API 키 (필수)",
            "api_key": "YOUR_BINANCE_API_KEY",
            "api_secret": "YOUR_BINANCE_SECRET_KEY"
        },

        "trading": {
            "_comment": "거래 대상 심볼",
            "symbols": ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
        },

        "risk": {
            "_comment": "리스크 관리",
            "position_size": 0.02,
            "max_positions": 3,
            "stop_loss": 0.02,
            "take_profit": 0.03,
            "daily_loss_limit": 0.05
        },

        "trailing_stop": {
            "_comment": "트레일링 스탑 설정",
            "enabled": True,
            "activation": 0.02,
            "distance": 0.01
        },

        "strategy": {
            "_comment": "전략 설정",
            "threshold": 3,
            "base_timeframe": "1h",
            "trend_timeframe": "4h",
            "entry_score_threshold": 0.2,
            "allow_sideways_entry": True,
            "scan_interval": 300
        },

        "ml": {
            "_comment": "머신러닝 설정",
            "enabled": True,
            "min_probability": 0.60,
            "weight": 0.3
        }
    }

    with open(path, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)

def create_readme(folder):
    """README 파일 생성"""
    readme = """# Binance Trader v1.0

바이낸스 선물 자동 트레이딩 봇

## 사용 방법

### 1. API 키 설정
1. `binance_settings.json` 파일을 메모장으로 열기
2. 아래 부분에 바이낸스 API 키 입력:
   ```json
   "api": {
     "api_key": "여기에_API_KEY_입력",
     "api_secret": "여기에_SECRET_KEY_입력"
   }
   ```
3. 파일 저장

### 2. 실행
- `BinanceTrader.exe` 더블클릭

## 주요 기능

1. **선물 거래 (LONG/SHORT)**
   - 상승/하락 양방향 거래 지원

2. **멀티 타임프레임 분석**
   - 1시간, 4시간 봉 통합 분석

3. **머신러닝 예측**
   - Random Forest 기반 진입 신호

4. **트레일링 스탑**
   - 수익 구간 진입 시 자동 추적

5. **리스크 관리**
   - 손절/익절 자동 실행
   - 일일 손실 한도

## 설정 변경

### 거래 대상
```json
"trading": {
  "symbols": ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
}
```

### 리스크 관리
```json
"risk": {
  "position_size": 0.02,    // 포지션 크기 2%
  "stop_loss": 0.02,        // 손절 2%
  "take_profit": 0.03       // 익절 3%
}
```

### 스캔 간격
```json
"strategy": {
  "scan_interval": 300      // 5분마다 스캔
}
```

## 주의사항

- 선물 거래는 원금 손실 위험이 있습니다
- API 키는 절대 타인에게 공유하지 마세요
- 소액으로 테스트 후 사용을 권장합니다
- 레버리지 설정에 주의하세요

## 문제 해결

### API 키 오류
- binance_settings.json의 API 키가 정확한지 확인
- 바이낸스에서 선물 거래 권한 활성화 확인
- IP 제한 설정 확인

### 거래가 안 됨
- entry_score_threshold를 낮춰보세요 (0.2 → 0.1)
- allow_sideways_entry를 true로 설정

### 프로그램이 바로 종료됨
- 명령 프롬프트에서 실행하여 오류 메시지 확인
- binance_settings.json 형식 오류 확인

---
Binance Trader v1.0 - Futures Trading Bot
"""

    with open(os.path.join(folder, "README.md"), 'w', encoding='utf-8') as f:
        f.write(readme)

if __name__ == "__main__":
    build_binance_exe()
