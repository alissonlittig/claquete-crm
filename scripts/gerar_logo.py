"""
scripts/gerar_logo.py
----------------------
Gera o monograma da Claquete (assets/claquete_monograma.png) só com código,
sem nenhum arquivo de imagem de origem.

O desenho é uma claquete de cinema estilizada:
    - a "haste" de cima, levemente aberta, com as listras diagonais
      amarelo/grafite que são a assinatura visual do sistema;
    - o corpo arredondado em amarelo, com um "C" vazado em grafite.

Como rodar (a partir da pasta raiz do projeto):

    python scripts/gerar_logo.py

O desenho é feito em 4x o tamanho final e reduzido no fim, para as bordas
saírem suaves (antialiasing).
"""

import math
import os

from PIL import Image, ImageDraw

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DESTINO = os.path.join(BASE_DIR, "assets", "claquete_monograma.png")

# Mesmas cores de ui/theme.py
AMARELO = (250, 204, 21, 255)     # #FACC15
GRAFITE = (10, 12, 16, 255)       # #0A0C10

TAMANHO = 512
ESCALA = 4


def _haste(tam: int) -> Image.Image:
    """Faixa listrada da haste, desenhada reta (é girada depois)."""
    largura, altura = int(tam * 0.86), int(tam * 0.17)
    faixa = Image.new("RGBA", (largura, altura), (0, 0, 0, 0))
    d = ImageDraw.Draw(faixa)
    raio = int(altura * 0.28)
    d.rounded_rectangle((0, 0, largura - 1, altura - 1), radius=raio, fill=AMARELO)

    # Listras diagonais em grafite, recortadas pela máscara arredondada
    listras = Image.new("RGBA", (largura, altura), AMARELO)
    dl = ImageDraw.Draw(listras)
    passo = int(altura * 1.25)
    espessura = int(passo * 0.5)
    for x in range(-altura, largura + altura, passo):
        dl.polygon([(x, altura), (x + altura, 0), (x + altura + espessura, 0),
                    (x + espessura, altura)], fill=GRAFITE)
    mascara = Image.new("L", (largura, altura), 0)
    ImageDraw.Draw(mascara).rounded_rectangle(
        (int(altura * 0.12), int(altura * 0.12),
         largura - 1 - int(altura * 0.12), altura - 1 - int(altura * 0.12)),
        radius=int(raio * 0.7), fill=255)
    faixa.paste(listras, (0, 0), mascara)
    return faixa


def gerar() -> str:
    tam = TAMANHO * ESCALA
    img = Image.new("RGBA", (tam, tam), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # ---------------- corpo
    margem = int(tam * 0.07)
    topo_corpo = int(tam * 0.36)
    d.rounded_rectangle((margem, topo_corpo, tam - margem, tam - margem),
                        radius=int(tam * 0.09), fill=AMARELO)

    # ---------------- haste aberta (girada a partir da dobradiça à esquerda)
    haste = _haste(tam)
    girada = haste.rotate(14, resample=Image.BICUBIC, expand=True)
    x_haste = margem - int(tam * 0.005)
    y_haste = topo_corpo - girada.height + int(tam * 0.035)
    img.alpha_composite(girada, (x_haste, max(0, y_haste)))

    # ---------------- "C" vazado no corpo
    cx = tam / 2
    cy = (topo_corpo + tam - margem) / 2
    raio = (tam - margem - topo_corpo) * 0.33
    espessura = int(raio * 0.46)
    caixa = (cx - raio, cy - raio, cx + raio, cy + raio)
    d.arc(caixa, start=45, end=315, fill=GRAFITE, width=espessura)
    # Pontas arredondadas do C
    for angulo in (45, 315):
        rad = math.radians(angulo)
        meio = raio - espessura / 2
        px, py = cx + meio * math.cos(rad), cy + meio * math.sin(rad)
        r = espessura / 2
        d.ellipse((px - r, py - r, px + r, py + r), fill=GRAFITE)

    final = img.resize((TAMANHO, TAMANHO), Image.LANCZOS)
    os.makedirs(os.path.dirname(DESTINO), exist_ok=True)
    final.save(DESTINO, optimize=True)
    return DESTINO


if __name__ == "__main__":
    print(f"Monograma gerado em: {gerar()}")
