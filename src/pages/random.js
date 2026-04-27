/**
 * 随机刷题页 /random?type=reading-mcq&from=cet6-2024-12-1&pIdx=0
 */
import { el } from "../ui/components.js";
import { findPracticeUnit, unitSourceLabel } from "../core/exam-practice.js";
import { examAttemptKey, trySaveExamAttempt } from "../core/local-db.js";
import { isVerifiedAnswer, renderReviewBoard, renderSection } from "./exam.js";

export async function render(ctx) {
  const { host, router, query } = ctx;
  const unit = await findPracticeUnit({
    type: query.type,
    from: query.from,
    pIdx: query.pIdx || 0,
    section: query.section,
  });

  if (!unit) {
    host.appendChild(el("div", { class: "card" }, [
      el("h3", {}, "没有找到这道随机题"),
      el("div", { class: "label", style: "margin-bottom:14px" }, "可能是链接参数不完整,或者题池还没有生成。"),
      el("button", { class: "primary", onClick: () => router.go("/practice") }, "回随机刷题"),
    ]));
    return;
  }

  const answers = {};
  const startedAt = Date.now();
  host.appendChild(el("div", { class: "row between", style: "margin-bottom:12px" }, [
    el("button", { class: "ghost", onClick: () => router.go("/practice") }, "← 返回刷题"),
    el("div", { style: "text-align:center; flex:1" }, [
      el("div", { style: "font-weight:800; font-size:16px" }, unit.title),
      el("div", { class: "label" }, `来自 ${unitSourceLabel(unit)} · 可回到原卷查看上下文`),
    ]),
    el("button", { class: "ghost", onClick: () => router.go("/exam", { id: unit.examId }) }, "原卷"),
  ]));

  host.appendChild(el("div", { class: "card" }, [
    renderSection(unit.section, answers),
  ]));

  host.appendChild(el("div", { class: "row between", style: "margin-top:16px" }, [
    el("button", { onClick: () => router.go("/practice") }, "换题型"),
    el("button", { class: "primary", onClick: () => submit(host, router, unit, answers, startedAt) }, "提交本题"),
  ]));
}

async function submit(host, router, unit, answers, startedAt) {
  const stats = collectStats(unit.section, answers);
  const endedAt = Date.now();
  const attempt = {
    mode: "practice",
    examId: unit.examId,
    examType: unit.exam.type,
    practiceUnitId: unit.id,
    practiceType: unit.type,
    title: unit.title,
    source: unitSourceLabel(unit),
    startedAt,
    endedAt,
    answers: JSON.parse(JSON.stringify(answers)),
    totalObjective: stats.total,
    answeredObjective: stats.answered,
    scorableObjective: stats.scorable,
    correctObjective: stats.correct,
    verifiedObjective: stats.verified,
    pendingObjective: stats.pending,
    textChars: stats.textChars,
    answerReady: stats.scorable > 0,
    totalScore: stats.scorable ? Math.round(stats.correct / stats.scorable * 100) : null,
  };
  attempt.localDbKey = examAttemptKey(attempt);
  const localSaved = await trySaveExamAttempt(attempt);
  host.innerHTML = "";
  host.appendChild(el("div", { class: "card", style: "text-align:center; padding:32px" }, [
    el("div", { style: "font-size:42px" }, "✓"),
    el("h2", { style: "margin:8px 0" }, "本题已提交"),
    el("div", { class: "label" }, `${unit.title} · ${unitSourceLabel(unit)}`),
    el("div", { class: "grid cols-3", style: "margin:24px 0" }, [
      stat("客观题作答", `${stats.answered}/${stats.total}`, stats.total ? `${Math.round((stats.answered / stats.total) * 100)}% 完成` : "主观题"),
      stat("文本字符", String(stats.textChars), stats.textChars ? `约 ${Math.round(stats.textChars / 5)} 词` : "未作答"),
      stat("用时", formatDuration(endedAt - startedAt), "本次随机练习"),
    ]),
    stats.scorable
      ? el("div", {
          class: stats.pending ? "feedback warn" : "feedback ok",
          style: "max-width:620px; margin:0 auto 16px",
        }, `本题已判分: ${stats.correct}/${stats.scorable} · 已核验 ${stats.verified} 题 / 待复核 ${stats.pending} 题。`)
      : el("div", { class: "feedback warn", style: "max-width:620px; margin:0 auto 16px" },
          "答案库还在抽取中,这里先记录作答完成度。等 Step 2.5 接入后,随机刷题会同步显示对错和解析。"),
    localSaved
      ? el("div", { class: "label", style: "margin-bottom:16px" }, "已同步到本地 SQLite 数据库。")
      : el("div", { class: "label", style: "margin-bottom:16px" }, "本地 SQLite 暂不可用,本次只在当前页面完成。"),
    el("div", { class: "row", style: "justify-content:center" }, [
      el("button", { class: "ghost", onClick: () => router.go("/exam", { id: unit.examId }) }, "查看原卷"),
      el("button", { class: "primary", onClick: () => router.go("/practice") }, "再抽一题"),
    ]),
  ]));

  if (stats.scorable) {
    host.appendChild(renderReviewBoard({
      id: unit.examId,
      title: `${unit.title} · ${unitSourceLabel(unit)}`,
      sections: [unit.section],
    }, answers));
  }
}

function collectStats(section, answers) {
  let total = 0;
  let answered = 0;
  let scorable = 0;
  let correct = 0;
  let verified = 0;
  let pending = 0;
  let textChars = 0;
  if (section.type === "writing") {
    textChars = (answers[section.id || "writing"] || "").length;
  } else if (section.type === "translation") {
    textChars = (answers.translation || "").length;
  } else {
    const questions = section.questions || section.passages?.flatMap((p) => p.questions || []) || [];
    total = questions.length;
    for (const q of questions) {
      if (answers[q.number]) answered += 1;
      if (q.answer) {
        scorable += 1;
        if (answers[q.number] === q.answer) correct += 1;
        if (isVerifiedAnswer(q)) verified += 1;
        else pending += 1;
      }
    }
  }
  return { total, answered, scorable, correct, verified, pending, textChars };
}

function stat(label, value, sub) {
  return el("div", { class: "stat" }, [
    el("div", { class: "label" }, label),
    el("div", { class: "value" }, value),
    sub ? el("div", { class: "sub" }, sub) : null,
  ]);
}

function formatDuration(ms) {
  const totalSeconds = Math.max(1, Math.round(ms / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return minutes ? `${minutes}分${seconds}秒` : `${seconds}秒`;
}
