# check_ml_status.py

import os
from ml_signal_generator import MLSignalGenerator

print("\n" + "="*60)
print("🔍 ML 모델 상태 확인")
print("="*60)

# 파일 존재 여부
model_file = "ml_model_random_forest.pkl"
scaler_file = "ml_scaler.pkl"

print(f"\n📁 모델 파일:")
if os.path.exists(model_file):
    size = os.path.getsize(model_file) / 1024
    print(f"  ✅ {model_file} (크기: {size:.1f} KB)")
else:
    print(f"  ❌ {model_file} (없음)")

if os.path.exists(scaler_file):
    size = os.path.getsize(scaler_file) / 1024
    print(f"  ✅ {scaler_file} (크기: {size:.1f} KB)")
else:
    print(f"  ❌ {scaler_file} (없음)")

# 모델 로드 테스트
print(f"\n🤖 모델 로드 테스트:")
ml_gen = MLSignalGenerator(model_type='random_forest')

if ml_gen.is_trained:
    print(f"  ✅ 학습된 모델 사용 가능")
    print(f"  📊 특성 개수: {len(ml_gen.feature_names)}개")
    print(f"  🎯 모델 타입: {ml_gen.model_type}")
else:
    print(f"  ❌ 학습된 모델 없음 (학습 필요)")

print("="*60)