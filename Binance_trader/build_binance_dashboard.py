# build_binance_dashboard.py - 바이낸스 대시보드 exe 빌드 스크립트

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

def build_dashboard_exe():
    """바이낸스 대시보드 exe 파일 빌드"""
    print("=" * 60)
    print("Binance Dashboard - EXE 빌드 시작")
    print("=" * 60)

    check_pyinstaller()

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--name", "BinanceDashboard",
        "--console",
        "--noconfirm",

        # 의존성 수집
        "--collect-all", "ccxt",
        "--collect-all", "rich",

        # 숨겨진 import
        "--hidden-import", "ccxt",
        "--hidden-import", "ccxt.binance",
        "--hidden-import", "rich",
        "--hidden-import", "rich.console",
        "--hidden-import", "rich.table",
        "--hidden-import", "rich.live",
        "--hidden-import", "rich.layout",
        "--hidden-import", "rich.panel",
        "--hidden-import", "requests",
        "--hidden-import", "urllib3",
        "--hidden-import", "certifi",
        "--hidden-import", "json",
        "--hidden-import", "logging",
        "--hidden-import", "datetime",

        # 메인 스크립트
        "binance_dashboard.py"
    ]

    print("\n빌드 명령어:")
    print(" ".join(cmd))
    print("\n빌드 중... (약 1-3분 소요)")

    result = subprocess.run(cmd, capture_output=False)

    if result.returncode == 0:
        print("\n" + "=" * 60)
        print("[OK] 빌드 성공!")
        print("=" * 60)

        exe_path = os.path.join("dist", "BinanceDashboard.exe")
        if os.path.exists(exe_path):
            print(f"\n실행 파일: {os.path.abspath(exe_path)}")
            copy_to_release()
        else:
            print("[WARN] exe 파일을 찾을 수 없습니다.")
    else:
        print("\n[ERROR] 빌드 실패!")
        print("위의 오류 메시지를 확인하세요.")

def copy_to_release():
    """Release 폴더에 복사"""
    release_folder = "BinanceTrader_Release"

    # Release 폴더가 없으면 생성
    if not os.path.exists(release_folder):
        os.makedirs(release_folder)

    # 대시보드 exe 복사
    src = os.path.join("dist", "BinanceDashboard.exe")
    dst = os.path.join(release_folder, "BinanceDashboard.exe")

    if os.path.exists(src):
        shutil.copy(src, dst)
        print(f"\n[OK] {dst} 복사 완료")

    print("\n" + "=" * 60)
    print("대시보드 빌드 완료!")
    print("=" * 60)
    print(f"\n폴더: {os.path.abspath(release_folder)}")
    print("\n실행 방법:")
    print(f"  1. {release_folder} 폴더로 이동")
    print(f"  2. BinanceDashboard.exe 실행")
    print(f"\n주의: binance_settings.json이 같은 폴더에 있어야 합니다.")

if __name__ == "__main__":
    build_dashboard_exe()
