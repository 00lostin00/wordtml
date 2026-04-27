/**
 * 首次访问欢迎弹窗，之后不再显示。
 */

const SEEN_KEY = "wordtml_welcome_seen_v1";

export function initWelcome() {
  if (localStorage.getItem(SEEN_KEY)) return;
  mountWelcome();
}

function mountWelcome() {
  const overlay = document.createElement("div");
  overlay.className = "wl-overlay";
  overlay.innerHTML = `
    <div class="wl-modal">
      <div class="wl-header">
        <span class="wl-logo">wordtml</span>
        <span class="wl-badge">使用说明</span>
        <a class="wl-gh-link" href="https://github.com/00lostin00/wordtml" target="_blank" title="GitHub 项目主页">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z"/>
          </svg>
        </a>
      </div>

      <div class="wl-body">
        <p class="wl-intro">欢迎使用 wordtml —— 专注于 CET-6 / 考研英语一的单词记忆与真题练习网站。</p>

        <div class="wl-section">
          <div class="wl-section-title">📖 单词学习</div>
          <ul>
            <li>默认词表为 <b>CET-6 四六级核心词</b>，可在「设置」页切换为考研词表</li>
            <li>支持六种练习模式：英译中选择、中译英选择、闪卡、拼写、听写、拼图</li>
            <li>基于 <b>SRS 间隔重复算法</b>，自动安排每日新词与到期复习，建议每天打开</li>
            <li>在「设置」里可调整每日新词数量（默认 20 个）</li>
          </ul>
        </div>

        <div class="wl-section">
          <div class="wl-section-title">📝 真题练习</div>
          <ul>
            <li>收录 CET-6 历年真题（2015–2025）及考研英语一（2001–2025）</li>
            <li>支持完整模拟考试和分题型专项刷题两种模式</li>
            <li><b>部分年份答案不完整</b>，主要集中在 2013–2021 年部分卷次，做题时如遇题目无答案属正常现象</li>
            <li><b>听力部分暂不支持</b>，真题中听力题目会显示为空，不影响其他题型</li>
            <li>做题记录保存在服务器数据库，换浏览器也不会丢失</li>
          </ul>
        </div>

        <div class="wl-section">
          <div class="wl-section-title">✦ AI 助手</div>
          <ul>
            <li>点击页面右下角 <b>✦</b> 蓝色按钮打开 AI 对话窗口</li>
            <li>可以询问单词释义、题目解析、语法问题、写作建议等</li>
            <li>使用 DeepSeek 模型，对话记录存在本地浏览器中</li>
          </ul>
        </div>

        <div class="wl-section">
          <div class="wl-section-title">⚠️ 重要注意事项</div>
          <ul>
            <li><b>单词学习进度存储在浏览器 IndexedDB 中</b>，请勿清除浏览器缓存/数据，否则进度全部丢失</li>
            <li>建议固定使用同一浏览器访问，不要在多个浏览器之间切换</li>
            <li>AI 对话记录存在浏览器本地，清除缓存后会丢失</li>
          </ul>
        </div>
      </div>

      <div class="wl-footer">
        <label class="wl-check-label">
          <input type="checkbox" id="wl-no-show" />
          不再显示
        </label>
        <button class="wl-start-btn" id="wl-start">开始使用</button>
      </div>
    </div>
  `;

  document.body.appendChild(overlay);

  document.getElementById("wl-start").addEventListener("click", () => {
    if (document.getElementById("wl-no-show").checked) {
      localStorage.setItem(SEEN_KEY, "1");
    }
    overlay.classList.add("wl-overlay--out");
    setTimeout(() => overlay.remove(), 280);
  });

  // 点遮罩也能关
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) {
      localStorage.setItem(SEEN_KEY, "1");
      overlay.classList.add("wl-overlay--out");
      setTimeout(() => overlay.remove(), 280);
    }
  });
}
