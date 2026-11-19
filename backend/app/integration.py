"""Mount Backend Dev 2 case routers behind Backend Dev 1 access control.

Dev 2's analysis and strategy routers (``backend/src``) have no authentication of
their own. They are mounted here only with router-level dependencies that require:

- an authenticated lawyer session (via ``get_case_access`` -> ``LawyerDep``),
- active membership of the case in the path (404 for unknown or not-owned cases),
- a same-origin ``Origin`` header on state-changing requests (CSRF).

Dev 2 handler code is unchanged. See ``DOCS/dev1-to-dev2-requests.md`` R4/R5.
"""

import sys
from pathlib import Path

from fastapi import Depends, FastAPI

from app.auth.dependencies import require_same_origin_for_writes
from app.cases.dependencies import get_case_access

API_PREFIX = "/api/v1"
CASE_GUARDS = [
    Depends(require_same_origin_for_writes),
    Depends(get_case_access),
]


def _ensure_repo_root_importable() -> None:
    # Dev 2 modules import themselves as ``backend.src.*``, which needs the
    # repository root on sys.path.
    repo_root = str(Path(__file__).resolve().parents[2])
    if repo_root not in sys.path:
        sys.path.append(repo_root)


def include_dev2_case_routers(app: FastAPI) -> None:
    _ensure_repo_root_importable()
    from backend.src.analysis.router import router as analysis_router
    from backend.src.strategy.router import router as strategy_router

    for router in (analysis_router, strategy_router):
        app.include_router(router, prefix=API_PREFIX, dependencies=CASE_GUARDS)
