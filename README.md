# wordtml

本地运行的单词记忆 SPA。前端是原生 ES Module,没有 build step;Python 只负责静态文件服务;学习进度存在浏览器 IndexedDB。

## 快速开始

```bash
python server.py 9000
```

然后打开:

```text
http://127.0.0.1:9000/
```

## 已有功能

### 学习与复习

- CET-6 主词表与示例 CET-4 词表
- SM-2 简化版 SRS,5 档熟练度
- 今日新词 + 到期复习
- 错题本,连续答对 3 次自动移出
- 数据导出、导入、清空

### 基础玩法

- 英译中选择
- 中译英选择
- 闪卡
- 拼写
- 听写
- 单词拼图

### 挑战玩法

- 地图闯关:5 章主题地图、普通/精英/Boss/宝箱/隐藏节点、1-3 星评价
- 段位赛:青铜到王者、每日挑战、连胜积分
- 快速反应:`/rapid`,30/60/90 秒限时混合题
- 连连看:`/match`,10 组英中配对,SVG 连线

### 商店与道具

- 金币经济
- 提示、跳过、延时、透视 4 类道具
- Boss/段位等限时场景支持延时道具

### 统计与成就

- `/stats` 学习统计
- 近 30 天学习热力图
- 正确率曲线
- 熟练度分布环图
- 章节进度
- 段位历程
- 成就墙

### 词表浏览

- `/browse` 当前词表浏览
- 搜索 word / 中文释义
- 按 band 过滤
- 按熟练度过滤
- 错题数优先排序
- 单词详情侧栏

### 真题中心

- `/exams` 真题入口,当前分为六级和考研英语一
- 六级已接入 53 卷结构化数据,完整/近完整卷可进入做题页
- `/exam?id=...` 支持写作、听力选项、选词填空、段落匹配、仔细阅读、翻译的 PoC 做题
- 交卷会写入 `examAttempts`,列表页展示最近提交记录
- 答案与解析抽取仍在 Step 2.5,当前暂不批改

## 目录结构

```text
wordtml/
├── server.py
├── index.html
├── src/
│   ├── app.js
│   ├── router.js
│   ├── core/
│   │   ├── achievements.js
│   │   ├── items.js
│   │   ├── map-engine.js
│   │   ├── rank-engine.js
│   │   ├── session.js
│   │   ├── srs.js
│   │   ├── store.js
│   │   └── wordlist.js
│   ├── modes/
│   │   ├── _interface.js
│   │   ├── choice-cn.js
│   │   ├── choice-en.js
│   │   ├── dictation.js
│   │   ├── flashcard.js
│   │   ├── mixed.js
│   │   ├── puzzle.js
│   │   └── spelling.js
│   ├── pages/
│   │   ├── browse.js
│   │   ├── home.js
│   │   ├── learn.js
│   │   ├── map.js
│   │   ├── match.js
│   │   ├── rank.js
│   │   ├── rapid.js
│   │   ├── review.js
│   │   ├── settings.js
│   │   ├── shop.js
│   │   ├── stage.js
│   │   └── stats.js
│   └── ui/
│       ├── components.js
│       └── style.css
└── data/
    ├── schema.md
    ├── maps/
    └── wordlists/
```

## 接入自己的词表

1. 按 [data/schema.md](data/schema.md) 写一份 JSON,放到 `data/wordlists/`。
2. 在 `data/wordlists/index.json` 里登记。
3. 刷新页面,去设置页切换词表。

## 扩展玩法

每种标准单题玩法是一个 mode 文件:

```js
export default {
  id: "your-mode",
  name: "你的玩法",
  description: "一句话介绍",
  render(ctx) {
    // ctx.word / ctx.pool / ctx.index / ctx.total
    // ctx.items / ctx.hasTimer / ctx.useItem(kind)
    // 答完调 ctx.onAnswer({ correct, quality, responseMs })
    return domNode;
  },
};
```

然后在 [src/modes/_interface.js](src/modes/_interface.js) 注册即可。标准 mode 会自动接入 SRS、错题本、统计、道具栏。

## 数据存储

IndexedDB 数据库名: `wordtml`。

当前 store:

- `progress`
- `wrongbook`
- `settings`
- `stats`
- `sessions`
- `mapProgress`
- `economy`
- `rankHistory`
- `achievements`
- `examAttempts`


## 验证

```bash
Get-ChildItem -Path src -Recurse -Filter *.js | ForEach-Object { node --check $_.FullName }
python server.py 9000
```
