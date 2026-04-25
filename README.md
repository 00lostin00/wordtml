# wordtml

本地运行的英语学习 SPA。前端是原生 ES Module，没有 npm/build step；后端是一个轻量 Python 静态服务，并额外提供本地 SQLite API，用来保存做题记录和同步浏览器里的 IndexedDB 数据。

## 当前状态

这版先作为阶段性检查点保存：

- 单词学习、复习、挑战、成就、商店等基础功能仍走浏览器 IndexedDB。
- 真题中心已接入 CET-6 和考研英语一数据。
- 考研英语一已经补入“真题答案速查”答案映射，随机抽题会直接读取更新后的结构化 JSON。
- 新增随机抽题入口和本地做题记录落库能力，适合后面继续把网页端记录迁移到本地数据库。
- 仍有部分真题结构需要继续清理，例如早年 KY1 缺阅读/作文 section、部分年份选项不全。

## 快速开始

```bash
python server.py 9000
```

然后打开：

```text
http://127.0.0.1:9000/
```

必须通过 HTTP 访问，不要直接双击 `index.html`，否则浏览器会拦截 ES module 的本地 import。

## 主要入口

- `/`：首页
- `/learn`：今日学习
- `/review`：复习
- `/browse`：词表浏览
- `/stats`：学习统计
- `/exams`：真题中心
- `/exam?id=...`：整卷做题
- `/practice?type=ky1&year=2024`：指定真题练习
- `/random?type=ky1`：随机抽题
- `/settings`：设置、导入导出、本地数据库同步状态

## 本地数据库

`server.py` 启动后会在项目根目录创建本地数据库：

```text
wordtml.db
```

相关文件已加入 `.gitignore`：

- `wordtml.db`
- `wordtml.db-shm`
- `wordtml.db-wal`

数据库 API 主要用于保存：

- exam attempts
- local sync state
- 后续可扩展的用户做题记录

如果只使用 GitHub Pages，静态页面仍能打开，但本地 SQLite API 不可用；需要本机运行 `python server.py 9000` 才有本地落库能力。

## 真题数据

结构化真题位于：

```text
data/exams/
```

关键文件：

- `data/exams/index.json`：真题索引
- `data/exams/ky1/*.json`：考研英语一结构化试卷
- `data/exams/cet6/*.json`：六级结构化试卷
- `data/exams/_answer_report.json`：答案覆盖报告
- `data/exams/_validation_report.json`：结构校验报告

目前 KY1 答案覆盖报告：

- `OK=25`
- `WARN=1`
- `FAIL=0`
- `2000` 是空卷，所以仍为 WARN

重点年份已经补满：

- `2010 40/40`
- `2012 40/40`
- `2024 45/45`
- `2025 40/40`

## 答案提取

KY1 答案提取脚本：

```bash
python tools/exam_extract_answers.py ky1 --all --write
python tools/exam_build_index.py
```

这版增强了：

- 跨年份“答案速查”文件识别
- 按年份切片，避免答案串年
- `1.D`、行内多答案、全角标点、OCR 后异常符号的解析
- 2010-2025 图片型速查 PDF 的 OCR 文本接入

图片型 PDF OCR 的临时目录是：

```text
tmp_exam_ocr/
```

该目录已忽略，不提交。

## 校验

常用检查：

```bash
Get-ChildItem -Path src -Recurse -Filter *.js | ForEach-Object { node --check $_.FullName }
python tools/exam_validate.py ky1 --all
python tools/exam_build_index.py
```

注意：`exam_validate.py ky1 --all` 现在仍会报很多结构问题，主要是旧数据解析不完整，不代表答案映射失败。判断答案覆盖优先看：

```text
data/exams/_answer_report.json
```

## 开发约定

- 不引入 bundler / npm / TypeScript / 前端框架。
- 静态前端继续用原生 ES Module。
- 真题 JSON 的题号和 ID 发布后尽量不要改。
- 本地数据库、OCR 图片、PDF 原始资料不要提交。
- 新增真题 PDF 后，先抽文本/OCR，再跑答案提取和索引构建。

## 下次继续

建议下一轮优先做：

- 清理 KY1 早年试卷结构，让阅读、翻译、作文 section 更完整。
- 把随机抽题的做题结果更完整地写入本地 SQLite。
- 给 `/attempt` 或做题历史页补一个更清晰的列表和回看入口。
- 处理 CET6 还有大量未跟踪原始抽取文件的问题，决定哪些需要提交、哪些只保留本地。
