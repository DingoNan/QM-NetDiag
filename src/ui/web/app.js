/* ============================================================
   NetDiag v2 · 前端逻辑 + Python 桥接
   ============================================================ */

// ============================================================
// 状态
// ============================================================
const State = {
  view: "welcome",          // welcome / dashboard / testing / result
  scenario: "general",
  category: "all",
  targets: [],             // 当前显示的目标列表
  allTargets: [],          // 全量目标（来自 Python）
  lastResult: null,        // 最近一次测试结果
  testing: false,
};

// ============================================================
// Python 桥接（pywebview 暴露的 window.pywebview.api）
// ============================================================
const API = {
  // 异步调用 Python 方法
  call: async (method, ...args) => {
    if (window.pywebview && window.pywebview.api) {
      try {
        return await window.pywebview.api[method](...args);
      } catch (e) {
        console.error(`API.${method} failed:`, e);
        throw e;
      }
    }
    // 浏览器降级（开发模式）：返回模拟数据
    return mockApi(method, args);
  },
};

// 模拟 API（用于本地浏览器调试）
async function mockApi(method, args) {
  console.log(`[Mock API] ${method}`, args);
  if (method === "get_preset_targets") {
    return MOCK_TARGETS;
  }
  if (method === "get_categories") {
    return MOCK_CATEGORIES;
  }
  if (method === "quick_test") {
    return MOCK_TEST_RESULT;
  }
  if (method === "save_poster") {
    return { success: true, path: "C:/tmp/poster.png" };
  }
  if (method === "copy_summary") {
    return { success: true };
  }
  return null;
}

// ============================================================
// Mock 数据（浏览器调试用）
// ============================================================
const MOCK_CATEGORIES = [
  { id: "game", name: "游戏", icon: "🎮", color: "#FF3D9A" },
  { id: "video", name: "视频", icon: "🎬", color: "#8B5CF6" },
  { id: "chat", name: "通讯", icon: "💬", color: "#00E5FF" },
  { id: "dev", name: "开发", icon: "👨‍💻", color: "#00FF9F" },
  { id: "overseas", name: "海外", icon: "🌍", color: "#FF3D5A" },
];

const MOCK_TARGETS = [
  { id: "tx-lol", name: "腾讯·英雄联盟", category: "game", score: 95, grade: "A+", latency: 35, loss: 0, status: "good", metrics: { avg_latency_ms: 35, loss_pct: 0, jitter_ms: 1.2 } },
  { id: "bilibili", name: "B站", category: "video", score: 88, grade: "A", latency: 80, loss: 0, status: "good", metrics: { avg_latency_ms: 80, loss_pct: 0 } },
  { id: "wechat", name: "微信", category: "chat", score: 90, grade: "A", latency: 60, loss: 0, status: "good", metrics: { avg_latency_ms: 60, loss_pct: 0 } },
  { id: "github", name: "GitHub", category: "dev", score: 65, grade: "B", latency: 280, loss: 0, status: "warn", metrics: { avg_latency_ms: 280, loss_pct: 0 } },
  { id: "steam", name: "Steam", category: "game", score: 78, grade: "B", latency: 150, loss: 0, status: "good", metrics: { avg_latency_ms: 150, loss_pct: 0 } },
  { id: "google", name: "Google", category: "overseas", score: 50, grade: "C", latency: 380, loss: 1, status: "warn", metrics: { avg_latency_ms: 380, loss_pct: 1 } },
  { id: "youtube", name: "YouTube", category: "video", score: 75, grade: "B", latency: 200, loss: 0, status: "good", metrics: { avg_latency_ms: 200, loss_pct: 0 } },
  { id: "taobao", name: "淘宝", category: "shopping", score: 92, grade: "A+", latency: 50, loss: 0, status: "good", metrics: { avg_latency_ms: 50, loss_pct: 0 } },
];

const MOCK_TEST_RESULT = {
  overall: {
    score: 82,
    grade: "A",
    label: "整体流畅",
    color: "#00FF9F",
    comment: "整体表现优秀；亮点：腾讯·英雄联盟、B站；短板：GitHub、Google。继续保持。",
    category_breakdown: {
      game: { score: 86, grade: "A", label: "流畅" },
      video: { score: 81, grade: "A", label: "流畅" },
      chat: { score: 90, grade: "A", label: "流畅" },
      dev: { score: 65, grade: "B", label: "一般" },
      overseas: { score: 50, grade: "C", label: "略卡" },
  },
    },
    targets: MOCK_TARGETS,
    duration: 28,
    scenario: "general",
    time: new Date().toISOString(),
};

// ============================================================
// 视图切换
// ============================================================
function showView(name) {
  ["welcome", "dashboard","testing", "result", "history", "settings", "custom"].forEach(v => {
    const el = document.getElementById(`view-${v}`);
    if (el) el.style.display = (v === name) ? "" : "none";
  });
  State.view = name;
  // 视图进入时的初始化
  if (name === "history") renderHistoryView();
  if (name === "settings") renderSettingsView();
  if (name === "custom") renderCustomView();
}

// ============================================================
// 启动：加载目标列表
// ============================================================
async function init() {
  try {
    State.allTargets = await API.call("get_preset_targets", State.scenario);
    State.targets = [...State.allTargets];
    renderDashboard();
  } catch (e) {
    console.error("初始化失败", e);
  }
  bindEvents();
}

function bindEvents() {
  // 场景选择
  document.querySelectorAll(".scenario-chip").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".scenario-chip").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      State.scenario = btn.dataset.scenario;
      // 重新加载目标
      API.call("get_preset_targets", State.scenario).then(targets => {
        State.allTargets = targets || [];
        State.targets = [...State.allTargets];
        renderDashboard();
      });
    });
  });

  // 启动测试
  document.getElementById("btn-start-test").addEventListener("click", () => startTest());
  document.getElementById("btn-quick-test").addEventListener("click", () => startTest());
  document.getElementById("btn-refresh").addEventListener("click", () => startTest());
  document.getElementById("btn-retry").addEventListener("click", () => startTest());

  // 停止测试
  document.getElementById("btn-stop-test").addEventListener("click", () => stopTest());

  // 分类切换
  document.querySelectorAll(".category-tab").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".category-tab").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      State.category = btn.dataset.cat;
      filterTargets();
    });
  });

  // 结果页操作
  document.getElementById("btn-share").addEventListener("click", () => onShare());
  document.getElementById("btn-save-img").addEventListener("click", () => onSaveImg());
  document.getElementById("btn-copy").addEventListener("click", () => onCopy());

  // 自定义目标（占位）
  document.getElementById("btn-custom-target").addEventListener("click", () => {
    showView("custom");
  });

  // 顶部按钮（占位）
  document.getElementById("btn-history").addEventListener("click", () => {
    showView("history");
  });
  document.getElementById("btn-theme").addEventListener("click", () => {
    const order = ["dark", "light", "system"];
    const cur = State.theme || "dark";
    const next = order[(order.indexOf(cur) + 1) % order.length];
    State.theme = next;
    document.documentElement.setAttribute("data-theme", next);
    API.call("update_setting", "theme", next).catch(() => {});
    alert(`主题已切换为：${next}`);
  });
  document.getElementById("btn-settings").addEventListener("click", () => {
    showView("settings");
  });

  // 历史页
  const btnBackHist = document.getElementById("btn-back-from-history");
  if (btnBackHist) btnBackHist.addEventListener("click", () => showView("dashboard"));
  const btnClearHist = document.getElementById("btn-clear-history");
  if (btnClearHist) btnClearHist.addEventListener("click", async () => {
    if (!confirm("确定要清空所有历史记录？此操作不可恢复。")) return;
    const r = await API.call("clear_history");
    alert("已清空 " + (r.cleared || 0) + " 条历史");
    renderHistoryView();
  });
  const btnExportHist = document.getElementById("btn-export-history");
  if (btnExportHist) btnExportHist.addEventListener("click", async () => {
    try {
      const data = await API.call("get_history", 365 * 5);
      const json = JSON.stringify(data, null, 2);
      const blob = new Blob([json], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `netdiag-history-${Date.now()}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      alert("导出失败：" + e);
    }
  });

  // 设置页
  const btnBackSet = document.getElementById("btn-back-from-settings");
  if (btnBackSet) btnBackSet.addEventListener("click", () => showView("dashboard"));
  const btnClearAll = document.getElementById("btn-clear-all-data");
  if (btnClearAll) btnClearAll.addEventListener("click", async () => {
    if (!confirm("确定要清空全部用户数据？包括收藏、自定义、历史、成就。")) return;
    await API.call("clear_all_user_data");
    alert("已清空全部数据");
    renderSettingsView();
  });
  const btnResetSet = document.getElementById("btn-reset-settings");
  if (btnResetSet) btnResetSet.addEventListener("click", async () => {
    await API.call("reset_settings");
    alert("已重置设置");
    renderSettingsView();
  });
  // 设置项变化
  ["setting-theme", "setting-font-size"].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener("change", async (e) => {
      const key = id.replace("setting-", "").replace("-", "_");
      await API.call("update_setting", key, e.target.value);
    });
  });
  ["setting-test-count", "setting-timeout", "setting-ping-count"].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener("change", async (e) => {
      const key = { "setting-test-count": "default_test_count", "setting-timeout": "test_timeout", "setting-ping-count": "ping_count" }[id];
      await API.call("update_setting", key, parseInt(e.target.value));
    });
  });

  // 自定义目标页
  const btnBackCustom = document.getElementById("btn-back-from-custom");
  if (btnBackCustom) btnBackCustom.addEventListener("click", () => showView("dashboard"));
  const btnAddCustom = document.getElementById("btn-add-custom");
  if (btnAddCustom) btnAddCustom.addEventListener("click", async () => {
    const name = document.getElementById("custom-name").value.trim();
    const host = document.getElementById("custom-host").value.trim();
    const port = parseInt(document.getElementById("custom-port").value) || 443;
    const test_type = document.getElementById("custom-test-type").value;
    const note = document.getElementById("custom-note").value.trim();
    if (!name || !host) {
      alert("名称和主机不能为空");
      return;
    }
    await API.call("add_custom_target", { name, host, port, test_type, note });
    // 清空表单
    document.getElementById("custom-name").value = "";
    document.getElementById("custom-host").value = "";
    document.getElementById("custom-note").value = "";
    renderCustomView();
  });
}

// ============================================================
// 仪表盘渲染
// ============================================================
function renderDashboard() {
  renderTargetGrid();
  if (State.lastResult) {
    renderResultIntoDashboard(State.lastResult);
  }
}

function filterTargets() {
  if (State.category === "all") {
    State.targets = [...State.allTargets];
  } else {
    State.targets = State.allTargets.filter(t => t.category === State.category);
  }
  renderTargetGrid();
}

function renderTargetGrid() {
  const grid = document.getElementById("target-grid");
  if (!grid) return;
  if (State.targets.length === 0) {
    grid.innerHTML = '<div style="color: var(--text-muted); padding: 32px; text-align: center;">该分类下暂无目标</div>';
    return;
  }
  grid.innerHTML = State.targets.map(t => {
    const score = t.score ?? null;
    const latency = t.metrics ? (t.metrics.avg_latency_ms ?? null) : null;
    const loss = t.metrics ? (t.metrics.loss_pct ?? 0) : null;
    let status = t.status || "idle";
    if (score !== null) {
      if (score >= 80) status = "good";
      else if (score >= 60) status = "warn";
      else status = "bad";
    }
    const statusLabel = { good: "流畅", warn: "略卡", bad: "卡顿", idle: "未测" }[status];
    const metric = latency !== null ? `${Math.round(latency)}<span class="target-card-unit">ms</span>` : "—";
    const lossPct = loss ? `丢包 ${loss.toFixed(1)}%` : "";
    return `
      <div class="target-card" data-id="${t.id}">
        <div class="target-card-name">${escapeHtml(t.name)}</div>
        <div class="target-card-status status-${status}">${statusLabel}${lossPct ? " · " + lossPct : ""}</div>
        <div class="target-card-metric">${metric}</div>
        ${score !== null ? `<div class="target-card-unit">评分 ${score} · ${t.grade || ""}</div>` : ""}
      </div>
    `;
  }).join("");
}

// ============================================================
// 测试流程
// ============================================================
async function startTest() {
  if (State.testing) return;
  State.testing = true;

  showView("testing");
  renderTestingView();

  try {
    // 调用 Python 跑一键全测
    const result = await API.call("quick_test", State.scenario);
    if (result && result.overall) {
      // 把每个目标的 metrics 也填上（用于历史趋势和评分）
      result.targets = (result.targets || []).map(t => ({
        ...t,
        metrics: t.metrics || {},
      }));
      State.lastResult = result;
      State.allTargets = result.targets;  // 更新为带分数的目标
      State.targets = [...State.allTargets];
      renderResult(result);
    } else {
      alert("测试失败：" + (result && result.error || "未知错误"));
    }
  } catch (e) {
    console.error(e);
    alert("测试异常：" + e);
  } finally {
    State.testing = false;
  }
}

function renderTestingView() {
  // 进度点（10 包）
  const progress = document.getElementById("testing-progress");
  progress.innerHTML = Array.from({ length: 10 }, (_, i) =>
    `<div class="progress-dot ${i < 1 ? 'done' : ''}" data-step="${i}"></div>`
  ).join("");

  // 测试项列表（用当前目标的前 6 个）
  const list = document.getElementById("testing-list");
  const items = State.allTargets.slice(0, 6);
  list.innerHTML = items.map((t, i) => `
    <div class="testing-item">
      <span class="testing-item-name">${escapeHtml(t.name)}</span>
      <div class="testing-item-progress">
        <div class="testing-item-progress-bar" style="width: ${i < 1 ? 100 : 0}%;"></div>
      </div>
      <span class="testing-item-status">${i < 1 ? '✓ ' + Math.round((t.metrics && t.metrics.avg_latency_ms) || 0) + 'ms' : '⏳ 等待'}</span>
    </div>
  `).join("");

  // 简单动画：进度点逐步点亮
  let step = 1;
  const tick = () => {
    if (!State.testing) return;
    document.querySelectorAll(".progress-dot").forEach((dot, i) => {
      if (i < step) dot.classList.add("done");
      if (i === step) dot.classList.add("active");
    });
    if (step < 10) { step++; setTimeout(tick, 200); }
  };
  tick();
}

function stopTest() {
  State.testing = false;
  API.call("stop_test").catch(() => {});
  showView("welcome");
}

// ============================================================
// 结果页渲染
// ============================================================
function renderResult(result) {
  showView("result");
  document.getElementById("result-score").textContent = Math.round(result.overall.score);
  document.getElementById("result-grade").textContent = result.overall.grade;
  document.getElementById("result-comment").textContent = result.overall.comment || result.overall.label || "";

  // 目标明细
  const rows = document.getElementById("result-rows");
  rows.innerHTML = result.targets.map(t => {
    const metrics = t.metrics || {};
    const latency = metrics.avg_latency_ms;
    const loss = metrics.loss_pct;
    const scoreColor = t.score >= 80 ? "var(--status-good)" : t.score >= 60 ? "var(--status-warn)" : "var(--status-bad)";
    return `
      <div class="poster-row">
        <span class="poster-row-name">${escapeHtml(t.name)}</span>
        <span class="poster-row-score" style="color: ${scoreColor};">
          ${t.score}${t.grade ? ' ' + t.grade : ''}
          ${latency !== undefined && latency !== null ? ` · ${Math.round(latency)}ms` : ''}
          ${loss ? ` · 丢包${loss.toFixed(1)}%` : ''}
        </span>
      </div>
    `;
  }).join("");

  // 同步更新仪表盘
  renderResultIntoDashboard(result);
}

function renderResultIntoDashboard(result) {
  document.getElementById("overall-score").textContent = Math.round(result.overall.score);
  document.getElementById("overall-grade").textContent = result.overall.grade;
  document.getElementById("overall-title").textContent = result.overall.label || "测试完成";
  document.getElementById("overall-comment").textContent = result.overall.comment || "";
  document.getElementById("meta-count").textContent = result.targets.length;
  document.getElementById("meta-duration").textContent = result.duration ? `${result.duration} 秒` : "—";
  document.getElementById("meta-scenario").textContent = scenarioName(result.scenario);

  // 评分环
  const scoreRing = document.querySelector(".score-ring svg circle:nth-child(2)");
  if (scoreRing) {
    const offset = 314 - (314 * result.overall.score / 100);
    scoreRing.style.transition = "stroke-dashoffset 800ms ease-out";
    scoreRing.setAttribute("stroke-dashoffset", offset);
  }

  // 时间戳
  const dt = new Date(result.time || Date.now());
  document.getElementById("dashboard-time").textContent = `${dt.getMonth() + 1}-${dt.getDate()} ${dt.getHours()}:${String(dt.getMinutes()).padStart(2, '0')}`;
}

// ============================================================
// 结果页操作
// ============================================================
async function onShare() {
  if (!State.lastResult) return;
  // 简化：弹窗显示摘要
  const summary = generateSummary(State.lastResult);
  if (navigator.share) {
    try {
      await navigator.share({ title: "NetDiag 网络体检", text: summary });
    } catch (e) { /* 取消 */ }
  } else {
    alert(summary);
  }
}

async function onSaveImg() {
  if (!State.lastResult) return;
  try {
    const r = await API.call("save_poster", State.lastResult);
    if (r && r.path) {
      alert("海报已保存到：" + r.path);
    } else {
      alert("保存失败");
    }
  } catch (e) {
    alert("保存失败：" + e);
  }
}

async function onCopy() {
  if (!State.lastResult) return;
  const summary = generateSummary(State.lastResult);
  try {
    await navigator.clipboard.writeText(summary);
    const r = await API.call("copy_summary", summary);
    alert("已复制到剪贴板");
  } catch (e) {
    alert("复制失败：" + e);
  }
}

function generateSummary(result) {
  const lines = [];
  lines.push("┏━━━━━━━━━━━━━━━━━━━━━━━━┓");
  lines.push("┃  📊 NetDiag 网络体检     ┃");
  lines.push("┗━━━━━━━━━━━━━━━━━━━━━━━━┛");
  lines.push("");
  lines.push(`综合评分：${Math.round(result.overall.score)} 分 · ${result.overall.grade}`);
  lines.push(`状态：${result.overall.label || ""}`);
  lines.push("");
  lines.push("【测试明细】");
  result.targets.slice(0, 6).forEach(t => {
    const m = t.metrics || {};
    const latency = m.avg_latency_ms;
    const loss = m.loss_pct;
    let extra = "";
    if (latency !== undefined && latency !== null) extra += ` ${Math.round(latency)}ms`;
    if (loss) extra += ` 丢包${loss.toFixed(1)}%`;
    lines.push(`  • ${t.name}：${t.score}${t.grade || ''}${extra}`);
  });
  lines.push("");
  lines.push(`测试时间：${new Date(result.time || Date.now()).toLocaleString()}`);
  lines.push("NetDiag v2.0 · 浅木·先生");
  return lines.join("\n");
}

// ============================================================
// 工具
// ============================================================
function escapeHtml(text) {
  if (text == null) return "";
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function scenarioName(s) {
  return ({ general: "通用", game: "游戏", video: "视频", office: "办公", dev: "开发", overseas: "海外" })[s] || s;
}

// ============================================================
// 历史趋势页
// ============================================================
async function renderHistoryView() {
  try {
    const records = await API.call("get_history", 30);
    const totalEl = document.getElementById("hist-total-count");
    const avgEl = document.getElementById("hist-avg-score");
    const trendEl = document.getElementById("hist-trend");
    const listEl = document.getElementById("history-list");

    if (!records || records.length === 0) {
      totalEl.textContent = "0";
      avgEl.textContent = "—";
      trendEl.textContent = "—";
      listEl.innerHTML = '<div style="color: var(--text-muted); padding: 32px; text-align: center;">还没有测试记录，点击一键全测开始</div>';
      drawTrendSvg([]);
      return;
    }

    // 按 timestamp 升序
    records.sort((a, b) => (a.timestamp || 0) - (b.timestamp || 0));
    const scores = records.map(r => r.overall_score || 0);
    const total = records.length;
    const avg = (scores.reduce((s, v) => s + v, 0) / scores.length).toFixed(1);
    totalEl.textContent = total;
    avgEl.textContent = avg;

    // 趋势（最后3次与之前3次对比）
    if (scores.length >= 6) {
      const last3 = scores.slice(-3).reduce((s, v) => s + v, 0) / 3;
      const prev3 = scores.slice(-6, -3).reduce((s, v) => s + v, 0) / 3;
      const diff = last3 - prev3;
      if (diff > 2) trendEl.textContent = "↑ 变好";
      else if (diff < -2) trendEl.textContent = "↓ 变差";
      else trendEl.textContent = "→ 持平";
    } else {
      trendEl.textContent = "数据不足";
    }

    // 趋势 SVG
    drawTrendSvg(records);

    // 最近 10 条
    const recent = records.slice(-10).reverse();
    listEl.innerHTML = recent.map(r => {
      const dt = new Date(r.time || r.timestamp * 1000);
      const dt_str = `${dt.getMonth() + 1}-${dt.getDate()} ${dt.getHours()}:${String(dt.getMinutes()).padStart(2, "0")}`;
      const sc = r.overall_score || 0;
      const color = sc >= 80 ? "var(--status-good)" : sc >= 60 ? "var(--status-warn)" : "var(--status-bad)";
      return `
        <div class="history-item">
          <span class="history-item-time">${dt_str}</span>
          <span class="history-item-scenario">${scenarioName(r.scenario || "general")}</span>
          <span class="history-item-score" style="color: ${color};">${sc} ${r.overall_grade || ""}</span>
        </div>
      `;
    }).join("");
  } catch (e) {
    console.error("renderHistoryView error:", e);
  }
}

function drawTrendSvg(records) {
  const svg = document.getElementById("trend-svg");
  if (!svg) return;
  while (svg.firstChild) svg.removeChild(svg.firstChild);

  if (!records || records.length === 0) {
    svg.innerHTML = '<text x="400" y="110" text-anchor="middle" fill="#8B95B5" font-size="14">暂无数据</text>';
    return;
  }

  records.sort((a, b) => (a.timestamp || 0) - (b.timestamp || 0));
  const W = 800, H = 220, pad_l = 50, pad_r = 20, pad_t = 20, pad_b = 30;
  const inner_w = W - pad_l - pad_r;
  const inner_h = H - pad_t - pad_b;

  // 网格
  for (let k = 0; k <= 4; k++) {
    const yy = pad_t + inner_h * k / 4;
    const v = 100 * (1 - k / 4);
    const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
    line.setAttribute("x1", pad_l);
    line.setAttribute("y1", yy);
    line.setAttribute("x2", W - pad_r);
    line.setAttribute("y2", yy);
    line.setAttribute("stroke", "#252F4A");
    line.setAttribute("stroke-width", "1");
    svg.appendChild(line);
    const txt = document.createElementNS("http://www.w3.org/2000/svg", "text");
    txt.setAttribute("x", pad_l - 6);
    txt.setAttribute("y", yy + 4);
    txt.setAttribute("text-anchor", "end");
    txt.setAttribute("fill", "#8B95B5");
    txt.setAttribute("font-size", "10");
    txt.textContent = Math.round(v);
    svg.appendChild(txt);
  }

  // 折线
  const n = records.length;
  const pts = [];
  for (let i = 0; i < n; i++) {
    const px = pad_l + (inner_w * i / Math.max(1, n - 1));
    const py = pad_t + inner_h * (1 - (records[i].overall_score || 0) / 100);
    pts.push(`${px.toFixed(1)},${py.toFixed(1)}`);
    // 圆点
    const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    circle.setAttribute("cx", px);
    circle.setAttribute("cy", py);
    circle.setAttribute("r", "3");
    circle.setAttribute("fill", "#00E5FF");
    svg.appendChild(circle);
  }
  const poly = document.createElementNS("http://www.w3.org/2000/svg", "polyline");
  poly.setAttribute("fill", "none");
  poly.setAttribute("stroke", "#00E5FF");
  poly.setAttribute("stroke-width", "2");
  poly.setAttribute("stroke-linejoin", "round");
  poly.setAttribute("points", pts.join(" "));
  svg.appendChild(poly);

  // X 轴日期标签（最多 6 个）
  const step = Math.max(1, Math.floor(n / 6));
  for (let i = 0; i < n; i += step) {
    const dt = new Date(records[i].time || records[i].timestamp * 1000);
    const label = `${dt.getMonth() + 1}-${dt.getDate()}`;
    const px = pad_l + (inner_w * i / Math.max(1, n - 1));
    const txt = document.createElementNS("http://www.w3.org/2000/svg", "text");
    txt.setAttribute("x", px);
    txt.setAttribute("y", H - 10);
    txt.setAttribute("text-anchor", "middle");
    txt.setAttribute("fill", "#8B95B5");
    txt.setAttribute("font-size", "10");
    txt.textContent = label;
    svg.appendChild(txt);
  }
}

// ============================================================
// 设置页
// ============================================================
async function renderSettingsView() {
  try {
    // 设置
    const settings = await API.call("get_settings");
    if (settings) {
      const themeEl = document.getElementById("setting-theme");
      const fontEl = document.getElementById("setting-font-size");
      const countEl = document.getElementById("setting-test-count");
      const timeoutEl = document.getElementById("setting-timeout");
      const pingEl = document.getElementById("setting-ping-count");
      if (themeEl) themeEl.value = settings.theme || "dark";
      if (fontEl) fontEl.value = settings.font_size || "standard";
      if (countEl) countEl.value = settings.default_test_count || 5;
      if (timeoutEl) timeoutEl.value = settings.test_timeout || 5;
      if (pingEl) pingEl.value = settings.ping_count || 5;
      State.theme = settings.theme || "dark";
    }

    // 公网 IP
    const pubIp = await API.call("get_public_ip");
    const pubIpEl = document.getElementById("setting-public-ip");
    if (pubIpEl) pubIpEl.textContent = pubIp.ip || "未获取";

    // Wi-Fi
    const wifi = await API.call("get_wifi_signal");
    const wifiEl = document.getElementById("setting-wifi");
    if (wifiEl) {
      if (wifi.connected) {
        wifiEl.textContent = `${wifi.ssid} · ${wifi.signal_pct || "?"}% (${wifi.signal_quality || "?"})`;
      } else {
        wifiEl.textContent = wifi.note || "未连接";
      }
    }

    // 网卡
    const ifaces = await API.call("get_interfaces");
    const ifEl = document.getElementById("setting-interfaces");
    if (ifEl) {
      const active = ifaces.filter(i => i.is_up);
      ifEl.textContent = `${active.length} / ${ifaces.length} 个启用`;
    }

    // 成就
    const achievements = await API.call("get_achievements");
    const unlockedCount = achievements.filter(a => a.unlocked).length;
    const achCountEl = document.getElementById("achievement-count");
    if (achCountEl) achCountEl.textContent = `${unlockedCount}/${achievements.length}`;
    const achListEl = document.getElementById("achievements-list");
    if (achListEl) {
      achListEl.innerHTML = achievements.map(a => `
        <div class="achievement-item ${a.unlocked ? "unlocked" : "locked"}">
          <div class="achievement-icon" style="color: ${a.color || "#8B95B5"};">${a.unlocked ? a.icon : "🔒"}</div>
          <div class="achievement-info">
            <div class="achievement-name">${escapeHtml(a.name)}</div>
            <div class="achievement-desc">${escapeHtml(a.description)}</div>
          </div>
        </div>
      `).join("");
    }
  } catch (e) {
    console.error("renderSettingsView error:", e);
  }
}

// ============================================================
// 自定义目标页
// ============================================================
async function renderCustomView() {
  try {
    const customs = await API.call("get_custom_targets");
    const countEl = document.getElementById("custom-count");
    if (countEl) countEl.textContent = customs.length;
    const listEl = document.getElementById("custom-targets-list");
    if (listEl) {
      if (customs.length === 0) {
        listEl.innerHTML = '<div style="color: var(--text-muted); padding: 24px; text-align: center;">还没有自定义目标，使用上方表单添加</div>';
      } else {
        listEl.innerHTML = customs.map(t => `
          <div class="custom-item">
            <div class="custom-item-info">
              <div class="custom-item-name">${escapeHtml(t.name)}</div>
              <div class="custom-item-host">${escapeHtml(t.host)}:${t.port}</div>
              ${t.note ? `<div class="custom-item-note">${escapeHtml(t.note)}</div>` : ""}
            </div>
            <button class="btn-icon danger" data-id="${escapeHtml(t.id)}" title="删除">🗑</button>
          </div>
        `).join("");
        // 删除按钮事件
        listEl.querySelectorAll(".btn-icon.danger").forEach(btn => {
          btn.addEventListener("click", async () => {
            const id = btn.dataset.id;
            if (!confirm("确定删除？")) return;
            await API.call("remove_custom_target", id);
            renderCustomView();
          });
        });
      }
    }
  } catch (e) {
    console.error("renderCustomView error:", e);
  }
}

// ============================================================
// 启动
// ============================================================
init();