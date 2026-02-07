# train_advanced_ml.py
# 고급 ML 모델 학습 스크립트

import sys
import os
import logging
from datetime import datetime

# Windows 콘솔 UTF-8 설정
if sys.platform == 'win32':
    os.system('chcp 65001 > nul 2>&1')
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('ml_training.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

def main():
    print("=" * 60)
    print("[Advanced ML] Model Training Start")
    print("=" * 60)
    print(f"시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # 설정 로드
    try:
        from config import TRADING_PAIRS
        print(f"[*] Training coins: {', '.join(TRADING_PAIRS)}")
    except ImportError:
        TRADING_PAIRS = ['BTC', 'ETH', 'XRP', 'SOL', 'DOGE']
        print(f"[!] config.py load failed, using default: {', '.join(TRADING_PAIRS)}")

    print()

    # 고급 ML 엔진 로드
    try:
        from advanced_ml_engine import AdvancedMLEngine
        print("[OK] Advanced ML Engine loaded")
    except ImportError as e:
        print(f"[ERROR] Advanced ML Engine load failed: {e}")
        print("\nInstall required libraries:")
        print("  pip install xgboost lightgbm torch")
        return

    print()

    # 엔진 초기화 및 학습
    engine = AdvancedMLEngine()

    print("[*] Model training started (takes 5-10 minutes)...")
    print()

    try:
        results = engine.train(TRADING_PAIRS, retrain=True)

        print()
        print("=" * 60)
        print("[*] Training Results Summary")
        print("=" * 60)

        if 'ensemble' in results:
            print("\n[Ensemble Model]")
            for model_name, metrics in results['ensemble'].items():
                if isinstance(metrics, dict):
                    print(f"  {model_name.upper()}:")
                    print(f"    Accuracy: {metrics['accuracy']:.1%}")
                    print(f"    Precision: {metrics['precision']:.1%}")
                    print(f"    F1: {metrics['f1']:.1%}")

        if 'lstm' in results:
            print("\n[LSTM Model]")
            lstm = results['lstm']
            print(f"  Accuracy: {lstm['accuracy']:.1%}")
            print(f"  Precision: {lstm['precision']:.1%}")
            print(f"  F1: {lstm['f1']:.1%}")

        print()
        print("=" * 60)
        print("[OK] Training Complete!")
        print(f"Model saved to: ml_models/")
        print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

    except Exception as e:
        logger.error(f"Training failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
