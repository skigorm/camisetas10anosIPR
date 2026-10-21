# Log do projeto — Camisetas 10 anos IPR

Registro do que foi feito no site de encomendas das camisetas comemorativas, com foco no visualizador 3D. A seção 3 serve de receita para outras campanhas.

- **Site:** https://camisetasipr.vercel.app
- **Repositório:** https://github.com/skigorm/camisetas10anosIPR (branch `main`)
- **Período:** outubro de 2026

---

## 1. Visão geral

Site estático, sem build: HTML, CSS e JS puros.

| Arquivo | Função |
|---|---|
| `index.html` | Página única: catálogo, tamanhos, carrinho, checkout com Pix e diálogos |
| `style.css` | Estilos (minificados em poucas linhas) |
| `app.js` | Catálogo (`models`), carrinho em `localStorage`, envio do pedido e visualizador de fotos |
| `viewer3d.js` | Visualizador 3D (módulo ES, carregado só quando alguém clica em "Ampliar foto") |
| `assets/3d/*.webp` | Texturas de frente e costas de cada camisa, usadas pelo 3D |
| `assets/SiteIPR.jpg` | Imagem do topo (gerada a partir do `SiteIPR.png`) |
| `tools/` | Scripts que geram as texturas 3D (não vão para o site, veja `.vercelignore`) |

### Rodar localmente

```bash
cd SiteCamisetas
python3 -m http.server 8000
# abrir http://localhost:8000 (Cmd+Shift+R para evitar a versão em cache)
```

### Publicação

O repositório está ligado à Vercel (projeto `camisetasipr`). **Todo push na `main` publica sozinho** em cerca de 1 minuto. O status aparece no commit do GitHub como "Vercel: success". Para conferir pelo terminal:

```bash
gh api repos/skigorm/camisetas10anosIPR/commits/main/status --jq '.statuses[] | {context, state, target_url}'
```

Na Vercel, o projeto usa Framework Preset **Other**, sem comando de build e sem pasta de saída.

### Pedidos → Google Forms

O site não grava direto numa planilha. O formulário do checkout (`#buyer-form`) faz POST para um **Google Forms** ("Camisas personalizadas - IPR 10 anos") por um iframe oculto. Cada campo do site corresponde a um `entry.<id>` do formulário:

- nome: `entry.678089650`, WhatsApp: `entry.1980537466`, observação: `entry.903378757`
- quantidades por modelo e tamanho: matriz `entries` no topo do `app.js` (3 modelos × 7 campos)

A planilha só recebe os pedidos se, no Google Forms, a aba **Respostas** estiver ligada ao Planilhas ("Vincular ao Planilhas").

**Para conferir os campos** depois de qualquer mudança no formulário: baixe a página `viewform` e procure cada id do `app.js`. Os 24 batiam em 20/10/2026.

```bash
curl -sL "https://docs.google.com/forms/d/e/<ID>/viewform" -o form.html
for id in $(grep -oE '[0-9]{8,10}' app.js | sort -u); do grep -q "\[\[$id," form.html || echo "faltando: $id"; done
```

---

## 2. Linha do tempo

1. **Rodar localmente** com `python3 -m http.server`.
2. **Publicação:** `git init`, primeiro commit e push para o repositório, que estava vazio. Depois, importação na Vercel pelo painel (feita pelo usuário).
3. **Verificação do Google Forms:** o formulário existe e aceita respostas, e os 24 `entry.*` batem.
4. **Primeira versão do "Ampliar foto":** a foto virava entre frente e costas, um cartão 2D girando com CSS 3D. Só funcionava para a Soli, a única com foto das costas.
5. **3D de verdade com as artes dos PDFs:** veja a seção 3. O usuário enviou `Camiseta 01/02/03.pdf` (na pasta Downloads) e pediu que a arte vetorial fosse usada também na frente, para ganhar definição.
6. **Zoom:** rodinha do mouse, pinça e botões − / +. Com zoom, arrastar na vertical percorre a camisa. A camisa também passou a abrir um pouco mais perto.
7. **Imagem de topo** trocada por `SiteIPR.png`, publicada como JPG de 133 KB (o PNG tinha 1,1 MB).

Commits: `a46eae8` (site inicial), `a4ffebc` (3D + zoom), `66ae384` (imagem de topo).

---

## 3. Visualizador 3D — como replicar

### 3.1 Ideia geral

Não existe um modelo 3D feito por designer. O 3D é montado no navegador a partir de **duas imagens por camisa** (frente e costas, PNG/WebP com fundo transparente):

1. o **contorno** (canal alfa) da imagem da frente define a silhueta;
2. dentro da silhueta, o volume é "inflado": a profundidade cresce com a distância até a borda, com bordas arredondadas e um leve abaulado no peito;
3. a textura da frente é aplicada na face da frente e a das costas na face de trás, que é espelhada;
4. uma camada interna plana fecha a costura lateral, onde frente e costas se encontram.

O resultado convence de frente, de costas e em ângulos intermediários. Bem de lado, a manga e a gola ficam simplificadas. Para o objetivo (ver a arte girando) foi aprovado como "perfeito".

As texturas são geradas **uma vez**, offline, por `tools/build_textures.py`. O navegador só carrega 6 arquivos WebP de 60 a 150 KB.

### 3.2 Insumos necessários

| Insumo | Requisitos | Nesta campanha |
|---|---|---|
| **Mockup de frente** de cada camisa | Vista frontal, **fundo liso** de uma cor, camisa inteira visível. Todos os mockups devem ser **o mesmo modelo 3D de camisa** (mesmo corte), como acontece quando o designer renderiza tudo no mesmo programa (CLO3D e similares). | `assets/branca-frente.jpg`, `vinho-frente.jpg`, `soli-frente.png` (1254 a 1600 px) |
| **PDF de arte** de cada camisa | Uma página por arte (frente, costas e separações). Páginas A4 na mesma escala da área de impressão. | `Camiseta 01.pdf` (vinho), `02` (Soli), `03` (branca) |
| Um mockup com estampa **pequena** | Serve de camisa "em branco" para todas: apagar uma estampa pequena não deixa marca. | `soli-frente.png` (só uma logo no peito) |

Páginas usadas de cada PDF:

| Camisa | PDF | Frente | Costas | Observação |
|---|---|---|---|---|
| Branca e vermelha | Camiseta 03 | p1 | p2 (logo IPR 10 anos) | p3 é separação em preto (ignorar) |
| Vinho | Camiseta 01 | p1 (fundo vinho) | p2 (logo IPR 10 anos) | logo das costas aplicada em **branco** (decisão nossa, veja a seção 5) |
| Soli Deo Gloria | Camiseta 02 | p1 | p4 (texto completo) | p2, p3, p5 e p6 são partes ou separações |

### 3.3 Passo a passo

```bash
# 0) ambiente Python isolado (uma vez)
python3 -m venv .venv && .venv/bin/pip install -r tools/requirements.txt

# 1) PDFs -> PNG em alta resolução (~288 dpi). "Camiseta 01.pdf" vira c01-p1.png, c01-p2.png...
mkdir -p tools/art
.venv/bin/python tools/render_pdf.py tools/art ~/Downloads/Camiseta*.pdf

# 2) editar o bloco CAMPANHA no fim de tools/build_textures.py (veja 3.4)

# 3) gerar as texturas (o 4º argumento opcional salva PNGs de prévia para conferir)
mkdir -p /tmp/previa
.venv/bin/python tools/build_textures.py assets tools/art assets/3d /tmp/previa

# 4) registrar cada camisa no app.js
#    views:['3d/<nome>-frente.webp','3d/<nome>-costas.webp']
```

O script imprime, para cada camisa, onde encontrou a arte na foto (`art fractions x y largura`, em frações da camisa). Confira as prévias antes de publicar: arte no lugar certo, sem sobras da estampa antiga e gola das costas limpa.

### 3.4 O que o `build_textures.py` faz (e onde ajustar)

1. **Recorte do fundo** (`load_front`): a cor do fundo é a mediana das bordas da imagem. A transparência é suave entre as distâncias de cor 18 e 46, só o maior objeto é mantido e a borda é erodida 1 px para não deixar halo. O recorte fica simétrico em volta da camisa, para a frente e as costas espelhadas se alinharem.
2. **Onde a arte está na foto** (`register`): compara a arte do PDF com os pixels "estampados" da foto (cor ou brilho fora do padrão do tecido). Testa 23 escalas e todas as posições via FFT, com o centro horizontal preso a ±3% do meio da camisa. Sem essa trava, uma arte pequena "gruda" no lugar errado.
3. **Camisa em branco** (`remove_print`): apaga a estampa da foto base (área da arte dilatada 8 px), preenche com o tecido ao redor (borrões normalizados em 4 escalas) e devolve a granulação da malha com ruído da mesma intensidade.
4. **Costas**: espelha a camisa em branco. Preenche a abertura da gola (elipse centrada, raio de 20% da largura e 16,5% da altura) puxando o tecido **de baixo para cima**. Desenha uma faixa de gola (ribana) com costura no topo.
5. **Tingimento** (`tint`): para camisas coloridas, cor da malha × sombra da camisa branca (luminância ÷ percentil 92). A cor vinho foi medida no próprio mockup vinho (percentil 75: RGB 131, 66, 66).
6. **Aplicação da arte** (`apply_art`): "color-to-alpha" contra a cor do papel da página (branco, ou vinho na Camiseta 01). Isso funciona para arte em fundo colorido e preserva tons intermediários. A arte é multiplicada pela sombra do tecido para seguir as dobras.
   - Posição da **frente**: a encontrada no passo 2, para a respectiva foto.
   - Posição das **costas**: a mesma da frente, espelhada. Exceção: na vinho foi usada a posição da branca (`back_place`), porque a página 1 da vinho tem outro enquadramento e a logo ficava grande e alta demais.
7. Saída em **WebP com transparência**, 1400 px de altura, qualidade 90.

Constantes que valem a pena conhecer:

- `PAGE_W = 0.51`, `PAGE_TOP = 0.13`: largura da página A4 ≈ 51% da largura da camisa, começando 13% abaixo do topo da gola. São só o ponto de partida da busca; o passo 2 refina.
- `H_OUT = 1400`: altura das texturas.
- Gola: `0.5 * SW`, `0.2 * SW`, `0.165 * SH`. Ajuste se o modelo de camisa mudar.

### 3.5 O que o `viewer3d.js` faz (e onde ajustar)

- Usa **Three.js 0.170.0** via jsDelivr, carregado só ao clicar em "Ampliar foto".
- Malha: grade de 220 vértices na altura (`GRID`). Profundidade de 10% da altura (`DEPTH`), arredondamento nos 9% perto da borda (`EDGE`).
  - O volume só começa onde a textura é **totalmente opaca** (alfa > 235) e 1,5 célula para dentro da borda. Isso evita furos na costura lateral.
  - A distância até a borda é suavizada em 3 passadas, para o contorno não ficar serrilhado de lado.
  - A malha passa 2 células além do contorno; o recorte exato vem da transparência da textura (`alphaTest` + `alphaToCoverage`).
- Material: `MeshLambertMaterial` com `emissiveMap` = a própria textura (62%). As fotos já trazem a sombra do tecido, então as luzes só acrescentam o sombreamento que muda ao girar.
- Controles:
  - arrastar na horizontal gira, com inércia;
  - tocar ou clicar vira de lado;
  - botões Frente/Costas;
  - giro automático lento até a primeira interação;
  - zoom de 1× a 3,2× (abre em 1,18×) pela rodinha, pinça ou botões − / +;
  - com zoom, arrastar na vertical percorre a camisa.
- Sem WebGL: `app.js` mantém o modo antigo (cartão 2D virando entre as duas texturas).
- No celular, o canvas usa `touch-action: none`. Sobre a camisa, o dedo controla o 3D em vez de rolar a página.

### 3.6 O que não funcionou (para não repetir)

- **Apagar uma estampa grande da própria foto** (branca com círculos vermelhos, vinho com círculos dourados) deixou fantasmas e manchas: o tecido acompanha as dobras e a estampa da foto não bate com a arte plana. Solução: usar **uma única camisa base com estampa pequena** e tingir.
- **Detectar a estampa pela cor** na malha vinho confundia a trama e as sombras das dobras com estampa. Detectar só serve para *localizar* a arte, nunca como máscara de remoção.
- **Registro livre** de uma arte pequena (logo da Soli) achou outro lugar. A trava de centro horizontal resolveu.
- **Preencher a gola das costas com o entorno** deixou um "U" escuro, porque puxava a sombra da gola. O certo é puxar o tecido de baixo.
- **Volume começando antes da borda opaca** abriu furos brancos na lateral.
- **Recorte de mockups lado a lado** (frente e costas na mesma foto): meça os limites das colunas antes, senão entra a ponta da manga da outra camisa.

---

## 4. Checklist para uma nova campanha

1. Pedir ao designer:
   - **mockup de frente de cada camisa no mesmo modelo 3D**, com fundo liso;
   - **PDF das artes** (frente e costas por página);
   - a **cor de impressão das costas**, se o PDF trouxer a logo em cinza ou neutra.
2. Atualizar `models` no `app.js`: nome, foto do catálogo e `views`.
3. Recriar o Google Forms e atualizar a URL do `action` no `index.html`, os `entry.*` e a matriz `entries`. Conferir com o comando da seção 1.
4. Gerar as texturas (seção 3.3) e conferir as prévias.
5. Trocar a imagem de topo. Para fotos, publicar em JPG (~85% de qualidade).
6. Atualizar a chave Pix e o favorecido no `index.html`, os prazos e o preço (65 no `app.js`).
7. Testar local e fazer push. A Vercel publica.

---

## 5. Decisões em aberto e pendências

- **Logo das costas da vinho em branco:** o PDF traz a logo em cinza, que quase não aparece no vinho. Confirmar com a gráfica. Para trocar, mude `ink=(244, 239, 230)` na chamada da vinho e gere de novo.
- **Logo das costas da branca em cinza escuro**, como no PDF. Pode ser vermelha, como a frente. Para trocar, passe `ink=` na chamada da branca.
- **`assets/glb/`** (`camiseta_0X_360.glb`): apareceu na pasta durante o trabalho, não foi criada neste processo e **não é usada pelo site**. Entrou no commit `a4ffebc` a pedido ("comita tudo").
- Os PDFs originais estão só em `~/Downloads`. Para ser possível reproduzir as texturas depois, vale guardar uma cópia num lugar fixo (por exemplo, `tools/art-src/`).
- `assets/banner-colecao.png` (imagem antiga do topo) não é mais usada.
