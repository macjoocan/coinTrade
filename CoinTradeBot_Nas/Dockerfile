# Upbit Trader Docker Image
# Synology NAS (Intel x86_64) 호환

FROM python:3.11-slim

# 시간대 설정
ENV TZ=Asia/Seoul
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 작업 디렉토리
WORKDIR /app

# 시스템 의존성 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Python 패키지 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 복사
COPY main_trading_bot.py .
COPY config.py .
COPY improved_strategy.py .
COPY risk_manager.py .
COPY position_recovery.py .
COPY daily_summary.py .
COPY momentum_scanner_improved.py .
COPY multi_timeframe_analyzer.py .
COPY ml_signal_generator.py .
COPY market_condition_check.py .
COPY rapid_market_detector.py .
COPY adaptive_risk_manager.py .
COPY adaptive_score_manager.py .
COPY advanced_ml_engine.py .
COPY partial_exit_manager.py .
COPY pyramiding_manager.py .
COPY averaging_down_manager.py .
COPY slippage_manager.py .
COPY volatility_monitor.py .
COPY swing_holding_enhancer.py .
COPY trade_history_manager.py .
COPY score_performance_tracker.py .
COPY adaptive_preset_manager.py .
COPY auto_optimizer.py .
COPY train_advanced_ml.py .
COPY upbit_web_dashboard.py .
COPY unified_dashboard.py .

# ML 모델: 복사하지 않음 - 봇 시작 시 자동 학습
RUN mkdir -p ml_models

# 데이터 볼륨 (로그, 포지션, 거래내역)
VOLUME ["/app/data"]

# 실행
CMD ["python", "-u", "main_trading_bot.py"]
