# 板材横切排样优化

本地网页工具：输入一张矩形板材、锯缝宽度和 1～7 件矩形零件，求**可执行**的横切排样方案。
后端 Python/FastAPI，前端原生 HTML/JavaScript/CSS（SVG 按比例绘制），全部依赖随容器安装。

## 启动（单条命令）

```bash
docker compose up --build
```

然后浏览器访问 **http://localhost:8000**

（等价写法：`docker build -t plate-cutting . && docker run -p 8000:8000 plate-cutting`）

停止：`Ctrl+C`，或 `docker compose down`。

## 规则说明

- 板材宽、高均为 100～3000 mm 的整数；锯缝为 0～10 mm 的整数；
  零件 1～7 件，ID 唯一，宽、高为正整数，每件可旋转 90°。
- 切割方式：只能**从上向下横切**出行条，再在每行内**从左向右纵切**出零件；
  同一行内所有零件（旋转后）高度相同，该高度即行高。
- 每一刀必须留下两块正面积板材；锯缝单独占宽（不属于任何一块板材）；
  尺寸恰好贴边时无需切割；余料可舍弃；成品尺寸必须精确。
  因此：剩余高度/宽度为 0 时无需下刀，大于锯缝时可下刀分离余料，
  介于两者之间（0 < 余量 ≤ 锯缝）则方案不可行——**面积够但行高或锯缝不足不能算可行**。
- 允许舍弃放不下的零件。优化目标按优先级：
  1. 入选零件总面积最大；
  2. 切割总次数最少；
  3. 入选 ID 升序列表字典序最小。
- 没有任何零件可放时返回空方案（全板记为余料，0 刀）。

## 求解方法

零件数 ≤ 7，枚举所有零件子集、所有行条划分与每行的可行行高（每个零件至多两种朝向，
行高取各零件 `{宽, 高}` 的交集），按上述优先级选优；坐标、切割顺序与余料由最优方案展开生成。
`test_solver.py` 内含与独立朴素枚举的随机交叉验证（本地运行 `python3 test_solver.py`，仅需标准库）。

## API

### POST /api/optimize

请求：

```json
{
  "board": { "width": 1000, "height": 800 },
  "kerf": 3,
  "parts": [
    { "id": "P1", "width": 400, "height": 300 },
    { "id": "P2", "width": 300, "height": 200 }
  ]
}
```

响应（`ok: true`）：

```json
{
  "ok": true,
  "result": {
    "board": { "width": 1000, "height": 800 },
    "kerf": 3,
    "selected_ids": ["P1", "P2"],
    "unselected_ids": [],
    "total_area": 180000,
    "total_cuts": 3,
    "rows": [
      {
        "index": 1, "y": 0, "height": 300,
        "parts": [
          { "id": "P1", "x": 0, "y": 0, "width": 400, "height": 300, "rotated": false },
          { "id": "P2", "x": 403, "y": 0, "width": 200, "height": 300, "rotated": true }
        ],
        "right_leftover": { "x": 606, "y": 0, "width": 394, "height": 300 }
      }
    ],
    "bottom_leftover": { "x": 0, "y": 303, "width": 1000, "height": 497 },
    "cuts": [
      { "seq": 1, "type": "horizontal", "at": 300, "kerf": 3, "detail": "横切：……" },
      { "seq": 2, "type": "vertical", "row": 1, "at": 400, "kerf": 3, "detail": "纵切：……" }
    ]
  }
}
```

- 坐标系：原点在板材左上角，x 向右、y 向下，单位 mm。
- `cuts` 即执行顺序：先自上而下横切出行条，再逐行自左向右纵切。
- 输入非法时返回 `ok: false`，`errors` 以字段名为键指出问题，例如
  `{"board.width": "板材宽度必须为 100～3000 的整数", "parts[1].id": "ID「P1」重复"}`。

## 本地开发（不用 Docker）

```bash
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

## 目录结构

```
main.py              FastAPI 应用与输入校验
solver.py            排样求解器（枚举 + 三优先级选优）
static/index.html    单页应用
static/app.js        交互与 SVG 绘制
static/style.css     样式
test_solver.py       求解器测试与随机交叉验证
Dockerfile           镜像构建（依赖随容器安装）
docker-compose.yml   Compose 配置
requirements.txt     Python 依赖
```
