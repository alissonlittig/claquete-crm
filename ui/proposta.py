"""
ui/proposta.py
---------------
Gera a proposta comercial como um DOCUMENTO HTML COMPLETO e independente.

POR QUE UM DOCUMENTO SEPARADO
    A versão anterior montava a proposta dentro da própria página do sistema,
    usando Markdown. Isso causava dois problemas:

    1. O Markdown interpreta linhas com recuo como "bloco de código" e encerra
       o HTML nas linhas em branco — por isso apareciam trechos de código
       soltos no meio da proposta.
    2. Ao imprimir com Ctrl+P, o navegador imprimia a tela inteira do sistema
       (menu lateral, abas, botões), e não só a proposta.

    Agora a proposta é um documento à parte:
      - Na tela, ela aparece numa janela isolada (sem interferência do Markdown).
      - Para imprimir, você baixa o arquivo, abre no navegador e usa o botão
        "Imprimir / Salvar em PDF" — sai só a proposta, em folha A4.

SEGURANÇA
    Todo texto vindo do banco passa por `html.escape`, pelo mesmo motivo
    explicado em SEGURANCA.md: impedir que um nome de cliente com código
    malicioso seja executado.
"""

import base64
import html
import os
from datetime import date, timedelta

from db_utils import formatar_data_br, formatar_moeda

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGO_PATH = os.path.join(BASE_DIR, "assets", "claquete_monograma.png")

# Cores da Claquete (as mesmas de ui/theme.py). O documento é independente do
# Streamlit, por isso as cores são repetidas aqui em vez de importadas.
AMARELO = "#FACC15"
GRAFITE = "#0A0C10"
# No papel branco o amarelo não tem contraste para texto; os títulos usam um
# ciano escuro, e o amarelo fica para faixas e destaques sobre o grafite.
TINTA = "#0E7490"
LISTRAS = f"repeating-linear-gradient(135deg,{AMARELO} 0 12px,{GRAFITE} 12px 24px)"
ORDEM_CATEGORIAS = ["Produção", "Pós-produção", "Logística", "Gestão", "Mídia", "Outro"]


def _e(texto) -> str:
    """Escapa texto para HTML (proteção contra código malicioso)."""
    return html.escape(str(texto or ""), quote=True)


def _logo() -> str:
    try:
        with open(LOGO_PATH, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except OSError:
        return ""


def formatar_quantidade(quantidade: float, unidade: str) -> str:
    """
    Exibe a quantidade de forma natural:
        1.5 hora  -> "1h30"      0.5 hora -> "30min"
        40 km     -> "40 km"     2 diária -> "2 diárias"
    """
    quantidade = float(quantidade or 0)
    if unidade == "hora":
        horas = int(quantidade)
        minutos = round((quantidade - horas) * 60)
        if minutos == 60:
            horas, minutos = horas + 1, 0
        if horas and minutos:
            return f"{horas}h{minutos:02d}"
        if horas:
            return f"{horas}h"
        return f"{minutos}min"

    numero = f"{quantidade:g}".replace(".", ",")
    plurais = {"diária": "diárias", "mês": "meses", "unidade": "unidades",
               "pacote": "pacotes", "km": "km", "vez": "vezes"}
    rotulo = unidade if quantidade == 1 else plurais.get(unidade, unidade)
    return f"{numero} {rotulo}"


def _linha_info(rotulo: str, valor: str) -> str:
    if not valor:
        return ""
    return (f'<div class="info-linha"><span class="info-rotulo">{_e(rotulo)}</span>'
            f'<span class="info-valor">{_e(valor)}</span></div>')


def gerar_html_proposta(orc: dict, empresa: dict, numero: str,
                         para_impressao: bool = True) -> str:
    """
    Monta o documento HTML completo da proposta.

    `para_impressao=True` inclui o botão "Imprimir / Salvar em PDF" no topo
    (ele some automaticamente na hora de imprimir).
    """
    logo = _logo()
    img_logo = (f'<img src="data:image/png;base64,{logo}" alt="Claquete" class="logo" />'
                if logo else "")

    # ---------------- datas ----------------
    try:
        emissao = date.fromisoformat(orc["data"][:10])
    except (TypeError, ValueError):
        emissao = date.today()
    validade = emissao + timedelta(days=int(orc.get("validade_dias") or 15))

    # ---------------- itens agrupados por categoria ----------------
    grupos = {}
    for item in orc.get("itens", []):
        grupos.setdefault(item["categoria"] or "Outro", []).append(item)
    categorias = [c for c in ORDEM_CATEGORIAS if c in grupos] + \
                 [c for c in grupos if c not in ORDEM_CATEGORIAS]

    linhas = ""
    for categoria in categorias:
        itens = grupos[categoria]
        soma = sum(i["subtotal"] for i in itens)
        linhas += (f'<tr class="cat"><td colspan="4">{_e(categoria)}</td>'
                   f'<td class="num">{formatar_moeda(soma)}</td></tr>')
        for i in itens:
            equipe = f'{i["pessoas"]} pessoa{"s" if i["pessoas"] > 1 else ""}'
            linhas += (
                f'<tr>'
                f'<td>{_e(i["descricao"])}</td>'
                f'<td class="cen">{_e(formatar_quantidade(i["quantidade"], i["unidade"]))}</td>'
                f'<td class="cen">{_e(equipe)}</td>'
                f'<td class="num">{formatar_moeda(i["valor_unitario"])}'
                f'<span class="por">/{_e("pessoa" if i["unidade"] == "vez" else i["unidade"])}</span></td>'
                f'<td class="num">{formatar_moeda(i["subtotal"])}</td>'
                f'</tr>'
            )
    if not linhas:
        linhas = ('<tr><td colspan="5" class="vazio">Nenhum serviço adicionado '
                  'a este orçamento ainda.</td></tr>')

    linha_desconto = ""
    if orc.get("valor_desconto"):
        linha_desconto = (
            f'<div class="tot-linha"><span>Desconto ({orc["desconto_percent"]:g}%)</span>'
            f'<span class="desc">− {formatar_moeda(orc["valor_desconto"])}</span></div>'
        )

    # ---------------- blocos opcionais ----------------
    bloco_escopo = ""
    if (orc.get("escopo") or "").strip():
        bloco_escopo = (f'<section class="bloco"><h3>Escopo do projeto</h3>'
                        f'<p class="texto">{_e(orc["escopo"])}</p></section>')

    bloco_condicoes = ""
    if (orc.get("condicoes") or "").strip():
        bloco_condicoes = (f'<section class="bloco"><h3>Condições de pagamento</h3>'
                           f'<p class="texto">{_e(orc["condicoes"])}</p></section>')

    bloco_obs = ""
    if (orc.get("observacoes") or "").strip():
        bloco_obs = (f'<section class="bloco"><h3>Observações</h3>'
                     f'<p class="texto">{_e(orc["observacoes"])}</p></section>')

    data_evento = formatar_data_br(orc["data_evento"]) if orc.get("data_evento") else ""

    cliente_info = (
        _linha_info("Empresa / Cliente", orc.get("cliente_nome"))
        + _linha_info("Contato", orc.get("cliente_contato"))
        + _linha_info("E-mail", orc.get("cliente_email"))
        + _linha_info("Telefone", orc.get("cliente_telefone"))
    )
    empresa_info = (
        _linha_info("Responsável", orc.get("responsavel_nome"))
        + _linha_info("E-mail", empresa.get("empresa_email"))
        + _linha_info("Telefone", empresa.get("empresa_telefone"))
        + _linha_info("CNPJ", empresa.get("empresa_cnpj"))
    )
    datas_info = (
        _linha_info("Emissão", emissao.strftime("%d/%m/%Y"))
        + _linha_info("Válida até", validade.strftime("%d/%m/%Y"))
        + _linha_info("Data do evento / captação", data_evento)
        + _linha_info("Prazo de entrega", orc.get("prazo_entrega"))
    )

    rodape_itens = [empresa.get("empresa_nome"), empresa.get("empresa_cnpj") and
                    f'CNPJ {empresa.get("empresa_cnpj")}', empresa.get("empresa_email"),
                    empresa.get("empresa_telefone"), empresa.get("empresa_site"),
                    empresa.get("empresa_instagram"), empresa.get("empresa_cidade")]
    rodape = " · ".join(_e(x) for x in rodape_itens if x)

    barra_impressao = ""
    if para_impressao:
        barra_impressao = """
        <div class="barra no-print">
          <span>Proposta pronta. Use o botão ao lado e escolha
                <b>Salvar como PDF</b> no destino da impressão.</span>
          <button onclick="window.print()">🖨️ Imprimir / Salvar em PDF</button>
        </div>"""

    responsavel = _e(orc.get("responsavel_nome") or empresa.get("empresa_nome"))

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Proposta {numero} — {_e(orc.get("cliente_nome"))}</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Space+Grotesk:wght@600;700&display=swap" rel="stylesheet">
<style>
  * {{ box-sizing: border-box; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
  body {{ margin: 0; background: #E9E9EE; font-family: Inter, Arial, sans-serif;
          color: #1A1A22; font-size: 13px; line-height: 1.5; }}
  .folha {{ width: 210mm; min-height: 297mm; margin: 18px auto; background: #FFFFFF;
            box-shadow: 0 4px 24px rgba(0,0,0,.12); }}

  .barra {{ max-width: 210mm; margin: 18px auto 0; display: flex; gap: 12px;
            align-items: center; justify-content: space-between; background: {GRAFITE};
            color: #DBDBDB; padding: 12px 16px; border-radius: 10px; font-size: 13px; }}
  .barra button {{ background: {AMARELO}; color: {GRAFITE}; border: 0; border-radius: 8px;
                   padding: 10px 16px; font-weight: 700; cursor: pointer; font-size: 13px;
                   white-space: nowrap; }}

  .topo {{ background: {GRAFITE}; color: #fff; padding: 26px 34px 22px;
           display: flex; align-items: center; justify-content: space-between; }}
  .marca {{ display: flex; align-items: center; gap: 14px; }}
  .logo {{ width: 58px; height: auto; }}
  .marca-nome {{ font-family: 'Space Grotesk', Arial, sans-serif; font-weight: 700;
                 font-size: 26px; line-height: 1; letter-spacing: .01em; }}
  .marca-sub {{ font-size: 10px; color: #9A9AA6; letter-spacing: .18em;
                text-transform: uppercase; margin-top: 4px; }}
  .doc {{ text-align: right; }}
  .doc-tipo {{ font-size: 10px; color: #9A9AA6; letter-spacing: .16em; text-transform: uppercase; }}
  .doc-num {{ font-family: 'Space Grotesk', Arial, sans-serif; font-weight: 700; font-size: 20px; }}
  .listras {{ height: 8px; background: {LISTRAS}; }}

  .conteudo {{ padding: 28px 34px 30px; }}
  h1 {{ font-family: 'Space Grotesk', Arial, sans-serif; font-weight: 700; font-size: 24px;
        margin: 0 0 4px; color: {GRAFITE}; }}
  .para {{ color: #5A5A66; margin: 0 0 22px; }}
  .para b {{ color: {GRAFITE}; }}

  .grade {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; margin-bottom: 22px; }}
  .cartao {{ border: 1px solid #E2E2E8; border-radius: 10px; padding: 12px 14px; }}
  .cartao h4 {{ margin: 0 0 8px; font-size: 10px; letter-spacing: .14em;
                text-transform: uppercase; color: {TINTA}; }}
  .info-linha {{ display: flex; flex-direction: column; margin-bottom: 6px; }}
  .info-rotulo {{ font-size: 10px; color: #8A8A96; }}
  .info-valor {{ font-weight: 600; color: #1A1A22; word-break: break-word; }}

  .bloco {{ margin-bottom: 18px; page-break-inside: avoid; }}
  /* A tabela de valores PODE continuar na página seguinte — só não quebra
     no meio de uma linha. Antes ela era empurrada inteira para a página 2. */
  .bloco-tabela {{ margin-bottom: 18px; }}
  thead {{ display: table-header-group; }}
  h3 {{ font-size: 11px; letter-spacing: .14em; text-transform: uppercase;
        color: {TINTA}; margin: 0 0 8px; page-break-after: avoid; }}
  .texto {{ margin: 0; white-space: pre-wrap; color: #33333D; }}

  table {{ width: 100%; border-collapse: collapse; margin-top: 4px; }}
  thead th {{ font-size: 10px; letter-spacing: .1em; text-transform: uppercase;
              color: #8A8A96; text-align: left; padding: 8px 8px;
              border-bottom: 2px solid {GRAFITE}; }}
  td {{ padding: 8px; border-bottom: 1px solid #EEEEF2; vertical-align: top; }}
  tr {{ page-break-inside: avoid; }}
  tr.cat td {{ background: #F3F5F7; font-weight: 700; color: {GRAFITE};
               font-size: 11px; letter-spacing: .06em; text-transform: uppercase; }}
  .num {{ text-align: right; white-space: nowrap; }}
  .cen {{ text-align: center; white-space: nowrap; }}
  .por {{ color: #8A8A96; font-size: 11px; }}
  .vazio {{ text-align: center; color: #8A8A96; padding: 18px; }}

  .totais {{ margin: 16px 0 22px auto; width: 300px; page-break-inside: avoid; }}
  .tot-linha {{ display: flex; justify-content: space-between; padding: 5px 0; color: #5A5A66; }}
  .desc {{ color: #0C9F99; font-weight: 600; }}
  .tot-final {{ display: flex; justify-content: space-between; align-items: center;
                margin-top: 6px; padding: 12px 14px; border-radius: 10px;
                background: {GRAFITE}; color: #fff; }}
  .tot-final span:first-child {{ font-size: 11px; letter-spacing: .14em; text-transform: uppercase; }}
  .tot-final span:last-child {{ font-family: 'Space Grotesk', Arial, sans-serif; font-weight: 700;
                                 font-size: 21px; color: {AMARELO}; }}

  .aceite {{ margin-top: 30px; page-break-inside: avoid; }}
  .aceite p {{ color: #5A5A66; margin: 0 0 34px; }}
  .assinaturas {{ display: grid; grid-template-columns: 1fr 1fr; gap: 40px; }}
  .assinatura {{ border-top: 1px solid {GRAFITE}; padding-top: 6px; font-size: 12px; }}
  .assinatura span {{ display: block; color: #8A8A96; font-size: 11px; }}

  .rodape {{ margin-top: 28px; padding-top: 12px; border-top: 1px solid #E2E2E8;
             font-size: 10.5px; color: #8A8A96; text-align: center; }}

  /* A faixa escura do topo encosta na borda só na 1ª página; as páginas
     seguintes ganham margem em cima e embaixo para não ficarem coladas. */
  @page {{ size: A4; margin: 14mm 0 14mm 0; }}
  @page :first {{ margin-top: 0; }}
  @media print {{
    body {{ background: #FFFFFF; }}
    .no-print {{ display: none !important; }}
    .folha {{ margin: 0; box-shadow: none; width: 100%; min-height: auto; }}
  }}
</style>
</head>
<body>
{barra_impressao}
<div class="folha">
  <div class="topo">
    <div class="marca">
      {img_logo}
      <div>
        <div class="marca-nome">Claquete</div>
        <div class="marca-sub">Produtora Audiovisual</div>
      </div>
    </div>
    <div class="doc">
      <div class="doc-tipo">Proposta comercial</div>
      <div class="doc-num">Nº {numero}</div>
    </div>
  </div>
  <div class="listras"></div>

  <div class="conteudo">
    <h1>{_e(orc.get("titulo"))}</h1>
    <p class="para">Proposta preparada para <b>{_e(orc.get("cliente_nome"))}</b></p>

    <div class="grade">
      <div class="cartao"><h4>Cliente</h4>{cliente_info}</div>
      <div class="cartao"><h4>Claquete</h4>{empresa_info or _linha_info("Empresa", empresa.get("empresa_nome"))}</div>
      <div class="cartao"><h4>Datas</h4>{datas_info}</div>
    </div>

    {bloco_escopo}

    <section class="bloco-tabela">
      <h3>Investimento</h3>
      <table>
        <thead>
          <tr>
            <th>Serviço</th>
            <th style="text-align:center">Tempo / Qtd.</th>
            <th style="text-align:center">Equipe</th>
            <th style="text-align:right">Valor unitário</th>
            <th style="text-align:right">Subtotal</th>
          </tr>
        </thead>
        <tbody>{linhas}</tbody>
      </table>

      <div class="totais">
        <div class="tot-linha"><span>Subtotal</span><span>{formatar_moeda(orc.get("subtotal", 0))}</span></div>
        {linha_desconto}
        <div class="tot-final"><span>Valor total</span><span>{formatar_moeda(orc.get("total", 0))}</span></div>
      </div>
    </section>

    {bloco_condicoes}
    {bloco_obs}

    <section class="aceite">
      <h3>Aceite da proposta</h3>
      <p>Esta proposta é válida até <b>{validade.strftime("%d/%m/%Y")}</b>.
         De acordo com os serviços e valores descritos acima:</p>
      <div class="assinaturas">
        <div class="assinatura">{_e(orc.get("cliente_contato") or orc.get("cliente_nome"))}
          <span>{_e(orc.get("cliente_nome"))} · Data: ____/____/______</span></div>
        <div class="assinatura">{responsavel}
          <span>{_e(empresa.get("empresa_nome"))}</span></div>
      </div>
    </section>

    <div class="rodape">{rodape}</div>
  </div>
</div>
</body>
</html>"""
