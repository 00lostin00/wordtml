# wordtml

一个专注于 **CET-6 / 考研英语一** 的单词记忆与真题练习网站。前端用原生 ES Module 写成，不依赖 npm 或打包工具；后端是一个轻量 Python 服务，负责托管静态文件并提供 SQLite 接口保存做题记录。

**在线体验：[http://39.101.137.168:8081](http://39.101.137.168:8081)**

---

## 功能介绍

### 单词学习

- 默认词表为 **CET-6 四六级核心词**，可在「设置」页切换为考研词表
- 基于 **SRS 间隔重复算法**，自动安排每日新词与到期复习
- 六种练习模式：英译中选择、中译英选择、闪卡、拼写、听写、拼图
- 错题本、学习统计、成就系统、金币道具商店

### 挑战模式

- **地图闯关**：主题世界 + 关卡星级
- **段位赛**：青铜→王者限时混合题
- **快速反应**：30 / 60 / 90 秒限时连答
- **连连看**：10 组英中配对

### 真题练习

- 收录 CET-6 历年真题（2015–2025）及考研英语一（2001–2025）
- 支持整卷模拟和分题型专项刷题
- 做题记录保存在服务器 SQLite，换浏览器不丢失
- **注意**：部分年份答案不完整（主要集中在 CET-6 2013–2021 部分卷次），听力题目暂不支持

### AI 助手

- 页面右下角 **✦** 按钮打开对话窗口
- 可询问单词释义、题目解析、语法、写作等问题
- 使用 DeepSeek 模型，需在服务器配置 API Key

---

## 注意事项

- **单词学习进度存储在浏览器 IndexedDB 中**，请勿清除浏览器数据，否则进度全部丢失
- 建议固定使用同一浏览器访问，不要在多个浏览器之间切换
- AI 对话记录存在浏览器本地，清除缓存后丢失
- 必须通过 HTTP 地址访问，不能直接双击 `index.html` 打开

---

## 本地运行

需要 Python 3，无需 npm 或任何前端构建工具。

```bash
# 克隆项目
git clone https://github.com/00lostin00/wordtml.git
cd wordtml

# 启动服务（默认 8080 端口）
python server.py

# 或指定端口
python server.py 9000
```

浏览器打开 `http://127.0.0.1:8080/`

---

## 接入 AI 助手（可选）

AI 助手需要 DeepSeek API Key，在项目根目录新建 `deepseek.env`：

```
DEEPSEEK_API_KEY=sk-你的key
```

server.py 启动时会自动读取，无需其他配置。DeepSeek API Key 在 [platform.deepseek.com](https://platform.deepseek.com) 注册后获取。

---

## 部署到服务器

### 拉取代码

```bash
# 国内服务器推荐用加速镜像
git clone https://ghfast.top/https://github.com/00lostin00/wordtml.git
cd wordtml

pip3 install openai
echo "DEEPSEEK_API_KEY=sk-你的key" > deepseek.env
```

### 用 systemd 后台运行

```bash
cat > /etc/systemd/system/wordtml.service << 'EOF'
[Unit]
Description=wordtml
After=network.target

[Service]
WorkingDirectory=/var/www/wordtml
ExecStart=/usr/bin/python3 server.py 8081
Restart=always
Environment=WORDTML_HOST=0.0.0.0

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable wordtml
systemctl start wordtml
```

### 更新代码

```bash
cd /var/www/wordtml
git pull https://ghfast.top/https://github.com/00lostin00/wordtml.git
systemctl restart wordtml
```

### 配合 Nginx 反向代理（可选）

如果想用域名 + 80/443 端口访问，在 Nginx 里加一个 server block：

```nginx
server {
    server_name wordtml.你的域名.com;

    location / {
        proxy_pass http://127.0.0.1:8081;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## 真题数据说明

| 类型 | 覆盖年份 | 答案完整度 |
|------|----------|-----------|
| CET-6 | 2015–2025 | 部分年份答案缺失，2022–2025 较完整 |
| 考研英语一 | 2001–2025 | 客观题答案基本完整（754/754） |

听力题目结构存在但无音频，不影响其他题型使用。

---
