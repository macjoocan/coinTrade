# emergency_config_fix.py - 긴급 설정 수정 스크립트

"""
승률 5% 긴급 상황 대응
- 손절 완화
- 진입 조건 강화
- Conservative 모드로 전환
"""

import json

def emergency_fix():
    print("="*60)
    print("🚨 긴급 설정 수정 시작")
    print("="*60)

    # 1. config.py 백업
    print("\n1. config.py 백업 중...")
    try:
        with open('config.py', 'r', encoding='utf-8') as f:
            original = f.read()

        with open('config.py.backup', 'w', encoding='utf-8') as f:
            f.write(original)

        print("✅ 백업 완료: config.py.backup")
    except Exception as e:
        print(f"❌ 백업 실패: {e}")
        return

    # 2. 긴급 수정 적용
    print("\n2. 긴급 수정 적용 중...")

    modifications = {
        "손절 완화": {
            "'stop_loss': 0.005": "'stop_loss': 0.012",  # Conservative
            "'stop_loss': 0.006": "'stop_loss': 0.015",  # Balanced
            "'stop_loss': 0.008": "'stop_loss': 0.020",  # Aggressive
        },
        "진입 조건 강화": {
            "'entry_score_threshold': 5.0": "'entry_score_threshold': 7.0",  # Conservative
            "'entry_score_threshold': 4.5": "'entry_score_threshold': 6.5",  # Balanced
            "'entry_score_threshold': 4.0": "'entry_score_threshold': 6.0",  # Aggressive
        },
        "최대 포지션 축소": {
            "'max_positions': 3,  # conservative": "'max_positions': 1,  # conservative (긴급)",
            "'max_positions': 5,  # balanced": "'max_positions': 2,  # balanced (긴급)",
        },
        "프리셋 전환": {
            "ACTIVE_PRESET = 'balanced'": "ACTIVE_PRESET = 'conservative'  # 🚨 긴급 전환",
            "ACTIVE_PRESET = 'aggressive'": "ACTIVE_PRESET = 'conservative'  # 🚨 긴급 전환",
        }
    }

    modified = original
    applied_count = 0

    for category, changes in modifications.items():
        print(f"\n   {category}:")
        for old, new in changes.items():
            if old in modified:
                modified = modified.replace(old, new)
                print(f"      ✅ {old} → {new}")
                applied_count += 1
            else:
                print(f"      ⚠️ 찾을 수 없음: {old}")

    # 3. 수정된 내용 저장
    print(f"\n3. 변경사항 저장 중... (총 {applied_count}개 수정)")

    try:
        with open('config.py', 'w', encoding='utf-8') as f:
            f.write(modified)

        print("✅ config.py 수정 완료")
    except Exception as e:
        print(f"❌ 저장 실패: {e}")
        print("   백업에서 복구하세요: config.py.backup")
        return

    # 4. 요약 리포트
    print("\n" + "="*60)
    print("📊 긴급 수정 완료 요약")
    print("="*60)
    print(f"✅ 총 {applied_count}개 항목 수정")
    print("\n주요 변경사항:")
    print("  1. 손절: 0.5~0.8% → 1.2~2.0% (완화)")
    print("  2. 진입: 4.0~5.0점 → 6.0~7.0점 (강화)")
    print("  3. 포지션: 3~5개 → 1~2개 (축소)")
    print("  4. 프리셋: Conservative로 강제 전환")
    print("\n⚠️ 다음 단계:")
    print("  1. 봇을 재시작하세요")
    print("  2. 테스트 모드로 1~2일 관찰")
    print("  3. 승률 40% 이상 확인 후 실전 투입")
    print("\n백업 파일: config.py.backup")
    print("="*60)

if __name__ == "__main__":
    print("\n⚠️ 이 스크립트는 config.py를 자동 수정합니다.")
    print("   계속하시겠습니까?")

    confirm = input("   (yes 입력): ").strip().lower()

    if confirm == 'yes':
        emergency_fix()
    else:
        print("취소되었습니다.")
