/**
 * 词表浏览。
 * 支持搜索、band/熟练度过滤、错题排序和单词详情。
 */
import { el } from "../ui/components.js";
import { store } from "../core/store.js";
import { loadWordlist } from "../core/wordlist.js";

const BOX_LABELS = ["陌生", "学习中", "熟悉", "掌握", "永久"];

export async function render(ctx) {
  const { host, router } = ctx;
  const activeId = await store.getSetting("activeWordlist", "cet6");

  let wordlist;
  try {
    wordlist = await loadWordlist(activeId);
  } catch (e) {
    host.appendChild(el("div", { class: "card" }, [
      el("h3", {}, "词表加载失败"),
      el("div", { class: "feedback err" }, e.message),
      el("button", { class: "primary", onClick: () => router.go("/settings") }, "去设置"),
    ]));
    return;
  }

  const [progressRows, wrongRows] = await Promise.all([
    store.all("progress"),
    store.all("wrongbook"),
  ]);
  const progressMap = new Map(progressRows.filter((p) => p.wordlistId === activeId).map((p) => [p.wordId, p]));
  const wrongMap = new Map(wrongRows.filter((w) => w.wordlistId === activeId).map((w) => [w.wordId, w]));

  const state = {
    q: "",
    band: "all",
    box: "all",
    sort: "order",
    selected: wordlist.words[0],
  };

  host.appendChild(el("div", { class: "row between", style: "margin-bottom:16px" }, [
    el("div", {}, [
      el("h2", { style: "margin:0" }, "📚 词表浏览"),
      el("div", { class: "label", style: "margin-top:4px" }, `${wordlist.meta.name} · ${wordlist.words.length} 词`),
    ]),
    el("button", { class: "ghost", onClick: () => router.go("/") }, "返回首页"),
  ]));

  const listNode = el("div", { class: "browse-list" });
  const detailNode = el("div", { class: "browse-detail" });
  const countPill = el("span", { class: "pill" }, "");

  const searchInput = el("input", {
    type: "search",
    placeholder: "搜索 word / 中文释义",
    value: "",
  });
  const bandSelect = el("select", {}, [
    el("option", { value: "all" }, "全部频段"),
    ...bandOptions(wordlist).map((band) => el("option", { value: String(band) }, `Band ${band}`)),
  ]);
  const boxSelect = el("select", {}, [
    el("option", { value: "all" }, "全部熟练度"),
    el("option", { value: "new" }, "未学习"),
    ...BOX_LABELS.map((label, i) => el("option", { value: String(i) }, label)),
  ]);
  const sortSelect = el("select", {}, [
    el("option", { value: "order" }, "原始顺序"),
    el("option", { value: "word" }, "字母排序"),
    el("option", { value: "wrong" }, "错题数优先"),
    el("option", { value: "box-asc" }, "熟练度低优先"),
    el("option", { value: "box-desc" }, "熟练度高优先"),
  ]);

  const refresh = () => {
    state.q = searchInput.value.trim().toLowerCase();
    state.band = bandSelect.value;
    state.box = boxSelect.value;
    state.sort = sortSelect.value;
    renderList(listNode, detailNode, countPill, wordlist.words, progressMap, wrongMap, state);
  };
  searchInput.addEventListener("input", refresh);
  bandSelect.addEventListener("change", refresh);
  boxSelect.addEventListener("change", refresh);
  sortSelect.addEventListener("change", refresh);

  host.appendChild(el("div", { class: "card" }, [
    el("div", { class: "browse-toolbar" }, [
      searchInput,
      bandSelect,
      boxSelect,
      sortSelect,
      countPill,
    ]),
  ]));

  host.appendChild(el("div", { class: "browse-layout" }, [
    listNode,
    detailNode,
  ]));

  refresh();
}

function renderList(listNode, detailNode, countPill, words, progressMap, wrongMap, state) {
  const filtered = filterWords(words, progressMap, wrongMap, state);
  countPill.textContent = `${filtered.length} 个结果`;
  listNode.innerHTML = "";

  if (!filtered.length) {
    listNode.appendChild(el("div", { class: "empty" }, "没有匹配的单词。"));
    renderDetail(detailNode, null, null, null);
    return;
  }

  if (!state.selected || !filtered.some((w) => w.id === state.selected.id)) {
    state.selected = filtered[0];
  }

  for (const word of filtered) {
    const progress = progressMap.get(word.id);
    const wrong = wrongMap.get(word.id);
    const active = state.selected && state.selected.id === word.id;
    const row = el("button", {
      class: "browse-row" + (active ? " active" : ""),
      onClick: () => {
        state.selected = word;
        renderList(listNode, detailNode, countPill, words, progressMap, wrongMap, state);
      },
    }, [
      el("div", {}, [
        el("div", { class: "browse-word" }, word.word),
        el("div", { class: "label" }, firstDef(word)),
      ]),
      el("div", { class: "browse-row-meta" }, [
        word.band ? el("span", { class: "pill" }, `B${word.band}`) : null,
        el("span", { class: "pill" + (progress ? " ok" : "") }, progress ? BOX_LABELS[boxOf(progress)] : "未学"),
        wrong ? el("span", { class: "pill err" }, `错 ${wrong.count}`) : null,
      ]),
    ]);
    listNode.appendChild(row);
  }

  const selectedProgress = progressMap.get(state.selected.id);
  const selectedWrong = wrongMap.get(state.selected.id);
  renderDetail(detailNode, state.selected, selectedProgress, selectedWrong);
}

function renderDetail(node, word, progress, wrong) {
  node.innerHTML = "";
  if (!word) {
    node.appendChild(el("div", { class: "card empty" }, "选择一个单词查看详情。"));
    return;
  }

  const examples = Array.isArray(word.examples) ? word.examples : [];
  node.appendChild(el("div", { class: "card browse-detail-card" }, [
    el("div", { class: "row between" }, [
      el("div", {}, [
        el("div", { class: "browse-detail-word" }, word.word),
        el("div", { class: "label" }, word.id),
      ]),
      el("div", { class: "row", style: "gap:6px" }, [
        word.band ? el("span", { class: "pill" }, `Band ${word.band}`) : null,
        word.pos ? el("span", { class: "pill" }, word.pos) : null,
      ]),
    ]),
    word.phonetic ? el("div", { class: "browse-phonetic" }, word.phonetic) : null,
    section("中文释义", list(word.defs_cn || [])),
    word.defs_en && word.defs_en.length ? section("英文释义", list(word.defs_en)) : null,
    section("SRS 状态", srsBlock(progress, wrong)),
    examples.length ? section("例句", el("div", { class: "example-list" }, examples.map((ex) =>
      el("div", { class: "example" }, [
        ex.en ? el("div", {}, ex.en) : null,
        ex.cn ? el("div", { class: "label" }, ex.cn) : null,
      ])
    ))) : section("例句", el("div", { class: "label" }, "当前词表还没有例句。")),
    word.tags && word.tags.length ? section("标签", el("div", { class: "row" }, word.tags.map((tag) =>
      el("span", { class: "pill" }, tag)
    ))) : null,
  ]));
}

function filterWords(words, progressMap, wrongMap, state) {
  const q = state.q;
  const out = words.filter((word) => {
    if (state.band !== "all" && String(word.band || "") !== state.band) return false;
    const progress = progressMap.get(word.id);
    if (state.box === "new" && progress) return false;
    if (/^\d$/.test(state.box) && (!progress || boxOf(progress) !== Number(state.box))) return false;
    if (!q) return true;
    const hay = [word.word, ...(word.defs_cn || [])].join(" ").toLowerCase();
    return hay.includes(q);
  });

  out.sort((a, b) => {
    if (state.sort === "word") return a.word.localeCompare(b.word);
    if (state.sort === "wrong") return countWrong(wrongMap, b) - countWrong(wrongMap, a);
    if (state.sort === "box-asc") return boxSortValue(progressMap, a) - boxSortValue(progressMap, b);
    if (state.sort === "box-desc") return boxSortValue(progressMap, b) - boxSortValue(progressMap, a);
    return words.indexOf(a) - words.indexOf(b);
  });
  return out;
}

function section(title, child) {
  return el("div", { class: "browse-section" }, [
    el("div", { class: "section-title" }, title),
    child,
  ]);
}

function list(items) {
  return el("ul", { class: "rule-list" }, items.map((item) => el("li", {}, item)));
}

function srsBlock(progress, wrong) {
  if (!progress && !wrong) return el("div", { class: "label" }, "还没有学习记录。");
  return el("div", { class: "grid cols-2" }, [
    mini("熟练度", progress ? BOX_LABELS[boxOf(progress)] : "未学习"),
    mini("复习次数", progress ? progress.reps || 0 : 0),
    mini("下次复习", progress && progress.due ? formatDue(progress.due) : "—"),
    mini("错题次数", wrong ? wrong.count || 0 : 0),
  ]);
}

function mini(label, value) {
  return el("div", { class: "stat browse-mini" }, [
    el("div", { class: "label" }, label),
    el("div", { class: "value" }, String(value)),
  ]);
}

function bandOptions(wordlist) {
  const bands = new Set(wordlist.words.map((w) => w.band).filter(Boolean));
  return [...bands].sort((a, b) => Number(a) - Number(b));
}

function firstDef(word) {
  return (word.defs_cn || []).slice(0, 2).join("；") || "暂无释义";
}

function boxOf(progress) {
  return Math.max(0, Math.min(4, Number(progress.box || 0)));
}

function countWrong(wrongMap, word) {
  return Number(wrongMap.get(word.id)?.count || 0);
}

function boxSortValue(progressMap, word) {
  const progress = progressMap.get(word.id);
  return progress ? boxOf(progress) : -1;
}

function formatDue(ts) {
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return "—";
  return `${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
