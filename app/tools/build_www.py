#!/usr/bin/env python3
"""Builds app/www/index.html from the single-file game (../index.html, built by src/build.py with the font embedded)
and loads ads-config.js, ads.js, native-bridge.js and flix-privacy.js before the game. Fails if anything external is referenced."""
import re, sys, pathlib
app = pathlib.Path(__file__).resolve().parent.parent
src = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else app.parent / 'index.html'
s = src.read_text(encoding='utf-8')
tags = '<script src="ads-config.js"></script>\n<script src="ads.js"></script>\n<script src="native-bridge.js"></script>\n<script src="flix-privacy.js"></script>\n'
if '</head>' not in s: sys.exit('no </head> in game file')
s = s.replace('</head>', tags + '</head>', 1)
left = re.findall(r'(?:src|href)="(https?://[^"]+)"', s) + re.findall(r'url\((https?://[^)]+)\)', s)
if left: sys.exit('external resources still referenced: %s' % left)
(app / 'www' / 'index.html').write_text(s, encoding='utf-8')
print('www/index.html written from', src.name, len(s), 'bytes')
