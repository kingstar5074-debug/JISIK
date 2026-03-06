# us_penny_stock_scanner_mvp

## 1. 프로젝트 소개

- 미국 동전주(**$0.05 ~ $1.00**) 대상 수동 매매용 **후보 스캐너**
- **자동매매, 뉴스 분석, 악재 판별, GPT 분석, 알림, 주문 API** 는 **일절 포함하지 않음**
- `tickers.txt`를 사용하는 **watchlist 모드**와  
  `universe_candidates.txt` / `generated_universe_candidates.txt` 를 사용하는 **universe 모드** 지원
- 현재 미국 동부시간(ET)을 기준으로
  - premarket / regular / afterhours / closed 세션을 판별
- **가격 / 상승률 / 갭 / intraday / 거래량비율 / 평균 거래량 / dollar_volume** 필터 적용 후
- 조건을 통과한 종목을 **세션별 점수화(score)** 후 콘솔 표 형태로 **랭킹 출력**
- **자동 유니버스 생성 단계에서 이미 가격 + 유동성 기반으로 1차 정제**를 수행하고,  
  **스캐너 단계에서 다시 한 번 더 엄격하게 필터링**하는 이중 구조를 사용

## 2. 현재 기능 요약

- **watchlist 모드**
  - `.env`에서 `SCAN_MODE=watchlist`
  - `tickers.txt`에 적힌 워치리스트만 스캔
- **universe 모드**
  - `.env`에서 `SCAN_MODE=universe`
  - `UNIVERSE_FILE=universe_candidates.txt` 또는 `generated_universe_candidates.txt`
    를 사용해 더 큰 후보 풀을 스캔
- 데이터 provider
  - `DATA_PROVIDER=yahoo`   → Yahoo(`yfinance`) 기반
  - `DATA_PROVIDER=polygon` → Polygon.io 기반 (API 키 필요)
- Polygon provider
  - snapshot + 최근 20일 aggregates 를 사용해
  - 현재가 / 전일종가 / 금일 거래량 / 최근 평균 거래량 / 거래량비율 / 갭 / intraday / dollar_volume 계산
- 필터 (스캐너 단계)
  - price: `MIN_PRICE ~ MAX_PRICE`
  - percent_change: `MIN_CHANGE_PERCENT` 이상
  - gap_percent: `MIN_GAP_PERCENT` 이상
  - intraday_change_percent: `MIN_INTRADAY_CHANGE_PERCENT` 이상
  - volume_ratio: `MIN_VOLUME_RATIO` 이상
  - average_volume: `MIN_AVERAGE_VOLUME` 이상
  - dollar_volume: `MIN_DOLLAR_VOLUME` 이상
- 점수화(Scoring)
  - `momentum_score = percent_change`
  - `volume_score   = volume_ratio * 10`
  - `gap_score      = gap_percent`
  - `liquidity_score = min(dollar_volume / 1_000_000, 10)`
  - 세션별 가중치:
    - premarket  : momentum 0.35, volume 0.25, gap 0.40
    - regular    : momentum 0.45, volume 0.35, gap 0.20
    - afterhours : momentum 0.35, volume 0.40, gap 0.25
    - closed     : regular 과 동일
  - `total_score` =
    - `momentum_score * 세션별 momentum_weight +`
    - `volume_score * 세션별 volume_weight +`
    - `gap_score * 세션별 gap_weight +`
    - `liquidity_score * 0.15`
- 랭킹 출력
  - `total_score` 기준 내림차순 정렬
  - 상위 `TOP_RESULTS` 개수만 콘솔 표로 출력

## 3. 프로젝트 구조

```text
us_penny_stock_scanner_mvp/
  README.md
  requirements.txt
  .env.example
  main.py
  build_universe.py
  config.py
  tickers.txt
  universe_candidates.txt
  generated_universe_candidates.txt
  scanner/
    __init__.py
    models.py
    filters.py
    market_hours.py
    scanner.py
    scoring.py
    providers/
      __init__.py
      base.py
      yahoo_provider.py
      polygon_provider.py
      factory.py
  universe/
    __init__.py
    base.py
    watchlist_universe.py
    generated_universe.py
    polygon_universe_builder.py
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

## 5. 자동 유니버스 생성 (Polygon 기반, 가격 + 유동성 정제)

```bash
python build_universe.py
```

동작 개요:

- `.env`에서 `DATA_PROVIDER=polygon`, `POLYGON_API_KEY` 가 설정되어 있어야 함
- Polygon snapshot all-tickers 데이터를 가져와:
  1. **1단계 (snapshot 기반 압축)**  
     - `UNIVERSE_MIN_PRICE ~ UNIVERSE_MAX_PRICE` 가격 범위
     - `prev_close >= UNIVERSE_MIN_PREV_CLOSE`
     - `dollar_volume = price * current_volume >= UNIVERSE_MIN_DOLLAR_VOLUME`  
     - 위 조건을 만족하는 종목만 남기고, dollar_volume 기준으로 정렬
  2. **2단계 (aggregates 기반 평균 거래량 필터)**  
     - 1단계에서 압축된 종목에 대해서만 Polygon aggregates API를 호출
     - 최근 N일(현재 구현은 20일) **average_volume** 을 계산
     - `average_volume >= UNIVERSE_MIN_AVERAGE_VOLUME` 인 종목만 통과
  3. **최종 저장**
     - 유동성 필터까지 통과한 종목들을 정규화/중복 제거 후
     - 최대 `UNIVERSE_LIMIT` 개까지만 선택
     - 결과를 `UNIVERSE_OUTPUT_FILE`
       (기본 `generated_universe_candidates.txt`)에 저장

`build_universe.py` 실행 시 콘솔 출력 예시:

```text
유니버스 생성 시작
데이터 provider: polygon
가격 범위: 0.05 ~ 1.00
유동성 기준: avg_volume >= 50000 / dollar_volume >= 300000
전체 후보 수: 8200
가격 필터 통과: 540
유동성 필터 통과: 180
최종 저장 종목 수: 180
출력 파일: generated_universe_candidates.txt
```

이후 `.env` 에서:

```ini
SCAN_MODE=universe
UNIVERSE_FILE=generated_universe_candidates.txt
```

로 설정하고 `python main.py` 를 실행하면 **가격 + 유동성 기반으로 1차 정제된 유니버스**를
입력으로 사용해 스캐너가 동작합니다.

## 6. 스캐너 실행 방법

```bash
python main.py
```

- **watchlist 모드**
  - `.env`에서 `SCAN_MODE=watchlist` (또는 기본값 유지)
  - `tickers.txt`에 있는 티커만 스캔
- **universe 모드**
  - `.env`에서 `SCAN_MODE=universe`
  - `UNIVERSE_FILE=universe_candidates.txt` 또는
    `generated_universe_candidates.txt` 를 지정해 더 큰 후보 풀을 스캔

실행 시 콘솔에서는 최소 다음 정보들이 출력됩니다.

- 현재 시장 세션(ET)
- 현재 스캔 모드(watchlist / universe)
- 현재 데이터 provider (yahoo / polygon)
- 로드한 티커 수
- 필터 값
  - price / change / gap / intraday / volume_ratio / avg_volume / dollar_volume
- 각 종목별:
  - price, change%, gap%, intraday%, avg_vol, dollar_vol, vol_ratio, score
- 조회 성공 / 조회 실패 개수

## 7. .env 설정값 설명

### 7-1. 데이터 제공 / 모드

- `DATA_PROVIDER`
  - `yahoo`   : yfinance 기반 (기본값, 현재 안정적인 기본 경로)
  - `polygon` : Polygon.io 기반 (API 키 필요)
- `POLYGON_API_KEY`
  - Polygon API 키
  - `DATA_PROVIDER=polygon` 이면서 키가 없으면 친절한 에러 메시지를 띄우고 종료
- `SCAN_MODE`
  - `watchlist` : `tickers.txt` 기반 스캔 (기본값)
  - `universe`  : `UNIVERSE_FILE`에서 티커를 로드해 스캔
- `UNIVERSE_FILE`
  - `SCAN_MODE=universe`일 때 사용하는 후보 풀 파일 이름
  - 기본값: `universe_candidates.txt`

### 7-2. 유니버스 생성용 UNIVERSE_* 설정 (1차 거친 필터)

자동 유니버스 생성은 **가격 + 유동성** 기준으로 **후보를 거칠게 정제**하는 단계입니다.  
이 단계에서 너무 얇거나 비정상적인 종목을 미리 제거해,  
스캐너가 다루는 후보 풀 자체의 품질을 끌어올립니다.

- `UNIVERSE_OUTPUT_FILE`
  - `build_universe.py` 실행 시 생성할 유니버스 파일 이름
  - 기본값: `generated_universe_candidates.txt`
- `UNIVERSE_MIN_PRICE`
  - 유니버스 생성 시 사용할 최소 가격 (기본 `0.05`)
- `UNIVERSE_MAX_PRICE`
  - 유니버스 생성 시 사용할 최대 가격 (기본 `1.00`)
- `UNIVERSE_MIN_DOLLAR_VOLUME`
  - 1단계 필터에서 사용하는 **최소 달러 거래대금**
  - `dollar_volume = price * current_volume`
  - 기본값: `300000` (30만 달러 이상만 남김)
- `UNIVERSE_MIN_AVERAGE_VOLUME`
  - 2단계 필터에서 사용하는 **최소 평균 거래량**
  - Polygon aggregates 로 계산한 최근 N일 평균 거래량 기준
  - 기본값: `50000` (5만 주 이상만 최종 채택)
- `UNIVERSE_MIN_PREV_CLOSE`
  - 전일 종가가 너무 낮거나 비정상인 종목 제거용 최소 전일 종가
  - 기본값: `0.05`
- `UNIVERSE_LIMIT`
  - 유니버스 파일에 최종 저장할 최대 심볼 개수 (기본 `500`)

> **중요**  
> - 유니버스 생성용 `UNIVERSE_*` 값들은 **거친 1차 필터**입니다.  
> - 스캐너 실행 시 사용되는 `MIN_*` 필터와 **의도적으로 분리**되어 있습니다.  
> - 즉,  
>   1. **유니버스 단계**: “시장에서 실제로 어느 정도 거래가 되는 동전주 후보군”만 남기기  
>   2. **스캐너 단계**: 그 중에서 **전략에 맞는 상승/갭/유동성 조건을 훨씬 더 엄격하게** 적용  
>   하는 2단계 구조를 유지합니다.

### 7-3. 스캐너용 MIN_* 설정 (2차 정교한 필터)

- `MIN_PRICE`
  - 스캐너 필터용 최소 가격 (기본 `0.05`)
- `MAX_PRICE`
  - 스캐너 필터용 최대 가격 (기본 `1.00`)
- `MIN_CHANGE_PERCENT`
  - 스캐너 필터용 최소 상승률 % (기본 `15.0`)
- `MIN_GAP_PERCENT`
  - `gap_percent` 필터용 최소 갭 % (기본 `5.0`)
- `MIN_INTRADAY_CHANGE_PERCENT`
  - `intraday_change_percent` 필터용 최소 intraday % (기본 `10.0`)
- `MIN_VOLUME_RATIO`
  - 스캐너 필터용 최소 거래량비율 (기본 `3.0`)
- `MIN_DOLLAR_VOLUME`
  - 스캐너 단계에서 사용하는 최소 dollar_volume 필터값 (기본 `500000`)
- `MIN_AVERAGE_VOLUME`
  - 스캐너 단계에서 사용하는 최소 average_volume 필터값 (기본 `100000`)
- `TOP_RESULTS`
  - score 기준 상위 몇 개까지 출력할지 (기본 `20`)

### 7-4. 기타

- `PER_SYMBOL_DELAY_SECONDS`
  - yfinance/Polygon 호출 사이의 딜레이 초 (기본 `0.2`, 레이트리밋 완화용)
- `LOG_LEVEL`
  - 로그 레벨(기본 `INFO`)
- `LOG_DIR`
  - 로그 저장 폴더(기본 `logs`)

## 8. 리스크·유동성 필터 설명

### 8-1. 유니버스 단계의 유동성 필터

- **달러 거래대금 필터 (`UNIVERSE_MIN_DOLLAR_VOLUME`)**
  - `dollar_volume = price * current_volume`
  - snapshot 기준 현재 거래대금이 **너무 낮은 종목**을 1차적으로 제거
- **평균 거래량 필터 (`UNIVERSE_MIN_AVERAGE_VOLUME`)**
  - Polygon aggregates(N일) 로 계산한 평균 거래량이
  - `UNIVERSE_MIN_AVERAGE_VOLUME` 미만인 종목은 최종 유니버스에서 제외
- **전일 종가 필터 (`UNIVERSE_MIN_PREV_CLOSE`)**
  - 전일 종가가 극단적으로 낮거나 비정상적인 종목을 제거

이 단계에서 이미 “실제로 시장에서 어느 정도 거래가 이루어지는 동전주”만 남기기 때문에,  
스캐너가 다루는 후보 풀 자체의 **기본 유동성 품질이 보장**됩니다.

### 8-2. 스캐너 단계의 유동성 필터

- **average_volume 필터 (`MIN_AVERAGE_VOLUME`)**
  - 최근 거래량이 너무 적은 종목(거래가 거의 없는 종목)을 제외하기 위해 사용
  - `average_volume >= MIN_AVERAGE_VOLUME` 인 종목만 통과
- **dollar_volume 필터 (`MIN_DOLLAR_VOLUME`)**
  - `current_price * current_volume` 으로 계산
  - 실제 체결 가능성을 보기 위한 기초 지표
  - `dollar_volume >= MIN_DOLLAR_VOLUME` 인 종목만 통과

두 레벨의 유동성 필터를 통해:

1. **유니버스 단계**에서 “시장에 거의 존재하지 않는 수준의 얇은 종목”을 제거하고  
2. **스캐너 단계**에서 전략에 맞게 “지나치게 얇은 / 위험한 종목”을 한 번 더 걸러냅니다.

## 9. 세션별 점수화 설명

- 세션에 따라 **gap / momentum / volume** 의 의미가 다르기 때문에,
  세션별로 다른 가중치를 적용합니다.

- premarket
  - 갭이 중요 → `gap_weight 0.40`
  - `momentum 0.35`, `volume 0.25`
- regular
  - intraday momentum + 거래량이 중요
  - `momentum 0.45`, `volume 0.35`, `gap 0.20`
- afterhours
  - 거래량이 가장 중요
  - `momentum 0.35`, `volume 0.40`, `gap 0.25`
- closed
  - regular 와 동일 가중치 사용

`total_score` 계산식:

- `momentum_score * momentum_weight`
- `+ volume_score * volume_weight`
- `+ gap_score * gap_weight`
- `+ liquidity_score * 0.15`

## 10. 현재 한계점

- Yahoo(`yfinance`)는 **무료 데이터**이기 때문에
  - 지연, 누락, 레이트리밋(429) 등이 발생할 수 있음
  - 프리마켓/애프터마켓 데이터는 종목마다 제공 여부가 다름
- Polygon 기반 자동 유니버스 생성은
  - snapshot all-tickers + 가격 + 유동성 필터 기반의 **1차 정제 버전**이며,
  - Polygon 플랜·레이트리밋·데이터 품질에 영향을 받습니다.
- 점수화는 단순 가중합 기반의 초기 버전이며,
  - 전략/위험 관리까지 고려한 정교한 스코어는 아닙니다.
- **여전히 없는 것 (이번 배치에서도 금지)**
  - 뉴스 분석
  - offering / reverse split / delisting 등 악재 판별
  - GPT / LLM 기반 분석
  - 텔레그램/슬랙 등 알림
  - 주문/자동매매 API 연동

## 11. 실행 검증 체크리스트

1. 가상환경 생성 (`python -m venv .venv` 또는 `python3 -m venv .venv`)
2. 가상환경 활성화
3. `pip install -r requirements.txt`
4. `.env.example`을 `.env`로 복사
5. `.env`에서
   - `DATA_PROVIDER`
   - `SCAN_MODE`
   - `UNIVERSE_FILE` / `UNIVERSE_OUTPUT_FILE`
   - `UNIVERSE_MIN_PRICE`, `UNIVERSE_MAX_PRICE`
   - `UNIVERSE_MIN_DOLLAR_VOLUME`, `UNIVERSE_MIN_AVERAGE_VOLUME`, `UNIVERSE_MIN_PREV_CLOSE`
   - 스캐너용 필터 값(`MIN_*`)
6. (선택) `DATA_PROVIDER=polygon`, `POLYGON_API_KEY` 설정 후 `python build_universe.py` 실행
7. `generated_universe_candidates.txt` 생성 및 내용(티커 목록) 확인
8. `.env` 에서 `SCAN_MODE=universe`, `UNIVERSE_FILE=generated_universe_candidates.txt` 설정
9. `python main.py` 실행
10. 콘솔에서
    - 현재 시장 세션(ET)
    - 현재 스캔 모드 / provider
    - 로드한 티커 수 / 필터 값
    - 결과 표(gap%, intraday%, avg_vol, dollar_vol, vol_ratio, score)
    - 조회 성공/실패 개수
    가 정상적으로 출력되는지 확인

