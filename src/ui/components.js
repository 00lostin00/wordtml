/**
 * 轻量 DOM 构造工具。
 *
 *   el("div", { class: "card", onClick: fn }, [child1, child2])
 *   el("button", { class: "primary" }, "点我")
 */
export function el(tag, attrs = {}, children = null) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === "class") node.className = v;
    else if (k === "style") node.setAttribute("style", v);
    else if (k.startsWith("on") && typeof v === "function") {
      node.addEventListener(k.slice(2).toLowerCase(), v);
    } else if (k === "html") {
      node.innerHTML = v;
    } else {
      node.setAttribute(k, v);
    }
  }
  appendChildren(node, children);
  return node;
}

function appendChildren(node, children) {
  if (children == null) return;
  if (Array.isArray(children)) {
    for (const c of children) appendChildren(node, c);
    return;
  }
  if (typeof children === "string" || typeof children === "number") {
    node.appendChild(document.createTextNode(String(children)));
    return;
  }
  if (children instanceof Node) node.appendChild(children);
}

export function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
}

/**
 * 统计小卡:label + value + sub
 */
export function statBlock(label, value, sub = "") {
  return el("div", { class: "stat" }, [
    el("div", { class: "label" }, label),
    el("div", { class: "value" }, String(value)),
    sub ? el("div", { class: "sub" }, sub) : null,
  ]);
}

export function achievementNotice(items = []) {
  if (!items || !items.length) return null;
  return el("div", { class: "achievement-notice" }, [
    el("div", { class: "section-title" }, "新成就"),
    ...items.map((item) => el("div", { class: "achievement-pop" }, [
      el("div", { class: "achievement-mark" }, "✓"),
      el("div", {}, [
        el("div", { style: "font-weight:700" }, item.title || item.id),
        el("div", { class: "label" }, item.desc || "已解锁"),
      ]),
    ])),
  ]);
}
