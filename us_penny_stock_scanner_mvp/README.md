## 13. Strategy Stability Analysis

이 프로젝트는 단순히 **평균 점수만 비교**하는 것이 아니라,  
여러 번의 전략 비교 결과를 누적해 **전략의 안정성(변동성 포함)** 까지 함께 평가할 수 있습니다.

### 13-1. 안정성 지표 정의

`summarize_strategy_reports.py` 는 각 전략별로 `average_score` 값들의 분포를 기반으로 다음 지표를 계산합니다.

- `score_variance`  
  - 여러 번 실행된 compare 리포트에서  
    해당 전략의 `average_score` 값들에 대한 **분산(variance)**  
  - 값이 클수록 리포트 간 점수 변동성이 크다는 의미
- `score_std_dev`  
  - 위와 동일한 `average_score` 값들에 대한 **표준편차(standard deviation)**  
  - 분산의 제곱근으로, 점수 변동 정도를 직관적으로 보여줌
- `score_range`  
  - 여러 번 실행된 `average_score` 값들 중  
    `max(average_score) - min(average_score)`  
  - 가장 좋았을 때와 가장 나빴을 때 점수 차이
- `stability_score`  
  - 공식:  
    \[
    \text{stability\_score}
      = \frac{\text{average\_score\_mean}}{1 + \text{score\_std\_dev}}
    \]
  - 해석:
    - **평균 점수(average_score_mean)가 높을수록** 좋고,
    - **표준편차(score_std_dev)가 낮을수록** 좋으므로,
    - 두 값을 결합해 **“높은 점수를 안정적으로 유지하는 전략일수록” stability_score 가 커지는** 형태

데이터 개수가 부족한 경우는 다음과 같이 안전하게 처리합니다.

- `average_score` 리스트 길이 0 →  
  - `score_variance`, `score_std_dev`, `score_range`, `stability_score` 모두 `0.0`
- `average_score` 리스트 길이 1 →  
  - `score_variance = 0.0`, `score_std_dev = 0.0` 으로 처리

### 13-2. summarize_strategy_reports.py 의 안정성 분석

```bash
python summarize_strategy_reports.py
```

실행 시:

- 각 전략별 누적 요약에 다음 값들이 포함됩니다.
  - `average_score_mean`
  - `score_variance`
  - `score_std_dev`
  - `score_range`
  - `stability_score`
- JSON 요약(`strategy_summary_YYYYMMDD_HHMMSS.json`)의 `strategies.*` 객체에 위 필드가 모두 저장됩니다.
- CSV 요약(`strategy_summary_YYYYMMDD_HHMMSS.csv`)에도 동일한 열이 추가됩니다.
- PNG 차트가 하나 추가됩니다.
  - `strategy_summary_stability_score_YYYYMMDD_HHMMSS.png`
  - 각 전략의 `stability_score` 를 bar chart 로 시각화

콘솔에도 예를 들어 다음과 같이 출력됩니다.

```text
[balanced]
- 평균 average_score: 21.40
- score_variance: 5.20
- score_std_dev: 2.28
- score_range: 9.10
- stability_score: 6.52
```

### 13-3. compare_summaries.py 의 avg_stability_score

`compare_summaries.py` 는 여러 개의 summary JSON  
(`strategy_summary_*.json`) 을 다시 한 번 모아서 **2차 요약(“summary of summaries”)** 을 수행합니다.

```bash
python compare_summaries.py
```

동작:

- `REPORTS_DIR` 안의 `strategy_summary_*.json` 파일들을 읽고,
- `.env` 의 `SUMMARY_OF_SUMMARIES_FILTER_*` 설정에 따라
  - tags / provider / session 조건을 만족하는 summary 들만 필터링합니다.
- 각 전략별로 다음 값들의 평균을 계산합니다.
  - `avg_average_score_mean`
  - `avg_best_strategy_win_rate`
  - `avg_average_returned_count`
  - `avg_stability_score`  ← **여러 summary 에 기록된 stability_score 의 평균**
  - `summary_level_win_count`
  - `summary_level_win_rate`

출력:

- JSON: `summary_compare_YYYYMMDD_HHMMSS.json`
- CSV : `summary_compare_YYYYMMDD_HHMMSS.csv`
- PNG :
  1. `summary_compare_avg_score_YYYYMMDD_HHMMSS.png`
  2. `summary_compare_win_rate_YYYYMMDD_HHMMSS.png`
  3. `summary_compare_stability_score_YYYYMMDD_HHMMSS.png`  
     - 각 전략의 `avg_stability_score` bar chart

콘솔에는 예를 들어 다음과 같이 표시됩니다.

```text
[balanced]
- 평균 average_score_mean: 20.40
- 평균 best_strategy_win_rate: 32.10%
- 평균 average_returned_count: 9.40
- 평균 stability_score: 7.21
- summary 레벨 승리 횟수: 3
- summary 레벨 승리 비율: 42.8%
```

### 13-4. browse_reports.py 의 avg stability leader 표시

`browse_reports.py` 를 실행하면 `REPORTS_DIR` 아래에 생성된  
compare / summary / summary-compare 리포트 목록을 한눈에 볼 수 있습니다.

```bash
python browse_reports.py
```

특히 **summary 리포트 목록**에서는 각 파일에 대해:

- `timestamp` / `valid_reports`
- `top winner` (가장 승리가 많았던 전략)
- `avg stability leader` (stability_score 가 가장 높은 전략)
- 사용된 필터(tags, provider, session)

을 함께 보여줍니다.

예:

```text
[summary 리포트 목록]
1. strategy_summary_20260306_140500.json
   - timestamp: 20260306_140500 / valid_reports: 12
   - top winner: aggressive (41.7%)
   - avg stability leader: balanced
   - filters: tags=[premarket, polygon], provider=polygon, session=premarket
```

이를 통해 **“평균적으로 가장 많이 이기는 전략”** 과  
**“점수 변동성이 가장 낮아 안정적인 전략”** 을 동시에 비교할 수 있습니다.

### 13-5. 여전히 포함하지 않는 기능

이 프로젝트는 **수동 매매용 종목 선별**만을 목적으로 합니다.  
이번 배치(Strategy Stability Analysis)에서도 다음 기능들은 **일절 포함하지 않습니다.**

- 뉴스 분석
- 악재(offering, reverse split 등) 자동 판별
- GPT / LLM 기반 뉴스·이벤트 해석
- 텔레그램/슬랙 등 알림 기능
- 주문 API / 자동매매 / 반자동 주문 연동

앞으로의 배치에서도 **“사람이 직접 최종 결정을 내리는 구조”** 를 유지한 채,  
스캐너와 리포트 도구의 **분석 품질과 해석 편의성**만 단계적으로 강화하는 것을 목표로 합니다.

#  us_penny_stock_scanner_mvp
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
- **자동 유니버스 생성 단계에서 가격 + 유동성 + 메타데이터/심볼 타입 기반으로 1차 정제**를 수행하고,  
  **스캐너 단계에서 다시 한 번 더 엄격하게 필터링**하는 **2단계 구조**를 사용
- 유니버스 생성 시
  - 가능한 범위 내에서 **ETF / ETN / warrant / rights / units / preferred shares** 등을 제외하고
  - **보통주(common stock) 중심 유니버스**에 가깝게 정제
- 반복 실행 시 속도 향상을 위해
  - **평균 거래량 캐시**
  - **심볼 메타데이터 캐시**
  를 도입하여 **Polygon 호출 수를 줄임**
- 전략 운영 편의를 위해
  - **STRATEGY_PROFILE** (balanced/aggressive/conservative) 를 지원하고
  - 그 수치를 **`strategy_profiles.json` 외부 파일**에서 로드
  - 코드 수정 없이 JSON만 바꿔도 전략 튜닝이 가능
- 필터 동작/전략 효과를 이해하기 위해
  - **세션 유효 필터 출력**
  - **필터 리포트(단계별 탈락 개수)** 를 콘솔에 출력
  - `compare_strategies.py` 로 전략별 비교 리포트 실행
  - 비교 결과를 **JSON/CSV/PNG 차트** 로 `REPORTS_DIR`에 저장

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
- 유니버스 자동 생성 (build_universe)
  - 1단계(snapshot 기반)
    - `UNIVERSE_MIN_PRICE ~ UNIVERSE_MAX_PRICE` 가격 범위
    - `prev_close >= UNIVERSE_MIN_PREV_CLOSE`
    - `dollar_volume = price * current_volume >= UNIVERSE_MIN_DOLLAR_VOLUME`
  - 2단계(aggregates 기반)
    - 1단계에서 압축된 후보에 대해서만 Polygon aggregates API 호출
    - 최근 N일 평균 거래량 계산 후 `UNIVERSE_MIN_AVERAGE_VOLUME` 이상만 통과
  - 3단계(메타데이터/심볼 타입 기반)
    - Polygon ticker reference 메타데이터 + 심볼 패턴을 이용해
    - **ETF / ETN / warrant / rights / units / preferred shares** 등 비보통주를 최대한 제거
  - 결과를 `UNIVERSE_OUTPUT_FILE`(기본 `generated_universe_candidates.txt`)에 저장
- 필터 (스캐너 단계, 전략 프로파일/세션별 오버라이드 적용 가능)
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
  - 세션/전략별 가중치(`StrategyWeights`):
    - balanced
      - premarket  : momentum 0.35, volume 0.25, gap 0.40, liquidity 0.15
      - regular    : momentum 0.45, volume 0.35, gap 0.20, liquidity 0.15
      - afterhours : momentum 0.35, volume 0.40, gap 0.25, liquidity 0.15
      - closed     : regular 와 동일
    - aggressive / conservative 는 `strategy_profiles.json` 에 정의
  - `total_score` =
    - `momentum_score * momentum_weight +`
    - `volume_score * volume_weight +`
    - `gap_score * gap_weight +`
    - `liquidity_score * liquidity_weight`
- 전략 프리셋(STRATEGY_PROFILE)
  - `balanced` / `aggressive` / `conservative` 3종 지원
  - 프리셋에 따라
    - 세션별 가중치
    - 세션별 필터 최소값(모멘텀/갭/유동성 등)
    이 달라지며, `.env`의 `MIN_*` 값 위에서 오버라이드 형태로 적용
  - **모든 수치는 `strategy_profiles.json` 에서 관리**되므로,
    코드 수정 없이 JSON 수정만으로 전략 튜닝 가능
- 필터 리포트
  - 요청/성공/실패 개수
  - missing_data / price / change / gap / intraday / volume_ratio /
    average_volume / dollar_volume 별 탈락 개수
  - 최종 필터 통과 수 / 점수화 수 / 최종 출력 수를 콘솔에 요약 출력

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
  strategy_profiles.json
  scanner/
    __init__.py
    models.py
    filters.py
    market_hours.py
    scanner.py
    scoring.py
    strategy_profiles.py
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
    cache.py
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

## 5. 자동 유니버스 생성 (Polygon 기반, 가격 + 유동성 + 타입 정제)

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
  3. **3단계 (메타데이터/심볼 타입 필터)**  
     - Polygon ticker reference 메타데이터(타입, 이름 등) + 심볼 패턴을 활용해  
     - **ETF / ETN / warrant / rights / units / preferred shares** 등  
       비보통주 가능성이 높은 종목을 최대한 제외  
     - ADR / 외국 상장 등 특수 케이스는 이번 배치에서는 **완전 배제하지 않고** 유지 가능
  4. **최종 저장**
     - 타입 필터까지 통과한 종목들을 정규화/중복 제거 후
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
메타데이터 필터 통과: 142
최종 저장 종목 수: 142
출력 파일: generated_universe_candidates.txt

avg_volume cache hit: 350, miss: 190
meta cache hit: 120, miss: 22
```

이후 `.env` 에서:

```ini
SCAN_MODE=universe
UNIVERSE_FILE=generated_universe_candidates.txt
```

로 설정하고 `python main.py` 를 실행하면  
**가격 + 유동성 + 타입/심볼 기반으로 1차 정제된 유니버스**를
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
- 현재 전략 프로파일 (balanced / aggressive / conservative)
- 전략 프로파일 파일 이름 (`strategy_profiles.json` 기본)
- 로드한 티커 수
- 필터 값
  - 기본 필터(`MIN_*` 기반)
  - 현재 세션 유효 필터(전략 프로파일 오버라이드 반영)
- 각 종목별:
  - price, change%, gap%, intraday%, avg_vol, dollar_vol, vol_ratio, score
- 조회 성공 / 조회 실패 개수
- 필터 리포트
  - 어떤 필터에서 몇 종목이 탈락했는지 요약

## 7. strategy_profiles.json 설명

전략 프리셋 수치를 JSON 파일(`strategy_profiles.json`)에 정의해  
**코드 수정 없이 전략 수치만 자유롭게 튜닝**할 수 있습니다.

### 7-1. 위치와 구조

- 기본 위치: 프로젝트 루트
  - `us_penny_stock_scanner_mvp/strategy_profiles.json`
- `.env` 의 `STRATEGY_PROFILES_FILE` 로 파일명을 변경할 수 있음

예시 구조(요약):

```json
{
  "balanced": {
    "premarket_weights": {
      "momentum_weight": 0.35,
      "volume_weight": 0.25,
      "gap_weight": 0.40,
      "liquidity_weight": 0.15
    },
    "regular_weights": { ... },
    "afterhours_weights": { ... },
    "closed_weights": { ... },
    "premarket_thresholds": {},
    "regular_thresholds": {},
    "afterhours_thresholds": {},
    "closed_thresholds": {}
  },
  "aggressive": {
    "premarket_weights": { ... },
    "regular_weights": { ... },
    "afterhours_weights": { ... },
    "closed_weights": { ... },
    "premarket_thresholds": {
      "min_change_percent": 10.0,
      "min_gap_percent": 3.0,
      "min_intraday_change_percent": 8.0,
      "min_volume_ratio": 2.0,
      "min_average_volume": 80000.0,
      "min_dollar_volume": 400000.0
    },
    "regular_thresholds": { ... },
    "afterhours_thresholds": { ... },
    "closed_thresholds": { ... }
  },
  "conservative": {
    "premarket_weights": { ... },
    "regular_weights": { ... },
    "afterhours_weights": { ... },
    "closed_weights": { ... },
    "premarket_thresholds": {
      "min_change_percent": 15.0,
      "min_gap_percent": 5.0,
      "min_intraday_change_percent": 10.0,
      "min_volume_ratio": 3.0,
      "min_average_volume": 150000.0,
      "min_dollar_volume": 800000.0
    },
    "regular_thresholds": { ... },
    "afterhours_thresholds": { ... },
    "closed_thresholds": { ... }
  }
}
```

- `*_weights`
  - `momentum_weight`, `volume_weight`, `gap_weight`, `liquidity_weight` 4개 필수
- `*_thresholds`
  - `min_change_percent`
  - `min_gap_percent`
  - `min_intraday_change_percent`
  - `min_volume_ratio`
  - `min_average_volume`
  - `min_dollar_volume`
  - 필요 없는 값은 생략하거나 `null` 로 두면 `.env` 의 `MIN_*` 값을 사용

### 7-2. STRATEGY_PROFILES_FILE 설정

- `.env`:

```ini
STRATEGY_PROFILES_FILE=strategy_profiles.json
```

- 다른 파일 이름/경로를 쓰고 싶다면:

```ini
STRATEGY_PROFILES_FILE=my_strategy_profiles.json
```

으로 바꾸고, 해당 JSON 파일을 같은 프로젝트 루트에 두면 됩니다.

- 파일이 없거나, JSON 구조가 잘못되었거나, 필수 키가 누락되면:
  - `strategy_profiles.py` 에서 `ValueError` 를 발생시키고
  - `main.py` 가 그 메시지를 출력 후 종료합니다.

### 7-3. 전략 수치 튜닝 방법

1. `strategy_profiles.json` 을 열어 원하는 프로파일(`balanced`, `aggressive`, `conservative`)을 선택
2. `*_weights` 또는 `*_thresholds` 의 숫자를 조정
3. `.env` 의 `STRATEGY_PROFILE` 를 해당 프로파일로 설정
4. `python main.py` 를 다시 실행

코드를 건드리지 않고도  
**세션별 가중치/필터 기준을 자유롭게 변경**할 수 있습니다.

## 8. .env 설정값 설명 (전략 관련 요약)

- `STRATEGY_PROFILE`
  - `balanced` : 기본값, `.env` `MIN_*` 기준을 거의 그대로 사용
  - `aggressive` : gap/momentum 을 중시, 필터 완화
  - `conservative` : 유동성 중시, 평균 거래량/달러 거래대금 기준 강화
- `STRATEGY_PROFILES_FILE`
  - 전략 프리셋 JSON 파일 이름 (기본 `strategy_profiles.json`)
  - JSON 구조만 올바르면 코드 수정 없이 수치를 바꿀 수 있음

나머지 `DATA_PROVIDER`, `SCAN_MODE`, `UNIVERSE_*`, `MIN_*`, 캐시 설정 등은  
이전 섹션 설명과 동일합니다.

## 9. 필터 리포트 설명

스캐너 실행 후 콘솔에 다음과 같은 리포트가 추가로 출력됩니다.

예시:

```text
필터 리포트:
- 요청 종목 수: 180
- 조회 성공: 160
- 조회 실패: 20
- 데이터 누락 탈락: 12
- price 탈락: 18
- change 탈락: 25
- gap 탈락: 30
- intraday 탈락: 16
- volume_ratio 탈락: 22
- average_volume 탈락: 10
- dollar_volume 탈락: 8
- 최종 필터 통과: 19
- 점수화 완료: 19
- 최종 출력: 19
```

의미:

- **요청 종목 수**: 초기 티커 목록 개수
- **조회 성공/실패**: 데이터 provider 호출 성공/실패 개수
- **데이터 누락 탈락**: 필요한 필드(None)가 있어서 바로 탈락한 종목 수
- **price/change/gap/intraday/volume_ratio/average_volume/dollar_volume 탈락**:
  - 해당 조건을 **처음으로 위반한 시점** 기준으로 탈락 사유를 1개로 집계
  - 여러 조건을 동시에 위반해도 첫 번째 위반 기준으로만 카운트
- **최종 필터 통과**: 모든 필터를 통과한 종목 수
- **점수화 완료**: 점수 계산까지 완료된 종목 수
- **최종 출력**: 상위 `TOP_RESULTS` 컷 이후 콘솔에 실제로 표시된 종목 수

이를 통해

- 어떤 세션/전략에서
- 어떤 필터가 가장 강하게 작동해
- 얼마나 많은 종목을 탈락시키는지

한눈에 파악할 수 있어, 전략 튜닝에 직접적으로 도움이 됩니다.

## 10. 현재 한계점

- Yahoo(`yfinance`)는 **무료 데이터**이기 때문에
  - 지연, 누락, 레이트리밋(429) 등이 발생할 수 있음
  - 프리마켓/애프터마켓 데이터는 종목마다 제공 여부가 다름
- Polygon 기반 자동 유니버스 생성은
  - snapshot all-tickers + 가격 + 유동성 + 타입/심볼 필터 기반의 **1차 정제 버전**이며,
  - Polygon 플랜·레이트리밋·데이터 품질에 영향을 받습니다.
- 타입/심볼 필터는
  - ETF/ETN/워런트/우선주 등을 최대한 제거하려는 **휴리스틱 규칙**일 뿐  
  - 100% 정확한 법적/거래소 분류를 보장하지 않습니다.
- 전략 프리셋의 수치들은
  - **초기 버전**으로, 실제 전략에 맞춰 추후 튜닝이 필요합니다.
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
   - `STRATEGY_PROFILE`, `STRATEGY_PROFILES_FILE`
   - `CACHE_DIR`, `AVG_VOLUME_CACHE_TTL_HOURS`, `SYMBOL_META_CACHE_TTL_HOURS`
   - 스캐너용 필터 값(`MIN_*`)
6. (선택) `DATA_PROVIDER=polygon`, `POLYGON_API_KEY` 설정 후 `python build_universe.py` 실행
7. `generated_universe_candidates.txt` 생성 및 내용(티커 목록) 확인
8. `.env` 에서 `SCAN_MODE=universe`, `UNIVERSE_FILE=generated_universe_candidates.txt` 설정
9. `python main.py` 실행
10. 콘솔에서
    - 현재 시장 세션(ET)
    - 현재 스캔 모드 / provider
    - 현재 전략 프로파일 / 전략 프로파일 파일
    - 로드한 티커 수 / 필터 값
    - 세션 유효 필터(전략 오버라이드 반영)
    - 결과 표(gap%, intraday%, avg_vol, dollar_vol, vol_ratio, score)
    - 조회 성공/실패 개수
    - 필터 리포트(탈락 사유별 개수)
    가 정상적으로 출력되는지 확인

## 12. 전략 요약 리포트 도구

이 프로젝트는 `compare_strategies.py` 로 개별 시점의 전략 비교를 수행할 뿐만 아니라,  
여러 번 실행한 비교 결과(JSON 리포트)를 기반으로 **장기간 누적 성능을 요약**할 수 있습니다.

### 12-1. summarize_strategy_reports.py

```bash
python summarize_strategy_reports.py
```

동작:

- `.env` 의 `REPORTS_DIR` (기본 `reports/`) 안에서
  - `strategy_compare_*.json` 파일들을 모두 찾는다.
- 각 JSON 리포트를 읽어
  - `balanced`, `aggressive`, `conservative` 에 대한 통계를 누적 집계한다.
- 콘솔에 전략별 누적 요약을 출력하고,
  - JSON / CSV / PNG 차트로 요약 결과를 저장한다.

입력 JSON 구조는 `compare_strategies.py` 가 저장한 포맷을 그대로 사용합니다.

### 12-2. 누적 통계 항목

전략별로 다음 항목을 집계합니다.

- `number_of_runs`  
  - 해당 전략이 포함된 유효 리포트 개수
- `average_returned_count`  
  - 각 리포트의 `returned_count` 평균
- `average_passed_filters`  
  - 각 리포트의 `passed_filters` 평균
- `average_score_mean`  
  - 각 리포트의 `average_score` 평균 (None 인 리포트는 제외)
- `best_strategy_win_count`  
  - 한 리포트에서 `average_score` 가 가장 높았던 전략으로 집계된 횟수
- `best_strategy_win_rate`  
  - `win_count / valid_reports * 100%`

여기서 **best strategy 판단 기준**은:

- 각 리포트의 `strategies.*.average_score` 중 가장 큰 값을 가진 전략 1개에만 1승 부여
- 동점인 경우:
  - 첫 번째 최대값만 승리로 처리하거나,  
  - 동점 리포트를 건너뛰는 등 단순 규칙을 적용할 수 있으나,
  - 현재 구현은 **첫 번째 최대값 하나만 승리 처리**합니다.

### 12-3. 상위 종목 빈도 집계

각 전략별로 `top_symbols`에 자주 등장하는 종목 빈도도 집계합니다.

- 데이터 출처:
  - 각 compare JSON 리포트의
    - `strategies -> strategy_name -> top_symbols`
- 결과:
  - `summarize_strategy_reports.py` 실행 시 콘솔에
    - 전략별 상위 빈도 종목 TOP 10 을 출력
  - JSON 요약에도 `top_symbol_frequency` 로 포함

예시:

```text
[balanced 상위 빈도 종목]
- ABC: 7회
- XYZ: 5회
- LMN: 4회
```

### 12-4. 요약 결과 저장 포맷

- JSON:
  - 파일명: `strategy_summary_YYYYMMDD_HHMMSS.json`
  - 위치: `REPORTS_DIR` (기본 `reports/`)
  - 내용:
    - `total_reports`, `valid_reports`, `skipped_reports`
    - `strategies`(각 전략별 누적 통계)
    - `most_frequent_winner`(가장 승리가 많았던 전략 및 비율)
    - `top_symbol_frequency`(전략별 상위 빈도 종목)
- CSV:
  - 파일명: `strategy_summary_YYYYMMDD_HHMMSS.csv`
  - 위치: `REPORTS_DIR`
  - 행 단위(전략별 1행):
    - `strategy`
    - `number_of_runs`
    - `average_returned_count`
    - `average_passed_filters`
    - `average_score_mean`
    - `best_strategy_win_count`
    - `best_strategy_win_rate`
- PNG 차트:
  1. `strategy_summary_avg_score_YYYYMMDD_HHMMSS.png`
     - 전략별 `average_score_mean` bar chart
  2. `strategy_summary_win_rate_YYYYMMDD_HHMMSS.png`
     - 전략별 `best_strategy_win_rate` bar chart

모든 출력은 `.env` 의 `REPORTS_DIR` 아래에 저장되며,  
저장에 실패해도 콘솔 요약 출력은 유지됩니다.

## 14. Theme Tagging

이 프로젝트는 심볼 문자열을 기반으로 **간단한 테마 분류**를 수행해  
전략 성능을 섹터/테마 단위로도 조망할 수 있도록 준비합니다.

### 14-1. Theme Tagging Engine

`scanner/theme_tagger.py` 에서 다음 함수를 제공합니다.

```python
from scanner.theme_tagger import detect_theme_tags

tags = detect_theme_tags("TPET")
```

현재 구현은 **완전히 규칙 기반**이며, 뉴스·재무·주문과는 전혀 무관합니다.

- 입력: `symbol: str`
- 출력: `list[str]` (테마 태그 목록)

내부 룰(대문자 변환 후 부분 문자열 포함 여부):

- `oil` 테마
  - 키워드: `OIL`, `PET`, `ENER`, `DRILL`, `GAS`
- `ai` 테마
  - 키워드: `AI`, `DATA`, `TECH`, `ROBOT`, `ML`
- `biotech` 테마
  - 키워드: `BIO`, `PHAR`, `MED`, `THERA`
- `shipping` 테마
  - 키워드: `SHIP`, `TANK`, `SEA`, `MARINE`
- 어느 테마에도 해당하지 않으면
  - `["unknown"]` 반환

한 심볼이 여러 키워드에 매칭되면 다중 태그를 가질 수 있습니다.  
예: `"BIOAI"` → `["ai", "biotech"]` 와 같이 반환될 수 있습니다.

### 14-2. 전략 비교 리포트에서의 theme_tags

`compare_strategies.py` 실행 시:

```bash
python compare_strategies.py
```

각 전략별 상위 종목(top_symbols)에 대해:

- `detect_theme_tags(symbol)` 를 호출해 `theme_tags` 필드를 추가합니다.

JSON 리포트(`strategy_compare_*.json`) 예:

```json
{
  "strategies": {
    "balanced": {
      "top_symbols": [
        {
          "symbol": "TPET",
          "score": 23.5,
          "theme_tags": ["oil"]
        }
      ]
    }
  },
  "theme_frequency": {
    "oil": 6,
    "biotech": 3,
    "ai": 2
  }
}
```

- `theme_frequency` 는 한 번의 compare 실행에서  
  모든 전략의 상위 종목들에 등장한 테마의 단순 카운트입니다.

CSV 리포트(`strategy_compare_*.csv`)에서도:

- `theme_tags` 컬럼이 추가되어
  - `oil` / `ai,biotech` 등의 문자열로 테마 태그를 확인할 수 있습니다.

### 14-3. summary 리포트에서의 테마 누적

`summarize_strategy_reports.py` 는 여러 개의 compare 리포트를 모아  
전략별 누적 통계를 계산할 뿐 아니라, **전략별 테마 빈도(theme_frequency)** 도 함께 집계합니다.

```bash
python summarize_strategy_reports.py
```

summary JSON(`strategy_summary_*.json`) 구조 예:

```json
{
  "strategies": {
    "balanced": {
      "number_of_runs": 12,
      "average_score_mean": 21.4,
      "stability_score": 6.52,
      "theme_frequency": {
        "oil": 12,
        "ai": 3,
        "biotech": 5
      }
    }
  },
  "theme_frequency": {
    "oil": 20,
    "biotech": 11,
    "ai": 6
  }
}
```

- `strategies.*.theme_frequency`  
  - 해당 전략이 상위 종목으로 자주 선택한 테마들의 누적 빈도
- 루트 레벨 `theme_frequency`  
  - 모든 전략을 합친 전체 테마 빈도

또한, summary 실행 시 다음 차트가 추가로 생성됩니다.

- `strategy_summary_theme_distribution_YYYYMMDD_HHMMSS.png`
  - 전체 리포트에서 자주 등장한 테마들의 bar chart

이를 통해 **전략별로 어떤 테마 종목을 자주 선택하는지**,  
**전체적으로 어떤 테마가 많이 포착되는지** 를 빠르게 파악할 수 있습니다.

### 14-4. browse_reports 에서 top theme 확인

`browse_reports.py` 실행 시 summary 리포트 목록에서:

- `avg stability leader` 와 함께
- `top theme`(summary 기준 가장 자주 등장한 테마)를 추가로 표시합니다.

예:

```text
[summary 리포트 목록]
1. strategy_summary_20260306_140500.json
   - timestamp: 20260306_140500 / valid_reports: 12
   - top winner: aggressive (41.7%)
   - avg stability leader: balanced
   - top theme: oil
   - filters: tags=[premarket, polygon], provider=polygon, session=premarket
```

이를 바탕으로,  
예를 들어 **유가 테마(oil)** 에서 어떤 전략이 안정적으로 강한지,  
**biotech** 나 **ai** 테마에서의 전략 성능이 어떤지 등을  
차후 배치에서 보다 정교하게 분석할 수 있습니다.

