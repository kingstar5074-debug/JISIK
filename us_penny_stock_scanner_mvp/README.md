# us_penny_stock_scanner_mvp

## 1. 프로젝트 소개
- 미국 동전주(**$0.05 ~ $1.00**) 대상
- `tickers.txt`를 사용하는 **watchlist 모드**에서 시작
- `universe_candidates.txt`를 사용하는 **universe 모드**로 확장 가능
- 현재 미국 동부시간(ET)을 기준으로
  - premarket / regular / afterhours / closed 세션을 판별
- **가격 / 상승률 / 거래량비율** 필터 적용 후
- 조건을 통과한 종목을 **콘솔 표 형태로 출력**

## 2. 현재 MVP 기능
- **watchlist 모드**
  - `tickers.txt`에 적힌 워치리스트만 스캔
- **universe 모드**
  - `universe_candidates.txt`에 있는 더 큰 후보 풀을 스캔
- 현재 ET 기준 세션 판별 (`MarketClock`)
- Yahoo(`yfinance`) 기반 가격/거래량 조회
- 가격 / 상승률 / 거래량비율 필터 적용
- 조회 성공/실패 개수 집계 및 요약 출력

## 3. 프로젝트 구조

```text
us_penny_stock_scanner_mvp/
  README.md
  requirements.txt
  .env.example
  main.py
  config.py
  tickers.txt
  universe_candidates.txt
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
  universe/
    __init__.py
    base.py
    watchlist_universe.py
    generated_universe.py
  utils/
    __init__.py
    logger.py
    formatter.py
```

## 4. 설치 방법

### Windows (PowerShell 기준)

```bash
cd us_penny_stock_scanner_mvp
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

### macOS / Linux

```bash
cd us_penny_stock_scanner_mvp
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## 5. 실행 방법

```bash
python main.py
```

- **watchlist 모드**
  - `.env`에서 `SCAN_MODE=watchlist` (또는 기본값 유지)
  - `tickers.txt`에 있는 티커만 스캔
- **universe 모드**
  - `.env`에서 `SCAN_MODE=universe`
  - `UNIVERSE_FILE=universe_candidates.txt` 기준으로 더 많은 티커 스캔

실행 시 콘솔에서는 최소 다음 정보들이 출력됩니다.
- 현재 시장 세션(ET)
- 현재 스캔 모드(watchlist / universe)
- 로드한 티커 수
- 현재 필터 값
- 스캔 결과 표 또는 `조건 충족 종목 없음`
- 조회 성공 / 조회 실패 개수

## 6. .env 설정값 설명

- `SCAN_MODE`
  - `watchlist` : `tickers.txt` 기반 스캔 (기본값)
  - `universe`  : `UNIVERSE_FILE`에서 티커를 로드해 스캔
- `UNIVERSE_FILE`
  - `SCAN_MODE=universe`일 때 사용하는 후보 풀 파일 이름
  - 기본값: `universe_candidates.txt`
- `MIN_PRICE`
  - 최소 가격 (기본 `0.05`)
- `MAX_PRICE`
  - 최대 가격 (기본 `1.00`)
- `MIN_CHANGE_PERCENT`
  - 최소 상승률 % (기본 `15.0`)
- `MIN_VOLUME_RATIO`
  - 최소 거래량비율 (기본 `3.0`)
- `PER_SYMBOL_DELAY_SECONDS`
  - yfinance 호출 사이의 딜레이 초 (기본 `0.2`, 레이트리밋 완화용)
- `LOG_LEVEL`
  - 로그 레벨(기본 `INFO`)
- `LOG_DIR`
  - 로그 저장 폴더(기본 `logs`)

## 7. 현재 MVP 동작 방식

- 이 프로젝트는 아직 **“미국 전체 시장 실시간 스캐너 완성판”이 아니다.**
- 현재는 다음 두 가지 입력 소스 중 하나를 사용하는 **확장 준비 단계**이다.
  - `tickers.txt` (watchlist 모드)
  - `universe_candidates.txt` (universe 모드)
- 스캔 시점의 **현재 세션 기준**으로 동작한다.
  - 현재 시각이 premarket이면 premarket 기준
  - regular면 regular 기준
  - afterhours면 afterhours 기준
- 각 세션에 대해
  - 가격/상승률/거래량비율을 계산하고
  - 필터를 통과하는 종목만 콘솔 표에 표시한다.

## 8. 현재 단계 한계점

- Yahoo(`yfinance`)는 **무료 데이터**이기 때문에
  - 지연, 누락, 레이트리밋(429) 등이 발생할 수 있음
  - 프리마켓/애프터마켓 데이터는 종목마다 제공 여부가 다름
- `universe_candidates.txt`에는
  - 상폐되었거나 오래된 종목이 섞여 있을 수 있으며
  - 이런 종목은 “조회 실패”로 집계되지만 프로그램은 계속 동작한다.
- 아직 **미국 전체 시장을 완전 커버하는 실시간 스캐너는 아니다.**
- Polygon / Finnhub 같은 미국 데이터 API provider는 아직 연결되어 있지 않다.

## 9. 다음 배치 예정 기능

- Polygon / Finnhub provider 추가
- API 기반 실제 유니버스 구성(미국 전체 동전주 후보 수집/필터)
- 뉴스 분석
- 악재 필터(reverse split / offering / delisting / dilution)
- GPT 한줄 분석
- 텔레그램 알림

## 10. 실행 검증 체크리스트

1. 가상환경 생성 (`python -m venv .venv` 또는 `python3 -m venv .venv`)
2. 가상환경 활성화
3. `pip install -r requirements.txt`
4. `.env.example`을 `.env`로 복사
5. `.env`에서 `SCAN_MODE` / `UNIVERSE_FILE` / 필터 값 확인
6. `python main.py` 실행
7. 콘솔에서 **현재 시장 세션(ET)** 이 출력되는지 확인
8. **현재 스캔 모드(watchlist / universe)** 가 맞게 나오는지 확인
9. **로드한 티커 수**, 필터 값, 조회 성공/실패 개수가 함께 출력되는지 확인

