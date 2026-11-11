import sys, json
out = open(sys.argv[1], 'w', encoding='utf-8')
n = k = 0
for line in sys.stdin:
    n += 1
    if '"ko"' not in line and '"Korean"' not in line:
        continue
    try:
        e = json.loads(line)
    except Exception:
        continue
    if e.get('lang_code') != 'en':
        continue
    tr = []
    for t in e.get('translations', []) or []:
        if t.get('lang_code') == 'ko' or t.get('lang') == 'Korean':
            w = t.get('word') or ''
            if w:
                tr.append([w, t.get('sense') or '', t.get('roman') or ''])
    for s in e.get('senses', []) or []:
        for t in s.get('translations', []) or []:
            if t.get('lang_code') == 'ko' or t.get('lang') == 'Korean':
                w = t.get('word') or ''
                if w:
                    tr.append([w, t.get('sense') or (s.get('glosses') or [''])[0], t.get('roman') or ''])
    if not tr:
        continue
    snd = ''
    for s in e.get('sounds', []) or []:
        if s.get('ipa'):
            snd = s['ipa']; break
    out.write(json.dumps({'w': e.get('word'), 'p': e.get('pos'), 'ipa': snd, 'tr': tr,
                          'g': [(s.get('glosses') or [''])[0] for s in (e.get('senses') or [])][:3]}, ensure_ascii=False) + '\n')
    k += 1
print('lines', n, 'kept', k, file=sys.stderr)
