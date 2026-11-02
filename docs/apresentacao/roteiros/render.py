import markdown, re, sys, asyncio
from playwright.async_api import async_playwright
CSS = """
@page { size: A4; margin: 18mm 20mm 17mm 22mm; }
body { font-family: 'Times New Roman', 'Liberation Serif', serif; font-size: 12pt; line-height: 1.4; color: #1b2733; }
.cab { border-bottom: 2px solid #102a43; padding-bottom: 8px; margin-bottom: 18px; }
.cab .inst { font-family: Arial, sans-serif; font-size: 9pt; letter-spacing: .04em; color: #5b6b7f; text-transform: uppercase; }
h1 { font-family: Arial, sans-serif; font-size: 20pt; color: #102a43; margin: 4px 0 2px; }
.cab .sub { font-family: Arial, sans-serif; font-size: 10pt; color: #5b6b7f; }
h2 { font-family: Arial, sans-serif; font-size: 14pt; color: #102a43; margin: 22px 0 8px; border-left: 4px solid #c8102e; padding-left: 8px; }
h3 { font-family: Arial, sans-serif; font-size: 11.5pt; color: #102a43; background: #eef2f6; padding: 4px 8px; margin: 16px 0 6px; break-after: avoid; }
p { margin: 0 0 8px; text-align: justify; }
em { color: #5b6b7f; }
p:has(em) { text-align: left; }
strong { color: #c8102e; }
h2 + p strong, li strong { color: inherit; }
table { border-collapse: collapse; width: 100%; font-size: 10pt; margin: 6px 0 12px; break-inside: auto; }
th { background: #102a43; color: #fff; font-family: Arial, sans-serif; text-align: left; padding: 3px 6px; }
td { border-bottom: 1px solid #cbd2d9; padding: 2px 6px; vertical-align: top; }
tr { break-inside: avoid; }
ul { padding-left: 4px; list-style: none; } li { margin: 3px 0; }
.quebra { break-before: page; }
"""
def conv(src, dur, out):
    t = open(src, encoding='utf8').read()
    linhas = t.split('\n')
    titulo = linhas[0].lstrip('# ').strip()
    corpo = '\n'.join(l for l in linhas[1:] if not re.match(r'^\w{3} \d+, \d{4} ·', l))
    corpo = re.sub(r'^- \[ \] ', '- ☐ ', corpo, flags=re.M)
    html = markdown.markdown(corpo, extensions=['tables'])
    pass
    doc = f"""<!doctype html><html lang="pt-PT"><head><meta charset="utf-8"><style>{CSS}</style></head><body>
<div class="cab"><div class="inst">Universidade Agostinho Neto · Faculdade de Engenharia</div><h1>{titulo}</h1>
<div class="sub">Manuel Gonga Muinga · Defesa da dissertação de mestrado · 15 de Dezembro de 2026</div></div>{html}</body></html>"""
    open(out.replace('.pdf', '.html'), 'w', encoding='utf8').write(doc)
    async def go():
        async with async_playwright() as p:
            b = await p.chromium.launch(); pg = await b.new_page()
            await pg.set_content(doc, wait_until='load')
            await pg.pdf(path=out, format='A4', prefer_css_page_size=True, display_header_footer=True,
                header_template='<span></span>',
                footer_template=f'<div style="font-family:Arial;font-size:8pt;color:#5b6b7f;width:100%;padding:0 20mm 0 22mm;display:flex;justify-content:space-between"><span>Roteiro da defesa – {dur} minutos</span><span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>')
            await b.close()
    asyncio.run(go())
conv('roteiro_20.md', 20, 'Roteiro_Defesa_20min.pdf')
conv('roteiro_15.md', 15, 'Roteiro_Defesa_15min.pdf')
