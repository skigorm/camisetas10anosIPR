"""Gera as texturas de frente e costas usadas pelo visualizador 3D (viewer3d.js).

Uso:
    python tools/build_textures.py <pasta com as fotos> <pasta com as artes em PNG> <pasta de saida> [pasta de previews]

Exemplo (a partir da raiz do projeto):
    python tools/build_textures.py assets tools/art assets/3d

Passos, para cada camisa:
  1. recorta a camisa base (foto do mockup) do fundo liso;
  2. apaga a estampa da foto base, gerando uma camisa "em branco" com as dobras e sombras;
  3. monta as costas espelhando a frente e fechando a abertura da gola;
  4. tinge a base na cor da malha, quando a camisa nao for branca;
  5. aplica as artes vetoriais (paginas do PDF renderizadas) por cima, multiplicadas pela sombra do tecido.
A configuracao da campanha fica no bloco CAMPANHA, no fim do arquivo.
"""
import sys, numpy as np
from PIL import Image
from scipy import ndimage as nd

ASSETS, ART, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
PREVIEW = sys.argv[4] if len(sys.argv) > 4 else None
H_OUT = 1400

# Page-to-shirt mapping measured on the branca render: the A4 art page spans
# 51% of the shirt width, centred, starting 13% below the top of the collar.
PAGE_W, PAGE_TOP = 0.51, 0.13

def load_front(path):
    a = np.asarray(Image.open(path).convert('RGB')).astype(float)
    border = np.concatenate([a[:4].reshape(-1, 3), a[-4:].reshape(-1, 3), a[:, :4].reshape(-1, 3), a[:, -4:].reshape(-1, 3)])
    bg = np.median(border, 0)
    d = np.sqrt(((a - bg) ** 2).sum(2))
    alpha = np.clip((d - 18) / (46 - 18), 0, 1)
    solid = nd.binary_fill_holes(alpha > 0)
    lab, n = nd.label(solid)
    solid = lab == (np.bincount(lab.ravel())[1:].argmax() + 1)
    alpha = np.where(solid, np.maximum(alpha, nd.binary_erosion(solid, iterations=3)), 0)
    alpha = nd.gaussian_filter(nd.grey_erosion(alpha, size=3), 0.8)
    ys, xs = np.nonzero(alpha > 0.5)
    mx, my = int((xs.max() - xs.min()) * 0.02), int((ys.max() - ys.min()) * 0.02)
    x0, x1 = max(xs.min() - mx, 0), min(xs.max() + mx, a.shape[1])
    y0, y1 = max(ys.min() - my, 0), min(ys.max() + my, a.shape[0])
    # make the crop symmetric around the shirt centre so front and mirrored back align
    cx = (xs.min() + xs.max()) / 2
    half = max(cx - x0, x1 - cx)
    x0, x1 = int(cx - half), int(cx + half)
    pad = max(0, -x0), max(0, x1 - a.shape[1])
    a = np.pad(a, ((0, 0), pad, (0, 0)), mode='edge'); alpha = np.pad(alpha, ((0, 0), pad))
    x0 += pad[0]; x1 += pad[0]
    return a[y0:y1, x0:x1], alpha[y0:y1, x0:x1]

def norm_blur(img, w, s):
    num = nd.gaussian_filter(img * w[..., None], (s, s, 0))
    den = nd.gaussian_filter(w, s)[..., None]
    return num / np.maximum(den, 1e-6), den[..., 0]

def lum(a):
    return a @ np.array([.299, .587, .114])

def detect_print(a, alpha):
    inside = alpha > 0.5
    L = lum(a)
    Lb, _ = norm_blur(L[..., None], inside.astype(float), 25)
    chroma = a / (L[..., None] + 1)
    cd = np.sqrt(((chroma - np.median(chroma[inside], 0)) ** 2).sum(2))
    return inside & ((cd > 0.12) | (np.abs(L - Lb[..., 0]) > 22))

def remove_print(a, alpha, pr):
    inside = alpha > 0.5
    keep = (inside & ~pr).astype(float)
    out = a.copy()
    todo = pr & inside
    for s in (3, 8, 20, 50):
        f, den = norm_blur(a, keep, s)
        sel = todo & (den > 0.05)
        out[sel] = f[sel]
        todo &= ~sel
    # filled areas are too smooth next to the knit: add grain with the fabric's own amplitude
    hp = a - nd.gaussian_filter(a, (1.5, 1.5, 0))
    sd = hp[keep > 0].std(0)
    rng = np.random.default_rng(7)
    noise = nd.gaussian_filter(rng.standard_normal(a.shape[:2]), 0.7)[..., None]
    noise = noise / noise.std() * sd
    filled = (pr & inside)[..., None]
    return np.where(filled, out + noise, out)

def resized(arr, w, h):
    return np.asarray(Image.fromarray((arr * 255).astype(np.uint8)).resize((w, h), Image.LANCZOS)).astype(float) / 255

def register(a, alpha, aa, SW):
    """Find where the art page sits on the photo: (x, y, width) maximising overlap with the printed pixels."""
    from scipy.signal import fftconvolve
    k = 4
    D = detect_print(a, alpha)[::k, ::k].astype(float)
    D -= D[(alpha > 0.5)[::k, ::k]].mean()
    best = None
    for f in np.linspace(0.75, 1.3, 23):
        pw = int(PAGE_W * SW * f / k); ph = int(pw * aa.shape[0] / aa.shape[1])
        T = resized(aa, pw, ph)
        c = fftconvolve(np.pad(D, ((ph, ph), (pw, pw))), T[::-1, ::-1], mode='valid')
        # the print is centred on the chest: only allow horizontal offsets near the middle
        cols = np.arange(c.shape[1]); centre = cols - pw + pw / 2
        c[:, np.abs(centre - D.shape[1] / 2) > 0.03 * D.shape[1]] = -np.inf
        i = np.unravel_index(c.argmax(), c.shape)
        if best is None or c[i] > best[0]:
            best = (c[i], (i[1] - pw) * k, (i[0] - ph) * k, pw * k)
    return best[1:]

def page_art(path, ink=None):
    p = np.asarray(Image.open(path).convert('RGB')).astype(float)
    paper = np.median(np.concatenate([p[:8].reshape(-1, 3), p[-8:].reshape(-1, 3)]), 0)
    lim = np.where(p >= paper, 255.0, 0.0)
    need = np.abs(p - paper) / np.maximum(np.abs(lim - paper), 1)
    a = np.clip(need.max(2), 0, 1)
    col = paper + (p - paper) / np.maximum(a[..., None], 1e-3)
    if ink is not None:
        col = np.broadcast_to(np.array(ink, float), p.shape).copy()
    return np.clip(col, 0, 255), a

def apply_art(img, alpha, place, art_file, ink=None):
    h, w = alpha.shape
    L = lum(img)
    shade = np.clip(L / np.percentile(L[alpha > 0.5], 92), 0, 1.05)[..., None]
    col, aa = page_art(f'{ART}/{art_file}', ink)
    px, py, pw = place; ph = int(pw * aa.shape[0] / aa.shape[1])
    art = np.asarray(Image.fromarray(np.dstack([col, aa * 255]).astype(np.uint8)).resize((pw, ph), Image.LANCZOS)).astype(float)
    canvas = np.zeros((h, w, 4))
    ys, xs = slice(max(py, 0), min(py + ph, h)), slice(max(px, 0), min(px + pw, w))
    canvas[ys, xs] = art[ys.start - py:ys.stop - py, xs.start - px:xs.stop - px]
    aw = canvas[..., 3:] / 255 * (alpha[..., None] > 0.5)
    img[:] = img * (1 - aw) + canvas[..., :3] * shade * aw
    return canvas[..., 3] / 255

def shirt_box(alpha):
    ys, xs = np.nonzero(alpha > 0.5)
    return xs.min(), ys.min(), xs.max() - xs.min(), ys.max() - ys.min()

def locate(front_file, front_art):
    """Where each design sits on its own photo, as fractions of the shirt box."""
    a, alpha = load_front(f'{ASSETS}/{front_file}')
    sx0, sy0, SW, SH = shirt_box(alpha)
    _, fa = page_art(f'{ART}/{front_art}')
    px, py, pw = register(a, alpha, fa, SW)
    return (px - sx0) / SW, (py - sy0) / SH, pw / SW, a, alpha

# ---------------------------------------------------------------- CAMPANHA (base)
# Foto usada como camisa "em branco": escolha o mockup com a menor estampa, e a arte dessa estampa
BASE_PHOTO, BASE_ART = 'soli-frente.png', 'c02-p1.png'

fx, fy, fw, base, alpha = locate(BASE_PHOTO, BASE_ART)
h, w = alpha.shape
sx0, sy0, SW, SH = shirt_box(alpha)
_, fa = page_art(f'{ART}/{BASE_ART}')
pw = int(fw * SW); ph = int(pw * fa.shape[0] / fa.shape[1]); px = int(sx0 + fx * SW); py = int(sy0 + fy * SH)
canvas = np.zeros((h, w)); T = resized(fa, pw, ph)
canvas[py:py + ph, px:px + pw] = T[:h - py, :w - px][:canvas[py:py + ph, px:px + pw].shape[0], :canvas[py:py + ph, px:px + pw].shape[1]]
logo = nd.binary_dilation(canvas > 0.05, iterations=8) & (alpha > 0.5)
blank = remove_print(base, alpha, logo)
yy, xx = np.mgrid[0:h, 0:w]
ncx, nrx = sx0 + 0.5 * SW, 0.2 * SW
neck = (((xx - ncx) / nrx) ** 2 + ((yy - sy0) / (0.165 * SH)) ** 2 < 1) & (alpha > 0.5)
# back of the neck: continue the upper-back fabric just below the opening upwards
fill = blank.copy()
ry = 0.165 * SH
cols = np.arange(w); inside_cols = np.abs(cols - ncx) < nrx
yb = (sy0 + ry * np.sqrt(np.clip(1 - ((cols - ncx) / nrx) ** 2, 0, 1))).astype(int) + 6
src = nd.gaussian_filter1d(blank[np.minimum(yb, h - 1), cols], 6, axis=0)
rng = np.random.default_rng(3)
grain_sd = (blank - nd.gaussian_filter(blank, (1.5, 1.5, 0)))[alpha > 0.5].std(0)
for x in cols[inside_cols]:
    n = yb[x]
    fill[:n, x] = src[x] + rng.standard_normal((n, 1)) * grain_sd * 0.8
wn = nd.gaussian_filter(neck.astype(float), 8)[..., None] * (alpha[..., None] > 0.5)
blank_back = (blank * (1 - wn) + fill * wn)[:, ::-1].copy(); balpha = alpha[:, ::-1].copy()
top = np.argmax(balpha > 0.5, 0); rib = int(0.017 * SH)
bx = w - 1 - ncx
band = (np.abs(xx - bx) < nrx * 0.85) & (yy >= top[None, :]) & (yy < top[None, :] + rib)
seam = (np.abs(xx - bx) < nrx * 0.83) & (np.abs(yy - (top[None, :] + rib)) < 1.2)
blank_back[band] *= 0.95; blank_back[seam] *= 0.86

def tint(img, colour):
    if colour is None:
        return img.copy()
    L = lum(img)
    shade = L / np.percentile(L[alpha > 0.5], 92)
    return np.array(colour, float) * shade[..., None]

def build(front_file, front_art, art_file, name, colour=None, ink=None, back_place=None):
    fx, fy, fw = locate(front_file, front_art)[:3] if front_file != BASE_PHOTO else (globals()['fx'], globals()['fy'], globals()['fw'])
    pw = int(fw * SW); px = int(sx0 + fx * SW); py = int(sy0 + fy * SH)
    print(name, 'art fractions', round(fx, 3), round(fy, 3), round(fw, 3))
    front = tint(blank, colour); back = tint(blank_back, colour)
    apply_art(front, alpha, (px, py, pw), front_art)
    if back_place:
        bpw = int(back_place[2] * SW); bpx = int(sx0 + back_place[0] * SW); bpy = int(sy0 + back_place[1] * SH)
    else:
        bpw, bpx, bpy = pw, px, py
    apply_art(back, balpha, (w - bpx - bpw, bpy, bpw), art_file, ink)
    for img, al, side in ((front, alpha, 'frente'), (back, balpha, 'costas')):
        out = Image.fromarray(np.dstack([np.clip(img, 0, 255), al * 255]).astype(np.uint8))
        out = out.resize((round(w * H_OUT / h), H_OUT), Image.LANCZOS)
        out.save(f'{OUT}/{name}-{side}.webp', quality=90, method=6)
        if PREVIEW:
            out.save(f'{PREVIEW}/{name}-{side}.png')
    return fx, fy, fw

# ---------------------------------------------------------------- CAMPANHA (camisas)
# Cor da malha vinho: medida na propria foto do mockup vinho
va, valpha = load_front(f'{ASSETS}/vinho-frente.jpg')
VINHO = tuple(np.percentile(va[valpha > 0.5], 75, axis=0))
print('vinho fabric', VINHO)
# build(foto do mockup, arte da frente, arte das costas, nome de saida, colour=cor da malha, ink=cor unica para a arte das costas, back_place=posicao das costas)
branca_place = build('branca-frente.jpg', 'c03-p1.png', 'c03-p2.png', 'branca')
build('vinho-frente.jpg', 'c01-p1.png', 'c01-p2.png', 'vinho', colour=VINHO, ink=(244, 239, 230), back_place=branca_place)
build('soli-frente.png', 'c02-p1.png', 'c02-p4.png', 'soli')
