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
  ["welcome", "dashboard", "testing", "result"].forEach(v => {
    const el = document.getElementById(`view-${v}`);
    if (el) el.style.display = (v === name) ? "" : "none";
  });
  State.view = name;
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
    alert("自定义目标功能开发中（P0 将提供）。");
  });

  // 顶部按钮（占位）
  document.getElementById("btn-history").addEventListener("click", () => {
    alert("历史趋势功能开发中。");
  });
  document.getElementById("btn-theme").addEventListener("click", () => {
    alert("主题切换开发中（已默认暗色 Cyber Neon）。");
  });
  document.getElementById("btn-settings").addEventListener("click", () => {
    alert("设置功能开发中。");
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
// 启动
// ============================================================
init();