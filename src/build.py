#!/usr/bin/env python3
"""Builds the single-file game (index.html at the repo root) from src/: the page shell, the game script and the
Pixelify Sans font (SIL OFL, embedded as base64 so the game works offline and loads nothing from the internet).
Usage: python3 src/build.py"""
import base64, pathlib, re, subprocess, sys
src = pathlib.Path(__file__).resolve().parent
subprocess.run([sys.executable, str(src / 'build_i18n.py')], check=True)
root = src.parent
LATIN = 'U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD'
LATIN_EXT = 'U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,U+0308,U+0329,U+1D00-1DBF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF'
faces = []
for w in (400, 700):
    for sub, rng in (('latin', LATIN), ('latin-ext', LATIN_EXT)):
        b = base64.b64encode((src / 'fonts' / ('pixelify-sans-%s-%d-normal.woff2' % (sub, w))).read_bytes()).decode()
        faces.append("@font-face{font-family:'Pixelify Sans';font-style:normal;font-weight:%d;font-display:block;src:url(data:font/woff2;base64,%s) format('woff2');unicode-range:%s}" % (w, b, rng))
html = (src / 'index.src.html').read_text(encoding='utf-8')
game = (src / 'game.js').read_text(encoding='utf-8')
i18n = (src / 'i18n.js').read_text(encoding='utf-8')
html = html.replace('/*FONTFACE*/', ''.join(faces), 1).replace('/*GAME*/', game, 1).replace('<script src="i18n.js"></script>', '<script>' + i18n + '</script>', 1)
left = re.findall(r'(?:src|href)="(https?://[^"]+)"', html) + re.findall(r'url\((https?://[^)]+)\)', html)
if left: sys.exit('external resources referenced: %s' % left)
(root / 'index.html').write_text(html, encoding='utf-8')
print('index.html written,', len(html), 'bytes')
