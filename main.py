"""FastAPI 后端：板材横切排样优化。

- GET  /            返回单页应用
- POST /api/optimize  求解排样方案
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from solver import Part, build_result, solve

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="板材横切排样优化")


def _as_int(value) -> Optional[int]:
    """接受整数或整数值浮点（如 100.0），其余返回 None。布尔值非法。"""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _norm_id(value):
    """零件 ID：非空字符串或整数（整数值浮点归为整数），其余返回 None。"""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        s = value.strip()
        if s:
            return s
    return None


def validate(payload) -> Tuple[Optional[int], Optional[int], Optional[int],
                               List[Part], dict]:
    """校验请求体，返回 (板宽, 板高, 锯缝, 零件列表, 字段错误字典)。"""
    errors: dict = {}
    board_w = board_h = kerf = None
    parts: List[Part] = []

    if not isinstance(payload, dict):
        return None, None, None, [], {"payload": "请求体必须为 JSON 对象"}

    board = payload.get("board")
    if not isinstance(board, dict):
        errors["board"] = "缺少板材参数（board.width / board.height）"
    else:
        w = _as_int(board.get("width"))
        if w is None or not 100 <= w <= 3000:
            errors["board.width"] = "板材宽度必须为 100～3000 的整数"
        else:
            board_w = w
        h = _as_int(board.get("height"))
        if h is None or not 100 <= h <= 3000:
            errors["board.height"] = "板材高度必须为 100～3000 的整数"
        else:
            board_h = h

    k = _as_int(payload.get("kerf"))
    if k is None or not 0 <= k <= 10:
        errors["kerf"] = "锯缝必须为 0～10 的整数"
    else:
        kerf = k

    raw_parts = payload.get("parts")
    if not isinstance(raw_parts, list) or not 1 <= len(raw_parts) <= 7:
        errors["parts"] = "零件数量必须为 1～7 件"
    else:
        seen = set()
        for i, rp in enumerate(raw_parts):
            if not isinstance(rp, dict):
                errors[f"parts[{i}]"] = "零件格式错误"
                continue
            pid = _norm_id(rp.get("id"))
            if pid is None:
                errors[f"parts[{i}].id"] = "ID 不能为空（字符串或整数）"
            elif str(pid) in seen:
                errors[f"parts[{i}].id"] = f"ID「{pid}」重复"
            else:
                seen.add(str(pid))
            w = _as_int(rp.get("width"))
            if w is None or w < 1:
                errors[f"parts[{i}].width"] = "零件宽度必须为正整数"
            h = _as_int(rp.get("height"))
            if h is None or h < 1:
                errors[f"parts[{i}].height"] = "零件高度必须为正整数"
            if pid is not None and w is not None and w >= 1 \
                    and h is not None and h >= 1:
                parts.append(Part(pid, w, h))

    return board_w, board_h, kerf, parts, errors


@app.post("/api/optimize")
async def optimize(request: Request):
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse(
            {"ok": False, "errors": {"payload": "请求体不是合法 JSON"}},
            status_code=400,
        )
    board_w, board_h, kerf, parts, errors = validate(payload)
    if errors:
        return JSONResponse({"ok": False, "errors": errors}, status_code=422)
    plan = solve(board_w, board_h, kerf, parts)
    return {"ok": True, "result": build_result(board_w, board_h, kerf, parts, plan)}


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
