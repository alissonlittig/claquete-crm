"""
ui/componentes.py
------------------
Componentes de interface reutilizados por várias páginas:

1. `input_moeda` / `input_numero` — campos numéricos que começam VAZIOS em vez
   de mostrar "0.00". Isso resolve o comportamento incômodo em que, ao digitar,
   o zero inicial ficava empurrando os dígitos para a direita (você digitava
   "150" e o campo virava "0.00150" ou similar). Agora o campo aparece vazio,
   com um texto de exemplo, e você digita o valor direto.

2. `seletor_periodo` — filtro de datas central e destacado, com atalhos
   ("Este mês", "Este ano"...). Fica no topo das páginas e vale para TODOS os
   gráficos e números daquela página.
"""

from datetime import date
from typing import Optional, Tuple

import streamlit as st

from ui import theme

# Intervalo usado pela opção "Todo o período"
DATA_MINIMA = date(2000, 1, 1)
DATA_MAXIMA = date(2100, 12, 31)


# ---------------------------------------------------------------------------
# Entradas numéricas
# ---------------------------------------------------------------------------

def _number_input_seguro(container, rotulo: str, chave: str, **kwargs):
    """
    Wrapper em volta de `st.number_input` que começa VAZIO (value=None).

    O parâmetro `placeholder` só existe em versões mais novas do Streamlit,
    então ele é tentado primeiro e descartado se a versão instalada não
    aceitar — assim o sistema funciona em qualquer versão a partir da 1.31.
    """
    try:
        return container.number_input(rotulo, key=chave, **kwargs)
    except TypeError:
        kwargs.pop("placeholder", None)
        return container.number_input(rotulo, key=chave, **kwargs)


def input_moeda(container, rotulo: str, chave: str, valor_inicial: Optional[float] = None,
                ajuda: str = "") -> float:
    """
    Campo de valor em reais que começa vazio (sem o "0.00" atrapalhando a
    digitação). Retorna 0.0 quando o usuário não digitou nada.

    Uso:
        valor = input_moeda(col1, "Valor (R$)", chave="valor_aporte")
    """
    valor = _number_input_seguro(
        container, rotulo, chave,
        min_value=0.0,
        value=valor_inicial,
        step=None,
        format="%.2f",
        placeholder="0,00",
        help=ajuda or None,
    )
    return float(valor) if valor is not None else 0.0


def input_percentual(container, rotulo: str, chave: str,
                     valor_inicial: Optional[float] = None) -> float:
    """Campo de percentual (0 a 100). Começa vazio quando não há valor definido."""
    valor = _number_input_seguro(
        container, rotulo, chave,
        min_value=0.0,
        max_value=100.0,
        value=valor_inicial,
        step=None,
        format="%.1f",
        placeholder="0",
    )
    return float(valor) if valor is not None else 0.0


def input_inteiro(container, rotulo: str, chave: str,
                  valor_inicial: Optional[int] = None,
                  minimo: int = 0, maximo: Optional[int] = None,
                  ajuda: str = "") -> Optional[int]:
    """Campo de número inteiro que também começa vazio."""
    valor = _number_input_seguro(
        container, rotulo, chave,
        min_value=minimo,
        max_value=maximo,
        value=valor_inicial,
        step=1,
        placeholder="—",
        help=ajuda or None,
    )
    return int(valor) if valor is not None else None


# ---------------------------------------------------------------------------
# Seletor de período
# ---------------------------------------------------------------------------

ATALHOS = [
    "Este mês",
    "Últimos 3 meses",
    "Este ano",
    "Últimos 12 meses",
    "Todo o período",
    "Personalizado",
]


def _intervalo_do_atalho(atalho: str) -> Tuple[date, date]:
    hoje = date.today()
    if atalho == "Este mês":
        return date(hoje.year, hoje.month, 1), hoje
    if atalho == "Últimos 3 meses":
        mes = hoje.month - 2
        ano = hoje.year
        if mes <= 0:
            mes += 12
            ano -= 1
        return date(ano, mes, 1), hoje
    if atalho == "Este ano":
        return date(hoje.year, 1, 1), date(hoje.year, 12, 31)
    if atalho == "Últimos 12 meses":
        try:
            inicio = date(hoje.year - 1, hoje.month, 1)
        except ValueError:
            inicio = date(hoje.year - 1, hoje.month, 1)
        return inicio, hoje
    return DATA_MINIMA, DATA_MAXIMA


def seletor_periodo(chave: str = "periodo",
                    atalho_padrao: str = "Este ano") -> Tuple[date, date]:
    """
    Desenha o seletor de período no topo da página, dentro de um card
    destacado, e devolve o intervalo (data_inicial, data_final) escolhido.

    Todos os gráficos e indicadores da página devem usar esse intervalo,
    para que mudar o período atualize a página inteira.
    """
    with st.container(border=True):
        st.markdown(
            f"<div style='font-size:0.76rem;text-transform:uppercase;letter-spacing:0.09em;"
            f"font-weight:700;color:{theme.TEXTO_SECUNDARIO};margin-bottom:8px'>"
            f"🗓️ Período de análise</div>",
            unsafe_allow_html=True,
        )
        col_atalhos, col_datas = st.columns([3, 2])

        atalho = col_atalhos.radio(
            "Atalhos de período",
            ATALHOS,
            index=ATALHOS.index(atalho_padrao) if atalho_padrao in ATALHOS else 2,
            horizontal=True,
            key=f"{chave}_atalho",
            label_visibility="collapsed",
        )

        if atalho == "Personalizado":
            hoje = date.today()
            intervalo = col_datas.date_input(
                "Intervalo personalizado",
                value=(date(hoje.year, 1, 1), hoje),
                format="DD/MM/YYYY",
                key=f"{chave}_datas",
                label_visibility="collapsed",
            )
            if isinstance(intervalo, (tuple, list)) and len(intervalo) == 2:
                data_ini, data_fim = intervalo[0], intervalo[1]
            else:
                data_ini, data_fim = date(hoje.year, 1, 1), hoje
        else:
            data_ini, data_fim = _intervalo_do_atalho(atalho)
            if atalho == "Todo o período":
                texto = "Sem filtro de data — todos os registros"
            else:
                texto = (
                    f"{data_ini.strftime('%d/%m/%Y')} &nbsp;→&nbsp; "
                    f"{data_fim.strftime('%d/%m/%Y')}"
                )
            col_datas.markdown(
                f"<div style='text-align:right;padding-top:6px;color:{theme.BRANCO};"
                f"font-weight:600'>{texto}</div>",
                unsafe_allow_html=True,
            )

    return data_ini, data_fim


def periodo_iso(data_ini: date, data_fim: date) -> Tuple[str, str]:
    """Converte o par de datas para o formato ISO usado nas consultas."""
    return data_ini.isoformat(), data_fim.isoformat()
