# AI 트레이딩 에이전트 리서치 노트

인스타그램 릴스(`@trading_b.o.o.k`, "AI 증권팀 단타시켜서 1억..!?")에 등장한 화면들을 역추적해 정리한 문서다.
릴스는 서로 다른 두 오픈소스 프로젝트를 섞어 보여주고 있었고, 각각을 아래에 분리해 기록한다.

조사일: 2026-09-20

---

## 1. TradingAgents — 멀티 에이전트 LLM 트레이딩 프레임워크

- 저장소: https://github.com/TauricResearch/TradingAgents
- 논문: [arXiv:2412.20138](https://arxiv.org/abs/2412.20138)
- 라이선스: Apache-2.0
- 조사 시점 기준 ⭐107.7k, GitHub Trending #1 Repository of the Day 이력
- 최신: v0.5.0 (2026-09) — point-in-time 무결성, SEC EDGAR 원문 펀더멘털, 티커/날짜 그리드 백테스팅, 포트폴리오 인식 실행

### 무엇인가

실제 트레이딩 회사의 조직을 LLM 에이전트로 흉내 낸 **연구용** 프레임워크다.
역할이 분리된 에이전트들이 각자 분석한 뒤 **구조화된 토론**을 거쳐 매매 판단을 내린다.

### 에이전트 구성 (README 기준)

| 팀 | 역할 |
|---|---|
| Analyst Team | Fundamentals / Sentiment / News / Technical — 재무, 시장 심리, 글로벌 이벤트, 가격 패턴을 각각 분석 |
| Researcher Team | Bullish / Bearish 연구원이 분석 결과를 놓고 상승·하락 양쪽에서 반박 토론 |
| Trader Agent | 분석·리서치 리포트를 종합해 진입 타이밍과 규모를 결정 |
| Risk Management + Portfolio Manager | 변동성·유동성 기준으로 리스크 평가, PM이 거래 제안을 승인 또는 거부 |

오케스트레이션은 LangGraph StateGraph 기반이다.

### 실행

```bash
pip install .
tradingagents
```

LLM 제공자별 키를 환경변수로 넣는다:

```bash
export OPENAI_API_KEY=...
export GOOGLE_API_KEY=...
export ANTHROPIC_API_KEY=...
export DEEPSEEK_API_KEY=...
```

선택: `FRED_API_KEY`(거시 지표), `ALPHA_VANTAGE_API_KEY`.

> 키는 저장소에 절대 커밋하지 않는다. 이 리포의 `.env.example` 패턴을 따를 것.

---

## 2. Munder Difflin — 로컬 멀티 에이전트 하네스

- 저장소: https://github.com/chaitanyagiri/munder-difflin
- 사이트: https://munderdiffl.in
- 제작: Chaitanya Giri

릴스의 픽셀아트 사무실 화면(ADD AGENT, `claudeTerminalHarness`, JIM/KEVIN/STANLEY 카드)이 이 프로젝트다.
트레이딩과는 무관하며, 기존 Claude Code·Codex 등 구독을 그대로 쓰면서 로컬에서 여러 코딩 에이전트를
"사무실"처럼 띄워 두고 메시지·라우팅·메모리를 관리하는 도구다. Electron / React / TypeScript / Pixi.js /
xterm.js / node-pty 스택. 출처는 r/ClaudeAI 게시글.

---

## 확인한 것과 추정한 것

**화면에서 직접 확인됨**
- 주소창 `.../TradingAgents`, README 제목 `TradingAgents: Multi-Agents LLM Financial Trading Framework`, Apache-2.0 표기, TAURIC RESEARCH 배너
- 레딧 본문 "Munder Difflin은 로컬 다중 에이전트 하네스입니다"

**추정 / 2차 출처**
- 릴스에 나온 한국어 아키텍처 다이어그램(v0.2.5 표기)은 kakaocdn 호스팅 이미지로, 공식 문서가 아니라 제3자가 정리한 블로그 자료다. 구조 자체는 공식 README와 일치하지만 세부 문구는 그대로 인용하지 않는 편이 낫다.
- 영상 속 `SKHYNIX` 티커, `$1,138.56` 같은 호가는 시뮬레이션 화면이며 실제 체결이 아니다. 영상 하단에도 "AI 시뮬레이션 — 투자 조언이 아님"이 표기돼 있다.

---

## 주의

릴스 제목의 "1000달러로 1억"은 이 프레임워크의 성격과 다르다.
TradingAgents README는 명시적으로 이렇게 밝히고 있다:

> TradingAgents framework is designed for research purposes... It is not intended as financial, investment, or trading advice.

수익을 보장하는 자동매매 봇이 아니라, LLM 에이전트 간 토론으로 의사결정을 만드는 구조를 실험하는 연구 코드다.
이 리포의 기존 봇(`CoinTradeBot_Nas`, `Binance_trader`)에 아이디어를 가져올 때도
백테스트 결과 없이 실계좌에 붙이지 않는다.
