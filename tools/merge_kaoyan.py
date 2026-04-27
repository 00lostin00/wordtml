import json

def load_jsonl(path):
    rows = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows

def convert(entry, new_id, band):
    hw = entry.get('headWord', '')
    c = entry.get('content', {}).get('word', {}).get('content', {})

    phone = c.get('usphone') or c.get('phone', '')
    phonetic = '/' + phone + '/' if phone else ''

    trans = c.get('trans', [])
    pos_parts = []
    for t in trans:
        p = t.get('pos', '')
        label = p + '.'
        if p and label not in pos_parts:
            pos_parts.append(label)
    pos = '/'.join(pos_parts)

    defs_cn = [t['tranCn'] for t in trans if t.get('tranCn')]

    sents = c.get('sentence', {}).get('sentences', [])
    examples = [
        {'en': s['sContent'], 'cn': s['sCn']}
        for s in sents[:2]
        if s.get('sContent') and s.get('sCn')
    ]

    return {
        'id': 'kaoyan-' + str(new_id).zfill(4),
        'word': hw,
        'phonetic': phonetic,
        'pos': pos,
        'defs_cn': defs_cn,
        'examples': examples,
        'band': band,
    }

d1 = load_jsonl('KY_eg/1521164669833_KaoYan_1/KaoYan_1.json')
d2 = load_jsonl('KY_eg/1521164654696_KaoYan_2 (1)/KaoYan_2.json')

seen = {}
for e in d1:
    hw = e['headWord'].lower()
    if hw not in seen:
        seen[hw] = ('1', e)
for e in d2:
    hw = e['headWord'].lower()
    if hw not in seen:
        seen[hw] = ('2', e)

from_1 = sorted(
    [(e['wordRank'], e) for src, e in seen.values() if src == '1'],
    key=lambda x: x[0]
)
from_2 = sorted(
    [(e['wordRank'], e) for src, e in seen.values() if src == '2'],
    key=lambda x: x[0]
)

total_1 = len(from_1)
total_2 = len(from_2)
total = total_1 + total_2

words = []
idx = 1

for rank, e in from_1:
    if rank <= total_1 * 0.4:
        band = 1
    elif rank <= total_1 * 0.75:
        band = 2
    else:
        band = 3
    words.append(convert(e, idx, band))
    idx += 1

for rank, e in from_2:
    if rank <= total_2 * 0.3:
        band = 2
    else:
        band = 3
    words.append(convert(e, idx, band))
    idx += 1

output = {
    'meta': {
        'id': 'kaoyan',
        'name': '考研英语核心词汇',
        'lang': 'en',
        'target': 'zh-CN',
        'total': total,
        'bands': 3,
        'version': '2.0.0',
    },
    'words': words,
}

with open('data/wordlists/kaoyan.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

b1 = sum(1 for w in words if w['band'] == 1)
b2 = sum(1 for w in words if w['band'] == 2)
b3 = sum(1 for w in words if w['band'] == 3)
print('KaoYan_1:', total_1, 'KaoYan_2新增:', total_2, '合计:', total)
print('Band1:', b1, 'Band2:', b2, 'Band3:', b3)
for w in words[:3]:
    print(w['id'], w['word'], w['phonetic'], w['defs_cn'][:1])
