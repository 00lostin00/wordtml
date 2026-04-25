"""
CET6 词表清洗工具。
    python tools/clean_cet6.py

做三件事:
  1. 去重单词(同 word 重复出现)
  2. 清空明显 OCR 出错的音标(有乱码的直接置空,比显示错的好)
  3. 修几类能稳妥修的释义残留

原文件备份为 cet6.json.bak。
"""

import json
import re
import shutil
import sys
from pathlib import Path
from collections import OrderedDict

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "data" / "wordlists" / "cet6.json"
BACKUP = ROOT / "data" / "wordlists" / "cet6.json.bak"


# --- 音标判定 ---
# IPA 常见字符白名单(加了些常见替代写法)
IPA_CHARS = set(
    "abcdefghijklmnopqrstuvwxyz"
    "ɑæəɛɜɪɔʊʌʃʒθðŋʧʤ"
    "ˈˌːˑ "
    "()[].,-‐'’\"/"
)

# 判定音标是否疑似 OCR 破坏:
#   - 含中文冒号、竖线、反斜线等
#   - 含阿拉伯数字(IPA 里不该有数字;重音应是 ˈ ˌ)
#   - 含白名单外的字符(如乱码)
BAD_PATTERNS = [
    re.compile(r"[：|\\^`]"),         # 中文冒号/竖线/反斜/尖角
    re.compile(r"[0-9]"),              # 阿拉伯数字,IPA 不该出现
    re.compile(r"[一-鿿]"),    # 汉字
]


def phonetic_is_broken(ph: str) -> bool:
    if not ph:
        return False
    core = ph.strip().strip("/[]")
    if not core:
        return True
    for p in BAD_PATTERNS:
        if p.search(ph):
            return True
    # 大量白名单外字符也判坏
    bad = sum(1 for c in core if c not in IPA_CHARS)
    if bad >= 2:
        return True
    return False


# --- 释义清洗 ---
DEF_JUNK_RE = re.compile(r"^[\s\)\(]+|[\s\(\)]+$")
DEF_NORMALIZE_RE = re.compile(r"^\s*亦作\s*\)\s*", re.UNICODE)   # "亦作 ) 分析" -> "分析"

def clean_def(s: str) -> str:
    s = s or ""
    s = DEF_NORMALIZE_RE.sub("", s)
    s = DEF_JUNK_RE.sub("", s)
    return s.strip()


def main():
    if not TARGET.exists():
        print(f"ERR: 找不到 {TARGET}", file=sys.stderr)
        sys.exit(1)

    print(f"读取 {TARGET}")
    data = json.loads(TARGET.read_text(encoding="utf-8"))
    words = data.get("words", [])
    print(f"原始词数: {len(words)}")

    if not BACKUP.exists():
        shutil.copy2(TARGET, BACKUP)
        print(f"备份写入 {BACKUP}")
    else:
        print(f"备份已存在,跳过:{BACKUP}")

    # 1) 去重:同 word 只保留第一次
    seen = set()
    kept = []
    removed_dups = []
    for w in words:
        key = (w.get("word") or "").strip().lower()
        if not key:
            continue
        if key in seen:
            removed_dups.append(w.get("word"))
            continue
        seen.add(key)
        kept.append(w)

    # 2) 音标清洗
    phon_cleared = 0
    for w in kept:
        ph = w.get("phonetic", "")
        if phonetic_is_broken(ph):
            w["phonetic"] = ""
            phon_cleared += 1

    # 3) 释义残留清洗
    def_fixed = 0
    for w in kept:
        defs = w.get("defs_cn") or []
        new_defs = []
        for d in defs:
            nd = clean_def(d)
            if nd and nd != d:
                def_fixed += 1
            if nd:
                new_defs.append(nd)
        # 全部清空时保底放个原始第一条,防止词没释义
        if not new_defs and defs:
            new_defs = [defs[0]]
        w["defs_cn"] = new_defs

    # 4) 重编 ID,跟行号对齐
    prefix = data.get("meta", {}).get("id", "cet6")
    for i, w in enumerate(kept, 1):
        w["id"] = f"{prefix}-{i:04d}"

    data["words"] = kept
    if "meta" in data:
        data["meta"]["total"] = len(kept)

    TARGET.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    print("-" * 40)
    print(f"去重:       {len(removed_dups):>4} 个")
    if removed_dups:
        print(f"  样本:    {', '.join(removed_dups[:8])}")
    print(f"清空音标:   {phon_cleared:>4} 个(原先是 OCR 乱码)")
    print(f"修复释义:   {def_fixed:>4} 条")
    print(f"最终词数:   {len(kept):>4}")
    print(f"输出:       {TARGET}")


if __name__ == "__main__":
    main()
