'use strict';

const MAX_PARTS = 7;
const SVG_NS = 'http://www.w3.org/2000/svg';
const PALETTE = ['#f4a261', '#2a9d8f', '#e76f51', '#4363d8', '#8d5a97', '#90be6d', '#e9c46a'];

const partsTbody = document.querySelector('#parts-table tbody');
const addPartBtn = document.getElementById('add-part');
const form = document.getElementById('plan-form');
const errorsDiv = document.getElementById('form-errors');
const resultSection = document.getElementById('result-section');

/* ---------- 零件输入行 ---------- */

function refreshButtons() {
  const count = partsTbody.rows.length;
  addPartBtn.disabled = count >= MAX_PARTS;
  partsTbody.querySelectorAll('.remove-part').forEach((btn) => {
    btn.disabled = count <= 1;
  });
}

function addPartRow(id = '', w = '', h = '') {
  if (partsTbody.rows.length >= MAX_PARTS) return;
  const tr = document.createElement('tr');

  const mkInput = (cls, type, value, placeholder) => {
    const input = document.createElement('input');
    input.type = type;
    input.className = cls;
    input.value = value;
    if (placeholder) input.placeholder = placeholder;
    if (type === 'number') { input.min = '1'; input.step = '1'; }
    const td = document.createElement('td');
    td.appendChild(input);
    return td;
  };

  const tdBtn = document.createElement('td');
  const rm = document.createElement('button');
  rm.type = 'button';
  rm.className = 'remove-part';
  rm.textContent = '删除';
  rm.addEventListener('click', () => { tr.remove(); refreshButtons(); });
  tdBtn.appendChild(rm);

  tr.append(
    mkInput('part-id', 'text', id, '如 P1'),
    mkInput('part-w', 'number', w),
    mkInput('part-h', 'number', h),
    tdBtn,
  );
  partsTbody.appendChild(tr);
  refreshButtons();
}

addPartBtn.addEventListener('click', () => {
  addPartRow(`P${partsTbody.rows.length + 1}`);
});

/* ---------- 错误展示 ---------- */

function fieldElement(key) {
  if (key === 'board.width') return document.getElementById('board-width');
  if (key === 'board.height') return document.getElementById('board-height');
  if (key === 'kerf') return document.getElementById('kerf');
  const m = key.match(/^parts\[(\d+)\]\.(id|width|height)$/);
  if (m) {
    const tr = partsTbody.rows[Number(m[1])];
    if (!tr) return null;
    const cls = { id: '.part-id', width: '.part-w', height: '.part-h' }[m[2]];
    return tr.querySelector(cls);
  }
  return null;
}

function clearErrors() {
  errorsDiv.hidden = true;
  errorsDiv.innerHTML = '';
  document.querySelectorAll('input.invalid').forEach((el) => el.classList.remove('invalid'));
}

function showErrors(errors) {
  const ul = document.createElement('ul');
  for (const [field, msg] of Object.entries(errors)) {
    const li = document.createElement('li');
    li.textContent = `${field}：${msg}`;
    ul.appendChild(li);
    const el = fieldElement(field);
    if (el) el.classList.add('invalid');
  }
  errorsDiv.innerHTML = '';
  errorsDiv.appendChild(ul);
  errorsDiv.hidden = false;
  errorsDiv.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

/* ---------- 提交求解 ---------- */

function parseId(raw) {
  const s = raw.trim();
  if (/^-?\d{1,15}$/.test(s)) return Number(s); // 纯数字 ID 按整数处理，便于数值升序
  return s;
}

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  clearErrors();

  const payload = {
    board: {
      width: Number(document.getElementById('board-width').value),
      height: Number(document.getElementById('board-height').value),
    },
    kerf: Number(document.getElementById('kerf').value),
    parts: [...partsTbody.rows].map((tr) => ({
      id: parseId(tr.querySelector('.part-id').value),
      width: Number(tr.querySelector('.part-w').value),
      height: Number(tr.querySelector('.part-h').value),
    })),
  };

  let data;
  try {
    const resp = await fetch('/api/optimize', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    data = await resp.json();
  } catch (err) {
    showErrors({ 网络: `请求失败：${err.message}` });
    return;
  }
  if (!data.ok) {
    showErrors(data.errors || { 服务: '求解失败' });
    return;
  }
  renderResult(data.result);
  resultSection.hidden = false;
  resultSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
});

/* ---------- 结果渲染 ---------- */

function fmtIds(ids) {
  return ids.length ? ids.map(String).join('、') : '（无）';
}

function renderResult(result) {
  // 摘要
  const summary = document.getElementById('summary');
  summary.innerHTML = '';
  if (result.selected_ids.length === 0) {
    const note = document.createElement('p');
    note.className = 'empty-note';
    note.textContent = '空方案：没有任何零件可以放入该板材（面积够但行高或锯缝不足同样不可行）。';
    summary.appendChild(note);
  }
  const dl = document.createElement('dl');
  const items = [
    ['板材', `${result.board.width} × ${result.board.height} mm`],
    ['锯缝', `${result.kerf} mm`],
    ['入选零件', fmtIds(result.selected_ids)],
    ['未入选零件', fmtIds(result.unselected_ids)],
    ['入选总面积', `${result.total_area} mm²`],
    ['切割次数', `${result.total_cuts} 刀`],
  ];
  for (const [k, v] of items) {
    const dt = document.createElement('dt');
    dt.textContent = k;
    const dd = document.createElement('dd');
    dd.textContent = v;
    dl.append(dt, dd);
  }
  summary.appendChild(dl);

  renderDrawing(result);
  renderCuts(result);
  renderLeftovers(result);
  renderPartsTable(result);
}

function svgEl(tag, attrs = {}) {
  const el = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  return el;
}

function renderDrawing(result) {
  const container = document.getElementById('drawing');
  container.innerHTML = '';
  const W = result.board.width;
  const H = result.board.height;
  const k = result.kerf;

  const svg = svgEl('svg', { viewBox: `0 0 ${W} ${H}`, class: 'board-svg' });

  // 余料斜线填充图案
  const defs = svgEl('defs');
  const pattern = svgEl('pattern', {
    id: 'hatch', width: 8, height: 8,
    patternUnits: 'userSpaceOnUse', patternTransform: 'rotate(45)',
  });
  pattern.appendChild(svgEl('rect', { width: 8, height: 8, fill: '#eceff1' }));
  pattern.appendChild(svgEl('line', {
    x1: 0, y1: 0, x2: 0, y2: 8, stroke: '#b0bec5', 'stroke-width': 2.5,
  }));
  defs.appendChild(pattern);
  svg.appendChild(defs);

  svg.appendChild(svgEl('rect', { x: 0, y: 0, width: W, height: H, class: 'board-bg' }));

  // 余料
  const drawLeftover = (l) => {
    svg.appendChild(svgEl('rect', {
      x: l.x, y: l.y, width: l.width, height: l.height, class: 'leftover',
    }));
  };
  for (const row of result.rows) {
    if (row.right_leftover) drawLeftover(row.right_leftover);
  }
  if (result.bottom_leftover) drawLeftover(result.bottom_leftover);

  // 锯缝与切割线
  for (const cut of result.cuts) {
    if (cut.type === 'horizontal') {
      if (k > 0) {
        svg.appendChild(svgEl('rect', { x: 0, y: cut.at, width: W, height: k, class: 'kerf' }));
      }
      svg.appendChild(svgEl('line', {
        x1: 0, y1: cut.at + k / 2, x2: W, y2: cut.at + k / 2, class: 'cut-line',
      }));
    } else {
      const row = result.rows[cut.row - 1];
      if (k > 0) {
        svg.appendChild(svgEl('rect', {
          x: cut.at, y: row.y, width: k, height: row.height, class: 'kerf',
        }));
      }
      svg.appendChild(svgEl('line', {
        x1: cut.at + k / 2, y1: row.y,
        x2: cut.at + k / 2, y2: row.y + row.height,
        class: 'cut-line',
      }));
    }
  }

  // 零件
  const colorOf = new Map();
  result.selected_ids.forEach((id, i) => colorOf.set(String(id), PALETTE[i % PALETTE.length]));
  const fontSize = Math.max(W, H) / 34;
  for (const row of result.rows) {
    for (const p of row.parts) {
      const g = svgEl('g');
      const title = svgEl('title');
      title.textContent = `零件 ${p.id}：${p.width}×${p.height}`
        + `${p.rotated ? '（已旋转 90°）' : ''}，位于 (${p.x}, ${p.y})`;
      g.appendChild(title);
      const rect = svgEl('rect', {
        x: p.x, y: p.y, width: p.width, height: p.height, class: 'part',
      });
      rect.setAttribute('fill', colorOf.get(String(p.id)));
      g.appendChild(rect);
      const label = svgEl('text', {
        x: p.x + p.width / 2, y: p.y + p.height / 2,
        'font-size': fontSize, class: 'part-label',
      });
      label.textContent = String(p.id);
      g.appendChild(label);
      // 零件足够大时标注尺寸
      if (p.width > fontSize * 5 && p.height > fontSize * 2.4) {
        const dim = svgEl('text', {
          x: p.x + p.width / 2, y: p.y + p.height / 2 + fontSize * 1.15,
          'font-size': fontSize * 0.72, class: 'part-label-dim',
        });
        dim.textContent = `${p.width}×${p.height}${p.rotated ? ' ⟳' : ''}`;
        g.appendChild(dim);
      }
      svg.appendChild(g);
    }
  }

  svg.appendChild(svgEl('rect', { x: 0, y: 0, width: W, height: H, class: 'board-outline' }));
  container.appendChild(svg);

  // 图例
  const legend = document.createElement('div');
  legend.className = 'legend';
  const addLegend = (label, color, extraClass) => {
    const item = document.createElement('span');
    item.className = 'item';
    const sw = document.createElement('span');
    sw.className = `swatch${extraClass ? ' ' + extraClass : ''}`;
    if (color) sw.style.background = color;
    item.append(sw, document.createTextNode(label));
    legend.appendChild(item);
  };
  for (const [id, color] of colorOf) addLegend(`零件 ${id}`, color);
  addLegend('锯缝', null, 'kerf');
  addLegend('余料', null, 'leftover');
  container.appendChild(legend);
}

function renderCuts(result) {
  const ol = document.getElementById('cuts-list');
  ol.innerHTML = '';
  if (result.cuts.length === 0) {
    const li = document.createElement('li');
    li.textContent = '无需切割（零件恰好贴边或空方案）。';
    ol.appendChild(li);
    return;
  }
  for (const cut of result.cuts) {
    const li = document.createElement('li');
    li.textContent = `第 ${cut.seq} 刀｜${cut.detail}`;
    ol.appendChild(li);
  }
}

function renderLeftovers(result) {
  const ul = document.getElementById('leftover-list');
  ul.innerHTML = '';
  const items = [];
  for (const row of result.rows) {
    if (row.right_leftover) {
      const l = row.right_leftover;
      items.push(`第 ${row.index} 行右侧余料：${l.width} × ${l.height} mm（位于 x=${l.x}, y=${l.y}）`);
    }
  }
  if (result.bottom_leftover) {
    const l = result.bottom_leftover;
    items.push(`底部余料：${l.width} × ${l.height} mm（位于 x=${l.x}, y=${l.y}）`);
  }
  if (items.length === 0) items.push('无余料（板材恰好用尽）。');
  for (const text of items) {
    const li = document.createElement('li');
    li.textContent = text;
    ul.appendChild(li);
  }
}

function renderPartsTable(result) {
  const tbody = document.querySelector('#parts-result-table tbody');
  tbody.innerHTML = '';
  const placed = result.rows.flatMap((row) => row.parts);
  if (placed.length === 0) {
    const tr = document.createElement('tr');
    const td = document.createElement('td');
    td.colSpan = 6;
    td.textContent = '无入选零件。';
    tr.appendChild(td);
    tbody.appendChild(tr);
    return;
  }
  for (const p of placed) {
    const tr = document.createElement('tr');
    for (const v of [
      String(p.id), p.x, p.y, p.width, p.height,
      p.rotated ? '旋转 90°' : '原方向',
    ]) {
      const td = document.createElement('td');
      td.textContent = v;
      tr.appendChild(td);
    }
    tbody.appendChild(tr);
  }
}

/* ---------- 初始化 ---------- */

addPartRow('P1', 400, 300);
addPartRow('P2', 300, 200);
addPartRow('P3', 250, 500);
