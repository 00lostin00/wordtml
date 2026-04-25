/**
 * 提交记录详情页 /attempt
 *   ?lid=<localDbId>          从 SQLite 加载某条提交
 *   ?bid=<browserId>          从 IndexedDB 加载
 *   ?id=<examId>&t=<endedAt>  按 examId+endedAt 复合查找
 *
 * 渲染:头部摘要(分数/用时/作答情况) + 复用 exam.js 的 renderReviewBoard。
 */
import { el } from "../ui/components.js";
import { store } from "../core/store.js";
import { loadExam } from "../core/exam-loader.js";
import { tryGetExamAttempts } from "../core/local-db.js";
import { renderReviewBoard } from "./exam.js";

export async function render(ctx) {
  const { host, router, query } = ctx;

  // 找目标 attempt
  const attempt = await findAttempt(query);
  if (!attempt) {
    host.appendChild(el("div", { class: "card" }, [
      el("h3", {}, "找不到该提交记录"),
      el("div", { class: "label", style: "margin:8px 0" },
        `参数:${JSON.stringify(query)}`),
      el("button", { class: "primary", onClick: () => router.go("/exams") }, "回真题列表"),
    ]));
    return;
  }

  // 加载对应真题
  let exam;
  try {
    exam = await loadExam(attempt.examId);
  } catch (e) {
    host.appendChild(el("div", { class: "card" }, [
      el("h3", {}, "真题加载失败"),
      el("div", { class: "feedback err" }, e.message),
      el("button", { class: "primary", onClick: () => router.go("/exams") }, "回真题列表"),
    ]));
    return;
  }

  const answers = attempt.answers || {};
  const correct = attempt.correctObjective ?? 0;
  const scorable = attempt.scorableObjective ?? 0;
  const total = attempt.totalObjective ?? 0;
  const answered = attempt.answeredObjective ?? 0;
  const score = attempt.totalScore;
  const ts = attempt.endedAt || attempt.startedAt;

  // 顶部
  host.appendChild(el("div", { class: "row between", style: "margin-bottom:16px" }, [
    el("button", { class: "ghost", onClick: () => router.go("/exams") }, "← 回真题列表"),
    el("div", { style: "text-align:center; flex:1" }, [
      el("div", { style: "font-weight:700; font-size:16px" }, exam.title || exam.id),
      el("div", { class: "label" }, ts ? `提交于 ${formatDateTime(ts)}` : ""),
    ]),
    el("button", {
      class: "primary",
      onClick: () => router.go("/exam", { id: exam.id }),
    }, "再做一遍"),
  ]));

  // 摘要卡
  host.appendChild(el("div", { class: "card", style: "text-align:center; padding:24px" }, [
    el("div", { style: "font-size:42px" }, score != null ? `${score}` : "—"),
    el("div", { class: "label" }, score != null ? "客观题分数" : "本卷暂无标准答案"),
    el("div", { class: "grid cols-3", style: "margin-top:16px" }, [
      stat("答对 / 可批改", scorable ? `${correct}/${scorable}` : "—",
        scorable ? `${Math.round(correct / scorable * 100)}%` : "无答案库"),
      stat("作答 / 总题", `${answered}/${total}`,
        total ? `${Math.round(answered / total * 100)}% 完成` : ""),
      stat("作文/翻译", `${attempt.writingChars || 0}/${attempt.translationChars || 0}`, "字符"),
    ]),
  ]));

  // 详细批改(若有答案库)
  if (scorable > 0) {
    host.appendChild(renderReviewBoard(exam, answers));
  } else {
    host.appendChild(el("div", { class: "card", style: "margin-top:16px" }, [
      el("div", { class: "feedback warn" },
        "⚠️ 这套真题暂无标准答案库,只能查看你的作答,无法批改对错。"),
    ]));
    // 退而求其次:列出每题用户答案 + 题干(无标准答案)
    host.appendChild(renderRawAnswerList(exam, answers));
  }
}

function renderRawAnswerList(exam, answers) {
  const card = el("div", { class: "card", style: "margin-top:16px" });
  card.appendChild(el("h3", { style: "margin-top:0" }, "📋 你的作答"));
  for (const s of exam.sections || []) {
    if (s.type === "writing" || s.type === "translation") {
      const text = answers[s.id || s.type] || "";
      card.appendChild(el("details", { style: "margin-top:8px" }, [
        el("summary", { style: "cursor:pointer; font-weight:600" }, `${s.title || s.id} (${text.length} 字符)`),
        text
          ? el("pre", { style: "white-space:pre-wrap; padding:10px; background:var(--bg); border-radius:6px; margin-top:6px" }, text)
          : el("div", { class: "label", style: "margin-top:6px" }, "未作答"),
      ]));
      continue;
    }
    const allQ = s.questions || s.passages?.flatMap((p) => p.questions || []) || [];
    if (!allQ.length) continue;
    const det = el("details", { style: "margin-top:8px; padding:8px 12px; background:var(--bg); border-radius:8px" });
    det.appendChild(el("summary", { style: "cursor:pointer; font-weight:600" },
      `${s.title || s.id} · 共 ${allQ.length} 题`));
    const list = el("div", { style: "display:grid; grid-template-columns:repeat(auto-fill,minmax(80px,1fr)); gap:6px; margin-top:8px" });
    for (const q of allQ) {
      const userAns = answers[q.number] || "—";
      list.appendChild(el("div", {
        style: "padding:6px 10px; background:var(--bg-card); border-radius:6px; text-align:center; font-size:13px",
      }, [
        el("div", { class: "label" }, String(q.number)),
        el("strong", {}, userAns),
      ]));
    }
    det.appendChild(list);
    card.appendChild(det);
  }
  return card;
}

async function findAttempt(query) {
  // 1. 按 lid (SQLite localDbId) 找
  if (query.lid) {
    const all = await tryGetExamAttempts(500);
    return all.find((a) => String(a.localDbId) === String(query.lid)) || null;
  }
  // 2. 按 bid (IndexedDB autoIncrement key) 找
  if (query.bid) {
    const all = await store.all("examAttempts");
    return all.find((a) => String(a.browserId || a.id) === String(query.bid)) || null;
  }
  // 3. 按 examId + endedAt 找
  if (query.id) {
    const t = Number(query.t || 0);
    const browser = await store.all("examAttempts");
    let m = browser.find((a) => a.examId === query.id && (!t || Number(a.endedAt) === t));
    if (m) return m;
    const local = await tryGetExamAttempts(500);
    return local.find((a) => a.examId === query.id && (!t || Number(a.endedAt) === t)) || null;
  }
  return null;
}

function stat(label, value, sub = "") {
  return el("div", { class: "stat" }, [
    el("div", { class: "label" }, label),
    el("div", { class: "value" }, value),
    sub ? el("div", { class: "sub" }, sub) : null,
  ]);
}

function formatDateTime(ts) {
  const d = new Date(Number(ts));
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}
