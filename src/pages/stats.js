/**
 * 统计页。
 * 从 IndexedDB 汇总学习热力、正确率、熟练度、章节与段位状态。
 */
import { el, statBlock } from "../ui/components.js";
import { store } from "../core/store.js";
import { loadWordlist } from "../core/wordlist.js";
import {
  getMapIndex, loadChapter, getChapterProgress, chapterCompletion,
} from "../core/map-engine.js";
import { tierByPoints } from "../core/rank-engine.js";

const DAY_MS = 24 * 60 * 60 * 1000;
const BOX_LABELS = ["陌生", "学习中", "熟悉", "掌握", "永久"];

export async function render(ctx) {
  const { host, router } = ctx;
  host.innerHTML = "";

  const activeId = await store.getSetting("activeWordlist", "cet6");
  const [statsRows, sessions, progressRows, wrongRows, rank, rankHistory] = await Promise.all([
    store.all("stats"),
    store.all("sessions"),
    store.all("progress"),
    store.all("wrongbook"),
    store.getSetting("rank", null),
    store.all("rankHistory"),
  ]);

  let wordTotal = 0;
  try {
    const wordlist = await loadWordlist(activeId);
    wordTotal = wordlist.words.length;
  } catch {
    wordTotal = 0;
  }

  const progress = progressRows.filter((p) => !p.wordlistId || p.wordlistId === activeId);
  const wrongbook = wrongRows.filter((w) => !w.wordlistId || w.wordlistId === activeId);
  const days = lastNDays(30);
  const statsByDate = new Map(statsRows.map((row) => [row.date, row]));
  const totals = sumStats(statsRows);
  const learned = progress.length;
  const mastered = progress.filter((p) => Number(p.box || 0) >= 3).length;
  const currentRank = tierByPoints(rank ? rank.points || 0 : 0);

  host.appendChild(el("div", { class: "row between", style: "margin-bottom:16px" }, [
    el("div", {}, [
      el("h2", { style: "margin:0" }, "📊 学习统计"),
      el("div", { class: "label", style: "margin-top:4px" }, "热力、正确率、熟练度和闯关进度"),
    ]),
    el("div", { class: "row", style: "gap:8px" }, [
      el("button", { class: "ghost", onClick: () => router.go("/") }, "返回首页"),
      el("button", { class: "primary", onClick: () => router.go("/learn") }, "继续学习"),
    ]),
  ]));

  host.appendChild(el("div", { class: "grid cols-4" }, [
    statBlock("累计学习", learned, wordTotal ? `共 ${wordTotal} 词` : "当前词表"),
    statBlock("累计答题", totals.total, totals.total ? `正确 ${totals.correct}` : "尚无记录"),
    statBlock("总体正确率", percent(totals.correct, totals.total), "按每日统计汇总"),
    statBlock("错题本", wrongbook.length, "需要回炉"),
  ]));

  host.appendChild(el("div", { class: "grid cols-2", style: "margin-top:16px" }, [
    renderHeatmap(days, statsByDate),
    renderAccuracy(days, statsByDate),
  ]));

  host.appendChild(el("div", { class: "grid cols-2", style: "margin-top:16px" }, [
    renderMastery(progress, wordTotal),
    renderRank(rank, currentRank, sessions, rankHistory),
  ]));

  host.appendChild(await renderChapterProgress());

  host.appendChild(el("div", { class: "grid cols-3", style: "margin-top:16px" }, [
    statBlock("学习场次", sessions.length, sessions.length ? `最近 ${formatDateTime(latestSessionTime(sessions))}` : "暂无会话"),
    statBlock("已掌握", mastered, learned ? `${Math.round((mastered / learned) * 100)}% 已学词` : "先学几个词"),
    statBlock("段位积分", rank ? rank.points || 0 : 0, `${currentRank.label} · 最高 ${rank ? rank.highest || 0 : 0}`),
  ]));
}

function renderHeatmap(days, statsByDate) {
  const values = days.map((date) => {
    const row = statsByDate.get(date);
    return row ? Number(row.learned || 0) + Number(row.reviewed || 0) : 0;
  });
  const max = Math.max(1, ...values);
  const cells = days.map((date, index) => {
    const value = values[index];
    return el("div", {
      class: "heat-cell level-" + heatLevel(value, max),
      title: `${date} · ${value} 次`,
    });
  });
  return el("div", { class: "card" }, [
    el("div", { class: "section-title" }, "近 30 天热力"),
    el("div", { class: "stats-heatmap" }, cells),
    el("div", { class: "row between", style: "margin-top:10px" }, [
      el("span", { class: "label" }, days[0].slice(5)),
      el("span", { class: "label" }, `峰值 ${max} 次`),
      el("span", { class: "label" }, days[days.length - 1].slice(5)),
    ]),
  ]);
}

function renderAccuracy(days, statsByDate) {
  const points = days.map((date) => {
    const row = statsByDate.get(date);
    return row && row.total ? (row.correct || 0) / row.total : null;
  });
  const valid = points.filter((v) => v != null);
  const latest = valid.length ? `${Math.round(valid[valid.length - 1] * 100)}%` : "—";

  return el("div", { class: "card" }, [
    el("div", { class: "row between" }, [
      el("div", { class: "section-title", style: "margin:0" }, "正确率曲线"),
      el("span", { class: "pill" }, `最近 ${latest}`),
    ]),
    lineChart(points),
  ]);
}

function renderMastery(progress, wordTotal) {
  const buckets = [0, 0, 0, 0, 0];
  for (const row of progress) {
    const box = Math.max(0, Math.min(4, Number(row.box || 0)));
    buckets[box] += 1;
  }
  const total = wordTotal || Math.max(1, progress.length);
  return el("div", { class: "card" }, [
    el("div", { class: "section-title" }, "熟练度分布"),
    el("div", { class: "stats-donut-wrap" }, [
      donutChart(buckets, total),
      el("div", { class: "stats-legend" }, buckets.map((count, i) => (
        el("div", { class: "row between" }, [
          el("span", {}, BOX_LABELS[i]),
          el("span", { class: "pill" }, `${count} · ${Math.round((count / total) * 100)}%`),
        ])
      ))),
    ]),
  ]);
}

function renderRank(rank, currentTier, sessions, rankHistory) {
  const rankedSessions = sessions
    .filter((s) => /青铜|白银|黄金|铂金|钻石|王者|混合/.test(s.mode || ""))
    .sort((a, b) => (b.endedAt || 0) - (a.endedAt || 0))
    .slice(0, 5);
  const history = [...rankHistory]
    .sort((a, b) => Number(a.at || 0) - Number(b.at || 0))
    .slice(-12);

  const points = rank ? Number(rank.points || 0) : 0;
  const span = Math.max(1, currentTier.maxPoints - currentTier.minPoints);
  const pct = Math.round(((points - currentTier.minPoints) / span) * 100);

  return el("div", { class: "card" }, [
    el("div", { class: "section-title" }, "段位状态"),
    el("div", { style: "font-size:28px; font-weight:700" }, currentTier.label),
    el("div", { class: "label", style: "margin-top:4px" }, `积分 ${points} / ${currentTier.maxPoints}`),
    el("div", { class: "progress", style: "margin-top:12px" }, [
      el("div", { class: "bar", style: `width:${pct}%; background:${currentTier.color}` }),
    ]),
    el("div", { class: "grid cols-3", style: "margin-top:14px" }, [
      smallStat("最高", rank ? rank.highest || 0 : 0),
      smallStat("胜场", rank ? rank.wins || 0 : 0),
      smallStat("连胜", rank ? rank.streak || 0 : 0),
    ]),
    history.length
      ? rankSparkline(history)
      : el("div", { class: "feedback warn", style: "margin-top:12px" }, "段位历程会从下一场段位赛开始记录。"),
    el("div", { class: "stats-mini-list" }, rankedSessions.length
      ? rankedSessions.map((s) => el("div", { class: "row between" }, [
          el("span", {}, s.mode || "段位赛"),
          el("span", { class: "label" }, `${formatDateTime(s.endedAt)} · ${percent(s.correct, s.total)}`),
        ]))
      : [el("div", { class: "empty", style: "padding:16px 0" }, "还没有段位会话记录。")]),
  ]);
}

function rankSparkline(history) {
  const values = history.map((h) => Number(h.points || 0));
  const max = Math.max(40, ...values);
  const width = 520;
  const height = 120;
  const pad = 16;
  const path = values.map((value, i) => {
    const x = pad + (values.length <= 1 ? 0 : (i / (values.length - 1)) * (width - pad * 2));
    const y = height - pad - (value / max) * (height - pad * 2);
    return `${i === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`;
  }).join(" ");
  const svg = svgEl("svg", { viewBox: `0 0 ${width} ${height}`, class: "stats-rank-chart", role: "img" });
  svg.appendChild(svgEl("path", { d: path, class: "stats-line" }));
  for (const h of history) {
    const value = Number(h.points || 0);
    const i = history.indexOf(h);
    const x = pad + (history.length <= 1 ? 0 : (i / (history.length - 1)) * (width - pad * 2));
    const y = height - pad - (value / max) * (height - pad * 2);
    svg.appendChild(svgEl("circle", {
      cx: x, cy: y, r: 3.5, class: h.win ? "stats-dot" : "stats-dot rank-loss",
    }));
  }
  return el("div", { style: "margin-top:14px" }, [
    el("div", { class: "label" }, "最近段位历程"),
    svg,
  ]);
}

async function renderChapterProgress() {
  let index;
  try {
    index = await getMapIndex();
  } catch (e) {
    return el("div", { class: "card", style: "margin-top:16px" }, [
      el("div", { class: "section-title" }, "章节进度"),
      el("div", { class: "feedback err" }, e.message),
    ]);
  }

  const cards = [];
  for (const meta of index.chapters || []) {
    try {
      const chapter = await loadChapter(meta.id);
      const progress = await getChapterProgress(meta.id);
      const comp = chapterCompletion(chapter, progress);
      const pct = Math.round(comp.percent * 100);
      cards.push(el("div", { class: "stat" }, [
        el("div", { class: "row between" }, [
          el("div", { style: "font-weight:600" }, `${chapter.icon || meta.icon || "🗺️"} ${chapter.name}`),
          el("span", { class: "pill" }, `${pct}%`),
        ]),
        el("div", { class: "label", style: "margin-top:6px" },
          `通关 ${comp.cleared}/${comp.total} · 星数 ${comp.stars}/${comp.maxStars}`),
        el("div", { class: "progress", style: "margin-top:10px" }, [
          el("div", { class: "bar", style: `width:${pct}%` }),
        ]),
      ]));
    } catch (e) {
      cards.push(el("div", { class: "stat" }, [
        el("div", { style: "font-weight:600" }, meta.name || meta.id),
        el("div", { class: "feedback err" }, e.message),
      ]));
    }
  }

  return el("div", { class: "card", style: "margin-top:16px" }, [
    el("div", { class: "section-title" }, "章节进度"),
    cards.length
      ? el("div", { class: "grid cols-2" }, cards)
      : el("div", { class: "empty" }, "还没有章节配置。"),
  ]);
}

function lineChart(points) {
  const width = 560;
  const height = 220;
  const pad = 24;
  const usableW = width - pad * 2;
  const usableH = height - pad * 2;
  const coords = points.map((value, index) => {
    const x = pad + (points.length <= 1 ? 0 : (index / (points.length - 1)) * usableW);
    const y = value == null ? null : pad + (1 - value) * usableH;
    return { x, y, value };
  });
  const path = coords
    .filter((p) => p.y != null)
    .map((p, i) => `${i === 0 ? "M" : "L"} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`)
    .join(" ");

  const svg = svgEl("svg", { viewBox: `0 0 ${width} ${height}`, class: "stats-chart", role: "img" });
  for (const y of [0.25, 0.5, 0.75, 1]) {
    svg.appendChild(svgEl("line", {
      x1: pad, y1: pad + (1 - y) * usableH, x2: width - pad, y2: pad + (1 - y) * usableH,
      class: "stats-grid-line",
    }));
  }
  if (path) {
    svg.appendChild(svgEl("path", { d: path, class: "stats-line" }));
    for (const p of coords.filter((c) => c.y != null)) {
      svg.appendChild(svgEl("circle", {
        cx: p.x, cy: p.y, r: 3.5, class: "stats-dot",
      }));
    }
  }
  return svg;
}

function donutChart(buckets, total) {
  const radius = 64;
  const circumference = 2 * Math.PI * radius;
  const svg = svgEl("svg", { viewBox: "0 0 180 180", class: "stats-donut", role: "img" });
  svg.appendChild(svgEl("circle", {
    cx: 90, cy: 90, r: radius, class: "stats-donut-bg",
  }));

  let offset = 0;
  buckets.forEach((count, i) => {
    if (!count) return;
    const dash = (count / total) * circumference;
    const ring = svgEl("circle", {
      cx: 90, cy: 90, r: radius,
      class: `stats-donut-seg seg-${i}`,
      "stroke-dasharray": `${dash} ${circumference - dash}`,
      "stroke-dashoffset": -offset,
    });
    svg.appendChild(ring);
    offset += dash;
  });

  const label = svgEl("text", { x: 90, y: 86, class: "stats-donut-text" });
  label.textContent = String(buckets.reduce((a, b) => a + b, 0));
  svg.appendChild(label);
  const sub = svgEl("text", { x: 90, y: 108, class: "stats-donut-sub" });
  sub.textContent = "已学";
  svg.appendChild(sub);
  return svg;
}

function smallStat(label, value) {
  return el("div", { class: "stat stats-small-stat" }, [
    el("div", { class: "label" }, label),
    el("div", { class: "value" }, String(value)),
  ]);
}

function sumStats(rows) {
  return rows.reduce((acc, row) => {
    acc.learned += Number(row.learned || 0);
    acc.reviewed += Number(row.reviewed || 0);
    acc.correct += Number(row.correct || 0);
    acc.total += Number(row.total || 0);
    return acc;
  }, { learned: 0, reviewed: 0, correct: 0, total: 0 });
}

function lastNDays(n) {
  const out = [];
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  for (let i = n - 1; i >= 0; i -= 1) {
    out.push(new Date(today.getTime() - i * DAY_MS).toISOString().slice(0, 10));
  }
  return out;
}

function heatLevel(value, max) {
  if (!value) return 0;
  return Math.max(1, Math.min(4, Math.ceil((value / max) * 4)));
}

function percent(correct, total) {
  return total ? `${Math.round((Number(correct || 0) / Number(total)) * 100)}%` : "—";
}

function latestSessionTime(sessions) {
  return Math.max(...sessions.map((s) => Number(s.endedAt || s.startedAt || 0)));
}

function formatDateTime(ts) {
  if (!ts) return "—";
  const d = new Date(ts);
  return `${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

function svgEl(tag, attrs = {}) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  return node;
}
