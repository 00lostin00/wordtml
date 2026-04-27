/**
 * 真题列表页 /exams
 * 按年份分组,可玩的(complete + near-complete)优先突出,残缺的灰显。
 */
import { el } from "../ui/components.js";
import { store } from "../core/store.js";
import { examStatusInfo, getExamIndex, groupByYear, isExamPlayable } from "../core/exam-loader.js";
import { tryGetExamAttempts, trySyncExamAttempts } from "../core/local-db.js";

export async function render(ctx) {
  const { host, router } = ctx;

  let idx;
  try {
    idx = await getExamIndex();
  } catch (e) {
    host.appendChild(el("div", { class: "card" }, [
      el("h3", {}, "真题索引加载失败"),
      el("div", { class: "feedback err" }, e.message),
      el("div", { class: "label", style: "margin-top:12px" },
        "需要先跑 tools/exam_extract_text.py + tools/exam_parse.py + tools/exam_build_index.py。"),
    ]));
    return;
  }

  const exams = idx.exams || [];
  const summary = idx.summary || {};
  const browserAttempts = await store.all("examAttempts");
  trySyncExamAttempts(browserAttempts.map((attempt) => ({ ...attempt, mode: "exam" })));
  const attempts = mergeAttempts(browserAttempts, await tryGetExamAttempts())
    .filter((attempt) => (attempt.mode || "exam") === "exam");
  const latestByExam = latestAttemptMap(attempts);

  // 顶部统计
  host.appendChild(el("div", { class: "row between", style: "margin-bottom:16px" }, [
    el("h2", { style: "margin:0" }, "📜 真题中心"),
    el("div", { class: "row", style: "gap:8px" }, [
      el("span", { class: "pill ok" }, `完整 ${summary.complete || 0}`),
      el("span", { class: "pill" }, `近完整 ${summary.near || 0}`),
      el("span", { class: "pill warn" }, `部分 ${summary.partial || 0}`),
      el("span", { class: "pill" }, `残缺 ${summary.paperOnly || 0}`),
      el("span", { class: "pill ok" }, `可做 ${summary.objectiveReady || 0}`),
      el("button", { class: "ghost", onClick: () => router.go("/practice") }, "随机刷题"),
    ]),
  ]));

  const activeType = ctx.query.type || "";

  if (!activeType) {
    renderHub(host, router, exams, attempts, summary);
    return;
  }

  const filtered = exams.filter((e) => e.type === activeType);

  host.appendChild(el("div", { class: "row", style: "gap:8px; margin-bottom:16px;" }, [
    el("button", { class: "ghost", onClick: () => router.go("/exams") }, "← 返回分类"),
    ...["cet6", "ky1"].map((t) => el("button", {
      class: t === activeType ? "primary" : "ghost",
      onClick: () => router.go("/exams", { type: t }),
    }, typeLabel(t))),
  ]));

  const playableCount = filtered.filter(isExamPlayable).length;

  // 提示:客观题答案已接入
  host.appendChild(el("div", { class: "card", style: "margin-bottom:16px" }, [
    el("div", { class: "section-title" }, "客观题模式"),
    el("div", { style: "color:var(--fg-dim)" }, [
      "目前已结构化 ", el("strong", {}, String(filtered.length)), " 套真题，其中 ",
      el("strong", { style: "color:var(--ok)" }, String(playableCount)),
      " 套有可判分客观题答案，可直接点击做题。",
      el("div", { style: "margin-top:6px" }, "作文、翻译缺失时仍会显示完整度问题，但不会再锁住已接入答案的客观题。"),
    ]),
  ]));

  // 按年份分组
  const groups = groupByYear(filtered);
  if (!groups.length) {
    host.appendChild(el("div", { class: "card empty" }, `${typeLabel(activeType)} 暂无结构化真题。`));
    return;
  }
  for (const g of groups) {
    host.appendChild(el("div", { class: "section-title", style: "margin-top:24px" },
      `${g.year || "未知年份"}`));
    host.appendChild(el("div", { class: "grid cols-3" },
      g.exams.map((e) => examCard(e, router, latestByExam.get(e.id)))
    ));
  }
}

function typeLabel(t) {
  return { cet6: "🎓 CET-6 六级", ky1: "🚀 考研英语一", cet4: "📘 CET-4 四级" }[t] || t;
}

function renderHub(host, router, exams, attempts, summary) {
  const byType = countByType(exams);
  const playableByType = countPlayableByType(exams);
  const attemptsByType = countAttemptsByType(attempts, exams);
  host.appendChild(el("div", { class: "grid cols-2", style: "margin-bottom:16px" }, [
    typeCard({
      type: "cet6",
      title: "大学英语六级",
      desc: "听力、阅读、写作、翻译 6 个 section",
      count: byType.cet6 || 0,
      playable: playableByType.cet6 || 0,
      attempts: attemptsByType.cet6 || 0,
      enabled: true,
      router,
    }),
    typeCard({
      type: "ky1",
      title: "考研英语一",
      desc: "完型、阅读、新题型、翻译、写作",
      count: byType.ky1 || 0,
      playable: playableByType.ky1 || 0,
      attempts: attemptsByType.ky1 || 0,
      enabled: true,
      router,
    }),
  ]));

  const latest = [...attempts].sort((a, b) => Number(b.endedAt || 0) - Number(a.endedAt || 0)).slice(0, 5);
  host.appendChild(el("div", { class: "card" }, [
    el("div", { class: "section-title" }, "最近提交"),
    latest.length
      ? el("div", { class: "exam-attempt-list" }, latest.map((attempt) => attemptRow(attempt, exams)))
      : el("div", { class: "empty", style: "padding:18px 0" }, "还没有交卷记录。"),
  ]));
}

function typeCard({ type, title, desc, count, playable, attempts, enabled, router }) {
  return el("div", {
    class: "exam-type-card",
    onClick: enabled ? () => router.go("/exams", { type }) : null,
    style: `cursor:${enabled ? "pointer" : "not-allowed"}; opacity:${enabled ? 1 : 0.6}`,
  }, [
    el("div", { class: "row between" }, [
      el("div", { class: "exam-type-title" }, typeLabel(type)),
      el("span", { class: "pill" }, `${count} 卷`),
    ]),
    el("h3", { style: "margin:12px 0 4px" }, title),
    el("div", { class: "label" }, desc),
    el("div", { class: "grid cols-3", style: "margin-top:16px" }, [
      mini("可做", playable),
      mini("已交", attempts),
      mini("状态", count ? "已接入" : "待解析"),
    ]),
  ]);
}

function examCard(exam, router, latestAttempt) {
  const info = examStatusInfo(exam);
  const playable = isExamPlayable(exam);
  const monthLabel = exam.month ? `${exam.month}月` : "";
  const setLabel = exam.set ? `第${exam.set}套` : "";

  const card = el("div", {
    class: "stat",
    style: [
      `border-left:4px solid ${info.color}`,
      `cursor:${playable ? "pointer" : "not-allowed"}`,
      `opacity:${playable ? 1 : 0.55}`,
      "transition:transform 0.12s",
    ].join(";"),
    onClick: playable ? () => router.go("/exam", { id: exam.id }) : null,
  }, [
    el("div", { class: "row between" }, [
      el("div", { style: "font-weight:700; font-size:16px" }, `${monthLabel} ${setLabel}`.trim()),
      el("span", { class: "pill", style: `color:${info.color}; border-color:${info.color}` }, info.text),
    ]),
    el("div", { class: "label", style: "margin-top:6px" },
      `完整度 ${Math.round(exam.completeness * 100)}%`),
    exam.objectiveTotal
      ? el("div", { class: "label", style: "margin-top:4px; color:var(--accent)" },
          `客观题 ${exam.objectiveScorable || 0}/${exam.objectiveTotal} 可判分`)
      : null,
    exam.issues && exam.issues.length
      ? el("div", { class: "label", style: "margin-top:4px; color:var(--fg-faint); font-size:11px" },
          "缺:" + exam.issues.slice(0, 2).join(", "))
      : null,
    latestAttempt
      ? el("div", { class: "exam-attempt-pill" },
          `最近提交 ${formatDateTime(latestAttempt.endedAt)} · ${latestAttempt.answeredObjective}/${latestAttempt.totalObjective}`)
      : null,
  ]);

  if (playable) {
    card.addEventListener("mouseenter", () => card.style.transform = "translateY(-2px)");
    card.addEventListener("mouseleave", () => card.style.transform = "");
  }
  return card;
}

function latestAttemptMap(attempts) {
  const map = new Map();
  for (const attempt of attempts) {
    const prev = map.get(attempt.examId);
    if (!prev || Number(attempt.endedAt || 0) > Number(prev.endedAt || 0)) {
      map.set(attempt.examId, attempt);
    }
  }
  return map;
}

function mergeAttempts(browserRows, localRows) {
  const map = new Map();
  for (const row of [...(browserRows || []), ...(localRows || [])]) {
    const key = row.localDbId
      ? `local:${row.localDbId}`
      : `${row.examId || ""}:${row.mode || "exam"}:${row.endedAt || ""}:${row.startedAt || ""}`;
    map.set(key, row);
  }
  return [...map.values()];
}

function countByType(exams) {
  const out = {};
  for (const exam of exams) out[exam.type] = (out[exam.type] || 0) + 1;
  return out;
}

function countPlayableByType(exams) {
  const out = {};
  for (const exam of exams) {
    if (isExamPlayable(exam)) out[exam.type] = (out[exam.type] || 0) + 1;
  }
  return out;
}

function countAttemptsByType(attempts, exams) {
  const typeById = new Map(exams.map((exam) => [exam.id, exam.type]));
  const out = {};
  for (const attempt of attempts) {
    const type = typeById.get(attempt.examId) || String(attempt.examId || "").split("-")[0];
    out[type] = (out[type] || 0) + 1;
  }
  return out;
}

function attemptRow(attempt, exams) {
  const exam = exams.find((item) => item.id === attempt.examId);
  // 点击 → 详情页
  const goDetail = (router) => {
    const q = { id: attempt.examId };
    if (attempt.localDbId) q.lid = attempt.localDbId;
    else if (attempt.endedAt) q.t = attempt.endedAt;
    return q;
  };
  // 计算分数显示
  const scorable = attempt.scorableObjective ?? 0;
  const correct = attempt.correctObjective ?? 0;
  const scorePill = scorable > 0
    ? el("span", { class: "pill ok" }, `✓ ${correct}/${scorable} · ${attempt.totalScore || 0}分`)
    : el("span", { class: "pill" }, `${attempt.answeredObjective || 0}/${attempt.totalObjective || 0} 题`);
  const row = el("div", {
    class: "row between exam-attempt-row",
    style: "cursor:pointer; padding:8px 4px; border-radius:6px; transition:background .12s",
    onClick: () => {
      const q = { id: attempt.examId };
      if (attempt.localDbId) q.lid = attempt.localDbId;
      else if (attempt.endedAt) q.t = attempt.endedAt;
      location.hash = "#/attempt?" + new URLSearchParams(q).toString();
    },
  }, [
    el("div", {}, [
      el("div", { style: "font-weight:700" }, exam ? exam.title : attempt.examId),
      el("div", { class: "label" }, formatDateTime(attempt.endedAt)),
    ]),
    scorePill,
  ]);
  row.addEventListener("mouseenter", () => row.style.background = "var(--bg)");
  row.addEventListener("mouseleave", () => row.style.background = "");
  return row;
}

function mini(label, value) {
  return el("div", { class: "stat exam-mini" }, [
    el("div", { class: "label" }, label),
    el("div", { class: "value" }, String(value)),
  ]);
}

function formatDateTime(ts) {
  if (!ts) return "—";
  const d = new Date(ts);
  return `${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}
