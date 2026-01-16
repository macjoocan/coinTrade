# 🚨 긴급 조치 방안 - 승률 5% 회복 플랜

## 📊 현재 상황
- 승률: 5% (목표 60%)
- 최근 거래: 전량 손실
- 평균 손실: -0.7%
- 판단: **즉시 거래 중단 및 설정 재조정 필요**

---

## 🛑 1단계: 즉시 조치 (지금 바로!)

### A. **거래 즉시 중단**
```python
# 방법 1: 봇 종료 (Ctrl+C)
# 방법 2: config.py에서 일시 중단

EMERGENCY_STOP = True  # ← 이것만 True로 변경
```

### B. **현재 포지션 정리**
- 손절가 근처 포지션: 즉시 청산
- -1% 이상 손실: 손절 실행
- 수익 포지션: 보유

---

## ⚙️ 2단계: 설정 긴급 수정

### 1. 손절 완화 (가장 중요!)
```python
# config.py - STRATEGY_PRESETS 수정

'conservative': {
    'stop_loss': 0.012,  # 0.005 → 0.012 (1.2%)
},

'balanced': {
    'stop_loss': 0.015,  # 0.006 → 0.015 (1.5%)
},

'aggressive': {
    'stop_loss': 0.020,  # 0.008 → 0.020 (2.0%)
}
```

**이유**:
- 현재 시장 변동성: 1일 변동 ±0.5~1.0%
- 손절 0.5~0.8%는 너무 타이트 → 정상 변동도 손절
- 1.2~2.0%로 완화하면 생존율 상승

---

### 2. 진입 조건 강화
```python
# config.py

'conservative': {
    'entry_score_threshold': 7.0,  # 5.0 → 7.0
},

'balanced': {
    'entry_score_threshold': 6.5,  # 4.5 → 6.5
},

'aggressive': {
    'entry_score_threshold': 6.0,  # 4.0 → 6.0
}
```

**이유**:
- 하락장/횡보장에서는 높은 점수에만 진입
- 승률 회복 우선 (수익률은 나중에)

---

### 3. 최대 포지션 축소
```python
'conservative': {
    'max_positions': 1,  # 3 → 1 (집중!)
},

'balanced': {
    'max_positions': 2,  # 5 → 2
},
```

**이유**:
- 여러 종목에 분산 → 모두 손실
- 집중 투자로 신중하게

---

### 4. 활성 프리셋 변경
```python
# config.py 맨 위

ACTIVE_PRESET = 'conservative'  # 'balanced' → 'conservative'
```

**이유**:
- 현재는 생존이 최우선
- Conservative로 전환하여 리스크 최소화

---

## 🔍 3단계: 시장 상황 재분석 (1~2일 소요)

### A. 테스트 모드로 관찰
```bash
python main_trading_bot.py
# 선택: 1. 테스트 모드

# 1~2일 동안 신호만 확인
# 승률 예측이 40% 이상일 때만 재개
```

### B. 체크리스트
- [ ] BTC가 상승 추세로 전환?
- [ ] 주요 알트코인 3개 이상 상승?
- [ ] 거래량이 증가 추세?
- [ ] RSI가 30~70 범위?
- [ ] 테스트 모드에서 예상 승률 40% 이상?

**모두 체크되면 실전 재개**

---

## 📈 4단계: 점진적 재개

### Phase 1: 소액 재시작 (자본의 10%)
```python
# 1~2일 운영
# 목표: 승률 40% 이상 달성
```

### Phase 2: 자본 확대 (30%)
```python
# 승률 40% 달성 후
# 3~5일 운영
# 목표: 승률 50% 이상
```

### Phase 3: 전액 투입 (100%)
```python
# 승률 50% 달성 후
# 정상 운영
```

---

## 💡 추가 개선 사항

### 1. 시장 필터 추가
```python
# improved_strategy.py에 추가

def is_market_favorable(self):
    """시장 상황 확인"""
    from market_condition_check import MarketAnalyzer
    analyzer = MarketAnalyzer()
    condition = analyzer.analyze_market(TRADING_PAIRS)

    if condition == 'bearish':
        return False, "하락장 - 거래 중단"

    return True, "시장 OK"
```

### 2. 연속 손실 자동 중단
```python
# main_trading_bot.py - run() 메서드에 추가

if self.risk_manager.consecutive_losses >= 3:
    logger.error("🚨 연속 3회 손실 - 자동 중단")
    break  # 봇 종료
```

### 3. 변동성 체크 강화
```python
# 변동성이 높은 날은 거래 스킵
if self.volatility_monitor:
    market_vol, grade = self.volatility_monitor.get_market_volatility(TRADING_PAIRS)

    if grade in ['high', 'extreme']:
        logger.warning("고변동성 - 거래 스킵")
        continue
```

---

## 📋 체크리스트

### 즉시 실행
- [ ] 봇 중단 (Ctrl+C)
- [ ] 손실 포지션 청산
- [ ] config.py 수정 (손절 완화, 진입 강화)
- [ ] ACTIVE_PRESET = 'conservative' 변경
- [ ] 테스트 모드로 1~2일 관찰

### 1~2일 후
- [ ] 시장 회복 확인
- [ ] 테스트 모드 승률 40% 이상 확인
- [ ] 소액으로 실전 재개

### 1주일 후
- [ ] 승률 40% 이상 유지 확인
- [ ] 점진적 자본 확대
- [ ] 정상 운영 복귀

---

## 🎯 예상 효과

### 현재 설정 (수정 전)
```
손절: -0.6%
진입: 4.5점
승률: 5%
→ 결과: 지속적 손실
```

### 수정 후
```
손절: -1.5%
진입: 6.5점
승률: 45~55% (예상)
→ 결과: 생존 + 점진적 회복
```

---

## ⚠️ 중요한 원칙

1. **생존이 최우선**
   - 승률 < 30%: 즉시 중단
   - 일일 손실 -3% 초과: 즉시 중단

2. **시장을 이길 수 없다**
   - 하락장에서는 쉬어가기
   - 상승장을 기다리기

3. **설정은 시장에 맞춰 조정**
   - 변동성 높음 → 손절 완화
   - 하락장 → 진입 강화
   - 상승장 → 공격적 전환

---

**작성일**: 2026-01-15
**긴급도**: 🔴 최고
**실행 시점**: 즉시
