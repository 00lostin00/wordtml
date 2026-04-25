/**
 * Hash 路由。支持 #/path?k=v 形式。
 *
 * 用法:
 *   const router = new Router({
 *     "/":        () => renderHome(),
 *     "/learn":   (ctx) => renderLearn(ctx),
 *     ...
 *   });
 *   router.start(mountEl);
 *   router.go("/learn", { mode: "choice-en" });
 */
export class Router {
  constructor(routes) {
    this.routes = routes;
    this.host = null;
    this._onHash = this._onHash.bind(this);
  }

  start(host) {
    this.host = host;
    window.addEventListener("hashchange", this._onHash);
    this._onHash();
  }

  stop() {
    window.removeEventListener("hashchange", this._onHash);
  }

  go(path, query = {}) {
    const qs = new URLSearchParams(query).toString();
    location.hash = "#" + path + (qs ? "?" + qs : "");
  }

  _onHash() {
    const hash = location.hash.replace(/^#/, "") || "/";
    const [path, qstr] = hash.split("?");
    const query = Object.fromEntries(new URLSearchParams(qstr || ""));
    const handler = this.routes[path] || this.routes["*"];

    // nav active 高亮
    document.querySelectorAll("[data-route]").forEach((a) => {
      a.classList.toggle("active", a.dataset.route === path);
    });

    this.host.innerHTML = "";
    if (!handler) {
      this.host.innerHTML = `<div class="empty">404 · 没有这个页面</div>`;
      return;
    }
    Promise.resolve(handler({ path, query, host: this.host, router: this }))
      .catch((err) => {
        console.error(err);
        this.host.innerHTML = `<div class="card"><h3>出错了</h3><pre>${String(err.stack || err)}</pre></div>`;
      });
  }
}
