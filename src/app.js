/**
 * wordtml 入口。
 * 挂路由,各页面 lazy import(第一次访问才加载)。
 */
import { Router } from "./router.js";

const routes = {
  "/":         (ctx) => page("home", ctx),
  "/learn":    (ctx) => page("learn", ctx),
  "/review":   (ctx) => page("review", ctx),
  "/browse":   (ctx) => page("browse", ctx),
  "/map":      (ctx) => page("map", ctx),
  "/stage":    (ctx) => page("stage", ctx),
  "/rank":     (ctx) => page("rank", ctx),
  "/shop":     (ctx) => page("shop", ctx),
  "/match":    (ctx) => page("match", ctx),
  "/rapid":    (ctx) => page("rapid", ctx),
  "/stats":    (ctx) => page("stats", ctx),
  "/exams":    (ctx) => page("exams", ctx),
  "/exam":     (ctx) => page("exam", ctx),
  "/settings": (ctx) => page("settings", ctx),
};

async function page(name, ctx) {
  const mod = await import(`./pages/${name}.js`);
  await mod.render(ctx);
}

function comingSoon(ctx, title, desc) {
  ctx.host.innerHTML = `
    <div class="coming-soon">
      <div class="icon">🚧</div>
      <div class="title">${title}</div>
      <div class="desc">${desc}</div>
    </div>
  `;
}

const router = new Router(routes);
router.start(document.getElementById("app"));

// 暴露给调试用
window.__wordtml = { router };
