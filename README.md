# wordtml

wordtml 是一个可本地运行、也可部署到自己网站上的英语学习网站。前端使用原生 ES Module，不需要 npm、打包器或前端框架；后端是一个轻量 Python 服务，用来托管静态页面，并提供本地 SQLite 接口保存做题记录。

项目主要覆盖两类内容：

- 单词学习：CET-6 词表、学习、复习、错题、统计、地图闯关、段位、商店和小游戏练习。
- 真题练习：CET-6 和考研英语一结构化真题、整卷做题、随机刷题、答案回看和本地记录。

## 本地部署

### 1. 准备环境

需要本机安装 Python 3。项目没有 npm 依赖，所以不需要执行 `npm install`。

在 PowerShell 中进入项目目录：

```powershell
cd D:\wordtml
```

检查 Python 是否可用：

```powershell
python --version
```

如果系统里同时安装了多个 Python，也可以用：

```powershell
py --version
```

### 2. 本地私有配置

项目根目录可以放本地环境变量文件，例如：

```text
.env
```

`server.py` 启动时会自动读取本地环境变量文件里的 `KEY=value` 配置。环境变量文件只应该留在本机，不能提交到仓库；`.gitignore` 已经包含 `*.env`。

### 3. 启动服务

推荐使用 9000 端口：

```powershell
python server.py 9000
```

看到类似输出就说明启动成功：

```text
wordtml serving at http://127.0.0.1:9000/
local database: D:\wordtml\wordtml.db
Ctrl+C to stop.
```

然后在浏览器打开：

```text
http://127.0.0.1:9000/
```

必须通过 HTTP 地址访问，不要直接双击 `index.html`。直接打开本地 HTML 文件时，浏览器会拦截 ES Module 的本地导入，页面功能会不完整。

### 4. 端口被占用时

如果 9000 被占用，换一个端口即可：

```powershell
python server.py 8080
python server.py 5173
python server.py 3000
```

对应访问：

```text
http://127.0.0.1:8080/
```

### 5. 停止服务

回到运行 `server.py` 的 PowerShell 窗口，按：

```text
Ctrl+C
```

## 部署到自己的网站

项目没有前端构建步骤，仓库里的 `index.html`、`src/`、`data/` 等文件就是浏览器需要的文件。部署时可以按需要选择静态部署或 Python 服务部署。

### 方式一：静态部署

适合部署到普通静态网站空间、Nginx、Apache、GitHub Pages、Cloudflare Pages 或自己的对象存储/CDN。静态部署不需要 Python，也不需要安装依赖。

把仓库中这些内容上传到网站目录：

```text
index.html
src/
data/
README.md
```

如果网站根目录就是这个项目，访问：

```text
https://你的域名/
```

如果部署在子目录，例如 `/wordtml/`，访问：

```text
https://你的域名/wordtml/
```

页面使用 hash 路由，所以刷新 `#/learn`、`#/exams`、`#/exam?id=...` 这类地址时，不需要额外的服务器路由配置。只要静态服务器能正常返回 `index.html`、`src/` 和 `data/` 下的文件，网站就能打开。

静态部署可用内容：

- 单词学习、复习、词表浏览、地图、段位、商店、统计等前端功能。
- CET-6 和考研英语一真题浏览、整卷练习、随机刷题。
- 浏览器 IndexedDB 本地保存的学习数据。

静态部署不可用内容：

- `server.py` 提供的 SQLite 记录接口。
- `wordtml.db` 里的跨浏览器/跨设备本地记录。

这些不可用项不会影响页面打开和做题，只是服务端保存能力不会启用。

### 方式二：Python 服务部署

适合部署在自己的服务器上，并且希望保留 `server.py` 提供的本地 SQLite 记录接口。

服务器上进入项目目录后运行：

```bash
python server.py 9000 0.0.0.0
```

也可以用环境变量控制监听地址、端口和数据库位置：

```bash
WORDTML_HOST=0.0.0.0 WORDTML_PORT=9000 WORDTML_OPEN_BROWSER=0 python server.py
```

如果要把数据库放到固定目录：

```bash
WORDTML_DB_PATH=/var/lib/wordtml/wordtml.db WORDTML_HOST=0.0.0.0 WORDTML_PORT=9000 WORDTML_OPEN_BROWSER=0 python server.py
```

然后在 Nginx 里反向代理到本地端口，例如：

```nginx
server {
    server_name example.com;

    location / {
        proxy_pass http://127.0.0.1:9000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

生产环境不要提交或公开这些本地文件：

```text
*.env
wordtml.db
wordtml.db-shm
wordtml.db-wal
tmp_*
cet_eg/
KY_eg/
```

## 页面入口

页面使用 hash 路由，浏览器地址会长这样：

```text
http://127.0.0.1:9000/#/learn
```

常用入口：

- `#/`：首页
- `#/learn`：今日学习
- `#/review`：复习
- `#/browse`：词表浏览
- `#/map`：地图闯关
- `#/rank`：段位赛
- `#/shop`：道具商店
- `#/stats`：学习统计
- `#/exams`：真题中心
- `#/exam?id=ky1-2025`：指定真题整卷练习
- `#/practice`：随机刷题入口
- `#/random?...`：随机抽出的单题练习
- `#/attempt?...`：做题记录回看
- `#/settings`：设置、导入导出、本地数据库状态

## 数据保存

浏览器端数据保存在 IndexedDB，包括单词进度、错题、设置、成就、金币、段位记录等。

本地服务启动后，还会在项目根目录创建 SQLite 数据库：

```text
wordtml.db
wordtml.db-shm
wordtml.db-wal
```

这些文件用于保存真题做题记录和随机刷题历史，已经加入 `.gitignore`，只留在本机。

可以在设置页查看本地数据库是否启用。服务端相关接口包括：

- `GET /api/local/status`
- `GET /api/exam-attempts`
- `POST /api/exam-attempts`
- `GET /api/practice-history`
- `POST /api/practice-history`

## 词表数据

词表位于：

```text
data/wordlists/
```

关键文件：

- `data/wordlists/index.json`：词表索引
- `data/wordlists/cet6.json`：CET-6 词汇
- `data/wordlists/sample-cet4.json`：示例 CET-4 词表

当前页面默认围绕 CET-6 词表使用。设置页可以切换词表、导入备份或导出本地学习数据。

## 真题数据

结构化真题位于：

```text
data/exams/
```

关键文件：

- `data/exams/index.json`：真题索引
- `data/exams/ky1/*.json`：考研英语一结构化试卷
- `data/exams/cet6/*.json`：CET-6 结构化试卷
- `data/exams/_answer_report_ky1.json`：KY1 答案覆盖报告
- `data/exams/_answer_audit_report.json`：答案质量审计报告
- `data/exams/_validation_report.json`：结构校验报告
- `data/exams/_raw/ky1/`：KY1 原始抽取文本
- `data/exams/_raw/cet6/`：CET-6 原始抽取文本
- `data/exams/_raw/cet6_listening/`：单独整理的 CET-6 听力原文/答案文本

当前索引规模：

- 总计：`140`
- CET-6：`114`
- 考研英语一：`26`
- 完整度标签：`complete=7`、`near-complete=23`、`partial=47`、`paper-only=63`

KY1 当前答案覆盖：

- `OK=25`
- `WARN=1`
- `FAIL=0`
- 客观题答案：`754/754`
- 缺失答案：`0`
- 待复核答案：`7`

其中 `ky1-2000` 是空卷，所以仍为 WARN。

## 当前缺少的内容

已知缺口主要在真题结构质量，不是页面运行问题：

- 部分早年 KY1 缺少作文、阅读、新题型或翻译 section。
- 部分 KY1 题目只有答案字母，选项正文不完整。
- KY1 有 7 个答案因为当前选项解析不完整，被标为待复核。
- CET-6 数据仍有大量 `paper-only` 和 `partial` 条目，很多试卷只抽到了部分 section 或部分答案。
- CET-6 听力音频没有接入，当前只保存了可用的文本型听力原文/答案资料。
- 静态部署时只能使用前端页面和浏览器 IndexedDB，本地 SQLite 记录能力需要运行 `server.py`。

## 常用维护命令

检查前端 JS 语法：

```powershell
Get-ChildItem -Path src -Recurse -Filter *.js | ForEach-Object { node --check $_.FullName }
```

重新生成真题索引：

```powershell
python tools/exam_build_index.py
```

回填 KY1 可用答案：

```powershell
python tools/exam_extract_answers.py ky1 --all --write
```

审计 KY1 答案质量：

```powershell
python tools/exam_audit_answers.py ky1
```

校验 KY1 结构：

```powershell
python tools/exam_validate.py ky1 --all
```

## 文件提交注意

这些文件和目录是本地运行或抽取过程产生的，不应该提交：

- `wordtml.db`
- `wordtml.db-shm`
- `wordtml.db-wal`
- `*.env`
- `tmp_*`
- `data/external/`
- `data/reports/`
- `cet_eg/`
- `KY_eg/`

真题 JSON 的题号和 ID 被页面引用，修改时要保持稳定。
