# wordtml

**本地运行的单词记忆网站**。Python 起静态服务,SPA 前端,进度存在浏览器 IndexedDB 里。

## 快速开始

```bash
python server.py
```

浏览器会自动打开 http://127.0.0.1:8080/。

> 必须通过 HTTP 访问,不能直接双击 `index.html`(ES 模块不允许 `file://` 协议下相互 import)。

## 当前进度

### ✅ Phase 1 — 骨架 + 1 种玩法 + SRS(已完成,能跑通完整闭环)
- Python 静态服务
- SPA 路由框架(hash-based)
- IndexedDB 数据层(progress / wrongbook / settings / stats / sessions)
- SRS 引擎(SM-2 简化版,5 段熟练度 / 6 档间隔)
- 学习会话管理
- 玩法:**英译中选择**
- 页面:首页、学习、设置
- 词表加载器 + 示例词表(40 词)
- 数据导出 / 导入 / 清空

### 🚧 Phase 2 — 基础玩法补全(未开)
- 闪卡、中译英选择、拼写、听写、例句填空
- 复习页(到期 + 错题本)

### 🚧 Phase 3 — 地图闯关(未开)
- 5 主题世界:迷雾森林 / 风暴海岛 / 苍穹古堡 / 星海太空站 / 炽焰火山口
- 关卡节点类型:普通 / 精英 / Boss / 宝箱 / 隐藏
- 1–3 星评价 + 金币 + 道具系统

### 🚧 Phase 4 — 段位赛(未开)
- 青铜 → 王者,每段 I/II/III 三小段
- 每日挑战、晋级赛、连胜积分

### 🚧 Phase 5 — 趣味玩法 + 统计 + 成就(未开)
- 单词拼图 / 连连看 / 单词消消乐
- 热力图、正确率曲线、熟练度分布
- 成就徽章墙

## 目录结构

```
wordtml/
├── server.py                   Python 静态服务
├── index.html                  入口 SPA
├── src/
│   ├── app.js                  路由入口
│   ├── router.js               hash 路由
│   ├── core/
│   │   ├── store.js            IndexedDB 封装
│   │   ├── srs.js              间隔重复算法
│   │   ├── session.js          学习会话
│   │   └── wordlist.js         词表加载
│   ├── modes/
│   │   ├── _interface.js       玩法协议 + 注册表
│   │   └── choice-en.js        英译中选择
│   ├── pages/
│   │   ├── home.js
│   │   ├── learn.js
│   │   └── settings.js
│   └── ui/
│       ├── components.js       DOM 构造工具
│       └── style.css
└── data/
    ├── schema.md               词表 JSON schema
    └── wordlists/
        ├── index.json          词表索引
        └── sample-cet4.json    示例词表(40 词)
```

## 接入自己的词表

1. 按 [data/schema.md](data/schema.md) 写一份 JSON,丢到 `data/wordlists/`。
2. 在 `data/wordlists/index.json` 里登记一条。
3. 刷新页面,去设置页切换词表。

## 扩展玩法

每种玩法就一个文件。看 [src/modes/choice-en.js](src/modes/choice-en.js) 的结构,复制改一份:

```js
export default {
  id: "your-mode",
  name: "你的玩法",
  description: "一句话介绍",
  render(ctx) {
    // ctx.word / ctx.pool / ctx.index / ctx.total
    // 答完调 ctx.onAnswer({ correct, quality, responseMs })
    return domNode;
  },
};
```

然后在 [src/modes/_interface.js](src/modes/_interface.js) 注册一下就生效。会自动接入 SRS、错题本、统计。

## 数据存哪

全在浏览器 IndexedDB,数据库名 `wordtml`。
- 换电脑/清缓存之前,去**设置 → 数据管理 → 导出进度**,得到一个 JSON 备份。
- 新环境用"导入进度"还原。

## 环境

Python 3.8+ 即可(`server.py` 只用标准库)。前端用原生 ES Module,无 build step。
