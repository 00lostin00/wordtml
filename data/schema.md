# 词表 JSON Schema

## 文件位置
`data/wordlists/<id>.json`

## 顶层结构

```json
{
  "meta": {
    "id": "cet4",
    "name": "CET-4 四级词汇",
    "lang": "en",
    "target": "zh-CN",
    "total": 4500,
    "bands": 5,
    "version": "1.0.0"
  },
  "words": [ /* WordItem[] */ ]
}
```

### meta 字段
| 字段 | 必填 | 说明 |
|---|---|---|
| `id` | ✔ | 词表唯一 id,文件名与此一致 |
| `name` | ✔ | 展示名 |
| `lang` | ✔ | 源语言,ISO 639-1 |
| `target` | ✔ | 目标语言 |
| `total` |   | 总词数(仅供展示) |
| `bands` |   | 分频档数 |
| `version` |   | 版本号 |

## WordItem 结构

```json
{
  "id": "cet4-0001",
  "word": "abandon",
  "phonetic": "/əˈbændən/",
  "pos": "v.",
  "defs_cn": ["抛弃", "放弃"],
  "defs_en": ["to give up completely"],
  "examples": [
    { "en": "He abandoned his car.", "cn": "他弃车而去。" }
  ],
  "band": 1,
  "tags": ["高频", "核心"]
}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `id` | ✔ | 全局唯一 id,格式 `<wordlist-id>-<序号>` |
| `word` | ✔ | 单词本体 |
| `phonetic` |   | 音标 |
| `pos` |   | 词性缩写(n./v./adj./adv.…) |
| `defs_cn` | ✔ | 中文释义数组 |
| `defs_en` |   | 英文释义数组 |
| `examples` |   | 例句数组,每项 `{en, cn}` |
| `band` |   | 分频档,1 最高频 |
| `tags` |   | 自由标签 |

## 注意
- 词表**内容**是静态数据,不要写用户进度。用户进度存在浏览器 IndexedDB。
- `id` 一旦发布不要改 —— 改了会导致用户进度对不上。
- 新增字段可以随便加,前端未知字段忽略即可。
