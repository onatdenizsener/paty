#!/usr/bin/env python3
"""src/i18n_src.txt -> src/i18n.js (window.PATY_I18N). Checks that every line has all six languages."""
import json, pathlib, sys
src = pathlib.Path(__file__).resolve().parent
words, pats, mode, bad = {}, [], None, []
for n, line in enumerate((src / 'i18n_src.txt').read_text(encoding='utf-8').splitlines(), 1):
    if not line.strip() or line.startswith('#'): continue
    if line.strip() == '[words]': mode = 'w'; continue
    if line.strip() == '[patterns]': mode = 'p'; continue
    parts = [p.strip() for p in line.split(' || ')]
    if len(parts) != 6: bad.append('%d: %d columns' % (n, len(parts))); continue
    if mode == 'w':
        if parts[0] in words: bad.append('%d: duplicate %r' % (n, parts[0]))
        words[parts[0]] = parts[1:]
    else: pats.append(parts)
if bad: sys.exit('i18n_src.txt errors:\n' + '\n'.join(bad))
(src / 'i18n.js').write_text('window.PATY_I18N=' + json.dumps({'words': words, 'pats': pats}, ensure_ascii=False, separators=(',', ':')) + ';\n', encoding='utf-8')
print('i18n.js:', len(words), 'phrases,', len(pats), 'patterns')
