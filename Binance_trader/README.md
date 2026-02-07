# Binance Trader v2.4 (Gradient Scoring + Unified Dashboard)

바이낸스 선물 자동 트레이딩 봇 (그래디언트 기술지표 + 서버사이드 손절 + 통합 대시보드)

## 주요 기능

### 핵심 기능
- **선물 거래 (LONG/SHORT)**: 상승/하락 양방향 거래, 레버리지 설정
- **고급 ML 예측**: XGBoost + LightGBM + RandomForest 앙상블
- **분할 익절**: 수익 구간에서 일부 청산 후 나머지로 추가 수익 추구
- **적응형 익절 (ATR 기반)**: 시장 변동성에 따라 익절 타이밍 자동 조절
- **트레일링 스탑**: 수익 보호를 위한 추적 손절
- **시장 상태 분석**: 급락/급등장 감지 및 진입 차단

### v2.4 신규 기능
- **그래디언트 기술지표**: 이진(BUY/SELL) → 연속값(-1.0~+1.0) 점수로 개선
- **ccxt 4.4+ 업그레이드**: 바이낸스 Algo Order API 지원 (손절 -4120 오류 해결)
- **통합 대시보드**: 업비트+바이낸스 한 페이지에서 모니터링 (port 5002)

### v2.3 기능
- **서버사이드 손절**: 봇 종료/크래시 시에도 거래소에서 자동 손절 (STOP_MARKET)
- **텔레그램 알림**: 봇 상태, 포지션 진입/청산 실시간 알림
- **거래소 동기화**: 시작 시 실제 거래소 포지션과 자동 동기화
- **추세 반전 청산**: 반대 추세 감지 시 기존 포지션 강제 청산
- **Docker/NAS 지원**: Synology NAS 등에서 24시간 운영

---

## 설치 및 실행

### Windows (EXE)
1. `BinanceTrader.exe` 더블클릭
2. 같은 폴더에 `.env` 파일 생성 (API 키 설정)

### EXE 빌드 시 체크리스트
빌드 후 Release 폴더에 다음 파일들을 함께 복사:
- `README.md` - 사용 설명서
- `TUNING_GUIDE.md` - 설정 튜닝 가이드
- `binance_settings.json` - 설정 파일
- `.env.example` - 환경변수 예시 파일

### Docker (NAS/서버)
```bash
# 이미지 빌드
docker-compose build

# 컨테이너 실행
docker-compose up -d

# 로그 확인
docker logs -f binance-trader
```

---

## 설정 방법

### 1. API 키 설정 (.env 파일)

**중요**: API 키는 보안을 위해 `.env` 파일에서 관리합니다.

```env
# .env 파일 (따옴표 없이 입력)
BINANCE_API_KEY=여기에_API_KEY_입력
BINANCE_API_SECRET=여기에_SECRET_KEY_입력

# 텔레그램 알림 (선택)
TELEGRAM_BOT_TOKEN=봇토큰
TELEGRAM_CHAT_ID=채팅ID
```

**주의**: Docker 환경에서는 따옴표를 사용하면 안 됩니다!

### 2. 실행 모드 (binance_settings.json)
```json
"mode": "simulation"   // 시뮬레이션 (가상 거래)
"mode": "testnet"      // 테스트넷 (데모 API)
"mode": "live"         // 실전 (실제 거래)
```

### 3. 거래 대상
```json
"trading": {
  "symbols": ["BTC/USDT", "ETH/USDT", "SOL/USDT", "DOGE/USDT"]
}
```

### 4. 리스크 관리
```json
"risk": {
  "max_position_size": 0.25,  // 포지션 크기 25%
  "leverage": 3,              // 레버리지 3x
  "stop_loss": 0.02,          // 손절 2%
  "take_profit": 0.04,        // 익절 4%
  "daily_loss_limit": 0.05,   // 일일 손실 한도 5%
  "max_positions": 3          // 최대 동시 포지션
}
```

### 5. 트레일링 스탑
```json
"trailing_stop": {
  "enabled": true,
  "activation": 0.02,   // 2% 수익시 활성화
  "distance": 0.01      // 1% 거리 유지
}
```

### 6. 분할 익절
```json
"partial_exit": {
  "enabled": true,
  "trigger_profit": 0.015,  // 1.5% 수익시 발동
  "exit_ratio": 0.5,        // 50% 청산
  "adaptive": true          // ATR 기반 적응형
}
```

### 7. 추세 반전 청산
```json
"reverse_exit": {
  "enabled": true,
  "score_threshold": 0.3,   // 반대 점수 임계값
  "min_hold_minutes": 30    // 최소 보유 시간
}
```

### 8. ML 설정
```json
"ml": {
  "enabled": true,
  "min_probability": 0.6,
  "weight": 0.3
}
```

---

## 그래디언트 기술지표 (v2.4)

### 기존 방식 (이진)
```
RSI > 70 → SELL (+1)
RSI < 30 → BUY (-1)
그 외 → None (0)
```
**문제**: 하락장에서 RSI 40~60 구간이면 항상 tech_score=0 → SHORT 진입 불가

### 개선 방식 (그래디언트)
```
RSI 점수 = (50 - RSI) / 30  → -1.0 ~ +1.0 연속값
예: RSI 65 → (50-65)/30 = -0.5 (약한 매도 신호)
예: RSI 35 → (50-35)/30 = +0.5 (약한 매수 신호)
```

### 5개 지표 그래디언트 점수
| 지표 | 계산식 | 범위 |
|------|--------|------|
| RSI | (50 - RSI) / 30 | -1.0 ~ +1.0 |
| MA Cross | (MA20 - MA50) / MA50 * 50 | -1.0 ~ +1.0 |
| MACD | histogram / price * 1000 | -1.0 ~ +1.0 |
| Bollinger | (0.5 - %B) * 2 | -1.0 ~ +1.0 |
| Stochastic | (50 - K) / 50 | -1.0 ~ +1.0 |

**최종 tech_score** = 5개 지표 평균 → LONG(+) / SHORT(-) 방향 결정

---

## 텔레그램 알림 설정

### 1. 봇 토큰 발급
1. Telegram에서 `@BotFather` 검색
2. `/newbot` 명령어 입력
3. 봇 이름 설정 후 토큰 복사

### 2. Chat ID 확인
1. 생성한 봇에게 아무 메시지 전송
2. `https://api.telegram.org/bot{토큰}/getUpdates` 접속
3. `chat.id` 값 확인

### 3. .env 파일에 추가
```env
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=987654321
```

### 알림 종류
- 봇 시작/종료
- 포지션 진입 (코인, 방향, 가격, 수량)
- 포지션 청산 (수익률, 손익)
- 120초마다 상태 업데이트 (잔고, 포지션)

---

## Docker 배포 (Synology NAS)

### 필요 파일
```
binance-trader/
├── binance_trader.py
├── binance_dashboard.py
├── binance_ml_model.pkl
├── binance_advanced_ml.pkl
├── binance_settings.json
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── .env
```

### docker-compose.yml
```yaml
version: '3.8'
services:
  binance-trader:
    build: .
    container_name: binance-trader
    restart: unless-stopped
    env_file:
      - .env
    volumes:
      - ./binance_settings.json:/app/binance_settings.json:ro
      - ./data:/app/data
```

### 배포 명령어
```bash
# SSH 접속
ssh -p 포트 사용자@NAS_IP

# 폴더 이동
cd /volume1/docker/binance-trader

# 빌드 및 실행
sudo docker-compose build --no-cache
sudo docker-compose up -d

# 로그 확인
sudo docker logs -f binance-trader

# 재시작
sudo docker-compose restart

# 중지
sudo docker-compose down
```

### 코드 업데이트 시 (재빌드)

포지션이 열려있는 상태에서도 재빌드 가능합니다.

**안전한 이유:**
- 서버사이드 손절(STOP_MARKET)이 거래소에 등록되어 있어 봇이 꺼져도 손절 보호됨
- 재시작 시 거래소 포지션 자동 동기화

**주의:**
- 봇이 꺼진 동안 익절/트레일링 스탑은 작동하지 않음
- 가능한 빠르게 재빌드 완료할 것

```bash
# 1. NAS에 변경 파일 복사 (PC에서)
#    BinanceTrader_Nas/ 폴더의 파일을 NAS로 전송

# 2. SSH 접속
ssh -p 포트 사용자@NAS_IP
ssh -p macjoocan84@211.222.212.53
cd /volume1/docker/binance-trader

# 3. 중지 → 재빌드 → 시작 (한 줄로 실행)
sudo docker-compose down && sudo docker-compose build --no-cache && sudo docker-compose up -d

# 4. 정상 동작 확인
sudo docker logs -f binance-trader
```

**settings만 변경한 경우:**
- `binance_settings.json`은 볼륨 마운트(:ro)이므로 재빌드 없이 재시작만 하면 됨
```bash
sudo docker-compose restart
```

**코드(.py) 변경한 경우:**
- 이미지에 포함된 파일이므로 반드시 재빌드 필요

---

### 환경변수 변경 시
```bash
# .env 파일 수정 후
sudo docker-compose down
sudo docker-compose up -d
```

---

## 포지션 상태 표시

| 표시 | 의미 |
|------|------|
| `[T]` | 트레일링 스탑 활성화 |
| `[BE]` | 본전 보호 모드 (손절가 = 진입가) |
| `[SL]` | 서버사이드 손절 설정됨 |
| `잔량:0.003` | 분할 익절 후 남은 수량 |

---

## 문제 해결

### API 키 오류 (-2008, -2015)
- `.env` 파일에 따옴표 없이 입력했는지 확인
- Binance에서 **Futures 거래 권한** 활성화 확인
- IP 제한 설정 시 서버/NAS IP 추가

### 거래가 안 됨
- `entry_score_threshold`를 낮춰보세요 (0.2 → 0.1)
- `allow_sideways_entry`를 `true`로 설정
- 잔고가 최소 주문 금액(100 USDT) 이상인지 확인

### ML 모델 오류
- PC와 Docker의 scikit-learn 버전을 맞춰야 합니다
- PC 버전 확인: `pip show scikit-learn`
- requirements.txt에 동일 버전 지정: `scikit-learn==1.3.0`

### 타임스탬프 오류 (-1021)
- 자동으로 시간 동기화됩니다
- 지속되면 서버 시간 확인

### Docker 로그 안 보임
- SSH에서 확인: `sudo docker logs -f binance-trader`
- 컨테이너 상태: `sudo docker ps -a`

---

## 버전 히스토리

| 버전 | 주요 변경사항 |
|------|--------------|
| v2.4 | 그래디언트 기술지표, ccxt 4.4+ 업그레이드, 통합 대시보드 |
| v2.3 | 서버사이드 손절, 텔레그램 알림, Docker 지원, 거래소 동기화 |
| v2.2 | 고급 ML (XGBoost+LightGBM), 추세 반전 청산 |
| v2.1 | 분할 익절, 적응형(ATR) 익절, 시장 상태 분석 |
| v2.0 | 선물 거래, 트레일링 스탑, 기본 ML |

---

## 주의사항

- 선물 거래는 **원금 손실 위험**이 있습니다
- 시뮬레이션 모드로 충분히 테스트 후 실전 사용
- API 키는 절대 타인에게 공유하지 마세요
- 레버리지 설정에 주의하세요
- `.env` 파일은 `.gitignore`에 추가하세요

---

*Binance Trader v2.4 - Gradient Scoring + Unified Dashboard Edition*
