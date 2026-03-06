from __future__ import annotations

from rich.console import Console

from config import load_config
from universe.polygon_universe_builder import build_universe
from utils.logger import get_logger

log = get_logger(__name__)


def main() -> int:
    console = Console()
    cfg = load_config()

    console.print("유니버스 생성 시작")
    console.print(f"데이터 provider: {cfg.data_provider}")

    try:
        result = build_universe(cfg)
    except RuntimeError as e:
        console.print(str(e))
        return 1
    except Exception as e:
        log.exception("Universe build failed: %s", e)
        console.print(f"유니버스 생성 중 오류가 발생했습니다: {e}")
        return 1

    console.print(
        f"가격 범위: {cfg.universe_min_price:.2f} ~ {cfg.universe_max_price:.2f}"
    )
    console.print(f"수집 후보 수: {result.total_candidates}")
    console.print(f"최종 저장 종목 수: {result.saved_symbols}")
    console.print(f"출력 파일: {result.output_file}")

    console.print(
        "\n이제 .env 에서 SCAN_MODE=universe, "
        f"UNIVERSE_FILE={result.output_file.name} 으로 설정하면 "
        "생성된 유니버스를 기반으로 스캐너를 돌릴 수 있습니다."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

