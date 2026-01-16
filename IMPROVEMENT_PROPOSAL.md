# 🎯 손익비 개선 제안서

## 📊 현재 문제 진단

**증상**: 승률은 높지만 전체 수익은 낮음 또는 손실
**원인**: 손익비 불균형 (작은 수익 vs 큰 손실)

```
현재 설정:
- 목표 수익: +0.8% ~ +2.0%
- 손절: -1.0% ~ -1.8% (물타기 시)
- 손익비: 약 1:1 (불리함)

이상적인 설정:
- 손익비: 최소 2:1 (수익 2, 손실 1)
```

---

## 🔧 개선 방안

### **방안 1: 손절 강화 + 익절 확대 (권장)**

**핵심**: 손실은 빠르게 자르고, 수익은 충분히 끌고 간다

#### 1-1. 손절 타이트하게 조정

```python
# config.py 수정
STRATEGY_PRESETS = {
    'balanced': {
        'stop_loss': 0.006,  # 기존 0.010 → 0.006 (0.6%)
        # ... 기타 설정
    }
}

AVERAGING_DOWN_CONFIG = {
    'enabled': False,  # 물타기 비활성화 (손실 확대 방지)
    # 또는 물타기를 유지하되:
    'max_averaging_count': 1,  # 최대 1회로 제한
    'trigger_loss_rate': -0.004,  # -0.4%에서만 발동 (더 빠르게)
}
```

#### 1-2. 익절 목표 상향

```python
# config.py 수정
STRATEGY_CONFIG = {
    'min_profit_target': 0.025,  # 기존 0.02 → 0.025 (2.5%)
}
```

#### 1-3. 추적 손절 완화 (수익 더 끌기)

```python
# risk_manager.py:210-222 수정
def check_trailing_stop(self, symbol, current_price):
    # ... (기존 코드)

    # ✅ 수정: 추적 손절 기준 완화
    trailing_pct = None
    if profit_rate >= 0.040:      # 4% 이상: 1.0% 하락까지 허용
        trailing_pct = 0.010
    elif profit_rate >= 0.030:    # 3% 이상: 0.8% 하락까지 허용
        trailing_pct = 0.008
    elif profit_rate >= 0.020:    # 2% 이상: 0.6% 하락까지 허용
        trailing_pct = 0.006
    elif profit_rate >= 0.015:    # 1.5% 이상: 0.5% 하락까지 허용
        trailing_pct = 0.005
    elif profit_rate >= 0.010:    # 1.0% 이상: 본절가(+0.4%) 방어
        if current_price <= entry_price * 1.004:
            return True
        return False
```

**예상 효과**:
- 손실: -0.6% (기존 -1.0%)
- 수익: +2.5% ~ +4.0% (기존 +0.8% ~ +2.0%)
- **손익비: 약 3:1 ~ 6:1**

---

### **방안 2: 분할 익절 강화**

**핵심**: 수익은 나눠서 확정하되, 일부는 큰 수익 노린다

#### 2-1. 3단계 분할 익절

```python
# partial_exit_manager.py 수정 (새 로직 추가)

class EnhancedPartialExitManager:
    def __init__(self):
        self.exit_stages = {
            'stage1': {'profit_threshold': 0.012, 'exit_ratio': 0.30},  # 1.2% → 30% 익절
            'stage2': {'profit_threshold': 0.020, 'exit_ratio': 0.40},  # 2.0% → 40% 익절
            'stage3': {'profit_threshold': 0.035, 'exit_ratio': 0.30},  # 3.5% → 30% 익절 (전량 청산)
        }
        self.completed_stages = {}  # {symbol: ['stage1', 'stage2', ...]}

    def check_partial_exit(self, symbol, entry_price, current_price, current_quantity):
        profit_rate = (current_price - entry_price) / entry_price

        completed = self.completed_stages.get(symbol, [])

        # Stage 1: 1.2% 도달 시 30% 익절
        if profit_rate >= 0.012 and 'stage1' not in completed:
            sell_quantity = current_quantity * 0.30
            logger.info(f"🎯 {symbol} 1차 익절 (30%) @ +{profit_rate:.2%}")
            completed.append('stage1')
            return True, sell_quantity

        # Stage 2: 2.0% 도달 시 추가 40% 익절 (누적 70%)
        if profit_rate >= 0.020 and 'stage2' not in completed:
            sell_quantity = current_quantity * 0.40
            logger.info(f"🎯 {symbol} 2차 익절 (40%) @ +{profit_rate:.2%}")
            completed.append('stage2')
            return True, sell_quantity

        # Stage 3: 3.5% 도달 시 나머지 전량 익절
        if profit_rate >= 0.035 and 'stage3' not in completed:
            logger.info(f"🎯 {symbol} 최종 익절 (전량) @ +{profit_rate:.2%}")
            completed.append('stage3')
            return True, current_quantity  # 남은 전량

        self.completed_stages[symbol] = completed
        return False, 0
```

**예상 효과**:
- 작은 수익은 빠르게 확정 (30%)
- 중간 수익도 확정 (40%)
- 큰 수익은 끝까지 노림 (30%)
- **평균 손익비 개선: 약 2.5:1**

---

### **방안 3: 진입 신호 강화 (물량 조절)**

**핵심**: 신호가 약하면 작게 들어가고, 강하면 크게 들어간다

#### 3-1. 신호 등급별 포지션 크기

```python
# improved_strategy.py:336-340 수정

def should_enter_position(self, symbol, indicators):
    # ... (기존 분석 로직)

    # 최종 점수 계산
    final_score = ...

    # ✅ 신호 등급 분류
    if final_score >= 8.0:
        signal_grade = 'A'  # 최우량
        position_multiplier = 1.0
    elif final_score >= 6.5:
        signal_grade = 'B'  # 우량
        position_multiplier = 0.7
    elif final_score >= 5.0:
        signal_grade = 'C'  # 보통
        position_multiplier = 0.5
    else:
        return False, "신호 강도 부족"

    logger.info(f"신호 등급: {signal_grade} (점수: {final_score:.2f})")

    return True, {
        'reason': f"진입 조건 충족 (등급: {signal_grade})",
        'position_multiplier': position_multiplier  # 리스크 매니저에 전달
    }
```

#### 3-2. 리스크 매니저 연동

```python
# risk_manager.py:111 수정

def calculate_position_size(self, balance, symbol, current_price,
                           volatility=None, indicators=None,
                           signal_multiplier=1.0):  # ✅ 추가

    # ... (기존 계산)

    # ✅ 신호 강도 반영
    base_position_value *= signal_multiplier

    logger.info(f"신호 강도 조정: {signal_multiplier:.1%}")

    # ... (나머지 로직)
```

**예상 효과**:
- 약한 신호: 작은 포지션 → 손실 최소화
- 강한 신호: 큰 포지션 → 수익 극대화
- **손익비 간접 개선**

---

### **방안 4: 손절 후 재진입 금지 강화**

**핵심**: 같은 종목에서 반복 손실 방지

#### 4-1. 쿨다운 차등 적용

```python
# improved_strategy.py:113-120 수정

def is_in_cooldown(self, symbol):
    if symbol not in self.trade_cooldown:
        return False

    # ✅ 마지막 거래가 손실이었는지 확인
    last_trade_result = self.last_trade_results.get(symbol, 'unknown')

    if last_trade_result == 'loss':
        cooldown_time = 7200  # 손실 후 2시간 (기존 3분)
    else:
        cooldown_time = 600   # 수익 후 10분

    elapsed = time.time() - self.trade_cooldown[symbol]

    if elapsed < cooldown_time:
        logger.info(f"{symbol}: 쿨다운 중 (남은 시간: {(cooldown_time - elapsed)/60:.0f}분)")
        return True

    return False

def record_trade(self, symbol, trade_type, pnl=0):
    # ... (기존 코드)

    # ✅ 거래 결과 저장
    if trade_type == 'sell':
        self.last_trade_results[symbol] = 'profit' if pnl > 0 else 'loss'
```

**예상 효과**:
- 손실 종목에 재진입하여 추가 손실 방지
- **손실 빈도 감소**

---

## 🎯 **추천 조합**

### **즉시 적용 (안전한 개선)**
```
✅ 방안 1-1: 손절 0.6%로 강화
✅ 방안 1-2: 목표 익절 2.5%로 상향
✅ 방안 4: 손절 후 쿨다운 2시간
```

### **단계적 적용 (공격적 개선)**
```
1단계: 방안 1 전체 (손절/익절 비율 조정)
2단계: 방안 2 (3단계 분할 익절)
3단계: 방안 3 (신호 등급별 물량)
```

---

## 📈 **예상 성과**

### 현재 (추정)
```
승률: 65%
평균 수익: +1.2%
평균 손실: -1.5%
손익비: 0.8:1
기대값: (0.65 × 1.2%) + (0.35 × -1.5%) = 0.78% - 0.525% = 0.255%
```

### 개선 후 (방안 1 적용)
```
승률: 60% (약간 감소 예상)
평균 수익: +2.8%
평균 손실: -0.6%
손익비: 4.7:1
기대값: (0.60 × 2.8%) + (0.40 × -0.6%) = 1.68% - 0.24% = 1.44%
```

**ROI 개선: 약 5.6배**

---

## ⚠️ **주의사항**

1. **승률 하락 가능성**: 손절이 타이트해지면 승률이 60% 정도로 떨어질 수 있음
   - **하지만 손익비가 개선되어 전체 수익은 증가**

2. **백테스팅 필수**: 실전 투입 전 과거 데이터로 검증 필요

3. **단계적 적용**: 한 번에 모든 변경을 적용하지 말고, 하나씩 테스트

4. **시장 상황 고려**: 횡보장에서는 손절 타이트화가 불리할 수 있음

---

## 📋 **실행 체크리스트**

- [ ] `config.py`: 손절 0.6%, 목표 2.5% 수정
- [ ] `config.py`: 물타기 비활성화 또는 1회 제한
- [ ] `risk_manager.py`: 추적 손절 완화 (큰 수익 끌기)
- [ ] `improved_strategy.py`: 손절 후 쿨다운 2시간
- [ ] 테스트 모드로 1주일 검증
- [ ] 실전 소액 투입 (초기 자본의 10%)
- [ ] 1개월 후 성과 분석

---

**결론**: 손익비를 1:1에서 3:1 이상으로 개선하면, 승률이 60%로 떨어져도 전체 수익은 크게 증가합니다.
