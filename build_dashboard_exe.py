# build_dashboard_exe.py - 대시보드 exe 빌드 스크립트

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
    """대시보드 exe 파일 빌드"""
    print("=" * 60)
    print("CoinTrade Dashboard - EXE 빌드 시작")
    print("=" * 60)

    check_pyinstaller()

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--name", "CoinTradeDashboard",
        "--console",
        "--noconfirm",

        # 의존성 수집
        "--collect-all", "pyupbit",
        "--collect-all", "pandas",
        "--collect-all", "numpy",
        "--collect-all", "sklearn",
        "--collect-all", "rich",

        # 숨겨진 import
        "--hidden-import", "pyupbit",
        "--hidden-import", "pandas",
        "--hidden-import", "numpy",
        "--hidden-import", "sklearn",
        "--hidden-import", "sklearn.ensemble",
        "--hidden-import", "sklearn.ensemble._forest",
        "--hidden-import", "sklearn.preprocessing",
        "--hidden-import", "rich",
        "--hidden-import", "rich.console",
        "--hidden-import", "rich.table",
        "--hidden-import", "rich.live",
        "--hidden-import", "rich.layout",
        "--hidden-import", "rich.panel",
        "--hidden-import", "rich.progress",
        "--hidden-import", "requests",
        "--hidden-import", "websocket",
        "--hidden-import", "jwt",
        "--hidden-import", "dateutil",

        # 메인 스크립트
        "dashboard.py"
    ]

    print("\n빌드 명령어:")
    print(" ".join(cmd))
    print("\n빌드 중... (약 1-3분 소요)")

    result = subprocess.run(cmd, capture_output=False)

    if result.returncode == 0:
        print("\n" + "=" * 60)
        print("[OK] 빌드 성공!")
        print("=" * 60)

        exe_path = os.path.join("dist", "CoinTradeDashboard.exe")
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
    release_folder = "CoinTradeBot_Release"

    if not os.path.exists(release_folder):
        os.makedirs(release_folder)

    src = "dist/CoinTradeDashboard.exe"
    dst = os.path.join(release_folder, "CoinTradeDashboard.exe")

    if os.path.exists(src):
        shutil.copy(src, dst)
        print(f"\n[OK] {release_folder}에 복사 완료!")
        print(f"  - {dst}")

    print("\n사용 방법:")
    print("1. CoinTradeBot.exe와 같은 폴더에 settings.json 필요")
    print("2. CoinTradeDashboard.exe 실행")
    print("3. 봇과 별개로 실시간 모니터링 가능")

if __name__ == "__main__":
    build_dashboard_exe()
