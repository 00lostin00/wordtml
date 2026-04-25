/**
 * 玩法:闪卡
 * 看英文 → 翻面看中文 → 自评熟练度(不认识 / 模糊 / 记得 / 熟练)。
 * 自评打分直接对应 SRS 质量:0 / 2 / 4 / 5。
 */
import { el } from "../ui/components.js";
import { itemBar } from "./item-tools.js";

export default {
  id: "flashcard",
  name: "闪卡",
  description: "看词翻面,自评熟练度",

  render(ctx) {
    const { word, index, total, onAnswer } = ctx;
    const startedAt = Date.now();
    let flipped = false;

    const root = el("div", { class: "mode-host" });

    root.appendChild(el("div", { class: "row between" }, [
      el("span", { class: "pill" }, `第 ${index + 1} / ${total} 题`),
      el("span", { class: "pill" }, "闪卡"),
    ]));
    root.appendChild(el("div", { class: "progress" }, [
      el("div", { class: "bar", style: `width:${(index / total) * 100}%` }),
    ]));

    // 正面:单词
    const frontContent = [
      word.phonetic ? el("div", { class: "phonetic" }, word.phonetic) : null,
      el("div", { class: "prompt" }, word.word),
      word.pos ? el("span", { class: "pos" }, word.pos) : null,
      el("div", { class: "label", style: "margin-top:24px" }, "点击卡片或按空格翻面"),
    ];
    // 背面:释义
    const backContent = () => [
      word.phonetic ? el("div", { class: "phonetic" }, word.phonetic) : null,
      el("div", { class: "prompt", style: "font-size:26px" }, word.word),
      word.pos ? el("span", { class: "pos" }, word.pos) : null,
      el("div", { style: "margin-top:20px; font-size:20px" }, (word.defs_cn || []).join("; ")),
      word.examples && word.examples.length
        ? el("div", { style: "margin-top:16px; color:var(--fg-dim); font-size:14px" }, [
            el("div", {}, word.examples[0].en || ""),
            el("div", {}, word.examples[0].cn || ""),
          ])
        : null,
    ];

    const card = el("div", { class: "question-card", style: "cursor:pointer; user-select:none" }, frontContent);
    const ratingBar = el("div", { class: "options", style: "opacity:0.4; pointer-events:none" });

    const ratings = [
      { label: "完全不认识", quality: 0, correct: false, cls: "wrong" },
      { label: "模糊", quality: 2, correct: false, cls: "" },
      { label: "记得", quality: 4, correct: true, cls: "" },
      { label: "熟练", quality: 5, correct: true, cls: "correct" },
    ];

    const flip = () => {
      if (flipped) return;
      flipped = true;
      card.innerHTML = "";
      backContent().forEach((c) => c && card.appendChild(c));
      ratingBar.style.opacity = "1";
      ratingBar.style.pointerEvents = "auto";
    };

    card.addEventListener("click", flip);

    const keyHandler = (e) => {
      if (e.code === "Space") {
        e.preventDefault();
        flip();
      }
    };
    window.addEventListener("keydown", keyHandler);

    const tools = itemBar(ctx, {
      skip: () => window.removeEventListener("keydown", keyHandler),
    });
    if (tools) root.appendChild(tools);

    ratings.forEach((r) => {
      const btn = el("button", { class: "option " + r.cls }, r.label);
      btn.addEventListener("click", () => {
        window.removeEventListener("keydown", keyHandler);
        onAnswer({
          correct: r.correct,
          quality: r.quality,
          responseMs: Date.now() - startedAt,
        });
      });
      ratingBar.appendChild(btn);
    });

    root.appendChild(card);
    root.appendChild(ratingBar);
    return root;
  },
};
