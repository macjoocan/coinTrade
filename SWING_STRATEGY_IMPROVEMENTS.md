# 🎯 스윙 트레이딩 승률 개선 제안

**작성일**: 2026-01-17
**현재 문제**: 승률 61.9%지만 평균 수익 -0.11% (손실)
**원인**: 조기 익절 (58.8%가 소액 수익에서 매도)

---

## 📊 데이터 분석 결과

### 현재 성과
```
총 거래: 257회 (최근 30일)
승률: 61.9%
평균 수익: -0.11% ❌

매도 패턴:
- 손절 (<-1%): 10.1%
- 소액 익절 (0~1.5%): 58.8% ← 문제!
- 큰 익절 (>1.5%): 3.1% ← 너무 적음!

보유 시간:
- 평균: 2.2시간 (스캘핑 수준)
- 짧은 보유 (<12h): 승률 61.0%
- 긴 보유 (>=12h): 승률 81.8% ✅
```

### 핵심 발견
```
🔍 긴 보유(12h+)가 승률이 20%p 더 높음!
→ 스윙 전략으로 전환하면 승률 향상 가능
```

---

## 🎯 개선안 1: 스윙 홀딩 강화

### 목적
짧은 보유(2.2h) → 긴 보유(12~24h) 전환

### 구현
```python
# swing_holding_enhancer.py

class SwingHoldingEnhancer:
    """
    스윙 홀딩 강화 시스템
    - 조기 익절 방지
    - 최소 보유 시간 강제
    - 추세 지속 시 홀딩 연장
    """

    def __init__(self):
        self.min_swing_hold_hours = 12  # 최소 12시간 보유
        self.ideal_swing_hold_hours = 24  # 이상적 24시간

    def should_allow_exit(self, symbol, entry_time, current_pnl_rate):
        """
        스윙 관점에서 청산 허용 여부

        Returns:
            (allow, reason)
        """
        hold_hours = (datetime.now() - entry_time).total_seconds() / 3600

        # 1. 손절은 즉시 허용
        if current_pnl_rate < -0.015:  # -1.5%
            return True, "손절"

        # 2. 최소 보유 시간 미달 + 소액 수익 → 거부
        if hold_hours < self.min_swing_hold_hours:
            if current_pnl_rate < 0.025:  # +2.5% 미만
                return False, f"스윙 최소 보유 {self.min_swing_hold_hours}시간 미달 (현재: {hold_hours:.1f}h)"

        # 3. 큰 수익 (3%+) → 허용
        if current_pnl_rate >= 0.030:
            return True, "목표 수익 달성"

        # 4. 중간 수익 (2~3%) + 충분한 보유 → 허용
        if current_pnl_rate >= 0.020 and hold_hours >= self.min_swing_hold_hours:
            return True, "적정 수익 + 충분한 보유"

        # 5. 그 외 홀딩
        return False, "스윙 홀딩 중"

    def get_dynamic_min_hold(self, market_volatility):
        """
        변동성에 따른 동적 최소 보유 시간

        고변동성: 8시간 (빠른 움직임)
        중변동성: 12시간 (기본)
        저변동성: 18시간 (느린 움직임)
        """
        if market_volatility > 0.05:  # 5% 이상
            return 8
        elif market_volatility < 0.02:  # 2% 미만
            return 18
        else:
            return 12
```

### 예상 효과
```
Before:
- 평균 보유: 2.2시간
- 승률: 61.9%
- 평균 수익: -0.11%

After:
- 평균 보유: 12~18시간
- 예상 승률: 75~82% (데이터 기반)
- 예상 수익: +0.5~1.0%
```

---

## 🎯 개선안 2: 추세 추종 익절 시스템

### 목적
추세가 지속되는 동안 홀딩, 추세 반전 시에만 익절

### 구현
```python
# trend_following_exit.py

class TrendFollowingExit:
    """
    추세 추종 익절 시스템
    - 상승 추세 지속 → 홀딩
    - 추세 약화/반전 → 익절
    """

    def __init__(self):
        self.trend_weakening_threshold = 0.3  # 추세력 30% 미만

    def check_trend_continuation(self, ticker):
        """
        추세 지속 여부 확인

        Returns:
            (is_continuing, trend_strength)
        """
        df = pyupbit.get_ohlcv(ticker, interval='minute60', count=24)

        # 1. EMA 배열 체크
        df['ema12'] = df['close'].ewm(span=12).mean()
        df['ema26'] = df['close'].ewm(span=26).mean()

        ema_aligned = df.iloc[-1]['ema12'] > df.iloc[-1]['ema26']

        # 2. 최근 고점 갱신 여부
        recent_high = df['high'].tail(6).max()
        current_price = df.iloc[-1]['close']
        near_high = current_price >= recent_high * 0.98  # 고점 98% 이상

        # 3. 거래량 증가 여부
        vol_ma = df['volume'].tail(24).mean()
        recent_vol = df['volume'].tail(6).mean()
        vol_increasing = recent_vol > vol_ma * 1.1

        # 추세력 점수
        strength = 0
        if ema_aligned: strength += 0.4
        if near_high: strength += 0.4
        if vol_increasing: strength += 0.2

        is_continuing = strength >= 0.5  # 50% 이상

        return is_continuing, strength

    def should_take_profit(self, ticker, entry_price, current_price, hold_hours):
        """
        익절 여부 판단
        """
        pnl_rate = (current_price - entry_price) / entry_price

        # 1. 손실/소액 수익 → 추세 무관하게 홀딩
        if pnl_rate < 0.015:
            return False, "수익 부족"

        # 2. 최소 보유 시간 미달 → 홀딩
        if hold_hours < 12:
            return False, f"보유 시간 부족 ({hold_hours:.1f}h)"

        # 3. 추세 지속 중 → 홀딩
        is_continuing, strength = self.check_trend_continuation(ticker)
        if is_continuing and pnl_rate < 0.05:  # 5% 미만이면 더 기다림
            return False, f"추세 지속 중 (강도: {strength:.0%})"

        # 4. 추세 약화 + 수익 → 익절
        if not is_continuing and pnl_rate >= 0.015:
            return True, f"추세 약화 + 익절 (수익: {pnl_rate:.1%})"

        # 5. 큰 수익 → 무조건 익절
        if pnl_rate >= 0.05:
            return True, "목표 수익 달성"

        return False, "홀딩"
```

### 예상 효과
```
- 상승 추세 중 조기 익절 방지
- 큰 수익 기회 포착 (1.5% → 3~5%)
- 평균 수익 +0.5~1.2% 개선
```

---

## 🎯 개선안 3: 구간별 분할 익절

### 목적
한 번에 전량 매도 대신 구간별 분할 매도

### 구현
```python
# staged_profit_taking.py

class StagedProfitTaking:
    """
    구간별 분할 익절
    - 1차: +2% 도달 → 50% 매도
    - 2차: +3% 도달 → 30% 매도
    - 3차: +5% 도달 또는 추세 반전 → 나머지 매도
    """

    def __init__(self):
        self.stages = [
            {'target': 0.020, 'sell_ratio': 0.50},  # +2% → 50%
            {'target': 0.030, 'sell_ratio': 0.30},  # +3% → 30%
            {'target': 0.050, 'sell_ratio': 1.00},  # +5% → 전량
        ]
        self.stage_status = {}  # {symbol: current_stage}

    def check_partial_exit(self, symbol, entry_price, current_price, current_quantity):
        """
        분할 익절 체크

        Returns:
            (should_sell, sell_quantity, stage)
        """
        pnl_rate = (current_price - entry_price) / entry_price

        current_stage = self.stage_status.get(symbol, 0)

        # 각 단계 체크
        for i, stage in enumerate(self.stages):
            if i <= current_stage:
                continue  # 이미 실행된 단계

            if pnl_rate >= stage['target']:
                sell_qty = current_quantity * stage['sell_ratio']
                self.stage_status[symbol] = i

                return True, sell_qty, i+1

        return False, 0, current_stage

    def reset_position(self, symbol):
        """포지션 완전 청산 시 리셋"""
        if symbol in self.stage_status:
            del self.stage_status[symbol]
```

### 예상 효과
```
Before:
- +1.5% 도달 → 전량 매도 → 기회 손실

After:
- +2% → 50% 매도 (수익 확정)
- 나머지 50% → +3~5% 추가 수익 기회
- 평균 수익: +0.8~1.5%
```

---

## 🎯 개선안 4: 진입 품질 강화

### 목적
진입 시점의 추세 강도 확인으로 승률 향상

### 구현
```python
# entry_quality_filter.py

class EntryQualityFilter:
    """
    진입 품질 필터
    - 단순 점수만 보지 않고 추세 강도 확인
    - 약한 신호는 거부
    """

    def check_entry_quality(self, ticker, base_score):
        """
        진입 품질 검증

        Returns:
            (is_high_quality, quality_score, reason)
        """
        df = pyupbit.get_ohlcv(ticker, interval='minute60', count=48)

        quality_checks = []

        # 1. 추세 명확성 (EMA 배열)
        df['ema12'] = df['close'].ewm(span=12).mean()
        df['ema26'] = df['close'].ewm(span=26).mean()
        df['ema50'] = df['close'].ewm(span=50).mean()

        last = df.iloc[-1]
        ema_aligned = (last['ema12'] > last['ema26'] > last['ema50'])
        quality_checks.append(('EMA 배열', 0.3 if ema_aligned else 0))

        # 2. 거래량 확인
        vol_ma = df['volume'].tail(24).mean()
        recent_vol = df['volume'].tail(6).mean()
        vol_surge = recent_vol > vol_ma * 1.5
        quality_checks.append(('거래량 급증', 0.25 if vol_surge else 0))

        # 3. 과매수 확인 (RSI)
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        last_rsi = rsi.iloc[-1]

        rsi_ok = 40 < last_rsi < 75  # 과매수 아님
        quality_checks.append(('RSI 적정', 0.25 if rsi_ok else 0))

        # 4. 지지선 근처 (바닥 확인)
        recent_low = df['low'].tail(24).min()
        current_price = last['close']
        near_support = current_price <= recent_low * 1.05  # 저점 5% 이내
        quality_checks.append(('지지선 근처', 0.2 if near_support else 0))

        # 품질 점수 계산
        quality_score = sum(score for _, score in quality_checks)

        is_high_quality = quality_score >= 0.6  # 60% 이상

        reasons = [name for name, score in quality_checks if score > 0]

        return is_high_quality, quality_score, reasons

    def enhance_entry_score(self, ticker, base_score):
        """
        기본 점수에 품질 점수 가중
        """
        is_high, quality, reasons = self.check_entry_quality(ticker, base_score)

        if is_high:
            # 품질 좋으면 보너스
            enhanced = base_score * (1 + quality * 0.2)  # 최대 20% 보너스
            return enhanced, f"고품질 진입 ({', '.join(reasons)})"
        else:
            # 품질 낮으면 감점
            enhanced = base_score * 0.9
            return enhanced, "진입 품질 보통"
```

### 예상 효과
```
- 약한 신호 필터링 → 승률 5~10% 향상
- 고품질 진입만 허용 → 큰 수익 확률 증가
```

---

## 🎯 개선안 5: 손절 지능화

### 목적
현재 손절(-1.5%) 유지하되, 상황별 차등 적용

### 구현
```python
# intelligent_stop_loss.py

class IntelligentStopLoss:
    """
    지능형 손절 시스템
    - 변동성 고려
    - 진입 품질 고려
    - 시간 경과 고려
    """

    def get_dynamic_stop_loss(self, symbol, entry_price, entry_time,
                               entry_quality, market_volatility):
        """
        동적 손절가 계산

        Args:
            entry_quality: 0~1 (진입 품질)
            market_volatility: 변동성
        """
        base_stop = 0.015  # 기본 -1.5%

        # 1. 진입 품질이 높으면 손절 완화
        if entry_quality >= 0.8:
            base_stop = 0.020  # -2.0%
        elif entry_quality >= 0.6:
            base_stop = 0.015  # -1.5%
        else:
            base_stop = 0.012  # -1.2% (빡빡하게)

        # 2. 변동성 고려
        if market_volatility > 0.05:  # 고변동성
            base_stop *= 1.3  # 여유 주기
        elif market_volatility < 0.02:  # 저변동성
            base_stop *= 0.9  # 타이트하게

        # 3. 시간 경과 고려 (시간이 지날수록 타이트하게)
        hold_hours = (datetime.now() - entry_time).total_seconds() / 3600

        if hold_hours > 24:  # 24시간 이상
            base_stop *= 0.8  # 20% 타이트하게
        elif hold_hours > 12:  # 12시간 이상
            base_stop *= 0.9  # 10% 타이트하게

        return base_stop

    def should_stop_loss_now(self, current_pnl_rate, dynamic_stop):
        """
        즉시 손절 여부
        """
        return current_pnl_rate <= -dynamic_stop
```

### 예상 효과
```
- 고품질 진입: 손절 여유 → 반등 기회
- 저품질 진입: 손절 빡빡 → 빠른 컷
- 변동성 고려 → 불필요한 손절 감소
```

---

## 🎯 통합 시스템 아키텍처

```python
# swing_master.py

class SwingTradingMaster:
    """
    스윙 트레이딩 마스터 시스템
    - 5가지 개선안 통합
    """

    def __init__(self):
        self.holding_enhancer = SwingHoldingEnhancer()
        self.trend_exit = TrendFollowingExit()
        self.staged_profit = StagedProfitTaking()
        self.entry_filter = EntryQualityFilter()
        self.smart_stop = IntelligentStopLoss()

    def evaluate_entry(self, ticker, base_score):
        """진입 평가"""
        is_quality, quality_score, reasons = self.entry_filter.check_entry_quality(ticker, base_score)

        if not is_quality:
            return False, 0, "진입 품질 부족"

        enhanced_score = base_score * (1 + quality_score * 0.2)

        return True, enhanced_score, f"고품질 ({', '.join(reasons)})"

    def should_exit(self, symbol, ticker, entry_price, entry_time,
                    current_price, current_quantity, entry_quality):
        """청산 평가"""
        hold_hours = (datetime.now() - entry_time).total_seconds() / 3600
        current_pnl = (current_price - entry_price) / entry_price

        # 1. 손절 체크
        dynamic_stop = self.smart_stop.get_dynamic_stop_loss(
            symbol, entry_price, entry_time, entry_quality, 0.03  # 변동성
        )

        if current_pnl <= -dynamic_stop:
            return True, current_quantity, "손절"

        # 2. 분할 익절 체크
        should_partial, partial_qty, stage = self.staged_profit.check_partial_exit(
            symbol, entry_price, current_price, current_quantity
        )

        if should_partial:
            return True, partial_qty, f"{stage}차 분할 익절"

        # 3. 스윙 홀딩 체크
        allow_exit, reason = self.holding_enhancer.should_allow_exit(
            symbol, entry_time, current_pnl
        )

        if not allow_exit:
            return False, 0, reason

        # 4. 추세 추종 익절 체크
        should_tp, tp_reason = self.trend_exit.should_take_profit(
            ticker, entry_price, current_price, hold_hours
        )

        if should_tp:
            remaining = current_quantity - self.staged_profit.get_sold_quantity(symbol)
            return True, remaining, tp_reason

        return False, 0, "홀딩 유지"
```

---

## 📊 예상 개선 효과

### Before (현재)
```
승률: 61.9%
평균 수익: -0.11%
평균 보유: 2.2시간
큰 수익: 3.1%

문제:
- 조기 익절 (58.8%)
- 스캘핑 수준 보유 시간
```

### After (개선 후)
```
예상 승률: 70~75% (+10%p)
예상 평균 수익: +0.8~1.2% (+1%p)
예상 보유: 12~18시간 (스윙)
예상 큰 수익: 15~20% (+12%p)

개선 요인:
1. 스윙 홀딩 강제 → 승률 75~82%
2. 추세 추종 → 큰 수익 포착
3. 분할 익절 → 수익 최적화
4. 진입 품질 → 승률 향상
5. 지능형 손절 → 손실 최소화
```

---

## 🚀 구현 우선순위

### Phase 1: 즉시 적용 (오늘)
✅ 개선안 1: 스윙 홀딩 강화
- 최소 보유 12시간 강제
- 소액 익절 방지

### Phase 2: 1~2일 내 (주말)
✅ 개선안 3: 분할 익절
- +2% → 50% 매도
- +3% → 30% 매도

### Phase 3: 1주일 내
✅ 개선안 2: 추세 추종 익절
✅ 개선안 4: 진입 품질 필터

### Phase 4: 고도화 (2주 내)
✅ 개선안 5: 지능형 손절
✅ 통합 마스터 시스템

---

## ⚠️ 주의사항

1. **점진적 도입**: 한 번에 모두 적용 말고 하나씩 테스트
2. **데이터 수집**: 각 개선안 적용 후 최소 20회 거래 데이터 수집
3. **A/B 테스팅**: 개선안 적용 전후 비교
4. **시장 상황**: 하락장에서는 보수적으로 조정

---

**작성일**: 2026-01-17
**예상 적용**: Phase 1부터 시작
**목표**: 승률 70%+, 평균 수익 +1%
