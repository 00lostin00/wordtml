/**
 * 玩法:英译中选择
 * 给英文单词,从 4 个中文释义选项中选正确的一个。
 */
import { el } from "../ui/components.js";
import { itemBar } from "./item-tools.js";

function pickDistractors(pool, correctWord, n = 3) {
  const pick = [];
  const used = new Set([correctWord.id]);
  const candidates = pool.filter((w) => !used.has(w.id));
  while (pick.length < n && candidates.length) {
    const idx = Math.floor(Math.random() * candidates.length);
    const w = candidates.splice(idx, 1)[0];
    pick.push(w);
  }
  return pick;
}

function primaryDef(word) {
  return (word.defs_cn && word.defs_cn[0]) || "(无释义)";
}

export default {
  id: "choice-en",
  name: "英译中选择",
  description: "看单词,选中文释义",

  render(ctx) {
    const { word, pool, index, total, onAnswer } = ctx;
    const startedAt = Date.now();

    // 组装选项
    const distractors = pickDistractors(pool, word, 3);
    const options = [word, ...distractors]
      .map((w) => ({ word: w, def: primaryDef(w), correct: w.id === word.id }))
      .sort(() => Math.random() - 0.5);

    const root = el("div", { class: "mode-host" });

    // 顶部进度
    root.appendChild(el("div", { class: "row between" }, [
      el("span", { class: "pill" }, `第 ${index + 1} / ${total} 题`),
      el("span", { class: "pill" }, "英译中"),
    ]));

    root.appendChild(el("div", { class: "progress" }, [
      el("div", { class: "bar", style: `width:${(index / total) * 100}%` }),
    ]));

    // 题目卡
    const qCard = el("div", { class: "question-card" }, [
      word.phonetic ? el("div", { class: "phonetic" }, word.phonetic) : null,
      el("div", { class: "prompt" }, word.word),
      word.pos ? el("span", { class: "pos" }, word.pos) : null,
    ]);
    root.appendChild(qCard);

    // 选项
    const optBox = el("div", { class: "options" });
    const feedback = el("div", { class: "feedback" });
    const optBtns = [];

    const tools = itemBar(ctx, {
      hint: () => {
        const correctIndex = options.findIndex((opt) => opt.correct);
        if (correctIndex >= 0) optBtns[correctIndex].classList.add("correct");
        feedback.textContent = `提示: ${primaryDef(word)}`;
        feedback.className = "feedback ok";
      },
      xray: () => {
        const wrong = optBtns
          .map((btn, i) => ({ btn, opt: options[i] }))
          .filter((row) => !row.opt.correct && !row.btn.disabled);
        if (!wrong.length) return;
        const picked = wrong[Math.floor(Math.random() * wrong.length)];
        picked.btn.disabled = true;
        picked.btn.style.opacity = "0.35";
        feedback.textContent = "透视已排除一个错误选项";
        feedback.className = "feedback ok";
      },
    });
    if (tools) root.appendChild(tools);

    options.forEach((opt) => {
      const btn = el("button", { class: "option" }, opt.def);
      btn.addEventListener("click", () => {
        const responseMs = Date.now() - startedAt;
        optBtns.forEach((b) => (b.disabled = true));
        btn.classList.add(opt.correct ? "correct" : "wrong");
        if (!opt.correct) {
          // 同时点亮正确答案
          optBtns.forEach((b, i) => {
            if (options[i].correct) b.classList.add("correct");
          });
        }
        feedback.textContent = opt.correct ? "✓ 正确" : `✗ 正确答案:${primaryDef(word)}`;
        feedback.className = "feedback " + (opt.correct ? "ok" : "err");

        setTimeout(() => {
          onAnswer({
            correct: opt.correct,
            quality: opt.correct ? (responseMs < 3000 ? 5 : 4) : 1,
            responseMs,
          });
        }, opt.correct ? 500 : 1100);
      });
      optBtns.push(btn);
      optBox.appendChild(btn);
    });

    root.appendChild(optBox);
    root.appendChild(feedback);
    return root;
  },
};
