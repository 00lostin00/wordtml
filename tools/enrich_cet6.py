"""
Enrich and repair the CET-6 word list with ECDICT.

Usage:
    python tools/enrich_cet6.py
    python tools/enrich_cet6.py --dry-run

This script intentionally does not touch the PDF/OCR extraction pipeline. It only
reads data/wordlists/cet6.json and data/external/ecdict.csv, then updates the
published word list in place while preserving every word id.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
WORDLIST_PATH = ROOT / "data" / "wordlists" / "cet6.json"
BACKUP_PATH = ROOT / "data" / "wordlists" / "cet6.pre-ecdict.json"
ECDICT_PATH = ROOT / "data" / "external" / "ecdict.csv"
REPORT_PATH = ROOT / "data" / "reports" / "cet6-ecdict-report.json"

ECDICT_URL = "https://github.com/skywind3000/ECDICT"


# High-confidence repairs found by comparing the OCR text + Chinese gloss with
# ECDICT. IDs are preserved; only the displayed word text is corrected. These
# are keyed by id to avoid changing a legitimate short word elsewhere.
ID_WORD_FIXES = {
    "cet6-0010": "atmosphere",
    "cet6-0015": "factory",
    "cet6-0030": "superior",
    "cet6-0036": "acupuncture",
    "cet6-0038": "theater",
    "cet6-0046": "depend",
    "cet6-0048": "despite",
    "cet6-0089": "intelligent",
    "cet6-0102": "engine",
    "cet6-0107": "recognize",
    "cet6-0119": "investigate",
    "cet6-0121": "caption",
    "cet6-0124": "migrate",
    "cet6-0147": "request",
    "cet6-0149": "certain",
    "cet6-0150": "passenger",
    "cet6-0167": "objective",
    "cet6-0166": "finance",
    "cet6-0177": "accomplish",
    "cet6-0199": "lawyer",
    "cet6-0200": "prospect",
    "cet6-0202": "suspect",
    "cet6-0205": "plain",
    "cet6-0230": "property",
    "cet6-0244": "inspire",
    "cet6-0253": "unemployed",
    "cet6-0271": "unique",
    "cet6-0285": "collapse",
    "cet6-0288": "complement",
    "cet6-0291": "congress",
    "cet6-0311": "policy",
    "cet6-0322": "expedition",
    "cet6-0330": "rare",
    "cet6-0336": "metropolitan",
    "cet6-0362": "register",
    "cet6-0371": "retrieve",
    "cet6-0377": "sample",
    "cet6-0381": "imagine",
    "cet6-0388": "stalk",
    "cet6-0425": "forum",
    "cet6-0427": "indigenous",
    "cet6-0431": "segregate",
    "cet6-0432": "salary",
    "cet6-0434": "legend",
    "cet6-0464": "tape",
    "cet6-0469": "stereotype",
    "cet6-0498": "rank",
    "cet6-0505": "frame",
    "cet6-0534": "steam",
    "cet6-0535": "struggle",
    "cet6-0547": "vary",
    "cet6-0574": "negligent",
    "cet6-0575": "globe",
    "cet6-0584": "rhythm",
    "cet6-0598": "empirical",
    "cet6-0618": "eligible",
    "cet6-0630": "layer",
    "cet6-0639": "temple",
    "cet6-0640": "postpone",
    "cet6-0650": "react",
    "cet6-0697": "particle",
    "cet6-0740": "complicate",
    "cet6-0745": "contagious",
    "cet6-0746": "ambiguous",
    "cet6-0748": "impair",
    "cet6-0781": "query",
    "cet6-0784": "interpret",
    "cet6-0791": "corporation",
    "cet6-0824": "discipline",
    "cet6-0832": "aspire",
    "cet6-0843": "margin",
    "cet6-0858": "disappoint",
    "cet6-0869": "attorney",
    "cet6-0876": "surgery",
    "cet6-0900": "regret",
    "cet6-0922": "allergic",
    "cet6-0936": "probe",
    "cet6-0938": "malversation",
    "cet6-0954": "manipulate",
    "cet6-0986": "fury",
    "cet6-0992": "antique",
    "cet6-1003": "evade",
    "cet6-1052": "countryside",
    "cet6-1060": "safeguard",
    "cet6-1073": "layoff",
    "cet6-1119": "fleet",
    "cet6-1148": "verge",
    "cet6-1208": "dwarf",
    "cet6-1221": "slack",
    "cet6-1226": "swamp",
    "cet6-1235": "scrap",
    "cet6-1245": "ceremony",
    "cet6-1247": "crack",
    "cet6-1338": "retaliate",
    "cet6-1365": "rip",
    "cet6-1413": "excel",
    "cet6-1459": "rig",
    "cet6-1548": "conceive",
    "cet6-1611": "zeal",
    "cet6-1773": "spice",
    "cet6-1812": "motel",
    "cet6-1842": "mansion",
    "cet6-1891": "rebel",
    "cet6-2032": "oval",
    "cet6-2237": "verse",
    "cet6-2238": "epic",
    "cet6-2250": "ceramic",
    "cet6-2444": "affiliate",
    "cet6-2575": "cliche",
    "cet6-2892": "let",
    "cet6-3068": "hi",
    "cet6-3075": "sir",
    "cet6-3196": "noodle",
    "cet6-3216": "hot dog",
    "cet6-3217": "pie",
    "cet6-3377": "office",
    "cet6-3616": "lot",
    "cet6-3623": "several",
    "cet6-3653": "steel",
    "cet6-3821": "pig",
    "cet6-3859": "onion",
    "cet6-3864": "bush",
    "cet6-3888": "internet",
    "cet6-3951": "olympic",
    "cet6-3974": "plot",
    "cet6-3980": "piano",
    "cet6-4066": "nice",
    "cet6-4080": "slow",
    "cet6-4081": "soft",
    "cet6-4084": "sure",
    "cet6-4087": "total",
    "cet6-4225": "increase",
    "cet6-4244": "mix",
    "cet6-4298": "win",
    "cet6-4580": "via",
    "cet6-4594": "in",
    "cet6-4743": "remain",
}


# Targeted overrides for entries where ECDICT is either too old-fashioned or too
# narrow for a CET memorization list. These still preserve ids and word order.
FIELD_OVERRIDES = {
    "cet6-0462": {
        "word": "laptop",
        "phonetic": "/'læptɒp/",
        "pos": "n.",
        "defs_cn": ["笔记本电脑", "手提电脑"],
    },
    "cet6-0560": {
        "word": "mall",
        "phonetic": "/mɔ:l/",
        "pos": "n.",
        "defs_cn": ["商场", "购物中心"],
    },
    "cet6-1781": {
        "word": "gown",
        "phonetic": "/gaun/",
        "pos": "n.",
        "defs_cn": ["女礼服", "长袍", "法衣"],
    },
    "cet6-1960": {
        "word": "loophole",
        "phonetic": "/'lu:phәul/",
        "pos": "n.",
        "defs_cn": ["漏洞", "空子"],
    },
    "cet6-1519": {
        "word": "deregulate",
        "phonetic": "/di:'regjuleit/",
        "pos": "v.",
        "defs_cn": ["解除管制"],
    },
    "cet6-3096": {
        "word": "air-conditioning",
        "phonetic": "",
        "pos": "n.",
        "defs_cn": ["空气调节", "空调系统"],
    },
    "cet6-3234": {
        "word": "ice cream",
        "phonetic": "",
        "pos": "n.",
        "defs_cn": ["冰淇淋"],
    },
    "cet6-3216": {
        "word": "hot dog",
        "phonetic": "/hɔt dɔɡ/",
        "pos": "n.",
        "defs_cn": ["热狗"],
    },
    "cet6-3888": {
        "word": "internet",
        "phonetic": "/'intәnet/",
        "pos": "n.",
        "defs_cn": ["因特网", "互联网"],
    },
    "cet6-4069": {
        "word": "online",
        "phonetic": "",
        "pos": "adj./adv.",
        "defs_cn": ["在线的", "联网的"],
    },
    "cet6-4316": {
        "word": "teen",
        "phonetic": "/ti:n/",
        "pos": "n./adj.",
        "defs_cn": ["青少年", "十几岁的"],
    },
    "cet6-4574": {
        "word": "will",
        "phonetic": "/wil/",
        "pos": "aux./n./v.",
        "defs_cn": ["将会", "愿意", "必须", "意志", "遗嘱"],
    },
    "cet6-4576": {
        "word": "ought to",
        "phonetic": "/ɔ:t tə/",
        "pos": "modal.",
        "defs_cn": ["应该"],
    },
    "cet6-4578": {
        "word": "according to",
        "phonetic": "",
        "pos": "prep.",
        "defs_cn": ["根据", "按照", "取决于", "据...所说"],
    },
    "cet6-4740": {
        "word": "am",
        "phonetic": "/æm/",
        "pos": "v.",
        "defs_cn": ["是"],
    },
}


POS_ALIASES = {
    "a": "adj.",
    "adj": "adj.",
    "adjective": "adj.",
    "adv": "adv.",
    "adverb": "adv.",
    "aux": "aux.",
    "conj": "conj.",
    "int": "int.",
    "interj": "int.",
    "n": "n.",
    "num": "num.",
    "pl": "pl.",
    "prep": "prep.",
    "pron": "pron.",
    "suf": "suf.",
    "pref": "pref.",
    "v": "v.",
    "vi": "vi.",
    "vt": "vt.",
}

POS_PREFIX_RE = re.compile(
    r"^(?:\[[^\]]+\]\s*)?"
    r"(?P<pos>abbr|adj|adv|aux|conj|interj|int|n|num|pl|pref|prep|pron|suf|"
    r"vi|vt|v|a)\.\s*",
    re.IGNORECASE,
)
DOMAIN_PREFIX_RE = re.compile(r"^\[[^\]]{1,12}\]\s*")
CHINESE_RE = re.compile(r"[\u3400-\u9fff]")
SPLIT_DEF_RE = re.compile(r"[;,，；]")


@dataclass
class DictIndex:
    exact: dict[str, dict[str, str]]
    stripped: dict[str, dict[str, str]]
    total_rows: int


def strip_word(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())


def has_chinese(value: str) -> bool:
    return bool(CHINESE_RE.search(value or ""))


def normalize_multiline(value: str) -> str:
    # ECDICT stores line breaks inside CSV fields as the two characters "\n".
    return (value or "").replace("\\n", "\n")


def chinese_char_set(value: str) -> set[str]:
    return set(CHINESE_RE.findall(value or ""))


def prefer_row(current: dict[str, str] | None, candidate: dict[str, str]) -> dict[str, str]:
    if current is None:
        return candidate
    current_score = sum(bool(current.get(key)) for key in ("translation", "phonetic", "definition"))
    candidate_score = sum(bool(candidate.get(key)) for key in ("translation", "phonetic", "definition"))
    return candidate if candidate_score > current_score else current


def load_ecdict(path: Path) -> DictIndex:
    exact: dict[str, dict[str, str]] = {}
    stripped: dict[str, dict[str, str]] = {}
    total_rows = 0

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            total_rows += 1
            word = (row.get("word") or "").strip()
            if not word:
                continue
            lowered = word.lower()
            exact[lowered] = prefer_row(exact.get(lowered), row)

            sw = strip_word(word)
            if sw:
                stripped[sw] = prefer_row(stripped.get(sw), row)

    return DictIndex(exact=exact, stripped=stripped, total_rows=total_rows)


def normalize_phonetic(value: str) -> str:
    core = (value or "").strip().strip("/[]")
    if not core:
        return ""
    return f"/{core}/"


def normalize_pos_token(token: str) -> str:
    key = (token or "").strip().lower().strip(".")
    return POS_ALIASES.get(key, f"{key}.") if key else ""


def add_unique(target: list[str], value: str) -> None:
    if value and value not in target:
        target.append(value)


def extract_pos_from_translation(translation: str) -> list[str]:
    out: list[str] = []
    for raw_line in normalize_multiline(translation).splitlines():
        line = raw_line.strip()
        match = POS_PREFIX_RE.match(line)
        if match:
            add_unique(out, normalize_pos_token(match.group("pos")))
    return out


def extract_pos_from_ecdict_pos(pos: str) -> list[str]:
    out: list[str] = []
    for part in (pos or "").split("/"):
        token = part.split(":", 1)[0].strip()
        add_unique(out, normalize_pos_token(token))
    return out


def normalize_pos(row: dict[str, str]) -> str:
    tokens: list[str] = []
    for token in extract_pos_from_translation(row.get("translation", "")):
        add_unique(tokens, token)
    for token in extract_pos_from_ecdict_pos(row.get("pos", "")):
        add_unique(tokens, token)
    return "/".join(tokens)


def remove_pos_prefix(line: str) -> str:
    text = line.strip()
    while True:
        match = POS_PREFIX_RE.match(text)
        if not match:
            break
        text = text[match.end() :].strip()
    return text


def clean_def_part(value: str) -> str:
    text = DOMAIN_PREFIX_RE.sub("", value.strip())
    text = text.strip(" \t\r\n.。")
    return text


def parse_defs_cn(translation: str, max_defs: int = 10) -> list[str]:
    official: list[str] = []
    network: list[str] = []

    for raw_line in normalize_multiline(translation).splitlines():
        line = raw_line.strip()
        if not line or not has_chinese(line):
            continue

        bucket = network if line.startswith("[网络]") else official
        line = line.replace("[网络]", "").strip()
        line = remove_pos_prefix(line)

        for part in SPLIT_DEF_RE.split(line):
            item = clean_def_part(part)
            if has_chinese(item):
                add_unique(bucket, item)

    defs = official or network
    return defs[:max_defs]


def parse_defs_en(definition: str, max_defs: int = 6) -> list[str]:
    out: list[str] = []
    for raw_line in normalize_multiline(definition).splitlines():
        line = raw_line.strip()
        if line:
            add_unique(out, line)
    return out[:max_defs]


def snapshot_word(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "word": item.get("word", ""),
        "phonetic": item.get("phonetic", ""),
        "pos": item.get("pos", ""),
        "defs_cn": list(item.get("defs_cn") or []),
        "defs_en": list(item.get("defs_en") or []),
    }


def apply_field_override(item: dict[str, Any]) -> bool:
    override = FIELD_OVERRIDES.get(str(item.get("id", "")))
    if not override:
        return False
    changed = False
    for key, value in override.items():
        if item.get(key) != value:
            item[key] = value
            changed = True
    return changed


def exact_match_is_suspicious(item: dict[str, Any], row: dict[str, str]) -> bool:
    word = str(item.get("word", ""))
    if len(strip_word(word)) > 4:
        return False

    current_chars = chinese_char_set(" ".join(str(part) for part in (item.get("defs_cn") or [])))
    if not current_chars:
        return False

    dict_chars = chinese_char_set(normalize_multiline(row.get("translation", "")))
    return len(current_chars & dict_chars) == 0


def find_dict_row(item: dict[str, Any], index: DictIndex) -> tuple[dict[str, str] | None, str, str | None]:
    word = str(item.get("word", ""))
    fixed_by_id = ID_WORD_FIXES.get(str(item.get("id", "")))
    if fixed_by_id and fixed_by_id.lower() in index.exact:
        return index.exact[fixed_by_id.lower()], "known_ocr_fix", fixed_by_id

    lowered = word.strip().lower()
    if lowered in index.exact:
        row = index.exact[lowered]
        if exact_match_is_suspicious(item, row):
            return None, "suspicious_exact", None
        return row, "exact", None

    sw = strip_word(word)
    if sw in index.stripped:
        return index.stripped[sw], "stripped", index.stripped[sw].get("word")

    return None, "unmatched", None


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def enrich_word(item: dict[str, Any], row: dict[str, str], match_type: str, replacement: str | None) -> dict[str, Any]:
    before = snapshot_word(item)

    dict_word = (row.get("word") or "").strip()
    if match_type in {"known_ocr_fix", "stripped"} and dict_word:
        item["word"] = dict_word

    phonetic = normalize_phonetic(row.get("phonetic", ""))
    if phonetic:
        item["phonetic"] = phonetic

    pos = normalize_pos(row)
    if pos:
        item["pos"] = pos

    defs_cn = parse_defs_cn(row.get("translation", ""))
    if defs_cn:
        item["defs_cn"] = defs_cn

    defs_en = parse_defs_en(row.get("definition", ""))
    if defs_en:
        item["defs_en"] = defs_en

    apply_field_override(item)
    after = snapshot_word(item)

    return {
        "id": item.get("id"),
        "match_type": match_type,
        "replacement": replacement,
        "before": before,
        "after": after,
    }


def override_word(item: dict[str, Any], match_type: str) -> dict[str, Any] | None:
    before = snapshot_word(item)
    if not apply_field_override(item):
        return None
    after = snapshot_word(item)
    return {
        "id": item.get("id"),
        "match_type": match_type,
        "replacement": None,
        "before": before,
        "after": after,
    }


def build_report(
    *,
    data: dict[str, Any],
    index: DictIndex,
    changes: list[dict[str, Any]],
    unmatched: list[dict[str, Any]],
    suspicious: list[dict[str, Any]],
    dry_run: bool,
) -> dict[str, Any]:
    word_fixes = [
        change
        for change in changes
        if change["before"]["word"] != change["after"]["word"]
    ]
    defs_changed = sum(change["before"]["defs_cn"] != change["after"]["defs_cn"] for change in changes)
    phonetic_changed = sum(change["before"]["phonetic"] != change["after"]["phonetic"] for change in changes)
    pos_changed = sum(change["before"]["pos"] != change["after"]["pos"] for change in changes)
    defs_en_added = sum(not change["before"]["defs_en"] and bool(change["after"]["defs_en"]) for change in changes)

    words = data.get("words", [])
    missing_phonetic = sum(1 for item in words if not item.get("phonetic"))
    missing_pos = sum(1 for item in words if not item.get("pos"))
    missing_defs = sum(1 for item in words if not item.get("defs_cn"))

    return {
        "dry_run": dry_run,
        "source": {
            "name": "ECDICT",
            "url": ECDICT_URL,
            "csv": str(ECDICT_PATH.relative_to(ROOT)).replace("\\", "/"),
            "license": "MIT",
            "rows_loaded": index.total_rows,
            "unique_words_loaded": len(index.exact),
        },
        "wordlist": {
            "path": str(WORDLIST_PATH.relative_to(ROOT)).replace("\\", "/"),
            "id": data.get("meta", {}).get("id"),
            "total": len(words),
        },
        "summary": {
            "matched": len(changes),
            "unmatched": len(unmatched),
            "suspicious_exact_skipped": len(suspicious),
            "word_fixed": len(word_fixes),
            "defs_cn_changed": defs_changed,
            "phonetic_changed": phonetic_changed,
            "pos_changed": pos_changed,
            "defs_en_added": defs_en_added,
            "missing_phonetic_after": missing_phonetic,
            "missing_pos_after": missing_pos,
            "missing_defs_cn_after": missing_defs,
        },
        "word_fixes": word_fixes,
        "unmatched": unmatched,
        "suspicious_exact": suspicious,
        "sample_changes": changes[:40],
    }


def validate_ids_unchanged(before: list[str], after: list[dict[str, Any]]) -> None:
    after_ids = [str(item.get("id", "")) for item in after]
    if before != after_ids:
        raise RuntimeError("Word ids changed. Aborting to protect existing user progress.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="build report without writing the word list")
    args = parser.parse_args()

    if not WORDLIST_PATH.exists():
        raise FileNotFoundError(WORDLIST_PATH)
    if not ECDICT_PATH.exists():
        raise FileNotFoundError(ECDICT_PATH)

    data = load_json(WORDLIST_PATH)
    words = data.get("words", [])
    original_ids = [str(item.get("id", "")) for item in words]

    index = load_ecdict(ECDICT_PATH)

    changes: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    suspicious: list[dict[str, Any]] = []

    for item in words:
        word = str(item.get("word", ""))
        row, match_type, replacement = find_dict_row(item, index)
        if row is None:
            override_change = override_word(item, match_type)
            if override_change:
                changes.append(override_change)
                continue

            bucket = suspicious if match_type == "suspicious_exact" else unmatched
            lowered = word.strip().lower()
            dict_translation = ""
            if lowered in index.exact:
                dict_translation = normalize_multiline(index.exact[lowered].get("translation", ""))
            bucket.append(
                {
                    "id": item.get("id"),
                    "word": word,
                    "defs_cn": item.get("defs_cn", []),
                    "reason": match_type,
                    "dictionary_translation": dict_translation,
                }
            )
            continue
        changes.append(enrich_word(item, row, match_type, replacement))

    validate_ids_unchanged(original_ids, words)

    if "meta" in data:
        data["meta"]["total"] = len(words)
        data["meta"]["version"] = "1.1.0"

    report = build_report(
        data=data,
        index=index,
        changes=changes,
        unmatched=unmatched,
        suspicious=suspicious,
        dry_run=args.dry_run,
    )

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    dump_json(REPORT_PATH, report)

    if not args.dry_run:
        if not BACKUP_PATH.exists():
            shutil.copy2(WORDLIST_PATH, BACKUP_PATH)
        dump_json(WORDLIST_PATH, data)

    summary = report["summary"]
    print(f"matched={summary['matched']}")
    print(f"unmatched={summary['unmatched']}")
    print(f"suspicious_exact_skipped={summary['suspicious_exact_skipped']}")
    print(f"word_fixed={summary['word_fixed']}")
    print(f"defs_cn_changed={summary['defs_cn_changed']}")
    print(f"phonetic_changed={summary['phonetic_changed']}")
    print(f"pos_changed={summary['pos_changed']}")
    print(f"missing_phonetic_after={summary['missing_phonetic_after']}")
    print(f"missing_pos_after={summary['missing_pos_after']}")
    print(f"report={REPORT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
