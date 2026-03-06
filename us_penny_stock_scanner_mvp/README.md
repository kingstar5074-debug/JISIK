## us_penny_stock_scanner_mvp

미국 주식 시장에서 **$0.05 ~ $1.00** 구간의 동전주(페니스톡)를 대상으로,
현재 시간대(ET)를 기준으로 **프리마켓/정규장/애프터마켓**을 구분하고,
**급등(+% 상승률) + 거래량 급증(volume ratio)** 조건을 만족하는 종목을 콘솔 표로 출력하는 **최소 동작 MVP**입니다.

### 핵심 원칙
- **자동매매 없음**: 주문/체결 기능은 넣지 않습니다.
- **탐지만 수행**: 사람이 보고 수동 매매 판단을 할 수 있도록 출력만 합니다.
- **Provider 교체 가능**: 지금은 무료(야후/yfinance)로 시작하지만, Polygon/Finnhub로 갈아끼우기 쉽게 인터페이스를 분리했습니다.

---

## 설치 방법(macOS 기준)

### 1) Python 준비
- Python 3.11+ 권장

### 2) 가상환경 생성/활성화

```bash
cd us_penny_stock_scanner_mvp
python3 -m venv .venv
source .venv/bin/activate
```

### 3) 의존성 설치

```bash
pip install -r requirements.txt
```

### 4) 환경변수 설정

```bash
cp .env.example .env
```

필요하면 `.env`에서 필터 값을 조정하세요.

### 5) 실행

```bash
python main.py
```

---

## 설정값 설명(.env)

- `MIN_PRICE`: 최소 가격 (기본 0.05)
- `MAX_PRICE`: 최대 가격 (기본 1.00)
- `MIN_CHANGE_PERCENT`: 최소 상승률 % (기본 15.0)
- `MIN_VOLUME_RATIO`: 최소 거래량비율 (기본 3.0)
- `PER_SYMBOL_DELAY_SECONDS`: 티커당 요청 딜레이(기본 0.2초)
- `LOG_LEVEL`: 로그 레벨(기본 INFO)
- `LOG_DIR`: 로그 폴더(기본 logs)

---

## 현재 MVP 한계점
- yfinance(무료)는 **데이터 지연/누락/차단(레이트리밋)** 이 있을 수 있습니다.
- 프리/애프터 시간대의 가격/거래량 필드는 티커별로 제공 여부가 달라 **일부 종목은 계산이 불완전**할 수 있습니다.
- 현재는 `tickers.txt`에 적힌 티커만 스캔합니다(전체 시장 스캐너 아님).

---

## 다음 배치 예정(추천)
- 뉴스 분석
- 악재 필터(reverse split / offering / delisting / dilution)
- GPT 한줄 분석
- 텔레그램 알림

---

## 실행 순서(요약)
1. `tickers.txt`에서 티커 리스트 로드
2. 동부시간(ET) 기준 현재 세션 판별
3. Provider(yfinance)로 각 티커 가격/거래량 데이터 조회
4. 상승률/거래량비율 계산
5. 필터 적용(가격→상승률→거래량비율)
6. 조건 충족 종목을 정렬 후 콘솔 표로 출력

