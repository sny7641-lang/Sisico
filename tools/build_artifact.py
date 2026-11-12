#!/usr/bin/env python3
"""Make the Claude artifact version of the app from www/index.html.

The Artifact tool wraps the page in its own <html>/<head>/<body>, so this strips ours, drops the pieces
that only make sense in the installed app (manifest, service worker, API-key Claude module) and writes
artifact/index.html. Publish it with decks.js, words.js, examples-daily.js and dictionary.js as files.
"""
import os, re
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
s = open(os.path.join(ROOT, 'www', 'index.html'), encoding='utf-8').read()

head = s[s.index('<head>') + 6:s.index('</head>')]
body = s[s.index('<body>') + 6:s.index('</body>')]
title = re.search(r'<title>.*?</title>', head, re.S).group(0)
fonts = ''.join(re.findall(r'<link rel="(?:preconnect|stylesheet)"[^>]*>\n?', head))
style = re.search(r'<style>.*?</style>', head, re.S).group(0)

body = body.replace('<script src="claude-lookup.js"></script>\n', '')
body = re.sub(r'<script>\s*if \("serviceWorker" in navigator.*?</script>', '', body, flags=re.S)
# The API-key settings are not needed here: the artifact asks Claude on the viewer's own plan
body = re.sub(r'<details id="claude-settings">.*?</details>\s*', '<details id="claude-settings" hidden><input id="ck-key"><select id="ck-model"><option value="claude-opus-5-5"></option></select><button id="ck-save"></button><button id="ck-clear"></button><span id="ck-status"></span></details>\n', body, count=1, flags=re.S)
assert 'claude-lookup.js' not in body and 'serviceWorker' not in body

out = title + '\n<meta name="claude:viewport-fit-sides" content="cover">\n' + fonts + style + '\n' + body.strip() + '\n'
os.makedirs(os.path.join(ROOT, 'artifact'), exist_ok=True)
open(os.path.join(ROOT, 'artifact', 'index.html'), 'w', encoding='utf-8').write(out)
print('artifact/index.html', len(out.encode()) // 1024, 'KB')
