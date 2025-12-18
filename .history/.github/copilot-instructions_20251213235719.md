# 업비트 자동매매 봇 AI 코딩 가이드

## 🎯 프로젝트 개요
업비트(Upbit) 암호화폐 자동매매 봇 시스템 - 일 1.5% 목표 수익률, 멀티 시그널 통합 전략

## 🏗️ 핵심 아키텍처

### 주요 컴포넌트 계층구조
```
main_trading_bot.py (TradingBot)
├── improved_strategy.py (ImprovedStrategy) - 신호 생성 및 통합
│   ├── multi_timeframe_analyzer.py (MTF 분석)
│   ├── ml_signal_generator.py (머신러닝 예측)
│   └── market_condition_check.py (시장 분석)
├── risk_manager.py (RiskManager) - 리스크 관리 및 포지션 사이징
├── adaptive_preset_manager.py - 동적 전략 전환
├── partial_exit_manager.py - 부분 매도 자동화
├── pyramiding_manager.py - 추매 관리
├── averaging_down_manager.py - 물타기 관리
└── trade_history_manager.py - 거래 기록 및 통계
```

### 데이터 흐름 (핵심)
1. **신호 생성**: 3가지 독립 신호 → 가중 평균 (Technical 40% + MTF 40% + ML 20%)
2. **진입 결정**: 최종 점수 ≥ 프리셋별 기준점 (Conservative: 6.5, Balanced: 4.5, Aggressive: 3.8)
3. **포지션 크기**: Kelly Criterion 기반 계산 (승률 × 평균 손익비)
4. **모니터링**: 실시간 손절(-1.5%) / 부분 매도(+0.8%, +1.2%, +1.5%) / 익절(+2.0%)
5. **적응**: 연속 손실 2회 → 자동 보수적 전환

## ⚙️ 설정 시스템 (중요!)

### 프리셋 중심 아키텍처
**핵심**: [config.py](config.py)의 `STRATEGY_PRESETS`가 모든 설정을 지배합니다.
- `apply_preset(preset_name)` 함수로 전역 설정 덮어쓰기
- 기본값(`RISK_CONFIG`, `ADVANCED_CONFIG`)은 프리셋 적용 **전**에만 유효
- 활성 프리셋: `ACTIVE_PRESET` 변수 (기본: 'balanced')

### 프리셋 구조 예시
```python
'balanced': {
    'entry_score_threshold': 4.5,      # 진입 기준점
    'signal_weights': {                # 신호 가중치
        'technical': 0.40,
        'mtf': 0.50,
        'ml': 0.10
    },
    'max_positions': 5,                # 최대 동시 포지션
    'stop_loss': 0.010,                # 손절 비율
}
```

### 코드 수정 시 주의사항
- 설정값 읽을 때: 항상 프리셋 적용 **후**의 값 사용
- 새 설정 추가 시: `STRATEGY_PRESETS` 내 모든 프리셋에 값 추가
- 초기화 순서: `apply_preset()` → 클래스 인스턴스 생성

## 🔄 핵심 워크플로우

### 1. 진입 로직 (improved_strategy.py)
```python
# 3단계 체크
1. can_trade_today() - 거래 횟수, 쿨다운, 연속 손실
2. analyze_entry_signal() - 3가지 신호 통합
3. 최종 점수 ≥ entry_score_threshold
```

### 2. 신호 통합 패턴
```python
# 각 신호는 0~1 정규화된 점수 반환
technical_score = self._calculate_technical_score(...)  # 0.75
mtf_score = mtf_analyzer.analyze(symbol)['final_score']  # 0.68
ml_score = ml_generator.predict(symbol)['buy_probability']  # 0.62

# 가중 평균 (프리셋별 가중치)
final_score = (technical * W1 + mtf * W2 + ml * W3) * 10  # 10점 만점
```

### 3. 리스크 관리 패턴 (risk_manager.py)
- **초기 자본**: `initial_balance.txt` 파일에서 로드 (없으면 총 자산 계산)
- **Kelly Criterion**: `position_size = balance * kelly_fraction * max_position_size`
- **일일 손실 한도**: `daily_loss_limit` 초과 시 거래 중단

## 📋 코딩 컨벤션

### 로깅 스타일
```python
logger.info(f"✅ 매수 신호: {symbol} (점수: {score:.1f}/10)")
logger.warning(f"⚠️ 손절 발동: {symbol} ({loss_rate:.1%})")
logger.error(f"❌ API 오류: {e}")
```

### 파일 I/O 패턴
- JSON 파일: UTF-8 인코딩 필수 (`encoding='utf-8'`)
- 거래 기록: `trade_history.json` (TradeHistoryManager)
- 설정 저장: `initial_balance.txt`, `active_positions.json`

### 예외 처리
```python
try:
    df = pyupbit.get_ohlcv(ticker, interval='minute60', count=200)
    if df is None or len(df) < 50:
        return None  # 데이터 부족 시 None 반환
except Exception as e:
    logger.error(f"데이터 수집 실패: {e}")
    return None
```

## 🧪 테스트 & 디버깅

### 백테스트 실행
```bash
python tests/paper_trading_minutes.py  # 분봉 기반 시뮬레이션
python tests/test_backtest.py          # 일봉 기반 백테스트
```

### Dashboard 실행
```bash
python dashboard.py  # Streamlit 대시보드 (포트 8501)
```

### ML 모델 재학습
```python
from ml_signal_generator import MLSignalGenerator
ml_gen = MLSignalGenerator()
ml_gen.train_model(['BTC', 'ETH', 'XRP'])  # 2000개 1시간봉 학습
```

## 🔍 주요 디버깅 포인트

### 진입 안 될 때
1. [improved_strategy.py](improved_strategy.py) `can_trade_today()` 로그 확인
2. `entry_score_threshold` vs `final_score` 비교
3. 프리셋 확인: `logger.info(f"활성 프리셋: {ACTIVE_PRESET}")`

### 손익 계산 오류
- [risk_manager.py](risk_manager.py) `initial_balance` vs `current_balance` 확인
- `initial_balance.txt` 수동 편집 가능 (리셋 필요 시)

### MTF 신호 문제
- [multi_timeframe_analyzer.py](multi_timeframe_analyzer.py) 캐싱: 5분(300초) 유효
- `df is None` 체크 - 업비트 API 제한 가능성

## 📌 중요 파일 참조

| 파일 | 용도 | 주요 함수/클래스 |
|------|------|------------------|
| [README.md](README.md) | 전략 로직 상세 문서 | 의사결정 트리, 신호 점수 계산식 |
| [config.py](config.py) | 모든 설정의 중앙 관리 | `STRATEGY_PRESETS`, `apply_preset()` |
| [main_trading_bot.py](main_trading_bot.py) | 거래 실행 엔진 | `TradingBot.run_trading_cycle()` |
| [improved_strategy.py](improved_strategy.py) | 신호 통합 및 진입 결정 | `analyze_entry_signal()` |
| [risk_manager.py](risk_manager.py) | 포지션 사이징, 손실 관리 | `calculate_position_size()` |

## 🚫 안티패턴

❌ **하지 말 것**:
- 프리셋 무시하고 직접 `RISK_CONFIG` 수정
- `apply_preset()` 없이 설정값 변경
- JSON 파일에 한글 포함 시 `ensure_ascii=False` 누락
- 업비트 API 호출 시 에러 핸들링 없음 (티커 제한: 초당 10회)

✅ **권장사항**:
- 새 전략 테스트 시 프리셋 복사 후 수정
- 설정 변경 후 봇 재시작 필수
- 로그 파일(`trading.log`) 정기 확인
- Dashboard로 실시간 성과 모니터링
