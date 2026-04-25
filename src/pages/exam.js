/**
 * 真题做题页 /exam?id=cet6-2024-12-1
 * PoC 版:6 种 section 都能渲染,答案先存内存,提交时显示统计。
 * 真正的答案+解析校对要等 Step 2.5 (从 key.txt 抽答案) 上线。
 */
import { el } from "../ui/components.js";
import { store } from "../core/store.js";
import { loadExam } from "../core/exam-loader.js";

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

function renderSection(s, answers) {
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

function renderWriting(s, answers) {
  const root = el("div");
  root.appendChild(el("h3", { style: "margin-top:0" }, "✍️ Part I · Writing"));
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
  ta.value = answers.writing || "";
  const wc = el("div", { class: "label", style: "margin-top:6px; text-align:right" }, "0 词");
  ta.addEventListener("input", () => {
    answers.writing = ta.value;
    const words = (ta.value.trim().match(/\S+/g) || []).length;
    wc.textContent = `${words} 词 · ${ta.value.length} 字符`;
  });
  ta.dispatchEvent(new Event("input"));
  root.appendChild(ta);
  root.appendChild(wc);
  return root;
}

function renderListening(s, answers) {
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

function renderBankedCloze(s, answers) {
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

  // passage
  root.appendChild(el("div", {
    style: "padding:14px; background:var(--bg); border-radius:8px; line-height:1.85; white-space:pre-wrap; font-size:14px; max-height:300px; overflow-y:auto",
  }, s.passage || ""));

  // 26-35 题填空选择
  root.appendChild(el("div", { class: "section-title", style: "margin-top:16px" }, "你的选择"));
  const grid = el("div", { class: "grid cols-2", style: "gap:8px" });
  for (const q of s.questions || []) {
    const sel = el("select", { style: "width:100%" }, [
      el("option", { value: "" }, "—— 选择 ——"),
      ...Object.entries(wb).sort().map(([k, v]) =>
        el("option", { value: k }, `${k}) ${v}`)),
    ]);
    sel.value = answers[q.number] || "";
    sel.addEventListener("change", () => answers[q.number] = sel.value);
    grid.appendChild(el("div", { class: "row", style: "gap:8px" }, [
      el("strong", { style: "min-width:36px" }, String(q.number) + "."),
      sel,
    ]));
  }
  root.appendChild(grid);
  return root;
}

function renderMatching(s, answers) {
  const root = el("div");
  root.appendChild(el("h3", { style: "margin-top:0" }, "🔍 Reading Section B · 段落匹配"));

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

function renderReadingMcq(s, answers) {
  const root = el("div");
  root.appendChild(el("h3", { style: "margin-top:0" }, "📖 Reading Section C · 仔细阅读"));
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

function renderTranslation(s, answers) {
  const root = el("div");
  root.appendChild(el("h3", { style: "margin-top:0" }, "🌏 Part IV · Translation"));
  if (s.directions) {
    root.appendChild(el("div", { class: "label", style: "margin-bottom:12px" }, s.directions));
  }
  root.appendChild(el("div", {
    style: "padding:14px; background:var(--bg); border-radius:8px; line-height:1.85; margin-bottom:16px; font-size:15px",
  }, s.source || "(中文段落抽取失败)"));

  const ta = el("textarea", {
    rows: "10",
    style: "width:100%; font-size:15px; line-height:1.7",
    placeholder: "在此处用英语翻译…",
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
    if (s.type === "writing") writingChars = (answers.writing || "").length;
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
  await store.put("examAttempts", attempt);

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
    el("div", { class: "row", style: "justify-content:center; gap:8px" }, [
      el("button", { class: "ghost", onClick: () => router.go("/exams") }, "回真题列表"),
      el("button", { class: "primary", onClick: () => location.reload() }, "再做一遍"),
    ]),
  ]));
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
