from __future__ import annotations

"""
Polygon Smart Universe Builder (Massive v3 only).

유니버스 생성은 **Massive v3 reference tickers API** 만 사용합니다.
레거시 snapshot 엔드포인트(/v2/snapshot/locale/us/markets/stocks/tickers)는
사용하지 않으며, 호출 시 빌드가 실패하도록 설계되어 있습니다.

- 기존 watchlist 모드는 그대로 두고, universe 모드에서 사용할 심볼 풀만 생성합니다.
- POLYGON_API_KEY(.env/config) 를 API 키로 사용합니다.
"""

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Set
from urllib.parse import parse_qs, urlencode, urlparse

import requests

from config import load_config


# Massive v3 전용 base URL. 레거시 snapshot 경로로의 우발적 호출 방지.
MASSIVE_V3_BASE = "https://api.massive.com"
MASSIVE_V3_REFERENCE_TICKERS = "/v3/reference/tickers"

# 레거시 엔드포인트 문자열 – 이 경로가 코드에 포함되면 안 됨 (안전 검사용).
_LEGACY_SNAPSHOT_PATH = "/v2/snapshot/locale/us/markets/stocks/tickers"


def _assert_no_legacy_snapshot_url(url: str) -> None:
    """개발 중 레거시 snapshot URL 사용 시 즉시 실패."""
    if _LEGACY_SNAPSHOT_PATH in (url or ""):
        raise RuntimeError(
            "smart_universe_builder must not use the legacy snapshot endpoint. "
            "Use Massive v3 reference tickers only."
        )


PROJECT_ROOT = Path(__file__).resolve().parent


def _get_env_float(name: str, default: float) -> float:
    v = os.getenv(name)
    if v is None or v == "":
        return default
    try:
        return float(v)
    except Exception:
        return default


def _get_env_int(name: str, default: int) -> int:
    v = os.getenv(name)
    if v is None or v == "":
        return default
    try:
        return int(v)
    except Exception:
        return default


# 메타데이터 타입 제외: ETF, ETN, funds, warrants, rights, units, preferreds
_EXCLUDED_TYPES: Set[str] = {
    "ETF",
    "ETN",
    "ETP",
    "FUND",
    "MUTUAL_FUND",
    "TRUST",
    "PFD",
    "PREFERRED",
    "RIGHT",
    "UNIT",
    "WARRANT",
}

# name 필드에 있으면 제외할 키워드
_EXCLUDED_NAME_KEYWORDS: Set[str] = {
    "ETF",
    "ETN",
    "FUND",
    "TRUST",
    "PREFERRED",
    "PREF",
    "WARRANT",
    "RIGHT",
    "RIGHTS",
    "UNIT",
    "UNITS",
}


def _normalize_symbol(raw: str) -> Optional[str]:
    s = (raw or "").strip().upper()
    if not s:
        return None
    for ch in s:
        if not (("A" <= ch <= "Z") or ("0" <= ch <= "9") or ch == "."):
            return None
    return s


def _is_excluded_by_metadata(ticker_type: Optional[str], name: Optional[str]) -> bool:
    """타입/이름으로 ETF, ETN, warrant, preferred 등 제외."""
    t = (ticker_type or "").strip().upper()
    if t in _EXCLUDED_TYPES:
        return True
    n = (name or "").upper()
    if any(kw in n for kw in _EXCLUDED_NAME_KEYWORDS):
        return True
    return False


def _keep_by_metadata(entry: dict) -> bool:
    """
    active, market, locale, type(CS 선호) 기준으로 유지 여부 판단.
    제외 가능한 타입/이름이면 False.
    """
    active = entry.get("active")
    if active is False:
        return False
    market = (entry.get("market") or "").strip().lower()
    if market != "stocks":
        return False
    locale = (entry.get("locale") or "").strip().lower()
    if locale != "us":
        return False
    ticker_type = (entry.get("type") or "").strip().upper()
    if _is_excluded_by_metadata(ticker_type, entry.get("name")):
        return False
    # CS(Common Stock) 선호하지만, 다른 허용 타입도 있을 수 있으므로 제외만 하고 통과
    return True


def _fetch_all_reference_tickers(
    api_key: str,
    verbose: bool,
    timeout_seconds: int = 60,
) -> tuple[List[dict], int]:
    """
    Massive v3 reference tickers 를 cursor 기반 페이지네이션으로 전부 수집.
    반환: (results 리스트, 총 본 개수)
    """
    _assert_no_legacy_snapshot_url(MASSIVE_V3_BASE + MASSIVE_V3_REFERENCE_TICKERS)

    base_url = MASSIVE_V3_BASE.rstrip("/")
    path = MASSIVE_V3_REFERENCE_TICKERS
    url = f"{base_url}{path}"

    params: dict = {
        "apiKey": api_key,
        "market": "stocks",
        "locale": "us",
        "active": "true",
        "limit": 1000,
    }

    all_results: List[dict] = []
    total_seen = 0
    page = 0
    next_url: Optional[str] = None

    while True:
        page += 1
        if next_url is None:
            _assert_no_legacy_snapshot_url(url)
            resp = requests.get(url, params=params, timeout=timeout_seconds)
        else:
            _assert_no_legacy_snapshot_url(next_url)
            # next_url 이 절대 URL 이면 그대로 사용. apiKey 가 없을 수 있으므로 추가.
            parsed = urlparse(next_url)
            qs = parse_qs(parsed.query)
            if "apiKey" not in qs:
                qs["apiKey"] = [api_key]
            new_query = urlencode(qs, doseq=True)
            full_next = f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{new_query}"
            resp = requests.get(full_next, timeout=timeout_seconds)

        resp.raise_for_status()
        data = resp.json()

        results = data.get("results") or []
        total_seen += len(results)
        all_results.extend(results)

        if verbose:
            print(f"Page {page} fetched")

        next_url = data.get("next_url") or None
        if not next_url or not results:
            break

    return all_results, total_seen


def _build_universe_reference_only(
    api_key: str,
    max_symbols: int,
    verbose: bool,
    output_file: Path,
    reports_dir: Path,
) -> tuple[int, int, Path]:
    """
    Massive v3 reference tickers 만 사용해 유니버스 생성.
    (가격/거래량 등 live enrichment 는 이 버전에서 생략.)
    반환: (total_seen, total_kept, report_path)
    """
    if verbose:
        print("Using Massive v3 reference endpoint")
        print(f"Base URL: {MASSIVE_V3_BASE}")
        print("Fetching reference tickers...")

    raw_results, total_seen = _fetch_all_reference_tickers(api_key, verbose)

    kept: List[str] = []
    seen_symbols: set[str] = set()
    for entry in raw_results:
        ticker = (entry.get("ticker") or "").strip()
        if not ticker:
            continue
        sym = _normalize_symbol(ticker)
        if not sym or sym in seen_symbols:
            continue
        if not _keep_by_metadata(entry):
            continue
        seen_symbols.add(sym)
        kept.append(sym)

    total_kept = len(kept)
    if verbose:
        print(f"Metadata-kept symbols: {total_kept}")
        print(
            "Note: This build uses reference_only mode. "
            "Price/volume enrichment is skipped to avoid legacy snapshot dependency."
        )

    # cap
    selected = kept[:max_symbols]
    output_file.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(sorted(selected)) + ("\n" if selected else "")
    output_file.write_text(content, encoding="utf-8")
    if verbose:
        print(f"Saved: {output_file}")

    # JSON report
    report_dir = reports_dir / "universe"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "universe_build_report.json"
    try:
        rel_out = output_file.relative_to(PROJECT_ROOT)
        output_str = str(rel_out)
    except ValueError:
        output_str = str(output_file)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provider": "massive_v3",
        "api_base": MASSIVE_V3_BASE,
        "mode": "reference_only",
        "total_seen": total_seen,
        "total_kept": len(selected),
        "max_symbols": max_symbols,
        "output_file": output_str,
    }
    report_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    if verbose:
        print(f"Saved report: {report_path}")

    return total_seen, len(selected), report_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Polygon Smart Universe Builder (Massive v3)")
    parser.add_argument(
        "--price-min",
        type=float,
        default=None,
        help="reserved for future enrichment (currently unused in reference_only mode)",
    )
    parser.add_argument(
        "--price-max",
        type=float,
        default=None,
        help="reserved for future enrichment (currently unused in reference_only mode)",
    )
    parser.add_argument(
        "--min-volume",
        type=float,
        default=None,
        help="reserved for future enrichment (currently unused in reference_only mode)",
    )
    parser.add_argument(
        "--min-dollar-volume",
        type=float,
        default=None,
        help="reserved for future enrichment (currently unused in reference_only mode)",
    )
    parser.add_argument(
        "--max-symbols",
        type=int,
        default=None,
        help="maximum number of symbols to save (default: UNIVERSE_MAX_SYMBOLS or 1000)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="print detailed progress (Massive v3 usage, pages, counts)",
    )
    args = parser.parse_args()

    cfg = load_config()

    if not cfg.polygon_api_key:
        print(
            "POLYGON_API_KEY 가 설정되어 있지 않습니다. "
            ".env 또는 환경변수에 유효한 API 키를 설정한 뒤 다시 시도해 주세요."
        )
        return 1

    max_symbols_default = _get_env_int("UNIVERSE_MAX_SYMBOLS", 1000)
    max_symbols = args.max_symbols if args.max_symbols is not None else max_symbols_default
    if max_symbols <= 0:
        print(f"max_symbols 값은 1 이상이어야 합니다: max_symbols={max_symbols}")
        return 1

    output_file = PROJECT_ROOT / "universe" / "generated_universe.txt"

    try:
        total_seen, total_kept, report_path = _build_universe_reference_only(
            api_key=cfg.polygon_api_key,
            max_symbols=max_symbols,
            verbose=args.verbose,
            output_file=output_file,
            reports_dir=cfg.reports_dir,
        )
    except requests.RequestException as e:
        print(f"Massive v3 request failed: {e}")
        return 1
    except RuntimeError as e:
        print(str(e))
        return 1

    if args.verbose:
        print(f"Total seen: {total_seen}, saved: {total_kept}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
