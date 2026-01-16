# ⚙️ Config 최적화 완료 요약

**작성일**: 2026-01-17
**목적**: 스윙 트레이딩 및 3단계 점수 최적화에 맞게 설정 조정

---

## 📊 변경된 설정

### 1. STRATEGY_CONFIG - 스윙 트레이딩 최적화

#### Before (스캘핑 지향)
```python
STRATEGY_CONFIG = {
    'min_profit_target': 0.025,      # 2.5%
    'max_trades_per_day': 50,        # 하루 50회
    'min_hold_time': 600,            # 10분
    'trade_cooldown_minutes': 60,    # 1시간
}
```

#### After (스윙 트레이딩 지향)
```python
STRATEGY_CONFIG = {
    'min_profit_target': 0.030,      # 3.0% ✅
    'max_trades_per_day': 20,        # 하루 20회 ✅
    'min_hold_time': 43200,          # 12시간 ✅
    'trade_cooldown_minutes': 120,   # 2시간 ✅
}
```

**변경 이유**:
- `min_profit_target`: 2.5% → 3.0%
  - 스윙은 큰 수익 목표
  - 데이터: 3%+ 수익이 목표

- `max_trades_per_day`: 50 → 20
  - 스윙은 빈도보다 질
  - 하루 2~4회 진입이 이상적

- `min_hold_time`: 600초(10분) → 43200초(12시간)
  - 스윙 최소 보유 시간
  - 데이터: 12h+ 보유 시 승률 81.8%

- `trade_cooldown_minutes`: 60 → 120
  - 충분한 쿨다운으로 과도한 거래 방지

---

### 2. SWING_HOLDING_CONFIG - 신규 추가 ✅

```python
SWING_HOLDING_CONFIG = {
    'enabled': True,                      # 활성화
    'min_swing_hold_hours': 12,           # 최소 12시간 보유
    'ideal_swing_hold_hours': 24,         # 이상적 24시간
    'min_profit_for_early_exit': 0.025,   # 조기 익절 2.5%
    'good_profit_threshold': 0.030,       # 좋은 수익 3.0%
    'excellent_profit_threshold': 0.050,  # 탁월한 수익 5.0%
    'stop_loss_threshold': -0.015,        # 손절 -1.5%
}
```

**목적**:
- 조기 익절 방지 (소액 수익에서 매도 차단)
- 최소 보유 시간 강제
- 큰 수익 포착 기회 증가

---

### 3. STRATEGY_PRESETS - 진입 점수 조정 (3단계 최적화)

#### Conservative (현재 사용 중)
```python
'conservative': {
    'entry_score_threshold': 5.5,  # ✅ 6.0 → 5.5 (1단계)
    'mtf_min_score': 6.0,          # ✅ 6.5 → 6.0
    'mtf_min_consensus': 0.70,     # ✅ 0.75 → 0.70
    'ml_min_probability': 0.65,    # ✅ 0.70 → 0.65
    'stop_loss': 0.015,            # 1.5% 유지
    'max_positions': 1,            # 1개 유지
}
```

**변경 이유**:
- 최근 7일 매수 0회 → 진입 점수 너무 높음
- 5.5점으로 하향하여 거래 빈도 확보
- 데이터 수집 후 최적값 찾기 (3단계 전략)

---

## 🎯 설정 간 상호 작용

### 1. 스윙 홀딩 시스템 우선순위

```
손절 (-1.5%) → 즉시 허용 (최우선)
    ↓
큰 수익 (5%+) → 즉시 허용
    ↓
조기 익절 (2.5%+) + 보유 < 12h → 허용
    ↓
중간 수익 (2~3%) + 보유 < 12h → 거부 ⬅️ 스윙 홀딩
    ↓
소액 수익 (0~2%) + 보유 < 12h → 거부 ⬅️ 스윙 홀딩
    ↓
보유 >= 12h + 수익 >= 2% → 허용
```

### 2. min_hold_time vs 스윙 홀딩

```python
# STRATEGY_CONFIG
min_hold_time: 43200  # 12시간 (전략 레벨)

# SWING_HOLDING_CONFIG
min_swing_hold_hours: 12  # 12시간 (스윙 홀딩 레벨)
```

**차이점**:
- `min_hold_time`: 전략의 can_exit_position() 체크
- `min_swing_hold_hours`: 스윙 홀딩의 should_allow_exit() 체크

**결합 효과**:
- 두 시스템이 모두 12시간 강제
- 이중 안전장치
- 조기 익절 완전 차단

---

## 📊 예상 효과

### Before (구 설정)
```
진입 점수: 6.0 (너무 높음)
최소 보유: 10분 (스캘핑)
목표 수익: 2.5%
하루 거래: 0~1회 (진입 없음)
평균 보유: 2.2시간
승률: 61.9%
평균 수익: -0.11%
```

### After (새 설정)
```
진입 점수: 5.5 (현실적) ✅
최소 보유: 12시간 (스윙) ✅
목표 수익: 3.0% ✅
예상 거래: 주 1~3회
예상 보유: 12~18시간
예상 승률: 70~75%
예상 수익: +0.8~1.2%
```

---

## 🔍 설정별 세부 설명

### min_hold_time: 43200초 (12시간)

**적용 위치**:
```python
# improved_strategy.py
def can_exit_position(self, symbol, exit_type='normal'):
    elapsed_time = time.time() - self.position_entry_time[symbol]

    if exit_type == 'stop_loss':
        return True  # 손절은 즉시

    # 일반 익절은 min_hold_time 체크
    if elapsed_time < STRATEGY_CONFIG['min_hold_time']:
        return False  # 12시간 미달 거부
```

**효과**:
- 전략 레벨에서 1차 필터링
- 12시간 미만 매도 원천 차단

---

### min_profit_target: 0.030 (3.0%)

**적용 위치**:
```python
# improved_strategy.py
def check_profit_target(self, entry_price, current_price):
    pnl_rate = (current_price - entry_price) / entry_price
    return pnl_rate >= self.min_profit_target  # 3.0%
```

**효과**:
- 목표 수익 신호 발생 기준
- 스윙 홀딩과 결합하여 최종 판단

---

### max_trades_per_day: 20

**적용 위치**:
```python
# improved_strategy.py
def can_trade_today(self):
    today = datetime.now().strftime('%Y-%m-%d')
    return self.daily_trades[today] < self.max_trades_per_day
```

**효과**:
- 과도한 거래 방지
- 스윙 트레이딩에 적합한 빈도

---

### trade_cooldown_minutes: 120 (2시간)

**적용 위치**:
```python
# improved_strategy.py (스마트 쿨다운)
self.loss_cooldown = 7200  # 손실 후 2시간
self.win_cooldown = 600    # 수익 후 10분
```

**효과**:
- 손실 후 충분한 쿨다운
- 감정적 거래 방지
- 시장 안정화 대기

---

## ⚙️ 추가 고려사항

### 1. 진입 점수 3단계 최적화

**현재**: 1단계 (5.5점)
```
24시간 내 진입 있음?
→ Yes: 유지 (3~5일 데이터 수집)
→ No: 2단계로 진행 (5.0점)
```

**설정 조정**:
```python
# config.py
'conservative': {
    'entry_score_threshold': 5.5,  # 현재 1단계
}

# 필요시 수동 조정:
# 1단계 → 2단계: 5.5 → 5.0
# 2단계 → 3단계: 데이터 기반 최적값 (4.8~5.5)
```

---

### 2. 변동성 고려

**현재 설정**:
```python
VOLATILITY_CONFIG = {
    'enabled': True,
    'dynamic_adjustment': True,  # 변동성에 따라 자동 조정
}
```

**작동**:
- 고변동성: 손절 1.3~1.5배
- 저변동성: 손절 0.9배
- 스윙 홀딩과 독립적 작동

---

### 3. 슬리피지 관리

**현재 설정**:
```python
SLIPPAGE_CONFIG = {
    'enabled': True,
    'max_slippage_rate': 0.003,  # 0.3%
}
```

**효과**:
- 진입 시 슬리피지 체크
- 0.3% 초과 시 경고 또는 지정가 사용
- 스윙에서는 영향 적음 (보유 시간 길어서)

---

## 📋 설정 체크리스트

### 봇 시작 전 확인
- [x] STRATEGY_CONFIG 스윙 최적화 완료
- [x] SWING_HOLDING_CONFIG 추가 완료
- [x] Conservative 프리셋 5.5점 적용
- [x] main_trading_bot.py import 추가
- [x] SwingHoldingEnhancer 설정 전달

### 봇 시작 후 확인
- [ ] 초기화 로그 확인
  - "스윙 홀딩 강화 시스템 활성화"
  - "최소 보유: 12시간"
- [ ] 첫 진입 발생 시
  - 진입 점수 5.5~6.5 범위?
- [ ] 첫 익절 시도 시
  - 스윙 홀딩 로그 확인
  - "스윙 최소 보유 미달" 메시지

### 24시간 후 확인
- [ ] 진입 횟수: 1~2회?
- [ ] 평균 보유 시간: 10시간 이상?
- [ ] 소액 익절 차단 확인

### 1주일 후 확인
- [ ] 총 거래: 5~15회?
- [ ] 평균 보유: 12~18시간?
- [ ] 승률: 60% 이상?
- [ ] 평균 수익: 양수?

---

## 🎯 설정 튜닝 가이드

### 거래가 너무 없으면 (0회/24h)

**진입 점수 추가 하향**:
```python
'entry_score_threshold': 5.5 → 5.0  # 2단계
```

### 거래가 너무 많으면 (10회+/24h)

**진입 점수 상향**:
```python
'entry_score_threshold': 5.5 → 6.0  # 복구
```

### 보유 시간이 너무 짧으면

**스윙 홀딩 강화**:
```python
SWING_HOLDING_CONFIG = {
    'min_swing_hold_hours': 12 → 16,  # 더 길게
    'min_profit_for_early_exit': 0.025 → 0.030,  # 더 엄격
}
```

### 승률이 낮으면 (40% 미만)

**진입 기준 강화**:
```python
'entry_score_threshold': 5.5 → 6.0,
'mtf_min_score': 6.0 → 6.5,
```

---

## 📝 변경 이력

### 2026-01-17
- ✅ STRATEGY_CONFIG 스윙 최적화
  - min_profit_target: 2.5% → 3.0%
  - max_trades_per_day: 50 → 20
  - min_hold_time: 600s → 43200s (12h)
  - trade_cooldown_minutes: 60 → 120

- ✅ SWING_HOLDING_CONFIG 신규 추가
  - 최소 보유 12시간
  - 조기 익절 방지 로직

- ✅ Conservative 프리셋 조정
  - entry_score_threshold: 6.0 → 5.5 (3단계 1단계)

---

**작성일**: 2026-01-17
**상태**: ✅ 설정 최적화 완료
**적용**: main_trading_bot.py에 반영 완료
**테스트**: 봇 재시작 시 자동 적용
