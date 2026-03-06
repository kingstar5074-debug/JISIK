# us_penny_stock_scanner_mvp

## 1. 프로젝트 소개
미국 주식 시장에서 **$0.05 ~ $1.00** 구간의 동전주(페니스톡)를 대상으로,
**미국 동부시간(ET)** 기준 현재 시장 세션을 판별한 뒤,
워치리스트(`tickers.txt`)에 있는 티커를 스캔해서 **조건을 만족하는 종목만 콘솔 표로 출력**하는 **최소 동작 MVP**입니다.

## 2. 현재 MVP 기능
- **워치리스트 기반 스캔**: `tickers.txt`에 적힌 티커만 조회
- **시장 시간대 구분(ET)**: `premarket / regular / afterhours / closed`
- **필터링**
  - 가격: \(0.05 \le price \le 1.00\)
  - 상승률: change% ≥ 15.0
  - 거래량비율: volume_ratio ≥ 3.0
- **콘솔 출력**: ticker / price / change% / volume_ratio / 세션 표시

### 핵심 원칙
- **자동매매 없음**: 주문/체결 기능 없음
- **탐지만 수행**: 사람이 보고 수동 매매 판단
- **Provider 교체 가능 구조 유지**: 지금은 무료(yfinance)로 동작, 이후 Polygon/Finnhub로 교체 가능

---

## 3. 프로젝트 구조

```text
us_penny_stock_scanner_mvp/
  README.md
  requirements.txt
  .env.example
  main.py
  config.py
  tickers.txt
  scanner/
    __init__.py
    models.py
    filters.py
    market_hours.py
    scanner.py
    providers/
      __init__.py
      base.py
      yahoo_provider.py
  utils/
    __init__.py
    logger.py
    formatter.py
```

---

## 4. 설치 방법

### Python
- Python **3.11+ 권장**

### 가상환경(venv)
- 가상환경 생성 후 활성화

### 의존성 설치
- `requirements.txt` 설치

### 환경변수 파일
- `.env.example`을 복사해 `.env`를 만든 뒤 필요 시 값 조정

---

## 5. 실행 방법

프로젝트 루트에서 실행합니다.

```bash
python main.py
```

---

## 6. .env 설정값 설명

- `MIN_PRICE`: 최소 가격 (기본 0.05)
- `MAX_PRICE`: 최대 가격 (기본 1.00)
- `MIN_CHANGE_PERCENT`: 최소 상승률 % (기본 15.0)
- `MIN_VOLUME_RATIO`: 최소 거래량비율 (기본 3.0)
- `PER_SYMBOL_DELAY_SECONDS`: 티커당 요청 딜레이(기본 0.2초)
- `LOG_LEVEL`: 로그 레벨(기본 INFO)
- `LOG_DIR`: 로그 폴더(기본 logs)

---

## 7. Windows 실행 방법

PowerShell 기준 예시:

```bash
cd us_penny_stock_scanner_mvp
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python main.py
```

---

## 8. macOS 실행 방법

```bash
cd us_penny_stock_scanner_mvp
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python main.py
```

---

## 9. 최소 실행 테스트 기준(이번 핫픽스 목표)

아래 2개가 통과하면 “실행 가능 상태”로 판단합니다.

1) 문법/임포트 에러 없음:

```bash
python -m compileall .
```

2) 실제 실행 시 종료까지 정상 진행:

```bash
python main.py
```

정상 동작 시 최소한 아래 중 하나를 출력합니다.
- `현재 시장 세션(ET): ...` + 결과 테이블
- 또는 `조건 충족 종목 없음`

추가로 로그는 기본적으로 `logs/scanner.log`에 쌓입니다.

---

## 10. 현재 MVP 한계점
- yfinance(무료)는 **데이터 지연/누락/차단(레이트리밋)** 이 있을 수 있습니다.
- 프리/애프터 시간대의 가격/거래량 필드는 티커별로 제공 여부가 달라 **일부 종목은 계산이 불완전**할 수 있습니다.
- 현재는 `tickers.txt` 워치리스트 스캔만 지원합니다(전체 시장 탐색/발굴 아님).

---

## 다음 배치 예정 기능(요청 범위 밖)
- 뉴스 분석
- 악재 필터(reverse split / offering / delisting / dilution)
- GPT 한줄 분석
- 텔레그램 알림

