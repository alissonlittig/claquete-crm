"""
auth.py
-------
Controle de acesso ao sistema: tela de login, verificação de senha e
encerramento de sessão.

LOGIN DE DEMONSTRAÇÃO
    Esta é a versão pública de demonstração. Sem nenhuma configuração, o
    sistema aceita o usuário e a senha de DEMO_USUARIO / DEMO_SENHA, que
    aparecem na própria tela de login.

    Mesmo a senha de demonstração passa pelo mesmo caminho de uma senha
    real: ela é convertida em hash PBKDF2 uma vez, e o login compara hashes.

SENHAS PRÓPRIAS (OPCIONAL)
    Para usar senhas próprias, gere o hash com

        python scripts/gerar_senha.py

    e coloque as linhas em `.streamlit/secrets.toml` (ou em Settings → Secrets
    no Streamlit Community Cloud). Quando existe ao menos uma senha nos
    segredos, o login de demonstração deixa de valer.

    [senhas]
    Ana = "pbkdf2_sha256$200000$abc123...$def456..."

    O que fica guardado não é a senha em si, e sim um "hash" — um
    embaralhamento irreversível. Mesmo quem vê os segredos não descobre a
    senha original a partir dele.
"""

import base64
import hashlib
import hmac
import os
import secrets as py_secrets

import streamlit as st

from ui import theme

ALGORITMO = "pbkdf2_sha256"
ITERACOES = 200_000
MAX_TENTATIVAS = 5

# Credenciais exibidas na tela de login da demonstração.
DEMO_USUARIO = "demo"
DEMO_SENHA = "claquete"

# Depois deste tempo sem nenhuma interação, a sessão expira e é preciso
# entrar de novo. Protege o caso de alguém deixar o sistema aberto num
# computador compartilhado.
MINUTOS_INATIVIDADE = 240


# ---------------------------------------------------------------------------
# Geração e verificação de senha
# ---------------------------------------------------------------------------

def gerar_hash(senha: str) -> str:
    """
    Transforma uma senha em um hash seguro, no formato:
        pbkdf2_sha256$<iterações>$<sal>$<hash>

    O "sal" é um valor aleatório diferente para cada senha — é o que impede
    que duas pessoas com a mesma senha gerem o mesmo hash.
    """
    sal = py_secrets.token_hex(16)
    derivado = hashlib.pbkdf2_hmac(
        "sha256", senha.encode("utf-8"), sal.encode("utf-8"), ITERACOES
    )
    return f"{ALGORITMO}${ITERACOES}${sal}${derivado.hex()}"


def verificar_senha(senha: str, hash_guardado: str) -> bool:
    """
    Confere se a senha digitada corresponde ao hash guardado.

    Usa `hmac.compare_digest` em vez de `==` para que a comparação leve
    sempre o mesmo tempo, independentemente de quantos caracteres batem.
    """
    try:
        algoritmo, iteracoes, sal, esperado = hash_guardado.split("$")
        if algoritmo != ALGORITMO:
            return False
        derivado = hashlib.pbkdf2_hmac(
            "sha256", senha.encode("utf-8"), sal.encode("utf-8"), int(iteracoes)
        )
        return hmac.compare_digest(derivado.hex(), esperado)
    except (ValueError, AttributeError):
        return False


# ---------------------------------------------------------------------------
# Leitura dos segredos
# ---------------------------------------------------------------------------

def _senhas_dos_segredos() -> dict:
    """Senhas configuradas em st.secrets, no formato {nome: hash}."""
    try:
        senhas = st.secrets.get("senhas", {})
        return {str(nome): str(valor) for nome, valor in dict(senhas).items()}
    except Exception:
        # Nenhum arquivo de segredos encontrado — tratado como "não configurado".
        return {}


@st.cache_resource(show_spinner=False)
def _hash_demo() -> str:
    """Hash da senha de demonstração, calculado uma única vez por processo."""
    return gerar_hash(DEMO_SENHA)


def _carregar_senhas() -> tuple:
    """
    Devolve ({nome: hash}, eh_demo). Usa as senhas dos segredos quando
    existirem; senão, o usuário de demonstração.
    """
    senhas = _senhas_dos_segredos()
    if senhas:
        return senhas, False
    return {DEMO_USUARIO: _hash_demo()}, True


def usuario_logado() -> str:
    """
    Nome do usuário autenticado nesta sessão, ou string vazia.

    A cada verificação, confere também se a sessão não ficou parada por
    tempo demais — se ficou, ela é encerrada automaticamente.
    """
    usuario = st.session_state.get("auth_usuario", "")
    if not usuario:
        return ""

    from datetime import datetime, timedelta
    agora = datetime.now()
    ultimo = st.session_state.get("auth_ultima_atividade")
    if ultimo and agora - ultimo > timedelta(minutes=MINUTOS_INATIVIDADE):
        encerrar_sessao()
        return ""

    st.session_state["auth_ultima_atividade"] = agora
    return usuario


def encerrar_sessao() -> None:
    """Desloga o usuário atual."""
    for chave in ("auth_usuario", "auth_tentativas", "auth_ultima_atividade"):
        st.session_state.pop(chave, None)


# ---------------------------------------------------------------------------
# Telas
# ---------------------------------------------------------------------------

def _procurar_usuario(senhas: dict, digitado: str) -> str:
    """Nome cadastrado que corresponde ao digitado, sem diferenciar maiúsculas."""
    digitado = (digitado or "").strip().lower()
    for nome in senhas:
        if nome.lower() == digitado:
            return nome
    return ""


def _tela_login(senhas: dict, eh_demo: bool) -> None:
    """Formulário de login, exibido quando ninguém está autenticado."""
    logo = theme._logo_base64()
    img = f'<img src="data:image/png;base64,{logo}" style="width:78px" />' if logo else ""

    col_esq, col_meio, col_dir = st.columns([1, 1.5, 1])

    with col_meio:
        st.markdown(
            f"""
            <div style="text-align:center;padding:26px 0 6px 0">
                {img}
                <div style="font-family:'Space Grotesk',sans-serif;font-weight:700;
                            font-size:2.2rem;color:{theme.BRANCO};margin-top:12px">Claquete</div>
                <div style="font-size:0.8rem;color:{theme.TEXTO_SECUNDARIO};
                            letter-spacing:0.14em;text-transform:uppercase">CRM · ERP para produtoras</div>
                <div style="height:8px;width:130px;border-radius:3px;margin:16px auto 6px auto;
                            background:{theme.LISTRAS}"></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if eh_demo:
            st.markdown(
                f"""
                <div style="background:{theme.AMARELO}14;border:1px solid {theme.AMARELO}55;
                            border-radius:12px;padding:12px 16px;margin-bottom:12px">
                    <div style="color:{theme.AMARELO};font-weight:700">🎬 Demonstração</div>
                    <div style="margin-top:4px">
                        Usuário: <code>{theme.esc(DEMO_USUARIO)}</code>
                        &nbsp;·&nbsp; Senha: <code>{theme.esc(DEMO_SENHA)}</code></div>
                    <div style="color:{theme.TEXTO_SECUNDARIO};font-size:0.86rem;margin-top:6px">
                        Todos os dados são fictícios: empresa, sócios, clientes e valores.
                        Fique à vontade para cadastrar, editar e excluir — o banco volta
                        ao estado inicial a cada reinício do servidor.</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with st.container(border=True):
            st.markdown("#### Entrar no sistema")

            tentativas = st.session_state.get("auth_tentativas", 0)
            if tentativas >= MAX_TENTATIVAS:
                st.error(
                    "Muitas tentativas sem sucesso. Feche e abra a página "
                    "novamente para tentar de novo."
                )
                st.stop()

            with st.form("form_login"):
                digitado = st.text_input("Usuário")
                senha = st.text_input("Senha", type="password")
                entrar = st.form_submit_button("Entrar", width="stretch")

                if entrar:
                    usuario = _procurar_usuario(senhas, digitado)
                    if usuario and verificar_senha(senha, senhas[usuario]):
                        from datetime import datetime
                        st.session_state["auth_usuario"] = usuario
                        st.session_state["auth_ultima_atividade"] = datetime.now()
                        st.session_state.pop("auth_tentativas", None)
                        st.rerun()
                    else:
                        st.session_state["auth_tentativas"] = tentativas + 1
                        restantes = MAX_TENTATIVAS - st.session_state["auth_tentativas"]
                        if restantes > 0:
                            st.error(
                                f"Usuário ou senha incorretos. {restantes} tentativa(s) restante(s)."
                            )
                        else:
                            st.error("Muitas tentativas sem sucesso.")

    st.stop()


def exigir_login() -> str:
    """
    Porta de entrada de todas as páginas.

    Deve ser chamada logo depois de `theme.injetar_css()` e ANTES de qualquer
    conteúdo da página. Se o usuário não estiver autenticado, a tela de login
    é exibida e a execução da página é interrompida — assim nenhum dado
    financeiro chega ao navegador de quem não entrou.

    Devolve o nome do usuário autenticado.
    """
    if usuario_logado():
        return usuario_logado()

    senhas, eh_demo = _carregar_senhas()
    _tela_login(senhas, eh_demo)
    return ""
