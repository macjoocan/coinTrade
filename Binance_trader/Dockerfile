# Binance Trader Docker Image
# Synology DS220+ (Intel x86_64) 호환

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
COPY binance_trader.py .
COPY binance_dashboard.py .
COPY binance_web_dashboard.py .
COPY binance_ml_model.pkl .
COPY binance_advanced_ml.pkl .

# 데이터 볼륨 (설정, 로그, 포지션)
VOLUME ["/app/data"]

# 실행
CMD ["python", "-u", "binance_trader.py"]
