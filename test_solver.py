"""求解器测试：针对性用例 + 与独立朴素枚举的随机交叉验证 + 布局结构校验。

运行：python3 test_solver.py
"""

import itertools
import random

from solver import Part, build_result, solve


# ---------- 独立朴素枚举（用于交叉验证最优性） ----------

def brute_force(W, H, k, parts):
    """与 solve 无关的另一套枚举实现，返回 (area, cuts, id_keys)。"""
    n = len(parts)
    all_int = all(isinstance(p.id, int) for p in parts)
    keys = [(0, p.id) if all_int else (1, str(p.id)) for p in parts]
    areas = [p.w * p.h for p in parts]

    row_opt_cache = {}

    def row_options(idxs):
        key = tuple(sorted(idxs))
        if key in row_opt_cache:
            return row_opt_cache[key]
        common = {parts[key[0]].w, parts[key[0]].h}
        for i in key[1:]:
            common &= {parts[i].w, parts[i].h}
        m = len(key)
        out = []
        for hh in common:
            wsum = sum(parts[i].w if parts[i].h == hh else parts[i].h for i in key)
            rem = W - wsum - (m - 1) * k
            if rem == 0:
                out.append((hh, m - 1))
            elif rem > k:
                out.append((hh, m))
        row_opt_cache[key] = out
        return out

    def set_partitions(items):
        if not items:
            yield []
            return
        first, rest = items[0], items[1:]
        for p in set_partitions(rest):
            yield [(first,)] + p
            for i in range(len(p)):
                yield p[:i] + [p[i] + (first,)] + p[i + 1:]

    best = (0, 0, ())  # 空方案

    for r in range(1, n + 1):
        for subset in itertools.combinations(range(n), r):
            area = sum(areas[i] for i in subset)
            id_keys = tuple(sorted(keys[i] for i in subset))
            for partition in set_partitions(list(subset)):
                opts = [row_options(block) for block in partition]
                if any(not o for o in opts):
                    continue
                for choice in itertools.product(*opts):
                    rows = len(partition)
                    hsum = sum(hh for hh, _ in choice)
                    rem = H - hsum - (rows - 1) * k
                    if rem == 0:
                        hcuts = rows - 1
                    elif rem > k:
                        hcuts = rows
                    else:
                        continue
                    cuts = hcuts + sum(vc for _, vc in choice)
                    if (area > best[0]
                            or (area == best[0]
                                and (cuts < best[1]
                                     or (cuts == best[1] and id_keys < best[2])))):
                        best = (area, cuts, id_keys)
    return best


# ---------- 布局结构校验 ----------

def validate_layout(W, H, k, parts, result):
    by_id = {p.id: p for p in parts}
    placed = []
    rows = result["rows"]
    y = 0
    for ri, row in enumerate(rows):
        assert row["y"] == y, "行 y 坐标错误"
        hh = row["height"]
        assert hh > 0
        x = 0
        ps = row["parts"]
        assert ps, "行不能为空"
        for j, p in enumerate(ps):
            src = by_id[p["id"]]
            if p["rotated"]:
                assert p["width"] == src.h and p["height"] == src.w, "旋转尺寸错误"
            else:
                assert p["width"] == src.w and p["height"] == src.h, "成品尺寸必须精确"
            assert p["height"] == hh, "同行零件高度必须一致"
            assert p["x"] == x and p["y"] == y, "零件坐标错误"
            assert 0 <= p["x"] and p["x"] + p["width"] <= W
            assert 0 <= p["y"] and p["y"] + p["height"] <= H
            x += p["width"]
            if j < len(ps) - 1:
                x += k  # 零件间锯缝
            placed.append(p["id"])
        rem_w = W - x
        if row["right_leftover"] is None:
            assert rem_w == 0, "无行内余料时必须恰好贴边"
        else:
            l = row["right_leftover"]
            assert rem_w > k, "锯缝不足不能算可行"
            assert l["x"] == x + k and l["y"] == y
            assert l["width"] == rem_w - k > 0 and l["height"] == hh
        y += hh
        if ri < len(rows) - 1:
            y += k  # 行间锯缝
    rem_h = H - y
    if not rows:
        assert result["bottom_leftover"] == {"x": 0, "y": 0, "width": W, "height": H}
    elif result["bottom_leftover"] is None:
        assert rem_h == 0, "无底部余料时必须恰好贴边"
    else:
        l = result["bottom_leftover"]
        assert rem_h > k, "锯缝不足不能算可行"
        assert l["x"] == 0 and l["y"] == y + k
        assert l["width"] == W and l["height"] == rem_h - k > 0
    # 切割次数与顺序
    expected = 0
    if rows:
        expected += len(rows) - 1 + (1 if result["bottom_leftover"] else 0)
        for row in rows:
            expected += len(row["parts"]) - 1 + (1 if row["right_leftover"] else 0)
    assert result["total_cuts"] == expected == len(result["cuts"]), "切割次数不一致"
    types = [c["type"] for c in result["cuts"]]
    assert types == sorted(types, key=lambda t: 0 if t == "horizontal" else 1), \
        "必须先横切后纵切"
    assert [c["seq"] for c in result["cuts"]] == list(range(1, len(result["cuts"]) + 1))
    # 面积与 ID
    assert result["total_area"] == sum(by_id[i].w * by_id[i].h for i in placed)
    assert sorted(map(str, result["selected_ids"])) == sorted(map(str, placed))
    assert (sorted(map(str, result["selected_ids"] + result["unselected_ids"]))
            == sorted(map(str, by_id)))


# ---------- 针对性用例 ----------

def test_exact_fit_zero_cuts():
    plan = solve(100, 100, 5, [Part("A", 100, 100)])
    assert (plan.area, plan.cuts) == (10000, 0)


def test_kerf_insufficient_infeasible():
    # 剩余高度恰等于锯缝：下刀会留下零面积板材 → 不可行（锯缝不足）
    plan = solve(100, 100, 10, [Part("A", 100, 90)])
    assert plan.area == 0 and plan.rows == []


def test_kerf_just_enough():
    plan = solve(100, 100, 10, [Part("A", 100, 89)])
    assert (plan.area, plan.cuts) == (8900, 1)
    result = build_result(100, 100, 10, [Part("A", 100, 89)], plan)
    assert result["bottom_leftover"] == {"x": 0, "y": 99, "width": 100, "height": 1}


def test_rotation():
    plan = solve(100, 200, 0, [Part("A", 150, 50)])
    assert plan.area == 7500
    result = build_result(100, 200, 0, [Part("A", 150, 50)], plan)
    assert result["rows"][0]["parts"][0]["rotated"] is True


def test_cut_tiebreak():
    # {A} 与 {B,C} 面积同为 20000，{A} 只需 0 刀
    parts = [Part("A", 200, 100), Part("B", 100, 100), Part("C", 100, 100)]
    plan = solve(200, 100, 0, parts)
    assert plan.area == 20000 and plan.cuts == 0
    result = build_result(200, 100, 0, parts, plan)
    assert result["selected_ids"] == ["A"]


def test_id_tiebreak():
    # A、B 面积相同、同为 0 刀，取 ID 字典序较小者
    parts = [Part("B", 100, 100), Part("A", 100, 100)]
    result = build_result(100, 100, 0, parts, solve(100, 100, 0, parts))
    assert result["selected_ids"] == ["A"]
    assert result["unselected_ids"] == ["B"]


def test_empty_plan():
    # 怎么旋转都放不下
    plan = solve(100, 100, 0, [Part("A", 50, 120)])
    assert plan.area == 0 and plan.rows == []
    result = build_result(100, 100, 0, [Part("A", 50, 120)], plan)
    assert result["selected_ids"] == [] and result["unselected_ids"] == ["A"]
    assert result["cuts"] == []


def test_multi_row_with_kerf():
    # 两零件同行唯一公共行高 40，但 100+90+5=195 距板宽恰剩 5=锯缝 → 同行不可行；
    # 只能分两行：行高 40+40，行间锯缝 5，底部余量 15>5 可再切一刀
    parts = [Part("A", 100, 40), Part("B", 90, 40)]
    plan = solve(200, 100, 5, parts)
    assert plan.area == 7600 and plan.cuts == 4
    result = build_result(200, 100, 5, parts, plan)
    assert len(result["rows"]) == 2
    assert result["bottom_leftover"] == {"x": 0, "y": 90, "width": 200, "height": 10}
    validate_layout(200, 100, 5, parts, result)


def test_sample_from_page():
    parts = [Part("P1", 400, 300), Part("P2", 300, 200), Part("P3", 250, 500)]
    plan = solve(1000, 800, 3, parts)
    assert plan.area == 305000  # 三件全选，各占一行
    result = build_result(1000, 800, 3, parts, plan)
    validate_layout(1000, 800, 3, parts, result)


# ---------- 随机交叉验证 ----------

def fuzz(rounds=120, seed=20261005):
    rng = random.Random(seed)
    for t in range(rounds):
        W = rng.randint(100, 3000)
        H = rng.randint(100, 3000)
        k = rng.randint(0, 10)
        n = rng.randint(1, 7)
        parts = [Part(f"P{i + 1}", rng.randint(1, 1600), rng.randint(1, 1600))
                 for i in range(n)]
        plan = solve(W, H, k, parts)
        bf = brute_force(W, H, k, parts)
        assert (plan.area, plan.cuts, plan.id_keys) == bf, (
            f"第{t}例不一致: W={W} H={H} k={k} parts={parts} "
            f"solve=({plan.area},{plan.cuts},{plan.id_keys}) brute={bf}")
        result = build_result(W, H, k, parts, plan)
        validate_layout(W, H, k, parts, result)
    print(f"随机交叉验证通过：{rounds} 例")


if __name__ == "__main__":
    test_exact_fit_zero_cuts()
    test_kerf_insufficient_infeasible()
    test_kerf_just_enough()
    test_rotation()
    test_cut_tiebreak()
    test_id_tiebreak()
    test_empty_plan()
    test_multi_row_with_kerf()
    test_sample_from_page()
    print("针对性用例全部通过")
    fuzz()
    print("全部测试通过")
