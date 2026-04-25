/**
 * 真题做题页 /exam?id=cet6-2024-12-1
 * PoC 版:6 种 section 都能渲染,答案先存内存,提交时显示统计。
 * 真正的答案+解析校对要等 Step 2.5 (从 key.txt 抽答案) 上线。
 */
import { el } from "../ui/components.js";
import { store } from "../core/store.js";
import { loadExam } from "../core/exam-loader.js";
import { examAttemptKey, trySaveExamAttempt } from "../core/local-db.js";

export async function render(ctx) {
  const { host, router, query } = ctx;
  if (!query.id) {
    host.appendChild(el("div", { class: "card" }, [
      el("h3", {}, "未指定真题"),
      el("button", { class: "primary", onClick: () => router.go("/exams") }, "回真题列表"),
    ]));
    return;
  }

  let exam;
  try {
    exam = await loadExam(query.id);
  } catch (e) {
    host.appendChild(el("div", { class: "card" }, [
      el("h3", {}, "真题加载失败"),
      el("div", { class: "feedback err" }, e.message),
      el("button", { class: "primary", onClick: () => router.go("/exams") }, "回真题列表"),
    ]));
    return;
  }

  // 答题状态:{ "26": "B", "writing": "...", ... },内存级
  const answers = {};
  const startedAt = Date.now();
  let currentIdx = 0;
  const sections = exam.sections || [];

  // 顶栏
  const tabBar = el("div", { class: "row", style: "gap:6px; flex-wrap:wrap" });
  function refreshTabs() {
    tabBar.innerHTML = "";
    sections.forEach((s, i) => {
      const btn = el("button", {
        class: i === currentIdx ? "primary" : "ghost",
        style: "font-size:13px; padding:6px 10px",
        onClick: () => { currentIdx = i; refresh(); },
      }, sectionTabLabel(s));
      tabBar.appendChild(btn);
    });
  }
  refreshTabs();

  host.appendChild(el("div", { class: "row between", style: "margin-bottom:8px" }, [
    el("button", { class: "ghost", onClick: () => router.go("/exams") }, "← 返回列表"),
    el("div", { style: "text-align:center; flex:1" }, [
      el("div", { style: "font-weight:700; font-size:16px" }, exam.title || exam.id),
      el("div", { class: "label" }, `${(sections || []).length} 个 section`),
    ]),
    el("div", { style: "min-width:90px" }),  // spacer
  ]));
  host.appendChild(tabBar);

  const stage = el("div", { class: "card", style: "margin-top:16px; min-height:400px" });
  host.appendChild(stage);

  const navBar = el("div", { class: "row between", style: "margin-top:16px" });
  host.appendChild(navBar);

  function refresh() {
    refreshTabs();
    stage.innerHTML = "";
    const s = sections[currentIdx];
    if (!s) {
      stage.appendChild(el("div", { class: "empty" }, "无内容"));
    } else {
      stage.appendChild(renderSection(s, answers));
    }

    // 底部导航
    navBar.innerHTML = "";
    navBar.appendChild(el("button", {
      onClick: () => { if (currentIdx > 0) { currentIdx -= 1; refresh(); } },
    }, "← 上一节"));
    if (currentIdx < sections.length - 1) {
      navBar.appendChild(el("button", {
        class: "primary",
        onClick: () => { currentIdx += 1; refresh(); },
      }, "下一节 →"));
    } else {
      navBar.appendChild(el("button", {
        class: "primary",
        onClick: async () => submit(host, exam, answers, router, startedAt),
      }, "✓ 交卷"));
    }
  }

  refresh();
}

function sectionTabLabel(s) {
  const map = {
    "writing": "✍️ 写作",
    "listening": "🎧 听力",
    "reading-banked": "📝 选词",
    "reading-matching": "🔍 段落匹配",
    "reading-mcq": "📖 仔细阅读",
    "translation": "🌏 翻译",
  };
  return map[s.id] || s.title || s.id;
}

// =====================================================
// Section 渲染器
// =====================================================

export function renderSection(s, answers) {
  switch (s.type) {
    case "writing":         return renderWriting(s, answers);
    case "listening":       return renderListening(s, answers);
    case "banked-cloze":    return renderBankedCloze(s, answers);
    case "matching":        return renderMatching(s, answers);
    case "reading-mcq":     return renderReadingMcq(s, answers);
    case "translation":     return renderTranslation(s, answers);
    default:
      return el("div", { class: "empty" }, `未知 section 类型: ${s.type}`);
  }
}

export function renderWriting(s, answers) {
  const answerKey = s.id || "writing";
  const root = el("div");
  root.appendChild(el("h3", { style: "margin-top:0" }, `✍️ ${s.title || "Writing"}`));
  if (s.directions) {
    root.appendChild(el("div", { class: "label", style: "margin-bottom:12px; line-height:1.7" }, s.directions));
  }
  if (s.prompt) {
    root.appendChild(el("div", {
      style: "padding:14px; background:var(--bg); border-left:3px solid var(--accent); border-radius:6px; margin-bottom:16px; font-style:italic",
    }, "“" + s.prompt + "”"));
  }
  const ta = el("textarea", {
    rows: "14",
    style: "width:100%; font-size:15px; line-height:1.7",
    placeholder: "在此处写作(150–200 词)…",
  });
  ta.value = answers[answerKey] || "";
  const wc = el("div", { class: "label", style: "margin-top:6px; text-align:right" }, "0 词");
  ta.addEventListener("input", () => {
    answers[answerKey] = ta.value;
    const words = (ta.value.trim().match(/\S+/g) || []).length;
    wc.textContent = `${words} 词 · ${ta.value.length} 字符`;
  });
  ta.dispatchEvent(new Event("input"));
  root.appendChild(ta);
  root.appendChild(wc);
  return root;
}

export function renderListening(s, answers) {
  const root = el("div");
  root.appendChild(el("h3", { style: "margin-top:0" }, "🎧 Part II · Listening Comprehension"));
  root.appendChild(el("div", { class: "feedback warn", style: "text-align:left" },
    "⚠️ 听力原文/音频在 PoC 阶段暂未接入,这里只列出选项;后续 Step 2.5 抽完 key 会显示题干与原文。"));
  const list = el("div", { class: "grid", style: "gap:14px; margin-top:16px" });
  for (const q of s.questions || []) {
    list.appendChild(renderMcqItem(q, answers, "listening"));
  }
  root.appendChild(list);
  return root;
}

export function renderBankedCloze(s, answers) {
  const root = el("div");
  root.appendChild(el("h3", { style: "margin-top:0" }, "📝 Reading Section A · 选词填空"));

  // word bank
  const wb = s.wordBank || {};
  const wbBox = el("div", {
    style: "display:grid; grid-template-columns:repeat(3,1fr); gap:6px 12px; padding:12px; background:var(--bg); border-radius:8px; margin-bottom:16px",
  });
  for (const k of "ABCDEFGHIJKLMNO") {
    if (wb[k]) {
      wbBox.appendChild(el("div", { style: "font-family:monospace; font-size:14px" },
        [el("strong", {}, k + ") "), wb[k]]));
    }
  }
  root.appendChild(wbBox);

  // 收集题号 → blank node 映射,以便选项变化时刷新 passage 里的 box 内容
  const questions = s.questions || [];
  const numbers = questions.map((q) => q.number);
  const blankNodes = new Map();   // qnum → DOM 节点(span)
  const updateBlank = (qnum) => {
    const node = blankNodes.get(qnum);
    if (!node) return;
    const sel = answers[qnum];
    node.textContent = sel ? `${qnum} · ${wb[sel] || sel}` : `${qnum} · ___`;
    node.style.background = sel ? "rgba(106,167,255,0.18)" : "rgba(242,185,74,0.18)";
    node.style.color = sel ? "var(--accent)" : "var(--warn)";
  };

  // passage 里把 26-35 渲染成醒目方框(passage 缺数字也兜底:show 选项区)
  const passage = s.passage || "";
  const passageBox = el("div", {
    style: "padding:14px; background:var(--bg); border-radius:8px; line-height:2; font-size:14px; max-height:340px; overflow-y:auto",
  });
  // 拆分:用题号正则切,把数字替换成 span
  const numSet = new Set(numbers);
  const parts = passage.split(/(\b\d{1,2}\b)/);
  for (const part of parts) {
    const n = Number(part);
    if (numSet.has(n)) {
      const blank = el("span", {
        style: [
          "display:inline-block",
          "padding:2px 10px",
          "margin:0 4px",
          "border:1px dashed var(--warn)",
          "border-radius:6px",
          "font-weight:600",
          "min-width:80px",
          "text-align:center",
          "vertical-align:middle",
        ].join(";"),
      }, "");
      blankNodes.set(n, blank);
      passageBox.appendChild(blank);
      updateBlank(n);
    } else {
      passageBox.appendChild(document.createTextNode(part));
    }
  }
  root.appendChild(passageBox);

  // 缺失题号提示
  const missing = numbers.filter((n) => !blankNodes.has(n));
  if (missing.length) {
    root.appendChild(el("div", { class: "feedback warn", style: "font-size:12px; margin-top:8px" },
      `⚠️ 原文里这些题号没显示出来 (PDF 抽取漏了): ${missing.join(", ")} — 直接看下方选择区作答即可`));
  }

  // 选择区(永远 26-35 完整列出)
  root.appendChild(el("div", { class: "section-title", style: "margin-top:16px" }, "你的选择 (26-35)"));
  const grid = el("div", { class: "grid cols-2", style: "gap:8px" });
  for (const q of questions) {
    const sel = el("select", { style: "flex:1" }, [
      el("option", { value: "" }, "—— 选择 ——"),
      ...Object.entries(wb).sort().map(([k, v]) =>
        el("option", { value: k }, `${k}) ${v}`)),
    ]);
    sel.value = answers[q.number] || "";
    sel.addEventListener("change", () => {
      answers[q.number] = sel.value;
      updateBlank(q.number);
    });
    grid.appendChild(el("div", { class: "row", style: "gap:8px" }, [
      el("strong", { style: "min-width:36px; color:var(--accent)" }, String(q.number) + "."),
      sel,
    ]));
  }
  root.appendChild(grid);
  return root;
}

export function renderMatching(s, answers) {
  const root = el("div");
  root.appendChild(el("h3", { style: "margin-top:0" }, `🔍 ${s.title || "Reading Section B · 段落匹配"}`));

  // 段落(可折叠)
  const parasBox = el("details", { open: "true", style: "margin-bottom:16px" });
  parasBox.appendChild(el("summary", { style: "cursor:pointer; font-weight:600; padding:8px 0" },
    `📑 ${(s.paragraphs || []).length} 个段落(点击折叠)`));
  for (const p of s.paragraphs || []) {
    parasBox.appendChild(el("div", {
      style: "padding:10px; margin:6px 0; background:var(--bg); border-radius:6px; line-height:1.7; font-size:14px",
    }, [
      el("strong", { style: "color:var(--accent); margin-right:8px" }, `[${p.label}]`),
      p.text,
    ]));
  }
  root.appendChild(parasBox);

  // 题陈述
  root.appendChild(el("div", { class: "section-title" }, "选择段落"));
  const labels = (s.paragraphs || []).map((p) => p.label);
  for (const q of s.questions || []) {
    const sel = el("select", { style: "min-width:80px" }, [
      el("option", { value: "" }, "—"),
      ...labels.map((l) => el("option", { value: l }, l)),
    ]);
    sel.value = answers[q.number] || "";
    sel.addEventListener("change", () => answers[q.number] = sel.value);
    root.appendChild(el("div", { class: "row", style: "gap:12px; margin:8px 0; align-items:flex-start" }, [
      el("strong", { style: "min-width:36px; padding-top:4px" }, String(q.number) + "."),
      sel,
      el("div", { style: "flex:1" }, q.stem || ""),
    ]));
  }
  return root;
}

export function renderReadingMcq(s, answers) {
  const root = el("div");
  root.appendChild(el("h3", { style: "margin-top:0" }, `📖 ${s.title || "Reading Section C · 仔细阅读"}`));
  for (const psg of s.passages || []) {
    root.appendChild(el("div", { class: "section-title", style: "margin-top:24px" }, psg.label));
    root.appendChild(el("div", {
      style: "padding:14px; background:var(--bg); border-radius:8px; line-height:1.8; white-space:pre-wrap; font-size:14px; max-height:300px; overflow-y:auto; margin-bottom:12px",
    }, psg.text || ""));
    for (const q of psg.questions || []) {
      root.appendChild(renderMcqItem(q, answers, "mcq"));
    }
  }
  return root;
}

function renderMcqItem(q, answers, kind) {
  const opts = q.options || {};
  const wrap = el("div", {
    style: "padding:12px; border:1px solid var(--border); border-radius:8px; margin-bottom:10px",
  });
  const stem = q.stem || (kind === "listening" ? "(听力题干暂缺,见 Step 2.5)" : "");
  wrap.appendChild(el("div", { style: "font-weight:600; margin-bottom:8px" },
    [String(q.number) + ". ", stem]));
  for (const letter of "ABCD") {
    if (!(letter in opts)) continue;
    const radio = el("input", {
      type: "radio",
      name: `q${q.number}`,
      value: letter,
      style: "margin-right:8px",
    });
    if (answers[q.number] === letter) radio.checked = true;
    radio.addEventListener("change", () => answers[q.number] = letter);
    const label = el("label", {
      style: "display:block; padding:6px 10px; cursor:pointer; border-radius:6px",
    }, [radio, el("strong", {}, letter + ") "), opts[letter]]);
    label.addEventListener("mouseenter", () => label.style.background = "var(--bg)");
    label.addEventListener("mouseleave", () => label.style.background = "");
    wrap.appendChild(label);
  }
  return wrap;
}

export function renderTranslation(s, answers) {
  const root = el("div");
  const toChinese = s.targetLanguage === "zh";
  root.appendChild(el("h3", { style: "margin-top:0" }, `🌏 ${s.title || "Translation"}`));
  if (s.directions) {
    root.appendChild(el("div", { class: "label", style: "margin-bottom:12px" }, s.directions));
  }
  root.appendChild(el("div", {
    style: "padding:14px; background:var(--bg); border-radius:8px; line-height:1.85; margin-bottom:16px; font-size:15px",
  }, s.source || "(中文段落抽取失败)"));

  const ta = el("textarea", {
    rows: "10",
    style: "width:100%; font-size:15px; line-height:1.7",
    placeholder: toChinese ? "在此处写中文译文…" : "在此处用英语翻译…",
  });
  ta.value = answers.translation || "";
  const wc = el("div", { class: "label", style: "margin-top:6px; text-align:right" }, "0 词");
  ta.addEventListener("input", () => {
    answers.translation = ta.value;
    const words = (ta.value.trim().match(/\S+/g) || []).length;
    wc.textContent = `${words} 词 · ${ta.value.length} 字符`;
  });
  ta.dispatchEvent(new Event("input"));
  root.appendChild(ta);
  root.appendChild(wc);
  return root;
}

// =====================================================
// 提交
// =====================================================

async function submit(host, exam, answers, router, startedAt) {
  // 统计客观题作答
  const endedAt = Date.now();
  let totalObj = 0, answered = 0;
  let scorableObj = 0, correctObj = 0;
  let writingChars = 0, translationChars = 0;
  for (const s of exam.sections || []) {
    if (s.type === "writing") writingChars += (answers[s.id || "writing"] || "").length;
    else if (s.type === "translation") translationChars = (answers.translation || "").length;
    else {
      const allQ = s.questions || s.passages?.flatMap((p) => p.questions || []) || [];
      for (const q of allQ) {
        totalObj += 1;
        if (answers[q.number]) answered += 1;
        if (q.answer) {
          scorableObj += 1;
          if (answers[q.number] === q.answer) correctObj += 1;
        }
      }
    }
  }
  const totalScore = scorableObj ? Math.round((correctObj / scorableObj) * 100) : null;
  const answerReady = scorableObj > 0;

  const attempt = {
    examId: exam.id,
    examType: exam.type,
    startedAt,
    endedAt,
    answers: JSON.parse(JSON.stringify(answers)),
    totalObjective: totalObj,
    answeredObjective: answered,
    scorableObjective: scorableObj,
    correctObjective: correctObj,
    writingChars,
    translationChars,
    scoredSections: [],
    totalScore,
    answerReady,
  };
  const browserId = await store.put("examAttempts", attempt);
  attempt.browserId = browserId;
  attempt.mode = "exam";
  attempt.localDbKey = examAttemptKey(attempt);
  const localSaved = await trySaveExamAttempt(attempt);

  const feedback = answerReady
    ? el("div", { class: "feedback ok", style: "max-width:600px; margin:0 auto 16px" },
        `客观题已自动判分: ${correctObj}/${scorableObj} · ${totalScore}%`)
    : el("div", { class: "feedback warn", style: "max-width:600px; margin:0 auto 16px" },
        "⚠️ 答案库还在抽取中(Step 2.5)。结构化的题目和你的作答都已就位,等答案灌进 JSON 后这里会自动显示对错和解析。");

  host.innerHTML = "";
  host.appendChild(el("div", { class: "card", style: "text-align:center; padding:32px" }, [
    el("div", { style: "font-size:48px" }, "📨"),
    el("h2", { style: "margin:8px 0" }, "已交卷"),
    el("div", { class: "label" }, exam.title || exam.id),
    el("div", { class: "grid cols-3", style: "margin:24px 0" }, [
      stat("客观题作答", `${answered}/${totalObj}`,
        totalObj ? `${Math.round((answered / totalObj) * 100)}% 完成` : ""),
      stat("作文字符", String(writingChars), writingChars ? `约 ${Math.round(writingChars / 5)} 词` : "未作答"),
      stat("翻译字符", String(translationChars), translationChars ? `约 ${Math.round(translationChars / 5)} 词` : "未作答"),
    ]),
    feedback,
    el("div", { class: "feedback ok", style: "max-width:600px; margin:0 auto 16px" },
      `✓ 本次提交已记录 · ${formatDateTime(endedAt)}`),
    localSaved
      ? el("div", { class: "label", style: "margin-bottom:16px" }, "已同步到本地 SQLite 数据库。")
      : el("div", { class: "label", style: "margin-bottom:16px" }, "本地 SQLite 暂不可用,已先保存在浏览器 IndexedDB。"),
    el("div", { class: "row", style: "justify-content:center; gap:8px" }, [
      el("button", { class: "ghost", onClick: () => router.go("/exams") }, "回真题列表"),
      el("button", { class: "primary", onClick: () => location.reload() }, "再做一遍"),
    ]),
  ]));

  // 逐题对照(只在有答案库时显示)
  if (answerReady) {
    host.appendChild(renderReviewBoard(exam, answers));
  }
}

// =====================================================
// 提交后的逐题对照
// =====================================================

export function renderReviewBoard(exam, answers) {
  const root = el("div", { class: "card", style: "margin-top:16px" });
  root.appendChild(el("h3", { style: "margin-top:0" }, "📋 逐题查看"));
  root.appendChild(el("div", { class: "label", style: "margin-bottom:12px" },
    "✓ 答对  ✗ 答错  · 未作答  ☆ 暂无标准答案"));

  for (const s of exam.sections || []) {
    if (s.type === "writing" || s.type === "translation") {
      root.appendChild(renderWritingReview(s, answers));
      continue;
    }
    const allQ = s.questions || s.passages?.flatMap((p) => p.questions || []) || [];
    if (!allQ.length) continue;
    root.appendChild(renderSectionReview(s, allQ, answers));
  }
  return root;
}

function renderSectionReview(s, allQ, answers) {
  const det = el("details", { style: "margin-top:8px; padding:10px 14px; background:var(--bg); border-radius:8px" });
  // 算 section 内对错
  let correct = 0, total = 0, scorable = 0;
  for (const q of allQ) {
    total += 1;
    if (q.answer) {
      scorable += 1;
      if (answers[q.number] === q.answer) correct += 1;
    }
  }
  const summary = scorable
    ? `${sectionTabLabel(s)} · ${correct}/${scorable} 对`
    : `${sectionTabLabel(s)} · 共 ${total} 题(暂无标准答案)`;
  const sum = el("summary", { style: "cursor:pointer; font-weight:600; padding:4px 0" }, summary);
  det.appendChild(sum);

  const list = el("div", { style: "margin-top:8px" });
  for (const q of allQ) {
    list.appendChild(renderQuestionReview(q, answers));
  }
  det.appendChild(list);
  return det;
}

function renderQuestionReview(q, answers) {
  const userAns = answers[q.number] || "";
  const correct = q.answer || "";
  const noAnswer = !correct;
  const noResponse = !userAns;
  const isRight = !noAnswer && userAns === correct;

  let mark, color;
  if (noAnswer) { mark = "☆"; color = "var(--fg-faint)"; }
  else if (noResponse) { mark = "·"; color = "var(--fg-dim)"; }
  else if (isRight) { mark = "✓"; color = "var(--ok)"; }
  else { mark = "✗"; color = "var(--err)"; }

  const row = el("div", {
    style: "display:flex; gap:10px; padding:8px 6px; border-bottom:1px solid var(--border); align-items:flex-start",
  });
  row.appendChild(el("div", {
    style: `width:24px; flex:0 0 24px; font-weight:700; color:${color}; font-size:18px; line-height:1.2`,
  }, mark));
  row.appendChild(el("div", { style: "min-width:42px; color:var(--fg-dim)" }, String(q.number) + "."));

  const body = el("div", { style: "flex:1; min-width:0" });
  if (q.stem) {
    body.appendChild(el("div", { style: "font-size:14px; margin-bottom:4px" }, q.stem));
  }
  // 答案对照
  const answerLine = el("div", { class: "label", style: "margin-top:2px" });
  if (noAnswer) {
    answerLine.appendChild(el("span", {}, `你的: ${userAns || "—"} · 标准答案: 暂无`));
  } else {
    answerLine.appendChild(el("span", {}, `你的: `));
    answerLine.appendChild(el("strong", {
      style: `color:${noResponse ? "var(--fg-faint)" : (isRight ? "var(--ok)" : "var(--err)")}`,
    }, userAns || "未答"));
    answerLine.appendChild(el("span", {}, ` · 标准: `));
    answerLine.appendChild(el("strong", { style: "color:var(--ok)" }, correct));
  }
  body.appendChild(answerLine);

  // 解析(可折叠避免太长)
  if (q.explanation) {
    const exp = el("details", { style: "margin-top:6px" });
    exp.appendChild(el("summary", { style: "cursor:pointer; color:var(--fg-dim); font-size:12px" }, "解析"));
    exp.appendChild(el("div", {
      style: "padding:8px 10px; background:var(--bg-card); border-left:2px solid var(--accent); margin-top:4px; font-size:13px; line-height:1.7; color:var(--fg-dim)",
    }, q.explanation));
    body.appendChild(exp);
  }

  row.appendChild(body);
  return row;
}

function renderWritingReview(s, answers) {
  const userText = answers[s.id || s.type] || "";
  const ref = s.reference || "";
  const det = el("details", { style: "margin-top:8px; padding:10px 14px; background:var(--bg); border-radius:8px" });
  det.appendChild(el("summary", { style: "cursor:pointer; font-weight:600" },
    `${sectionTabLabel(s)} · ${userText.length} 字符${ref ? "(有参考答案)" : "(无参考答案)"}`));
  if (userText) {
    det.appendChild(el("div", { class: "label", style: "margin-top:8px" }, "你的作答:"));
    det.appendChild(el("div", {
      style: "padding:10px; background:var(--bg-card); border-radius:6px; line-height:1.7; white-space:pre-wrap; margin-top:4px",
    }, userText));
  }
  if (ref) {
    det.appendChild(el("div", { class: "label", style: "margin-top:12px" }, "参考答案:"));
    det.appendChild(el("div", {
      style: "padding:10px; background:var(--bg-card); border-left:2px solid var(--accent); border-radius:6px; line-height:1.7; white-space:pre-wrap; margin-top:4px; font-size:13px",
    }, ref));
  }
  return det;
}

function stat(label, value, sub) {
  return el("div", { class: "stat" }, [
    el("div", { class: "label" }, label),
    el("div", { class: "value" }, value),
    sub ? el("div", { class: "sub" }, sub) : null,
  ]);
}

function formatDateTime(ts) {
  const d = new Date(ts);
  return `${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}
