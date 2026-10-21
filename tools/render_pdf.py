"""Renderiza todas as paginas dos PDFs de arte em PNG de alta resolucao.

Uso:
    python tools/render_pdf.py <pasta de saida> <arquivo.pdf> [<arquivo.pdf> ...]

Cada pagina vira <prefixo>-p<N>.png, com o prefixo tirado dos digitos do nome do PDF:
"Camiseta 01.pdf" -> c01-p1.png, c01-p2.png ...
"""
import re, sys
import pypdfium2 as pdfium

out = sys.argv[1]
for path in sys.argv[2:]:
    digits = re.findall(r'\d+', path.rsplit('/', 1)[-1])
    prefix = 'c' + (digits[-1] if digits else 'x')
    pdf = pdfium.PdfDocument(path)
    for i in range(len(pdf)):
        img = pdf[i].render(scale=4).to_pil()  # escala 4 = ~288 dpi numa pagina A4
        img.save(f'{out}/{prefix}-p{i + 1}.png')
        print(path, 'pagina', i + 1, img.size)
