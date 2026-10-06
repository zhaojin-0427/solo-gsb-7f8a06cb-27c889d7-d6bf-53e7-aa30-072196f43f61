"""板材横切排样求解器。

切割模型（与题面约定一致）：
- 只能从上向下横切出行条，再在每行内从左向右纵切出零件；
- 同一行内所有零件（旋转后）高度相同，该高度即行高；
- 每刀必须留下两块正面积板材，锯缝 k 单独占宽（不属于任何一块板材）；
- 尺寸恰好贴边时无需切割；余料可舍弃；成品尺寸必须精确。

由此推出可行性规则：
- R 个行条：行高之和 + (R-1)*k <= H。
  剩余高度 == 0 时无需再切；剩余高度 > k 时需再横切一刀分离底部余料；
  0 < 剩余高度 <= k 时方案不可行（锯缝不足，下刀会留下零面积板材）。
- 行内 m 个零件同理：宽度之和 + (m-1)*k <= W；
  剩余宽度 == 0 时无需再切；剩余宽度 > k 时需再纵切一刀分离行内余料；
  否则该行排法不可行。

优化目标（优先级从高到低）：
1. 入选零件总面积最大；
2. 切割总次数最少；
3. 入选 ID 升序列表字典序最小。

零件数 <= 7，直接枚举所有子集、所有行条划分与每行可行行高。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple, Union

PartId = Union[int, str]


@dataclass(frozen=True)
class Part:
    id: PartId
    w: int
    h: int


@dataclass
class Plan:
    area: int                       # 入选零件总面积
    cuts: int                       # 切割总次数
    id_keys: tuple                  # 入选 ID 的排序键（升序），用于字典序比较
    rows: List[Tuple[int, int, int]]  # (零件掩码, 行高, 该行纵切次数)


def _sort_keys(parts: List[Part]) -> List[tuple]:
    """ID 排序键：全为整数时按数值升序，否则按字符串升序。"""
    all_int = all(isinstance(p.id, int) for p in parts)
    return [(0, p.id) if all_int else (1, str(p.id)) for p in parts]


def solve(board_w: int, board_h: int, kerf: int, parts: List[Part]) -> Plan:
    """返回最优方案；无可放零件时返回空方案（area=0, cuts=0, rows=[]）。"""
    n = len(parts)
    W, H, k = board_w, board_h, kerf
    keys = _sort_keys(parts)
    areas = [p.w * p.h for p in parts]

    # 每个零件子集作为“单独一行”时的可行选项：(行高, 该行纵切次数)
    row_opts: List[List[Tuple[int, int]]] = [[] for _ in range(1 << n)]
    for mask in range(1, 1 << n):
        members = [i for i in range(n) if mask >> i & 1]
        common = {parts[members[0]].w, parts[members[0]].h}
        for i in members[1:]:
            common &= {parts[i].w, parts[i].h}
            if not common:
                break
        m = len(members)
        for hh in sorted(common):
            # 行高定为 hh 后，每个零件的朝向与宽度唯一确定
            wsum = 0
            for i in members:
                p = parts[i]
                wsum += p.w if p.h == hh else p.h
            rem = W - wsum - (m - 1) * k
            if rem == 0:
                row_opts[mask].append((hh, m - 1))      # 恰好贴边，无需分离余料
            elif rem > k:
                row_opts[mask].append((hh, m))          # 需再纵切一刀分离行内余料
            # 0 < rem <= k 或 rem < 0：该行排法不可行

    # 子集面积前缀和
    subset_area = [0] * (1 << n)
    for mask in range(1, 1 << n):
        lsb = mask & -mask
        subset_area[mask] = subset_area[mask ^ lsb] + areas[lsb.bit_length() - 1]

    best = Plan(0, 0, (), [])  # 空方案始终可行，作为兜底

    def consider(area: int, cuts: int, id_keys: tuple, rows) -> None:
        nonlocal best
        better = area > best.area or (
            area == best.area
            and (cuts < best.cuts or (cuts == best.cuts and id_keys < best.id_keys))
        )
        if better:
            best = Plan(area, cuts, id_keys, list(rows))

    def dfs(remaining: int, rows: list, height_sum: int, mask_used: int) -> None:
        r = len(rows)
        if r:
            rem = H - height_sum - (r - 1) * k
            if rem == 0 or rem > k:
                ids = tuple(sorted(keys[i] for i in range(n) if mask_used >> i & 1))
                hcuts = r - 1 if rem == 0 else r
                cuts = hcuts + sum(vc for _, _, vc in rows)
                consider(subset_area[mask_used], cuts, ids, rows)
            if rem <= k:
                # 高度已用尽或锯缝不足：继续加行只会更糟，剪枝
                return
        if not remaining:
            return
        lsb = remaining & -remaining  # 编号最小的未决定零件
        # 分支一：不选该零件
        dfs(remaining ^ lsb, rows, height_sum, mask_used)
        # 分支二：选它，放入某个包含它的行（保证每种划分只枚举一次）
        sub = remaining
        while sub:
            if sub & lsb:
                for hh, vc in row_opts[sub]:
                    dfs(remaining ^ sub, rows + [(sub, hh, vc)],
                        height_sum + hh, mask_used | sub)
            sub = (sub - 1) & remaining

    dfs((1 << n) - 1, [], 0, 0)
    return best


def build_result(board_w: int, board_h: int, kerf: int,
                 parts: List[Part], plan: Plan) -> dict:
    """把最优方案展开为带坐标、方向、切割顺序与余料的结果字典。"""
    W, H, k = board_w, board_h, kerf
    n = len(parts)
    keys = _sort_keys(parts)

    # 行顺序不影响可行性，按行内最小 ID 排序使输出确定
    rows = sorted(
        plan.rows,
        key=lambda row: min(keys[i] for i in range(n) if row[0] >> i & 1),
    )

    rows_out = []
    hcuts = []  # 先执行的全部横切（自上而下）
    vcuts = []  # 再逐行执行的纵切（每行自左向右）
    y = 0
    R = len(rows)
    for ri, (mask, hh, _vc) in enumerate(rows):
        members = sorted((i for i in range(n) if mask >> i & 1),
                         key=lambda i: keys[i])
        x = 0
        parts_out = []
        for j, i in enumerate(members):
            p = parts[i]
            rotated = p.h != hh  # 行高等于原高则不旋转，否则旋转 90°
            w = p.h if rotated else p.w
            parts_out.append({
                "id": p.id, "x": x, "y": y,
                "width": w, "height": hh, "rotated": rotated,
            })
            x += w
            if j < len(members) - 1:
                vcuts.append({
                    "row": ri + 1, "at": x, "kerf": k,
                    "detail": (f"纵切：第 {ri + 1} 行 x={x} 处下刀"
                               f"（锯缝 {k}mm），分离零件 {p.id}（{w}×{hh}）"),
                })
                x += k
        rem_w = W - x
        right_leftover = None
        if rem_w > 0:  # 由可行性保证此时 rem_w > k
            lw = rem_w - k
            right_leftover = {"x": x + k, "y": y, "width": lw, "height": hh}
            vcuts.append({
                "row": ri + 1, "at": x, "kerf": k,
                "detail": (f"纵切：第 {ri + 1} 行 x={x} 处下刀"
                           f"（锯缝 {k}mm），分离行内余料（{lw}×{hh}）"),
            })
        rows_out.append({
            "index": ri + 1, "y": y, "height": hh,
            "parts": parts_out, "right_leftover": right_leftover,
        })
        y += hh
        if ri < R - 1:
            hcuts.append({
                "at": y, "kerf": k,
                "detail": (f"横切：y={y} 处下刀（锯缝 {k}mm），"
                           f"分离第 {ri + 1} 行行条（{W}×{hh}）"),
            })
            y += k

    bottom_leftover = None
    if R == 0:
        bottom_leftover = {"x": 0, "y": 0, "width": W, "height": H}
    else:
        rem_h = H - y
        if rem_h > 0:  # 由可行性保证此时 rem_h > k
            lh = rem_h - k
            bottom_leftover = {"x": 0, "y": y + k, "width": W, "height": lh}
            hcuts.append({
                "at": y, "kerf": k,
                "detail": (f"横切：y={y} 处下刀（锯缝 {k}mm），"
                           f"分离底部余料（{W}×{lh}）"),
            })

    # 切割顺序：先自上而下横切出行条，再逐行自左向右纵切零件
    cuts = []
    seq = 1
    for cut_type, group in (("horizontal", hcuts), ("vertical", vcuts)):
        for c in group:
            cuts.append({"seq": seq, "type": cut_type, **c})
            seq += 1

    selected_mask = 0
    for mask, _, _ in rows:
        selected_mask |= mask
    order = sorted(range(n), key=lambda i: keys[i])
    selected_ids = [parts[i].id for i in order if selected_mask >> i & 1]
    unselected_ids = [parts[i].id for i in order if not (selected_mask >> i & 1)]

    return {
        "board": {"width": W, "height": H},
        "kerf": k,
        "selected_ids": selected_ids,
        "unselected_ids": unselected_ids,
        "total_area": plan.area,
        "total_cuts": len(cuts),
        "rows": rows_out,
        "bottom_leftover": bottom_leftover,
        "cuts": cuts,
    }
