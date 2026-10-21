import sys, zipfile, re, shutil
src = sys.argv[1]; tmp = src + '.tmp'
# diapositivos que iniciam secção recebem "push"; os restantes "fade"
inicio = {1, 3, 5, 6, 9, 13, 15, 17}
zin = zipfile.ZipFile(src); zout = zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED)
for it in zin.infolist():
    data = zin.read(it.filename)
    m = re.fullmatch(r'ppt/slides/slide(\d+)\.xml', it.filename)
    if m:
        n = int(m.group(1)); x = data.decode('utf8')
        x = re.sub(r'<p:transition.*?</p:transition>', '', x, flags=re.S)
        efeito = '<p:push dir="u"/>' if n in inicio else '<p:fade/>'
        tr = f'<p:transition spd="med">{efeito}</p:transition>'
        assert '</p:clrMapOvr>' in x, n
        x = x.replace('</p:clrMapOvr>', '</p:clrMapOvr>' + tr, 1)
        data = x.encode('utf8')
    zout.writestr(it, data)
zout.close(); shutil.move(tmp, src); print('transições ok')
