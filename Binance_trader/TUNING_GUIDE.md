# Binance Trader 설정 튜닝 가이드

손실 상황별 설정 조정 가이드입니다.

---

## 1. 손실이 너무 클 때 (한 번에 큰 손실)

**증상:** 한 번 손절에 잔고의 5% 이상 손실

**조정:**
```json
"risk": {
  "stop_loss": 0.01,         // 1.5% → 1%로 축소
  "leverage": 2,             // 3x → 2x로 낮춤
  "max_position_size": 0.015 // 2% → 1.5%로 축소
}
```

**효과:** 개별 거래 손실 폭 감소

---

## 2. 승률이 낮을 때 (자주 손절)

**증상:** 10번 중 6번 이상 손절

**조정:**
```json
"strategy": {
  "entry_score_threshold": 0.3,  // 0.2 → 0.3 (진입 기준 강화)
  "allow_sideways_entry": false  // 횡보장 진입 차단
},
"ml": {
  "min_probability": 0.65        // 0.6 → 0.65 (ML 신뢰도 강화)
}
```

**효과:** 거래 횟수 감소, 승률 향상

---

## 3. 익절 전에 손절 당할 때

**증상:** 수익 구간 갔다가 손절로 끝남

**조정:**
```json
"risk": {
  "stop_loss": 0.02,        // 손절 여유 확대
  "take_profit": 0.025      // 익절은 약간 낮춤
},
"partial_exit": {
  "trigger_profit": 0.008,  // 조기 익절 (0.8%)
  "adaptive": true
},
"trailing_stop": {
  "activation": 0.01,       // 빠른 트레일링 활성화
  "distance": 0.006         // 타이트한 추적
}
```

**효과:** 수익 구간에서 일부 확보

---

## 4. 변동성 큰 시장에서 손실

**증상:** 급등락에 휩쓸려 손절

**조정:**
```json
"trailing_stop": {
  "activation": 0.01,       // 빠른 트레일링 활성화
  "distance": 0.005         // 타이트한 추적
},
"partial_exit": {
  "adaptive": true          // ATR 기반 적응형 필수
},
"risk": {
  "max_positions": 2        // 포지션 수 축소
}
```

**효과:** 변동성 대응력 향상

---

## 5. 연속 손실 (일일 한도)

**증상:** 하루에 3번 이상 연속 손절

**조정:**
```json
"risk": {
  "daily_loss_limit": 0.03,  // 5% → 3%로 축소
  "max_positions": 2         // 4 → 2개로 축소
},
"strategy": {
  "scan_interval": 300       // 120초 → 300초 (신중하게)
}
```

**효과:** 일일 최대 손실 제한

---

## 6. 수익은 나는데 적을 때

**증상:** 승률은 좋은데 수익이 작음

**조정:**
```json
"risk": {
  "take_profit": 0.04,      // 3% → 4%로 확대
  "leverage": 4             // 3x → 4x로 높임 (주의)
},
"trailing_stop": {
  "activation": 0.02,       // 트레일링 늦게 활성화
  "distance": 0.012         // 여유있게 추적
},
"partial_exit": {
  "exit_ratio": 0.3         // 50% → 30%만 조기 청산
}
```

**효과:** 수익 극대화 (리스크 증가)

---

## 요약 체크리스트

| 증상 | 조정 항목 | 방향 |
|------|----------|------|
| 큰 손실 | leverage, stop_loss, position_size | ⬇️ 낮춤 |
| 낮은 승률 | entry_score, ml_probability | ⬆️ 높임 |
| 익절 못함 | partial_exit trigger, trailing | ⬇️ 낮춤/빠르게 |
| 잦은 손절 | stop_loss | ⬆️ 여유 확대 |
| 연속 손실 | max_positions, daily_limit | ⬇️ 축소 |
| 수익 작음 | take_profit, leverage | ⬆️ 높임 |

---

## 권장 프리셋

### 보수적 (초보자/소액)
```json
{
  "risk": {
    "leverage": 2,
    "stop_loss": 0.01,
    "take_profit": 0.02,
    "max_positions": 2
  },
  "strategy": {
    "entry_score_threshold": 0.3
  },
  "partial_exit": {
    "trigger_profit": 0.008,
    "adaptive": true
  }
}
```

### 균형 (기본값)
```json
{
  "risk": {
    "leverage": 3,
    "stop_loss": 0.015,
    "take_profit": 0.03,
    "max_positions": 4
  },
  "strategy": {
    "entry_score_threshold": 0.2
  },
  "partial_exit": {
    "trigger_profit": 0.015,
    "adaptive": true
  }
}
```

### 공격적 (숙련자/고액)
```json
{
  "risk": {
    "leverage": 5,
    "stop_loss": 0.02,
    "take_profit": 0.05,
    "max_positions": 6
  },
  "strategy": {
    "entry_score_threshold": 0.15
  },
  "partial_exit": {
    "trigger_profit": 0.02,
    "adaptive": true
  }
}
```

---

## 주의사항

1. **한 번에 하나씩만 변경** - 여러 설정 동시 변경 시 원인 파악 어려움
2. **최소 10거래 후 판단** - 1~2번 거래로 판단하지 않기
3. **레버리지는 신중하게** - 수익도 크지만 손실도 큼
4. **백테스트 권장** - 실전 전 시뮬레이션 모드로 테스트

---

## 7. 추세 반전 청산 설정 (v2.3 신규)

**증상:** 수익 중인 포지션이 반대 추세로 손실 전환

**조정:**
```json
"reverse_exit": {
  "enabled": true,
  "score_threshold": 0.3,    // 반대 점수 임계값 (낮을수록 민감)
  "min_hold_minutes": 30     // 최소 보유 시간
}
```

**효과:** 추세 반전 시 빠른 청산으로 손실 방지

---

## 8. 소액 계좌 설정 (잔고 200 USDT 이하)

**증상:** 주문 금액이 작아서 거래 실패 (100 USDT 미만)

**조정:**
```json
"risk": {
  "max_position_size": 0.25,  // 25%로 확대
  "leverage": 3,              // 레버리지로 보완
  "max_positions": 2          // 동시 포지션 축소
}
```

**효과:** 최소 주문 금액(100 USDT) 충족

---

## v2.3 신규 기능

### 서버사이드 손절
- 봇 크래시/종료 시에도 거래소에서 자동 손절
- 포지션 진입 시 STOP_MARKET 주문 자동 설정
- 수동 설정 불필요 (항상 활성화)

### 텔레그램 알림
`.env` 파일에 설정:
```env
TELEGRAM_BOT_TOKEN=봇토큰
TELEGRAM_CHAT_ID=채팅ID
```

알림 종류:
- 봇 시작/종료
- 포지션 진입/청산
- 120초마다 상태 업데이트

### 거래소 동기화
- 시작 시 실제 거래소 포지션과 자동 동기화
- 수동 거래 후 봇 재시작해도 포지션 인식

---

*Binance Trader v2.3 - Server-Side SL + Telegram + Docker Edition*
