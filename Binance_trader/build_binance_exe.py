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

        # XGBoost/LightGBM: DLL + 데이터 파일 수집 (테스트 모듈 제외)
        "--collect-binaries", "xgboost",
        "--collect-binaries", "lightgbm",
        "--collect-data", "xgboost",
        "--collect-data", "lightgbm",
        "--copy-metadata", "xgboost",
        "--copy-metadata", "lightgbm",

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
        # 고급 ML 라이브러리 (v2.2)
        "--hidden-import", "xgboost",
        "--hidden-import", "lightgbm",
        "--hidden-import", "ta",
        "--hidden-import", "ta.momentum",
        "--hidden-import", "ta.trend",
        "--hidden-import", "ta.volatility",

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

    # 보존할 텍스트 파일 목록
    preserve_text_files = [
        ".env",
        "binance_settings.json",
        "binance_trading.log",
        "binance_history.json",
        "binance_positions.json",
    ]

    # 보존할 바이너리 파일 목록
    preserve_binary_files = [
        "binance_ml_model.pkl",
        "BinanceDashboard.exe"  # 대시보드 exe 보존
    ]

    # 기존 텍스트 파일들 백업
    text_backups = {}
    for filename in preserve_text_files:
        filepath = os.path.join(release_folder, filename)
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                text_backups[filename] = f.read()
            print(f"[INFO] 기존 {filename} 발견 - 보존됩니다")

    # 기존 바이너리 파일들 백업
    binary_backups = {}
    for filename in preserve_binary_files:
        filepath = os.path.join(release_folder, filename)
        if os.path.exists(filepath):
            with open(filepath, 'rb') as f:
                binary_backups[filename] = f.read()
            print(f"[INFO] 기존 {filename} 발견 - 보존됩니다")

    if os.path.exists(release_folder):
        shutil.rmtree(release_folder)

    os.makedirs(release_folder)

    # exe 복사
    shutil.copy("dist/BinanceTrader.exe", release_folder)

    # 백업된 텍스트 파일들 복원
    for filename, content in text_backups.items():
        filepath = os.path.join(release_folder, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"[OK] 기존 {filename} 복원 완료")

    # 백업된 바이너리 파일들 복원
    for filename, content in binary_backups.items():
        filepath = os.path.join(release_folder, filename)
        with open(filepath, 'wb') as f:
            f.write(content)
        print(f"[OK] 기존 {filename} 복원 완료")

    # binance_settings.json이 없으면 새로 생성
    settings_path = os.path.join(release_folder, "binance_settings.json")
    if not os.path.exists(settings_path):
        create_settings_template(settings_path)
        print(f"[OK] 새 binance_settings.json 생성 완료")

    # 문서 파일 복사 (소스에서 Release 폴더로)
    copy_docs(release_folder)

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
        "_version": "2.2.0",

        "mode": "simulation",

        "api": {
            "_comment": "바이낸스 API 키 (필수)",
            "key": "YOUR_BINANCE_API_KEY",
            "secret": "YOUR_BINANCE_SECRET_KEY"
        },

        "simulation": {
            "_comment": "시뮬레이션 초기 잔고",
            "initial_balance": 10000
        },

        "trading": {
            "_comment": "거래 대상 심볼",
            "symbols": ["BTC/USDT", "ETH/USDT", "SOL/USDT", "DOGE/USDT"]
        },

        "risk": {
            "_comment": "리스크 관리",
            "max_position_size": 0.02,
            "leverage": 3,
            "max_positions": 4,
            "stop_loss": 0.015,
            "take_profit": 0.03,
            "daily_loss_limit": 0.05
        },

        "trailing_stop": {
            "_comment": "트레일링 스탑 설정",
            "enabled": True,
            "activation": 0.015,
            "distance": 0.008
        },

        "partial_exit": {
            "_comment": "분할 익절 설정 (v2.1 신규)",
            "enabled": True,
            "trigger_profit": 0.015,
            "exit_ratio": 0.5
        },

        "market_analysis": {
            "_comment": "시장 상태 분석 (v2.1 신규)",
            "enabled": True,
            "crash_threshold_1h": -3.0,
            "crash_threshold_4h": -5.0,
            "rally_threshold_1h": 3.0,
            "rally_threshold_4h": 5.0
        },

        "strategy": {
            "_comment": "전략 설정",
            "threshold": 3,
            "base_timeframe": "1h",
            "trend_timeframe": "4h",
            "entry_score_threshold": 0.2,
            "allow_sideways_entry": True,
            "scan_interval": 120
        },

        "ml": {
            "_comment": "머신러닝 설정",
            "enabled": True,
            "min_probability": 0.60,
            "weight": 0.3
        },

        "advanced_ml": {
            "_comment": "고급 ML 설정 (v2.2 신규 - XGBoost+LightGBM+RF 앙상블)",
            "enabled": True,
            "weight": 0.4
        }
    }

    with open(path, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)

def copy_docs(folder):
    """문서 파일 복사 (소스 폴더에서 Release 폴더로)"""
    docs_to_copy = [
        "README.md",
        "TUNING_GUIDE.md",
        ".env.example"
    ]

    for doc in docs_to_copy:
        if os.path.exists(doc):
            shutil.copy(doc, folder)
            print(f"[OK] {doc} 복사 완료")
        else:
            print(f"[WARN] {doc} 파일을 찾을 수 없습니다")

if __name__ == "__main__":
    build_binance_exe()
