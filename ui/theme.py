"""
ui/theme.py
-----------
Identidade visual da Claquete.

CONCEITO
    A claquete de cinema: fundo grafite, amarelo de sinalização e as listras
    diagonais da haste, que aparecem como régua sob os títulos e no logo.

PALETA
    Grafite  #0A0C10  ·  Branco #FFFFFF  ·  Cinza texto #D5D9E0
    Amarelo claquete  #FACC15   (cor principal)
    Lima              #A3E635   ·   Ciano #22D3EE   ·   Azul #3B82F6

GRADIENTE ASSINATURA
    #FACC15 → #A3E635 → #22D3EE   (amarelo → lima → ciano)

TIPOGRAFIA (Google Fonts, livres)
    · Space Grotesk → títulos e números
    · Inter         → texto corrido

O monograma (assets/claquete_monograma.png) é gerado por
scripts/gerar_logo.py, sem nenhuma imagem de origem.
"""

import base64
import html as _html
import os
from typing import Optional

import streamlit as st


def esc(texto) -> str:
    """
    Torna um texto seguro para ser inserido dentro de HTML.

    POR QUE ISSO EXISTE
        Várias telas montam HTML com `unsafe_allow_html=True` para aplicar a
        identidade visual da marca. Se um texto vindo do banco (nome de
        cliente, título de tarefa, descrição de item...) for colocado
        diretamente nesse HTML, alguém poderia gravar uma tag maliciosa —
        por exemplo `<img src=x onerror="...">` — no nome de um cliente, e
        ela seria EXECUTADA no navegador de todos os sócios que abrissem a
        tela. Isso se chama XSS armazenado.

        `esc()` converte os caracteres perigosos (< > & " ') em seus
        equivalentes inofensivos, de modo que o texto apareça exatamente
        como foi digitado, sem virar código.

    REGRA PRÁTICA
        Todo dado vindo do banco ou digitado por alguém que for para dentro
        de um st.markdown(..., unsafe_allow_html=True) deve passar por aqui.
    """
    if texto is None:
        return ""
    return _html.escape(str(texto), quote=True)

# ---------------------------------------------------------------------------
# Paleta
# ---------------------------------------------------------------------------
PRETO = "#000000"
FUNDO = "#0A0C10"
SUPERFICIE = "#13161C"
SUPERFICIE_ALT = "#1B1F27"
BORDA = "#262B35"

BRANCO = "#FFFFFF"
CINZA_TEXTO = "#D5D9E0"
TEXTO = "#FFFFFF"
TEXTO_SECUNDARIO = "#8B93A1"

# Cores da marca
AMARELO = "#FACC15"
AMARELO_CLARO = "#FDE68A"
LIMA = "#A3E635"
CIANO = "#22D3EE"
AZUL = "#3B82F6"
TEAL = "#2DD4BF"

GRADIENTE = f"linear-gradient(90deg, {AMARELO}, {LIMA}, {CIANO})"
GRADIENTE_CURTO = f"linear-gradient(90deg, {AMARELO}, {LIMA})"
# Listras diagonais da haste da claquete — a assinatura visual do sistema.
LISTRAS = (f"repeating-linear-gradient(135deg, {AMARELO} 0 9px, "
           f"{FUNDO} 9px 18px)")

PRIMARIA = AMARELO
PRIMARIA_CLARA = AMARELO_CLARO
# Texto sobre fundo amarelo (botões) precisa ser escuro para ter contraste.
TEXTO_SOBRE_PRIMARIA = FUNDO

# Cores semânticas
POSITIVO = "#22C55E"
NEGATIVO = "#F87171"
ALERTA = "#F59E0B"

CORES_GRAFICO = [AMARELO, CIANO, LIMA, AZUL, TEAL, "#E2E8F0", NEGATIVO]

CORES_STATUS_EVENTO = {
    "Orçamento": TEXTO_SECUNDARIO,
    "Confirmado": AZUL,
    "Em Produção": ALERTA,
    "Concluído": POSITIVO,
    "Cancelado": NEGATIVO,
}

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGO_PATH = os.path.join(BASE_DIR, "assets", "claquete_monograma.png")

# Páginas do sistema, na ordem em que aparecem no menu lateral.
# (prefixo do arquivo, rótulo exibido, ícone)
#
# Os nomes de arquivo são propositalmente SEM ACENTO E SEM EMOJI: emojis em
# nomes de arquivo se corrompem ao sincronizar em alguns ambientes Windows
# (OneDrive em especial), o que fazia os itens sumirem do menu. O visual
# continua com ícone porque ele vem da coluna "ícone" abaixo, não do arquivo.
PAGINAS = [
    ("app.py", "Dashboard Geral", "📊"),
    ("pages/7_Agenda.py", "Agenda da Equipe", "🗓️"),
    ("pages/1_Socios_e_Aportes.py", "Sócios e Aportes", "🤝"),
    ("pages/2_Clientes_e_Eventos.py", "Clientes e Eventos", "👥"),
    ("pages/8_Orcamentos.py", "Orçamentos", "🧮"),
    ("pages/3_Fluxo_de_Caixa.py", "Fluxo de Caixa", "💵"),
    ("pages/4_Custos_Fixos.py", "Custos Fixos", "🏢"),
    ("pages/5_Investimentos.py", "Investimentos", "💻"),
    ("pages/6_DRE.py", "DRE", "📑"),
]


def _logo_base64() -> str:
    """Lê o monograma da marca e devolve em base64, para embutir direto no HTML."""
    try:
        with open(LOGO_PATH, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except OSError:
        return ""


def injetar_css() -> None:
    """
    Injeta as fontes da marca e todo o CSS de acabamento do sistema.

    IMPORTANTE: o Markdown do Streamlit encerra um bloco HTML na primeira
    linha em branco que encontra. Se o CSS for enviado com linhas vazias
    entre as seções, tudo o que vem depois da primeira linha vazia é exibido
    como TEXTO na tela em vez de ser aplicado como estilo.

    Por isso o CSS é escrito aqui de forma legível (com seções e comentários),
    mas as linhas em branco são removidas logo antes de injetar. Ao editar
    este arquivo, mantenha os comentários no formato /* ... */ — comentários
    de CSS são seguros; linhas em branco são tratadas automaticamente.
    """
    css = f"""<style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap');
        html, body, .stApp, [class*="css"] {{
            font-family: 'Inter', -apple-system, sans-serif;
            font-size: 17px;
        }}

        .stApp {{
            background:
                radial-gradient(1200px 500px at 12% -8%, rgba(250, 204, 21, 0.07) 0%, transparent 60%),
                radial-gradient(900px 420px at 88% 108%, rgba(34, 211, 238, 0.06) 0%, transparent 60%),
                {FUNDO};
        }}

        /* ---------------- Tipografia ---------------- */
        h1, h2, h3, h4 {{
            font-family: 'Space Grotesk', 'Inter', sans-serif !important;
            color: {BRANCO} !important;
            letter-spacing: -0.02em;
        }}
        h1 {{ font-weight: 700 !important; font-size: 2.5rem !important; }}
        h2 {{ font-weight: 700 !important; }}
        h3 {{ font-weight: 700 !important; font-size: 1.42rem !important; }}

        p, span, label, li, div {{ color: {CINZA_TEXTO}; font-size: 1.0rem; }}
        /* O Streamlit envolve o texto dos títulos num <span>; sem isto a regra
           acima encolheria os títulos para o tamanho do texto corrido. */
        h1 span, h2 span, h3 span, h4 span {{ font-size: inherit !important; color: inherit !important; }}
        .stMarkdown p {{ font-size: 1.02rem; line-height: 1.6; }}
        .stCaption, [data-testid="stCaptionContainer"] p {{ font-size: 0.92rem !important; }}

        /* Régua listrada (haste da claquete) sob o título da página */
        .claq-regua {{
            height: 8px; width: 150px; border-radius: 3px;
            background: {LISTRAS};
            margin: 2px 0 14px 0;
        }}
        .claq-subtitulo {{
            color: {TEXTO_SECUNDARIO}; font-size: 1.08rem; margin: 0 0 6px 0;
        }}

        /* ---------------- Menu lateral ---------------- */
        /* A largura é aplicada só quando a barra está ABERTA. Antes havia um
           min-width fixo que impedia o Streamlit de recolhê-la, deixando a
           página "travada" — o conteúdo não reaproveitava o espaço. */
        section[data-testid="stSidebar"] {{
            background: linear-gradient(180deg, #0D1015 0%, {FUNDO} 100%);
            border-right: 1px solid {BORDA};
            transition: width 0.25s ease-in-out, min-width 0.25s ease-in-out,
                        transform 0.25s ease-in-out, margin 0.25s ease-in-out;
        }}
        section[data-testid="stSidebar"][aria-expanded="true"] {{
            width: 300px !important;
            min-width: 300px !important;
        }}
        section[data-testid="stSidebar"][aria-expanded="false"] {{
            width: 0 !important;
            min-width: 0 !important;
        }}
        /* O conteúdo principal acompanha a animação e ocupa a largura liberada */
        section[data-testid="stMain"] .block-container {{
            transition: padding 0.25s ease-in-out, max-width 0.25s ease-in-out;
            max-width: 100%;
            padding-left: 3rem;
            padding-right: 3rem;
            padding-top: 3rem;
        }}
        /* esconde a navegação automática (usamos um menu próprio) */
        div[data-testid="stSidebarNav"] {{ display: none; }}

        .claq-marca {{
            display: flex; align-items: center; gap: 13px;
            padding: 6px 4px 16px 4px;
            border-bottom: 1px solid {BORDA};
            margin-bottom: 14px;
        }}
        .claq-marca img {{ width: 46px; height: auto; }}
        .claq-marca .claq-nome {{
            font-family: 'Space Grotesk', sans-serif; font-weight: 700;
            font-size: 1.5rem; color: {BRANCO}; line-height: 1; letter-spacing: -0.01em;
        }}
        .claq-marca .claq-desc {{
            font-size: 0.76rem; color: {TEXTO_SECUNDARIO};
            letter-spacing: 0.10em; text-transform: uppercase; margin-top: 4px;
        }}

        /* itens do menu lateral — fonte maior e mais legível */
        section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"] {{
            font-size: 1.12rem !important;
            font-weight: 600 !important;
            padding: 12px 14px !important;
            border-radius: 11px !important;
            margin-bottom: 3px !important;
            border: 1px solid transparent;
            transition: all 0.14s ease-in-out;
        }}
        section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"] p {{
            font-size: 1.12rem !important;
            font-weight: 600 !important;
            color: {CINZA_TEXTO} !important;
        }}
        section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"]:hover {{
            background: {SUPERFICIE_ALT} !important;
            border-color: {BORDA};
        }}
        section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"]:hover p {{
            color: {BRANCO} !important;
        }}

        /* ---------------- Cards de KPI ---------------- */
        .kpi-card {{
            position: relative; overflow: hidden;
            background: linear-gradient(160deg, {SUPERFICIE} 0%, {FUNDO} 130%);
            border: 1px solid {BORDA};
            border-radius: 16px;
            padding: 18px 20px 16px 20px;
            margin-bottom: 8px;
            min-height: 124px;
        }}
        .kpi-card::before {{
            content: ""; position: absolute; top: 0; left: 0; right: 0; height: 3px;
            background: {GRADIENTE};
        }}
        .kpi-card .kpi-titulo {{
            font-size: 0.82rem; color: {TEXTO_SECUNDARIO};
            text-transform: uppercase; letter-spacing: 0.09em;
            font-weight: 600; margin-bottom: 8px;
        }}
        /* O valor acompanha a largura do próprio card (unidade cqi), para
           "R$ 123.456,78" caber numa linha só também em notebooks, onde cinco
           cards lado a lado ficam estreitos. */
        .kpi-card {{ container-type: inline-size; }}
        .kpi-card .kpi-valor {{
            font-family: 'Space Grotesk', sans-serif; font-weight: 700;
            font-size: clamp(1.05rem, 12cqi, 1.85rem); color: {BRANCO}; line-height: 1.15;
            letter-spacing: -0.02em; white-space: nowrap;
        }}
        .kpi-card .kpi-subtitulo {{ font-size: 0.88rem; margin-top: 5px; font-weight: 500; }}

        /* ---------------- Badges ---------------- */
        .badge {{
            display: inline-block; padding: 3px 12px; border-radius: 999px;
            font-size: 0.76rem; font-weight: 700; letter-spacing: 0.02em;
        }}

        /* ---------------- Botões ---------------- */
        .stButton > button, .stFormSubmitButton > button, .stDownloadButton > button {{
            background: {PRIMARIA};
            color: {TEXTO_SOBRE_PRIMARIA} !important;
            border: none; border-radius: 11px;
            font-weight: 700 !important;
            font-size: 1.03rem !important;
            letter-spacing: 0.01em;
            padding: 0.5rem 1rem;
            transition: all 0.16s ease-in-out;
        }}
        .stButton > button p, .stFormSubmitButton > button p {{
            font-weight: 700 !important; color: {TEXTO_SOBRE_PRIMARIA} !important; font-size: 1.03rem !important;
        }}
        .stDownloadButton > button p {{ color: {TEXTO_SOBRE_PRIMARIA} !important; font-weight: 700 !important; }}
        .stButton > button:hover, .stFormSubmitButton > button:hover {{
            background: {AMARELO_CLARO};
            box-shadow: 0 0 18px rgba(250, 204, 21, 0.35);
            transform: translateY(-1px);
        }}
        /* botões secundários (kind="secondary") ficam discretos */
        .stButton > button[kind="secondary"] {{
            background: {SUPERFICIE_ALT}; border: 1px solid {BORDA};
        }}
        .stButton > button[kind="secondary"] p {{ color: {CINZA_TEXTO} !important; }}
        .stButton > button[kind="secondary"]:hover {{
            background: {SUPERFICIE_ALT}; border-color: {AMARELO}; box-shadow: none;
        }}

        /* ---------------- Formulários ---------------- */
        label, .stMarkdown label {{ font-weight: 600 !important; color: {CINZA_TEXTO} !important; font-size: 1.0rem !important; }}
        label p {{ font-size: 1.0rem !important; }}
        input, textarea, .stSelectbox div[data-baseweb="select"] > div {{
            background-color: {SUPERFICIE} !important;
            border-color: {BORDA} !important;
            color: {BRANCO} !important;
            font-size: 1.02rem !important;
        }}
        input:focus, textarea:focus {{ border-color: {PRIMARIA} !important; }}

        /* ---------------- Abas ---------------- */
        .stTabs [data-baseweb="tab-list"] {{ gap: 6px; border-bottom: 1px solid {BORDA}; }}
        .stTabs [data-baseweb="tab"] {{
            background-color: transparent; border-radius: 10px 10px 0 0;
            padding: 9px 17px; font-weight: 600;
        }}
        .stTabs [data-baseweb="tab"] p {{ font-size: 1.08rem !important; font-weight: 600 !important; }}
        .stTabs [aria-selected="true"] {{ background: {SUPERFICIE} !important; }}
        .stTabs [aria-selected="true"] p {{ color: {BRANCO} !important; }}
        .stTabs [data-baseweb="tab-highlight"] {{ background: {GRADIENTE_CURTO} !important; height: 3px; }}

        /* ---------------- Containers, expanders, tabelas ---------------- */
        div[data-testid="stVerticalBlockBorderWrapper"] {{
            border-color: {BORDA} !important; border-radius: 16px !important;
            background: rgba(19, 22, 28, 0.55);
        }}
        details, div[data-testid="stExpander"] {{
            background-color: {SUPERFICIE} !important;
            border: 1px solid {BORDA} !important; border-radius: 13px !important;
        }}
        div[data-testid="stExpander"] summary p {{ font-size: 1.06rem !important; font-weight: 600 !important; }}
        hr {{ border-color: {BORDA}; }}
        div[data-testid="stMetric"] {{
            background: {SUPERFICIE}; border: 1px solid {BORDA};
            border-radius: 14px; padding: 14px 16px;
        }}
        .stDataFrame {{ border-radius: 12px; overflow: hidden; font-size: 1.0rem; }}

        /* Esconde a dica "Press Enter to submit form" que o Streamlit coloca
           DENTRO dos campos de formulário — em colunas estreitas ela ficava
           por cima do valor digitado. */
        div[data-testid="InputInstructions"] {{ display: none !important; }}
        /* Rádio horizontal usado no seletor de período */
        div[role="radiogroup"] label p {{ font-size: 1.0rem !important; font-weight: 600 !important; }}
        </style>"""

    # Remove linhas em branco e a indentação do Python — sem isso, o Markdown
    # interromperia o bloco <style> e o restante do CSS apareceria como texto.
    css_limpo = "\n".join(
        linha.strip() for linha in css.splitlines() if linha.strip()
    )
    st.markdown(css_limpo, unsafe_allow_html=True)


def _resolver_pagina(caminho: str) -> Optional[str]:
    """
    Confirma que o arquivo da página existe em disco e devolve o caminho a ser
    usado no menu. Se o nome exato não for encontrado, procura na pasta
    `pages/` por um arquivo com o mesmo número inicial (ex.: "3_") — assim o
    menu continua funcionando mesmo que o nome do arquivo tenha sofrido
    alguma alteração de acentuação/codificação ao ser copiado entre máquinas.

    Devolve None quando não há nenhum arquivo correspondente.
    """
    caminho_absoluto = os.path.join(BASE_DIR, caminho)
    if os.path.exists(caminho_absoluto):
        return caminho

    if not caminho.startswith("pages/"):
        return None

    nome = os.path.basename(caminho)
    prefixo = nome.split("_", 1)[0] + "_"
    pasta_paginas = os.path.join(BASE_DIR, "pages")
    try:
        for arquivo in sorted(os.listdir(pasta_paginas)):
            if arquivo.startswith(prefixo) and arquivo.endswith(".py"):
                return f"pages/{arquivo}"
    except OSError:
        pass
    return None


def menu_lateral(pagina_atual: str = "") -> None:
    """
    Desenha o menu lateral da Claquete: a marca (logo + nome) como primeiro
    item, seguida dos links de navegação com fonte ampliada.

    `pagina_atual` é apenas informativo; o Streamlit já destaca sozinho a
    página ativa.
    """
    logo = _logo_base64()
    img_html = (
        f'<img src="data:image/png;base64,{logo}" alt="Claquete" />' if logo else ""
    )
    st.sidebar.markdown(
        f"""
        <div class="claq-marca">
            {img_html}
            <div>
                <div class="claq-nome">Claquete</div>
                <div class="claq-desc">CRM · ERP</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Aviso permanente de que esta é uma demonstração com dados fictícios.
    st.sidebar.markdown(
        f"""
        <div style="background:{AMARELO}14;border:1px solid {AMARELO}55;
                    border-radius:10px;padding:9px 12px;margin-bottom:12px">
            <div style="color:{AMARELO};font-weight:700;font-size:0.86rem">
                🎬 DEMONSTRAÇÃO</div>
            <div style="color:{TEXTO_SECUNDARIO};font-size:0.78rem;margin-top:2px">
                Dados fictícios. O banco volta ao<br>estado inicial a cada reinício.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    for caminho, rotulo, icone in PAGINAS:
        caminho_real = _resolver_pagina(caminho)
        if caminho_real is None:
            st.sidebar.markdown(
                f"<div style='padding:10px 13px;color:{ALERTA};font-size:0.92rem'>"
                f"⚠️ {esc(rotulo)} — arquivo não encontrado</div>",
                unsafe_allow_html=True,
            )
            continue
        try:
            st.sidebar.page_link(caminho_real, label=rotulo, icon=icone)
        except Exception as erro:
            # Antes isso era silencioso e o item simplesmente sumia do menu,
            # sem nenhuma pista do motivo. Agora o problema fica visível.
            st.sidebar.markdown(
                f"<div style='padding:10px 13px;color:{ALERTA};font-size:0.92rem'>"
                f"⚠️ {rotulo} — {type(erro).__name__}</div>",
                unsafe_allow_html=True,
            )

    # Atualizar dados + tempo de resposta do banco.
    # O botão limpa o cache de leitura — útil se o banco foi alterado por fora
    # do sistema (ex.: por um script rodado no terminal). O tempo de resposta é
    # medido uma vez por sessão e mostra, com número real, quanto o banco leva
    # para responder a partir do servidor onde o sistema está rodando.
    try:
        from database import medir_latencia_ms
        from db_utils import limpar_cache

        if "latencia_banco_ms" not in st.session_state:
            try:
                st.session_state["latencia_banco_ms"] = medir_latencia_ms()
            except Exception:
                st.session_state["latencia_banco_ms"] = None
        latencia = st.session_state["latencia_banco_ms"]
        texto_lat = f"{latencia:.0f} ms" if latencia is not None else "sem resposta"
        cor_lat = (POSITIVO if latencia is not None and latencia < 80
                   else ALERTA if latencia is not None and latencia < 250 else NEGATIVO)

        st.sidebar.markdown(
            f"<div style='margin-top:14px;font-size:0.78rem;color:{TEXTO_SECUNDARIO}'>"
            f"Banco local: <span style='color:{cor_lat};font-weight:700'>"
            f"{texto_lat}</span></div>",
            unsafe_allow_html=True,
        )
        if st.sidebar.button("🔄 Atualizar dados", key="botao_atualizar_dados",
                             width="stretch", type="secondary"):
            limpar_cache()
            st.session_state.pop("latencia_banco_ms", None)
            st.rerun()
    except Exception:
        pass

    # Rodapé: quem está logado + botão de sair.
    # Lê o session_state diretamente (em vez de importar o módulo auth) para
    # não criar dependência circular entre theme.py e auth.py.
    usuario = st.session_state.get("auth_usuario", "")
    if usuario:
        st.sidebar.markdown(
            f"""
            <div style="border-top:1px solid {BORDA};margin-top:18px;padding-top:14px">
                <div style="font-size:0.74rem;color:{TEXTO_SECUNDARIO};
                            text-transform:uppercase;letter-spacing:0.09em">Conectado como</div>
                <div style="font-weight:700;color:{BRANCO};font-size:1.04rem;
                            margin-top:3px">{esc(usuario.replace("_", " "))}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.sidebar.button("Sair", key="botao_sair", width="stretch",
                             type="secondary"):
            for chave in ("auth_usuario", "auth_tentativas"):
                st.session_state.pop(chave, None)
            st.rerun()


def cabecalho(titulo: str, subtitulo: str = "", icone: str = "") -> None:
    """Cabeçalho padrão de página: título + régua listrada da claquete."""
    prefixo = f"{icone}  " if icone else ""
    st.markdown(f"# {prefixo}{titulo}")
    st.markdown('<div class="claq-regua"></div>', unsafe_allow_html=True)
    if subtitulo:
        st.markdown(f'<p class="claq-subtitulo">{subtitulo}</p>', unsafe_allow_html=True)


def kpi_card(coluna, titulo: str, valor: str, subtitulo: str = "",
             cor_subtitulo: str = None) -> None:
    """Card de indicador com a faixa de gradiente da marca no topo."""
    cor = cor_subtitulo or TEXTO_SECUNDARIO
    with coluna:
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-titulo">{titulo}</div>
                <div class="kpi-valor">{valor}</div>
                <div class="kpi-subtitulo" style="color:{cor}">{subtitulo}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def badge_status(status: str) -> str:
    """HTML de uma etiqueta colorida para o status de um evento/projeto."""
    cor = CORES_STATUS_EVENTO.get(status, PRIMARIA_CLARA)
    return (
        f'<span class="badge" style="background-color:{cor}22; color:{cor}; '
        f'border:1px solid {cor}55;">{esc(status)}</span>'
    )


def cor_valor_financeiro(valor: float) -> str:
    """Verde da marca para valores positivos, coral para negativos."""
    return POSITIVO if valor >= 0 else NEGATIVO


def titulo_secao(texto: str, ajuda: str = "") -> None:
    """Subtítulo de seção com espaçamento consistente."""
    st.markdown(f"### {texto}")
    if ajuda:
        st.caption(ajuda)
