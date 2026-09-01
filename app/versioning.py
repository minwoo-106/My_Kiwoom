"""전략 결과를 서로 섞지 않기 위한 실행 버전 식별자입니다."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


# 전략 계산식 자체를 바꾸지 않는 한 이 값은 유지합니다.
STRATEGY_VERSION = "Trend Pullback V1 Multi"
CONFIG_VERSION = "V1-2026-09-01"


@dataclass(frozen=True)
class ExecutionVersion:
    strategy_version: str = STRATEGY_VERSION
    config_version: str = CONFIG_VERSION
    git_commit: str = "unknown"


def current_execution_version() -> ExecutionVersion:
    """Git이 없는 배포 폴더에서도 기록 기능이 멈추지 않도록 합니다."""
    try:
        root = Path(__file__).resolve().parents[1]
        commit = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=root,
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=1,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        commit = "unknown"
    return ExecutionVersion(git_commit=commit or "unknown")
