/**
 * 单词拼图。
 * 看中文释义,把打乱的字母点回正确顺序。
 */
import { el } from "../ui/components.js";
import { itemBar } from "./item-tools.js";

export default {
  id: "puzzle",
  name: "单词拼图",
  description: "把乱序字母拼回单词",
  render(ctx) {
    const started = Date.now();
    const word = ctx.word.word;
    const letters = shuffleLetters(word);
    const picked = [];
    const used = new Set();

    const answer = el("div", { class: "puzzle-answer" });
    const letterPad = el("div", { class: "puzzle-letters" });
    const feedback = el("div", { class: "feedback" });
    const submit = el("button", { class: "primary", disabled: true }, "提交");
    const clear = el("button", { class: "ghost" }, "重排");

    const root = el("div", { class: "question-card" }, [
      el("div", { class: "label" }, `第 ${ctx.index + 1} / ${ctx.total} 题`),
      el("div", { class: "prompt", style: "font-size:28px" }, defs(ctx.word)),
      ctx.word.pos ? el("div", { class: "pos" }, ctx.word.pos) : null,
      ctx.word.phonetic ? el("div", { class: "phonetic" }, ctx.word.phonetic) : null,
      answer,
      letterPad,
      feedback,
      el("div", { class: "row", style: "justify-content:center; margin-top:16px" }, [clear, submit]),
    ]);

    const tools = itemBar(ctx, {
      hint: async () => {
        revealNext();
        return "已放入一个字母";
      },
      xray: async () => `答案是 ${word}`,
      skip: async () => {
        feedback.textContent = "";
      },
    });
    if (tools) root.insertBefore(tools, answer);

    submit.addEventListener("click", () => {
      const guess = picked.map((p) => p.char).join("");
      const correct = guess.toLowerCase() === word.toLowerCase();
      feedback.textContent = correct ? "✓ 拼对了" : `答案是 ${word}`;
      feedback.className = "feedback " + (correct ? "ok" : "err");
      submit.disabled = true;
      setTimeout(() => ctx.onAnswer({
        correct,
        quality: correct ? 5 : 1,
        responseMs: Date.now() - started,
      }), 450);
    });

    clear.addEventListener("click", () => {
      picked.length = 0;
      used.clear();
      feedback.textContent = "";
      feedback.className = "feedback";
      renderState();
    });

    function pick(index) {
      if (used.has(index) || picked.length >= word.length) return;
      used.add(index);
      picked.push({ index, char: letters[index] });
      renderState();
    }

    function unpick(slotIndex) {
      const item = picked.splice(slotIndex, 1)[0];
      if (item) used.delete(item.index);
      renderState();
    }

    function revealNext() {
      const slot = picked.length;
      if (slot >= word.length) return;
      const wanted = word[slot].toLowerCase();
      const idx = letters.findIndex((char, index) => !used.has(index) && char.toLowerCase() === wanted);
      if (idx >= 0) pick(idx);
    }

    function renderState() {
      answer.innerHTML = "";
      for (let i = 0; i < word.length; i += 1) {
        const item = picked[i];
        answer.appendChild(el("button", {
          class: "puzzle-slot" + (item ? " filled" : ""),
          onClick: item ? () => unpick(i) : null,
        }, item ? item.char : ""));
      }

      letterPad.innerHTML = "";
      letters.forEach((char, index) => {
        letterPad.appendChild(el("button", {
          class: "puzzle-letter",
          disabled: used.has(index),
          onClick: () => pick(index),
        }, char));
      });

      submit.disabled = picked.length !== word.length;
    }

    renderState();
    return root;
  },
};

function shuffleLetters(word) {
  const letters = [...word];
  for (let i = letters.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [letters[i], letters[j]] = [letters[j], letters[i]];
  }
  if (letters.join("").toLowerCase() === word.toLowerCase() && letters.length > 1) {
    [letters[0], letters[1]] = [letters[1], letters[0]];
  }
  return letters;
}

function defs(word) {
  return (word.defs_cn || []).slice(0, 3).join("；") || "拼出这个单词";
}
