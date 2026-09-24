"""Ingresso personalizado do Creator Day Experience.

Monta em PNG, com o nome de quem comprou e o código do pedido, seguindo a arte
do evento: frente clara com foto, logo e dados; verso azul-marinho com o que a
pessoa vai viver. Fontes e imagens moram em studio/assets (nada vem da internet).
"""
from __future__ import annotations

import io
from datetime import date
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ASSETS = Path(__file__).resolve().parent / "assets"
FONTES = ASSETS / "fontes"
IMAGENS = ASSETS / "ingresso"

# ---------------------------------------------------------------- identidade
FUNDO = (219, 232, 248)
PAPEL = (241, 248, 254)
BRANCO = (255, 255, 255)
NAVY = (26, 60, 118)
NAVY_ESCURO = (21, 48, 96)
AZUL = (37, 99, 209)
TINTA = (23, 47, 92)
TINTA_SUAVE = (86, 114, 158)
LINHA = (198, 216, 240)
CLARO = (226, 236, 250)

EVENTO_DATA = date(2026, 10, 17)
DIAS = ("SEGUNDA", "TERÇA", "QUARTA", "QUINTA", "SEXTA", "SÁBADO", "DOMINGO")
MESES = ("JAN", "FEV", "MAR", "ABR", "MAI", "JUN", "JUL", "AGO", "SET", "OUT", "NOV", "DEZ")
DATA_CURTA = f"{EVENTO_DATA.day} {MESES[EVENTO_DATA.month - 1]} {EVENTO_DATA.year}"
DIA_SEMANA = DIAS[EVENTO_DATA.weekday()]

LARGURA, ALTURA = 1440, 1660
MARGEM, GAP = 70, 60
T_LARG, T_ALT = 620, 1500
RAIO = 34


@lru_cache(maxsize=32)
def _fonte(nome: str, tamanho: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTES / nome), tamanho)


def regular(t): return _fonte("Poppins-Regular.ttf", t)
def media(t): return _fonte("Poppins-Medium.ttf", t)
def semi(t): return _fonte("Poppins-SemiBold.ttf", t)
def negrito(t): return _fonte("Poppins-Bold.ttf", t)
def manuscrita(t): return _fonte("DancingScript.ttf", t)


@lru_cache(maxsize=8)
def _imagem(nome: str) -> Image.Image:
    return Image.open(IMAGENS / nome).convert("RGB")


def _largura_espacada(desenho, texto, fonte, espaco) -> int:
    return sum(desenho.textlength(ch, font=fonte) + espaco for ch in texto) - espaco if texto else 0


def _texto_espacado(desenho, xy, texto, fonte, cor, espaco=3.0, centro=False):
    """Escreve com espaço entre letras (o caixa-alta da arte é bem espaçado)."""
    x, y = xy
    if centro:
        x -= _largura_espacada(desenho, texto, fonte, espaco) / 2
    for ch in texto:
        desenho.text((x, y), ch, font=fonte, fill=cor)
        x += desenho.textlength(ch, font=fonte) + espaco
    return x


def _linhas(desenho, texto, fonte, largura_max):
    linhas, atual = [], ""
    for palavra in texto.split():
        teste = f"{atual} {palavra}".strip()
        if desenho.textlength(teste, font=fonte) <= largura_max or not atual:
            atual = teste
        else:
            linhas.append(atual)
            atual = palavra
    if atual:
        linhas.append(atual)
    return linhas


def _paragrafo(desenho, xy, texto, fonte, cor, largura_max, altura_linha, centro=True):
    x, y = xy
    for linha in _linhas(desenho, texto, fonte, largura_max):
        largura = desenho.textlength(linha, font=fonte)
        desenho.text((x - largura / 2 if centro else x, y), linha, font=fonte, fill=cor)
        y += altura_linha
    return y


def _mascara_ingresso(tamanho) -> Image.Image:
    """Formato do ingresso: cantos arredondados e o corte no topo, como na arte."""
    largura, altura = tamanho
    mascara = Image.new("L", tamanho, 0)
    d = ImageDraw.Draw(mascara)
    d.rounded_rectangle((0, 0, largura - 1, altura - 1), radius=RAIO, fill=255)
    corte_l, corte_a = 150, 40
    x0 = (largura - corte_l) / 2
    d.rounded_rectangle((x0, -corte_a, x0 + corte_l, corte_a), radius=22, fill=0)
    return mascara


def _cantos(desenho, caixa, cor, tamanho=34, espessura=4, cantos=("ne", "no", "se", "so")):
    """Cantos de visor de câmera, o detalhe do logo do evento."""
    x0, y0, x1, y1 = caixa
    if "no" in cantos:
        desenho.line([(x0, y0 + tamanho), (x0, y0), (x0 + tamanho, y0)], fill=cor, width=espessura)
    if "ne" in cantos:
        desenho.line([(x1 - tamanho, y0), (x1, y0), (x1, y0 + tamanho)], fill=cor, width=espessura)
    if "so" in cantos:
        desenho.line([(x0, y1 - tamanho), (x0, y1), (x0 + tamanho, y1)], fill=cor, width=espessura)
    if "se" in cantos:
        desenho.line([(x1 - tamanho, y1), (x1, y1), (x1, y1 - tamanho)], fill=cor, width=espessura)


def _logo(largura: int, claro: bool = False) -> Image.Image:
    """Logo do evento. `claro=True` devolve a versão branca, para o fundo azul."""
    logo = _imagem("logo.png")
    altura = round(logo.height * largura / logo.width)
    logo = logo.resize((largura, altura), Image.LANCZOS)
    cinza = logo.convert("L")
    if not claro:
        alfa = cinza.point(lambda v: 255 if v < 230 else 0)
        return Image.merge("RGBA", (*logo.split(), alfa))
    branco = Image.new("RGB", logo.size, BRANCO)
    alfa = cinza.point(lambda v: 255 if v < 230 else 0)
    return Image.merge("RGBA", (*branco.split(), alfa))


def _foto(nome: str, tamanho) -> Image.Image:
    """Corta a foto no tamanho pedido, sem distorcer."""
    foto = _imagem(nome)
    larg, alt = tamanho
    escala = max(larg / foto.width, alt / foto.height)
    foto = foto.resize((round(foto.width * escala), round(foto.height * escala)), Image.LANCZOS)
    esquerda = (foto.width - larg) // 2
    topo = (foto.height - alt) // 2
    return foto.crop((esquerda, topo, esquerda + larg, topo + alt))


# ---------------------------------------------------------------- ícones
def _clareia_topo(ingresso: Image.Image, foto_alt: int, altura: int = 230) -> None:
    """Clareia o topo da foto, para o texto azul-marinho ficar legível."""
    veu = Image.new("L", (1, altura))
    for y in range(altura):
        veu.putpixel((0, y), int(235 * (1 - (y / altura) ** 1.6)))
    veu = veu.resize((ingresso.width, altura))
    claro = Image.new("RGB", (ingresso.width, altura), PAPEL)
    ingresso.paste(claro, (0, 0), veu)


def _icone_calendario(d, x, y, cor, t=26):
    d.rounded_rectangle((x, y + 4, x + t, y + t + 2), radius=5, outline=cor, width=3)
    d.line([(x + 7, y), (x + 7, y + 8)], fill=cor, width=3)
    d.line([(x + t - 7, y), (x + t - 7, y + 8)], fill=cor, width=3)
    d.line([(x, y + 13), (x + t, y + 13)], fill=cor, width=3)


def _icone_local(d, x, y, cor, t=26):
    d.ellipse((x + 2, y, x + t - 2, y + t - 4), outline=cor, width=3)
    d.polygon([(x + t / 2 - 7, y + t - 10), (x + t / 2 + 7, y + t - 10), (x + t / 2, y + t + 4)], fill=cor)
    d.ellipse((x + t / 2 - 5, y + t / 2 - 7, x + t / 2 + 5, y + t / 2 + 3), fill=None, outline=cor, width=3)


def _icone_folha(d, x, y, cor, t=26):
    d.arc((x, y, x + t, y + t), start=180, end=320, fill=cor, width=3)
    d.arc((x, y, x + t, y + t), start=40, end=180, fill=cor, width=3)
    d.line([(x + 4, y + t - 2), (x + t - 4, y + 4)], fill=cor, width=3)


def _icone_brilho(d, x, y, cor, t=30):
    cx, cy, r = x + t / 2, y + t / 2, t / 2
    d.polygon([(cx, cy - r), (cx + r * 0.28, cy - r * 0.28), (cx + r, cy), (cx + r * 0.28, cy + r * 0.28),
               (cx, cy + r), (cx - r * 0.28, cy + r * 0.28), (cx - r, cy), (cx - r * 0.28, cy - r * 0.28)], fill=cor)


def _icone_pessoas(d, x, y, cor, t=30):
    # duas pessoas: cabeça e ombros, uma um pouco atrás
    d.ellipse((x + 2, y + 5, x + 13, y + 16), outline=cor, width=3)
    d.arc((x - 3, y + 17, x + 18, y + 36), start=195, end=345, fill=cor, width=3)
    d.ellipse((x + t - 15, y + 1, x + t - 2, y + 14), outline=cor, width=3)
    d.arc((x + t - 20, y + 15, x + t + 2, y + 35), start=195, end=345, fill=cor, width=3)


def _icone_camera(d, x, y, cor, t=30):
    d.rounded_rectangle((x, y + 6, x + t, y + t - 2), radius=6, outline=cor, width=3)
    d.line([(x + 9, y + 6), (x + 12, y + 1)], fill=cor, width=3)
    d.line([(x + t - 9, y + 6), (x + t - 12, y + 1)], fill=cor, width=3)
    d.ellipse((x + t / 2 - 7, y + 10, x + t / 2 + 7, y + 24), outline=cor, width=3)


def _icone_coracao(d, x, y, cor, t=30):
    import math
    pontos = []
    for i in range(61):
        a = 2 * math.pi * i / 60
        px = 16 * math.sin(a) ** 3
        py = 13 * math.cos(a) - 5 * math.cos(2 * a) - 2 * math.cos(3 * a) - math.cos(4 * a)
        pontos.append((x + t / 2 + px * t / 34, y + t / 2 - py * t / 34))
    d.line(pontos + [pontos[0]], fill=cor, width=3, joint="curve")


# ---------------------------------------------------------------- frente e verso
def _frente(nome: str, codigo: str) -> Image.Image:
    ingresso = Image.new("RGB", (T_LARG, T_ALT), PAPEL)
    foto_alt = 520
    ingresso.paste(_foto("foto-frente.jpg", (T_LARG, foto_alt)), (0, 0))
    _clareia_topo(ingresso, foto_alt)
    d = ImageDraw.Draw(ingresso)

    # etiquetas sobre a foto
    y = 74
    for palavra in ("SKINCARE", "CONEXÕES", "CONTEÚDO", "EXPERIÊNCIAS"):
        _texto_espacado(d, (52, y), palavra, semi(15), NAVY, 3.4)
        y += 27
    for i, texto in enumerate(("SALVADOR, BA", DATA_CURTA)):
        largura = _largura_espacada(d, texto, semi(16), 3.4)
        _texto_espacado(d, (T_LARG - 52 - largura, 80 + i * 30), texto, semi(16), NAVY, 3.4)

    # logo com os cantos, na parte clara
    logo = _logo(340)
    lx, ly = (T_LARG - logo.width) // 2, foto_alt + 62
    ingresso.paste(logo, (lx, ly), logo)
    _cantos(d, (lx - 40, ly - 30, lx + logo.width + 40, ly + logo.height + 26), AZUL, 30, 4)

    # frase
    y = ly + logo.height + 76
    y = _paragrafo(d, (T_LARG / 2, y), "Uma tarde para viver experiências, desacelerar, conectar e fazer networking.",
                   regular(24), TINTA, T_LARG - 120, 38)

    d.line([(60, y + 30), (T_LARG - 60, y + 30)], fill=LINHA, width=2)

    # nome de quem comprou
    y += 78
    nome = " ".join(nome.split()).upper()
    fonte_nome = negrito(40)
    while _largura_espacada(d, nome, fonte_nome, 2.5) > T_LARG - 90 and fonte_nome.size > 22:
        fonte_nome = negrito(fonte_nome.size - 2)
    _texto_espacado(d, (T_LARG / 2, y), nome, fonte_nome, NAVY, 2.5, centro=True)
    _texto_espacado(d, (T_LARG / 2, y + fonte_nome.size + 16), "PARTICIPANTE CONFIRMADA", semi(17), TINTA_SUAVE, 5.0, centro=True)

    # três colunas com ícones
    y += fonte_nome.size + 80
    colunas = (
        (_icone_calendario, (f"{DATA_CURTA}", DIA_SEMANA)),
        (_icone_local, ("SALVADOR, BA", "LOCAL EM BREVE")),
        (_icone_folha, ("SKINCARE", "CONTEÚDO", "CONEXÕES", "EXPERIÊNCIAS")),
    )
    largura_col = (T_LARG - 100) / 3
    for i, (icone, linhas) in enumerate(colunas):
        cx = 50 + largura_col * (i + 0.5)
        icone(d, cx - 13, y, NAVY)
        ty = y + 48
        for linha in linhas:
            _texto_espacado(d, (cx, ty), linha, semi(13), NAVY, 2.4, centro=True)
            ty += 22
        if i:
            d.line([(50 + largura_col * i, y - 6), (50 + largura_col * i, y + 118)], fill=LINHA, width=2)

    # código do pedido
    y += 178
    largura_codigo = _largura_espacada(d, codigo, semi(24), 5.0)
    d.rounded_rectangle(((T_LARG - largura_codigo - 80) / 2, y, (T_LARG + largura_codigo + 80) / 2, y + 62), radius=10, fill=CLARO)
    _texto_espacado(d, (T_LARG / 2, y + 16), codigo, semi(24), NAVY, 5.0, centro=True)

    # rodapé
    _texto_espacado(d, (T_LARG / 2, T_ALT - 96), "MAIS DO QUE UM EVENTO,", media(14), TINTA_SUAVE, 3.2, centro=True)
    _texto_espacado(d, (T_LARG / 2, T_ALT - 70), "UMA COMUNIDADE EM MOVIMENTO.", media(14), TINTA_SUAVE, 3.2, centro=True)
    return ingresso


def _verso() -> Image.Image:
    ingresso = Image.new("RGB", (T_LARG, T_ALT), NAVY)
    foto_alt = 470
    ingresso.paste(_foto("foto-verso.jpg", (T_LARG, foto_alt)), (0, T_ALT - foto_alt))
    d = ImageDraw.Draw(ingresso)

    y = 96
    for palavra in ("CREATORS", "BEAUTY", "REAL CONNECTIONS"):
        _texto_espacado(d, (52, y), palavra, semi(15), BRANCO, 3.4)
        y += 27
    for i, texto in enumerate(("SALVADOR, BA", DATA_CURTA)):
        largura = _largura_espacada(d, texto, semi(16), 3.4)
        _texto_espacado(d, (T_LARG - 52 - largura, 112 + i * 30), texto, semi(16), BRANCO, 3.4)

    logo = _logo(340, claro=True)
    lx, ly = (T_LARG - logo.width) // 2, 236
    ingresso.paste(logo, (lx, ly), logo)
    _cantos(d, (lx - 40, ly - 30, lx + logo.width + 40, ly + logo.height + 26), BRANCO, 30, 4)

    y = ly + logo.height + 86
    _texto_espacado(d, (T_LARG / 2, y), "VOCÊ FAZ PARTE", regular(28), BRANCO, 5.0, centro=True)
    _texto_espacado(d, (T_LARG / 2, y + 44), "DESSA EXPERIÊNCIA.", semi(28), BRANCO, 5.0, centro=True)

    y += 118
    itens = (
        (_icone_brilho, ("VIVA NOVAS", "EXPERIÊNCIAS")),
        (_icone_pessoas, ("CONECTE-SE", "COM OUTROS CREATORS")),
        (_icone_camera, ("CRIE CONTEÚDO", "DE FORMA REAL")),
        (_icone_coracao, ("FAÇA PARTE DE UMA", "COMUNIDADE QUE ACREDITA", "NO DESACELERAR")),
    )
    for icone, linhas in itens:
        icone(d, 64, y + 4, BRANCO)
        ty = y
        for linha in linhas:
            _texto_espacado(d, (140, ty), linha, media(16), BRANCO, 3.0)
            ty += 26
        y = max(ty + 26, y + 78)

    d.line([(64, y), (T_LARG - 64, y)], fill=(90, 122, 176), width=2)
    d.text((T_LARG / 2, y + 30), "Juntas,", font=manuscrita(46), fill=BRANCO, anchor="mm")
    d.text((T_LARG / 2, y + 86), "vamos mais longe.", font=manuscrita(46), fill=BRANCO, anchor="mm")
    return ingresso


def _com_formato(ingresso: Image.Image) -> Image.Image:
    recortado = Image.new("RGBA", ingresso.size, (0, 0, 0, 0))
    recortado.paste(ingresso, (0, 0), _mascara_ingresso(ingresso.size))
    return recortado


def gerar_ingresso(nome: str, codigo: str) -> bytes:
    """PNG do ingresso (frente e verso, lado a lado) com o nome e o código."""
    arte = Image.new("RGB", (LARGURA, ALTURA), FUNDO)
    d = ImageDraw.Draw(arte)
    _cantos(d, (34, 34, LARGURA - 34, ALTURA - 34), NAVY, 40, 4, cantos=("no", "se"))

    frente, verso = _com_formato(_frente(nome, codigo)), _com_formato(_verso())
    arte.paste(frente, (MARGEM, MARGEM), frente)
    arte.paste(verso, (MARGEM + T_LARG + GAP, MARGEM), verso)

    saida = io.BytesIO()
    arte.save(saida, format="PNG", optimize=True)
    return saida.getvalue()


def codigo_do_ingresso(purchase) -> str:
    """Código do ingresso a partir do pedido: CDX2026-0001."""
    return f"CDX{EVENTO_DATA.year}-{purchase.pk:04d}"
