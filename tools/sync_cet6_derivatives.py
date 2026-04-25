"""
Synchronize datasets derived from data/wordlists/cet6.json.

Usage:
    python tools/sync_cet6_derivatives.py

The script intentionally leaves the PDF/OCR pipeline alone. It refreshes only
secondary metadata used by the app:
  - data/wordlists/index.json
  - data/maps/index.json
  - data/maps/cet6-*.json
  - data/reports/cet6-derived-report.json
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
CET6_PATH = ROOT / "data" / "wordlists" / "cet6.json"
WORDLIST_INDEX_PATH = ROOT / "data" / "wordlists" / "index.json"
MAP_INDEX_PATH = ROOT / "data" / "maps" / "index.json"
MAP_DIR = ROOT / "data" / "maps"
REPORT_PATH = ROOT / "data" / "reports" / "cet6-derived-report.json"

# These entries are kept in the master word list to preserve ids, but should not
# be sampled by map chapters until they are manually resolved.
EXCLUDED_WORD_IDS = {
    "cet6-0129": "待核查: OCR 残片 an, 当前释义像 undergraduate course",
    "cet6-0328": "待核查: OCR 残片 be, 当前释义像 be humble/about",
    "cet6-1892": "重复词: 与 cet6-1891 rebel 重复",
}


CHAPTERS = [
    {
        "id": "cet6-forest",
        "name": "迷雾森林",
        "subtitle": "第 1 章 · 入门高频词",
        "description": "覆盖 CET-6 高频词前 500 个，适合建立第一轮熟悉度。",
        "icon": "🌲",
        "file": "cet6-forest.json",
        "wordRange": [0, 500],
        "theme": {"bg": "#1a2e1a", "accent": "#68b07b", "path": "#3a5a3a"},
        "nodes": [
            {"id": "1-1", "type": "normal", "name": "林间小径", "mode": "choice-en", "count": 10, "x": 15, "y": 90, "requires": []},
            {"id": "1-2", "type": "normal", "name": "苔藓石阶", "mode": "choice-cn", "count": 10, "x": 35, "y": 82, "requires": ["1-1"]},
            {"id": "1-3", "type": "normal", "name": "低语古树", "mode": "flashcard", "count": 10, "x": 60, "y": 76, "requires": ["1-2"]},
            {"id": "1-4", "type": "treasure", "name": "林中宝箱", "mode": "review", "count": 10, "x": 82, "y": 68, "requires": ["1-3"]},
            {"id": "1-5", "type": "normal", "name": "野花岔路", "mode": "spelling", "count": 10, "x": 70, "y": 58, "requires": ["1-3"]},
            {"id": "1-6", "type": "normal", "name": "回音溪谷", "mode": "dictation", "count": 10, "x": 48, "y": 52, "requires": ["1-5"]},
            {"id": "1-7", "type": "normal", "name": "朽木桥", "mode": "choice-en", "count": 10, "x": 25, "y": 46, "requires": ["1-6"]},
            {"id": "1-8", "type": "elite", "name": "守林猎人", "modes": ["choice-cn", "spelling"], "count": 15, "x": 15, "y": 36, "requires": ["1-7"]},
            {"id": "1-9", "type": "normal", "name": "萤火沼泽", "mode": "flashcard", "count": 10, "x": 38, "y": 30, "requires": ["1-8"]},
            {"id": "1-10", "type": "normal", "name": "铁锈废墟", "mode": "choice-en", "count": 10, "x": 60, "y": 26, "requires": ["1-9"]},
            {"id": "1-11", "type": "treasure", "name": "盗贼藏宝", "mode": "review", "count": 10, "x": 78, "y": 22, "requires": ["1-10"]},
            {"id": "1-12", "type": "boss", "name": "森林守卫 BOSS", "modes": ["choice-en", "choice-cn", "spelling", "dictation"], "count": 20, "timeLimit": 180, "x": 55, "y": 12, "requires": ["1-10", "1-11"]},
            {"id": "1-h", "type": "hidden", "name": "隐秘精灵树", "mode": "flashcard", "count": 10, "x": 85, "y": 8, "requires": ["1-12"]},
        ],
    },
    {
        "id": "cet6-island",
        "name": "风暴海岛",
        "subtitle": "第 2 章 · 进阶潮汐词",
        "description": "覆盖第 501-1500 个词，开始混入更细的动作词和场景词。",
        "icon": "🏝️",
        "file": "cet6-island.json",
        "wordRange": [500, 1500],
        "theme": {"bg": "#0f3550", "accent": "#4fb7d8", "path": "#6ec7e6"},
        "nodes": [
            {"id": "2-1", "type": "normal", "name": "浅滩登陆", "mode": "choice-en", "count": 10, "x": 12, "y": 88, "requires": []},
            {"id": "2-2", "type": "normal", "name": "贝壳礁", "mode": "choice-cn", "count": 10, "x": 32, "y": 80, "requires": ["2-1"]},
            {"id": "2-3", "type": "normal", "name": "潮音洞", "mode": "dictation", "count": 10, "x": 54, "y": 72, "requires": ["2-2"]},
            {"id": "2-4", "type": "treasure", "name": "沉船宝箱", "mode": "review", "count": 10, "x": 78, "y": 68, "requires": ["2-3"]},
            {"id": "2-5", "type": "normal", "name": "椰林风道", "mode": "flashcard", "count": 10, "x": 68, "y": 56, "requires": ["2-3"]},
            {"id": "2-6", "type": "normal", "name": "雨幕栈桥", "mode": "spelling", "count": 10, "x": 45, "y": 50, "requires": ["2-5"]},
            {"id": "2-7", "type": "normal", "name": "蓝潮灯塔", "mode": "choice-en", "count": 10, "x": 24, "y": 43, "requires": ["2-6"]},
            {"id": "2-8", "type": "elite", "name": "海盗副官", "modes": ["choice-cn", "spelling"], "count": 15, "x": 14, "y": 31, "requires": ["2-7"]},
            {"id": "2-9", "type": "normal", "name": "珊瑚迷宫", "mode": "flashcard", "count": 10, "x": 36, "y": 26, "requires": ["2-8"]},
            {"id": "2-10", "type": "normal", "name": "风眼平台", "mode": "dictation", "count": 10, "x": 60, "y": 22, "requires": ["2-9"]},
            {"id": "2-11", "type": "treasure", "name": "海神遗馈", "mode": "review", "count": 10, "x": 82, "y": 18, "requires": ["2-10"]},
            {"id": "2-12", "type": "boss", "name": "风暴船长 BOSS", "modes": ["choice-en", "choice-cn", "spelling", "dictation"], "count": 20, "timeLimit": 170, "x": 58, "y": 10, "requires": ["2-10", "2-11"]},
            {"id": "2-h", "type": "hidden", "name": "月下蓝洞", "mode": "flashcard", "count": 10, "x": 88, "y": 8, "requires": ["2-12"]},
        ],
    },
    {
        "id": "cet6-castle",
        "name": "苍穹古堡",
        "subtitle": "第 3 章 · 中坚密令词",
        "description": "覆盖第 1501-2500 个词，重点练低频但常考的抽象词。",
        "icon": "🏰",
        "file": "cet6-castle.json",
        "wordRange": [1500, 2500],
        "theme": {"bg": "#2c2351", "accent": "#9b7df0", "path": "#a990ff"},
        "nodes": [
            {"id": "3-1", "type": "normal", "name": "城门吊桥", "mode": "choice-en", "count": 10, "x": 15, "y": 89, "requires": []},
            {"id": "3-2", "type": "normal", "name": "纹章长廊", "mode": "choice-cn", "count": 10, "x": 34, "y": 81, "requires": ["3-1"]},
            {"id": "3-3", "type": "normal", "name": "烛火书库", "mode": "flashcard", "count": 10, "x": 58, "y": 75, "requires": ["3-2"]},
            {"id": "3-4", "type": "treasure", "name": "王宫宝匣", "mode": "review", "count": 10, "x": 83, "y": 68, "requires": ["3-3"]},
            {"id": "3-5", "type": "normal", "name": "回旋阶梯", "mode": "spelling", "count": 10, "x": 72, "y": 58, "requires": ["3-3"]},
            {"id": "3-6", "type": "normal", "name": "银镜厅", "mode": "dictation", "count": 10, "x": 50, "y": 51, "requires": ["3-5"]},
            {"id": "3-7", "type": "normal", "name": "钟楼暗门", "mode": "choice-en", "count": 10, "x": 27, "y": 45, "requires": ["3-6"]},
            {"id": "3-8", "type": "elite", "name": "守誓骑士", "modes": ["choice-cn", "spelling"], "count": 15, "x": 16, "y": 34, "requires": ["3-7"]},
            {"id": "3-9", "type": "normal", "name": "秘法庭院", "mode": "flashcard", "count": 10, "x": 38, "y": 29, "requires": ["3-8"]},
            {"id": "3-10", "type": "normal", "name": "云顶露台", "mode": "choice-cn", "count": 10, "x": 62, "y": 24, "requires": ["3-9"]},
            {"id": "3-11", "type": "treasure", "name": "占星宝库", "mode": "review", "count": 10, "x": 80, "y": 18, "requires": ["3-10"]},
            {"id": "3-12", "type": "boss", "name": "苍穹公爵 BOSS", "modes": ["choice-en", "choice-cn", "spelling", "dictation"], "count": 20, "timeLimit": 165, "x": 56, "y": 10, "requires": ["3-10", "3-11"]},
            {"id": "3-h", "type": "hidden", "name": "塔尖星宫", "mode": "dictation", "count": 10, "x": 88, "y": 8, "requires": ["3-12"]},
        ],
    },
    {
        "id": "cet6-space",
        "name": "星海太空站",
        "subtitle": "第 4 章 · 轨道强化词",
        "description": "覆盖第 2501-3500 个词，简单词与专项词混合强化。",
        "icon": "🚀",
        "file": "cet6-space.json",
        "wordRange": [2500, 3500],
        "theme": {"bg": "#101326", "accent": "#7f8cff", "path": "#8794ff"},
        "nodes": [
            {"id": "4-1", "type": "normal", "name": "发射甲板", "mode": "choice-en", "count": 10, "x": 14, "y": 88, "requires": []},
            {"id": "4-2", "type": "normal", "name": "低轨舱门", "mode": "choice-cn", "count": 10, "x": 33, "y": 80, "requires": ["4-1"]},
            {"id": "4-3", "type": "normal", "name": "零重力廊", "mode": "spelling", "count": 10, "x": 56, "y": 73, "requires": ["4-2"]},
            {"id": "4-4", "type": "treasure", "name": "补给舱", "mode": "review", "count": 10, "x": 81, "y": 69, "requires": ["4-3"]},
            {"id": "4-5", "type": "normal", "name": "星图控制室", "mode": "flashcard", "count": 10, "x": 72, "y": 58, "requires": ["4-3"]},
            {"id": "4-6", "type": "normal", "name": "量子通信塔", "mode": "dictation", "count": 10, "x": 49, "y": 51, "requires": ["4-5"]},
            {"id": "4-7", "type": "normal", "name": "陨石维修道", "mode": "choice-en", "count": 10, "x": 26, "y": 44, "requires": ["4-6"]},
            {"id": "4-8", "type": "elite", "name": "轨道哨兵", "modes": ["choice-cn", "spelling"], "count": 15, "x": 15, "y": 33, "requires": ["4-7"]},
            {"id": "4-9", "type": "normal", "name": "离子温室", "mode": "flashcard", "count": 10, "x": 37, "y": 28, "requires": ["4-8"]},
            {"id": "4-10", "type": "normal", "name": "深空雷达", "mode": "dictation", "count": 10, "x": 61, "y": 23, "requires": ["4-9"]},
            {"id": "4-11", "type": "treasure", "name": "黑匣档案", "mode": "review", "count": 10, "x": 80, "y": 17, "requires": ["4-10"]},
            {"id": "4-12", "type": "boss", "name": "星舰核心 BOSS", "modes": ["choice-en", "choice-cn", "spelling", "dictation"], "count": 20, "timeLimit": 160, "x": 55, "y": 9, "requires": ["4-10", "4-11"]},
            {"id": "4-h", "type": "hidden", "name": "虫洞观测点", "mode": "flashcard", "count": 10, "x": 87, "y": 7, "requires": ["4-12"]},
        ],
    },
    {
        "id": "cet6-volcano",
        "name": "炽焰火山口",
        "subtitle": "第 5 章 · 终焰收官词",
        "description": "覆盖第 3501-4763 个词，收束简单词、功能词和末段补漏。",
        "icon": "🌋",
        "file": "cet6-volcano.json",
        "wordRange": [3500, 4763],
        "theme": {"bg": "#3b1412", "accent": "#ff6f3d", "path": "#ff8a4f"},
        "nodes": [
            {"id": "5-1", "type": "normal", "name": "焦岩入口", "mode": "choice-en", "count": 10, "x": 13, "y": 89, "requires": []},
            {"id": "5-2", "type": "normal", "name": "黑曜石桥", "mode": "choice-cn", "count": 10, "x": 32, "y": 81, "requires": ["5-1"]},
            {"id": "5-3", "type": "normal", "name": "硫磺裂谷", "mode": "dictation", "count": 10, "x": 56, "y": 74, "requires": ["5-2"]},
            {"id": "5-4", "type": "treasure", "name": "熔岩宝箱", "mode": "review", "count": 10, "x": 82, "y": 68, "requires": ["5-3"]},
            {"id": "5-5", "type": "normal", "name": "灰烬坡道", "mode": "spelling", "count": 10, "x": 70, "y": 58, "requires": ["5-3"]},
            {"id": "5-6", "type": "normal", "name": "热浪风口", "mode": "flashcard", "count": 10, "x": 48, "y": 51, "requires": ["5-5"]},
            {"id": "5-7", "type": "normal", "name": "赤焰矿洞", "mode": "choice-en", "count": 10, "x": 25, "y": 45, "requires": ["5-6"]},
            {"id": "5-8", "type": "elite", "name": "熔铠统领", "modes": ["choice-cn", "spelling"], "count": 15, "x": 15, "y": 34, "requires": ["5-7"]},
            {"id": "5-9", "type": "normal", "name": "赤晶平台", "mode": "flashcard", "count": 10, "x": 38, "y": 28, "requires": ["5-8"]},
            {"id": "5-10", "type": "normal", "name": "火山祭坛", "mode": "choice-cn", "count": 10, "x": 62, "y": 23, "requires": ["5-9"]},
            {"id": "5-11", "type": "treasure", "name": "余烬秘藏", "mode": "review", "count": 10, "x": 80, "y": 17, "requires": ["5-10"]},
            {"id": "5-12", "type": "boss", "name": "熔核巨像 BOSS", "modes": ["choice-en", "choice-cn", "spelling", "dictation"], "count": 20, "timeLimit": 150, "x": 55, "y": 9, "requires": ["5-10", "5-11"]},
            {"id": "5-h", "type": "hidden", "name": "凤凰余火", "mode": "dictation", "count": 10, "x": 88, "y": 7, "requires": ["5-12"]},
        ],
    },
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def wordlist_quality(words: list[dict[str, Any]]) -> dict[str, Any]:
    band_counts = Counter(str(w.get("band", "")) for w in words)
    tag_counts = Counter(tag for w in words for tag in (w.get("tags") or []))
    return {
        "total": len(words),
        "bandCounts": {k: band_counts[k] for k in sorted(band_counts) if k},
        "tagCounts": dict(tag_counts),
        "missingPhonetic": sum(1 for w in words if not w.get("phonetic")),
        "missingPos": sum(1 for w in words if not w.get("pos")),
        "missingDefsCn": sum(1 for w in words if not w.get("defs_cn")),
        "withDefsEn": sum(1 for w in words if w.get("defs_en")),
        "excludedWordIds": sorted(EXCLUDED_WORD_IDS),
    }


def range_stats(words: list[dict[str, Any]], start: int, end: int) -> dict[str, Any]:
    segment = words[start:end]
    band_counts = Counter(str(w.get("band", "")) for w in segment)
    excluded = [w["id"] for w in segment if w.get("id") in EXCLUDED_WORD_IDS]
    playable = [w for w in segment if w.get("id") not in EXCLUDED_WORD_IDS]
    return {
        "range": [start, end],
        "total": len(segment),
        "playableTotal": len(playable),
        "bandCounts": {k: band_counts[k] for k in sorted(band_counts) if k},
        "missingPhonetic": sum(1 for w in segment if not w.get("phonetic")),
        "missingPos": sum(1 for w in segment if not w.get("pos")),
        "missingDefsCn": sum(1 for w in segment if not w.get("defs_cn")),
        "excludedWordIds": excluded,
    }


def node_summary(chapter: dict[str, Any]) -> dict[str, int]:
    counts = Counter(node.get("type", "normal") for node in chapter["nodes"])
    return {k: counts[k] for k in ["normal", "treasure", "elite", "boss", "hidden"] if counts[k]}


def build_chapter(spec: dict[str, Any], words: list[dict[str, Any]], source_version: str) -> dict[str, Any]:
    start, end = spec["wordRange"]
    stats = range_stats(words, start, end)
    excluded = stats["excludedWordIds"]
    return {
        "id": spec["id"],
        "name": spec["name"],
        "subtitle": spec["subtitle"],
        "description": spec["description"],
        "icon": spec["icon"],
        "wordlistId": "cet6",
        "wordRange": spec["wordRange"],
        "excludeWordIds": excluded,
        "sourceVersion": source_version,
        "wordStats": stats,
        "theme": spec["theme"],
        "nodes": spec["nodes"],
    }


def validate_chapter(chapter: dict[str, Any], total_words: int) -> list[str]:
    errors: list[str] = []
    start, end = chapter["wordRange"]
    if not (0 <= start < end <= total_words):
        errors.append(f"{chapter['id']}: invalid wordRange {chapter['wordRange']}")

    ids = [node["id"] for node in chapter["nodes"]]
    if len(ids) != len(set(ids)):
        errors.append(f"{chapter['id']}: duplicate node ids")

    node_ids = set(ids)
    for node in chapter["nodes"]:
        for req in node.get("requires", []):
            if req not in node_ids:
                errors.append(f"{chapter['id']}:{node['id']} requires missing node {req}")

    return errors


def build_wordlist_index(data: dict[str, Any], quality: dict[str, Any]) -> dict[str, Any]:
    return {
        "wordlists": [
            {
                "id": "sample-cet4",
                "name": "CET-4 示例词表",
                "file": "sample-cet4.json",
                "total": 40,
                "description": "40 个示例单词，用来跑通框架。",
            },
            {
                "id": "cet6",
                "name": data["meta"].get("name", "CET-6 六级词汇"),
                "file": "cet6.json",
                "total": quality["total"],
                "version": data["meta"].get("version", "1.0.0"),
                "description": "CET-6 主词表，已基于 ECDICT 补全音标、词性、中文释义和英文释义；ID 保持稳定。",
                "quality": quality,
            },
        ]
    }


def build_map_index(chapters: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "chapters": [
            {
                "id": chapter["id"],
                "name": chapter["name"],
                "subtitle": chapter["subtitle"],
                "description": chapter["description"],
                "icon": chapter["icon"],
                "file": f"{chapter['id']}.json",
                "wordlistId": chapter["wordlistId"],
                "wordRange": chapter["wordRange"],
                "wordCount": chapter["wordStats"]["total"],
                "playableWordCount": chapter["wordStats"]["playableTotal"],
            }
            for chapter in chapters
        ]
    }


def main() -> None:
    data = load_json(CET6_PATH)
    words = data.get("words", [])
    version = data.get("meta", {}).get("version", "unknown")

    quality = wordlist_quality(words)
    chapters = [build_chapter(spec, words, version) for spec in CHAPTERS]

    errors: list[str] = []
    for chapter in chapters:
        errors.extend(validate_chapter(chapter, len(words)))
    if errors:
        raise RuntimeError("\n".join(errors))

    dump_json(WORDLIST_INDEX_PATH, build_wordlist_index(data, quality))
    dump_json(MAP_INDEX_PATH, build_map_index(chapters))
    for chapter in chapters:
        dump_json(MAP_DIR / f"{chapter['id']}.json", chapter)

    report = {
        "wordlistId": "cet6",
        "source": str(CET6_PATH.relative_to(ROOT)).replace("\\", "/"),
        "sourceVersion": version,
        "quality": quality,
        "excludedWords": EXCLUDED_WORD_IDS,
        "chapters": [
            {
                "id": chapter["id"],
                "name": chapter["name"],
                "wordRange": chapter["wordRange"],
                "nodeSummary": node_summary(chapter),
                "wordStats": chapter["wordStats"],
            }
            for chapter in chapters
        ],
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    dump_json(REPORT_PATH, report)

    print(f"wordlist total={quality['total']}")
    print(f"missing phonetic={quality['missingPhonetic']}, pos={quality['missingPos']}, defs={quality['missingDefsCn']}")
    print(f"chapters={len(chapters)}")
    print(f"excluded ids={len(EXCLUDED_WORD_IDS)}")
    print(f"report={REPORT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
