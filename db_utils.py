"""
db_utils.py
-----------
Funções auxiliares genéricas usadas por todos os módulos de services/.
"""

import copy
import threading
import time
from datetime import datetime, date
from typing import Any, Iterable, Optional

from database import get_connection


def hoje_iso() -> str:
    """Data de hoje no formato ISO (YYYY-MM-DD), usado para salvar no banco."""
    return date.today().isoformat()


def agora_iso() -> str:
    """Timestamp completo no formato ISO, usado em campos de auditoria (criado_em)."""
    return datetime.now().isoformat(timespec="seconds")


def to_iso(valor) -> str:
    """
    Converte um valor de data vindo da interface (date, datetime ou string)
    para uma string ISO 'YYYY-MM-DD', formato padrão salvo no banco.
    """
    if isinstance(valor, str):
        return valor
    if isinstance(valor, (date, datetime)):
        return valor.strftime("%Y-%m-%d")
    raise TypeError(f"Tipo de data não suportado: {type(valor)}")


def rows_to_dicts(rows: Iterable) -> list:
    """Converte uma lista de linhas (dict-like ou tupla) em dicionários simples.
    Mantida por compatibilidade; o código interno usa `_linha_para_dict`."""
    return [dict(r) if isinstance(r, dict) else dict(r) for r in rows]


# ---------------------------------------------------------------------------
# CACHE DE LEITURA
# ---------------------------------------------------------------------------
# O Streamlit reexecuta a página inteira a cada clique. Sem cache, cada clique
# refazia todas as consultas da tela — e, com o banco hospedado na nuvem (como
# na versão em produção deste sistema), cada consulta é uma ida e volta pela
# internet.
#
# Agora o resultado de cada leitura fica guardado na memória do servidor e é
# reaproveitado nos cliques seguintes. A regra que mantém os dados corretos:
#
#   QUALQUER GRAVAÇÃO (incluir, editar, excluir) APAGA O CACHE INTEIRO.
#
# Como o sistema publicado roda num único servidor compartilhado pelos sócios,
# quando um deles grava algo, todos passam a ver o dado novo imediatamente.
# O prazo abaixo cobre apenas o caso de o banco ser alterado por FORA do
# sistema (por exemplo, por um script rodado no terminal).
SEGUNDOS_CACHE = 90

_cache = {}
_trava_cache = threading.Lock()


def limpar_cache() -> None:
    """Esquece todas as leituras guardadas. Chamado após qualquer gravação."""
    with _trava_cache:
        _cache.clear()


def _chave(tipo: str, sql: str, params) -> object:
    try:
        chave = (tipo, sql, tuple(params))
        hash(chave)
        return chave
    except TypeError:
        return None  # parâmetro que não pode ser usado como chave: sem cache


def _do_cache(chave):
    if chave is None:
        return False, None
    with _trava_cache:
        item = _cache.get(chave)
        if item and time.monotonic() - item[0] < SEGUNDOS_CACHE:
            # Cópia: as telas acrescentam campos aos resultados, e isso não
            # pode "sujar" o que está guardado.
            return True, copy.deepcopy(item[1])
    return False, None


def _guardar(chave, valor) -> None:
    if chave is None:
        return
    with _trava_cache:
        _cache[chave] = (time.monotonic(), copy.deepcopy(valor))


def _ler_com_nova_tentativa(funcao):
    """
    Executa uma leitura; se falhar (ex.: conexão expirada), abre
    uma conexão nova e tenta mais uma vez. Só é usado em LEITURAS — repetir
    uma gravação poderia duplicar um registro.
    """
    from database import descartar_conexao
    try:
        return funcao(get_connection())
    except Exception:
        descartar_conexao()
        return funcao(get_connection())


# ---------------------------------------------------------------------------
# OPERAÇÕES
# ---------------------------------------------------------------------------

def executar(sql: str, params: tuple = ()) -> int:
    """
    Executa um INSERT/UPDATE/DELETE e retorna o id do registro inserido
    (equivalente ao `lastrowid`). Funciona com qualquer driver compatível com
    a DB-API do Python (sqlite3 ou drivers de SQLite remoto).

    Toda gravação apaga o cache de leitura, para ninguém ver dado desatualizado.
    """
    from database import descartar_conexao
    conn = get_connection()
    try:
        cur = conn.execute(sql, params)
        rowid = getattr(cur, "lastrowid", None)
        if not rowid:
            rowid_row = conn.execute("SELECT last_insert_rowid()").fetchone()
            rowid = rowid_row[0] if rowid_row else None
        conn.commit()
        return rowid
    except Exception:
        # A gravação não é repetida (poderia duplicar), mas a conexão é
        # descartada para que a próxima operação comece com uma nova.
        descartar_conexao()
        raise
    finally:
        limpar_cache()
        _fechar(conn)


def _linha_para_dict(linha, colunas: list) -> dict:
    """Converte uma linha (sqlite3.Row, tupla ou já-dict) em um dict comum,
    usando os nomes de coluna do cursor — funciona com qualquer driver."""
    if isinstance(linha, dict):
        return dict(linha)
    return dict(zip(colunas, tuple(linha)))


def consultar(sql: str, params: tuple = ()) -> list:
    """Executa um SELECT e retorna uma lista de dicionários (com cache)."""
    chave = _chave("consultar", sql, params)
    achou, valor = _do_cache(chave)
    if achou:
        return valor

    def ler(conn):
        try:
            cur = conn.execute(sql, params)
            colunas = [d[0] for d in cur.description] if cur.description else []
            return [_linha_para_dict(linha, colunas) for linha in cur.fetchall()]
        finally:
            _fechar(conn)

    resultado = _ler_com_nova_tentativa(ler)
    _guardar(chave, resultado)
    return copy.deepcopy(resultado)


def consultar_um(sql: str, params: tuple = ()) -> Optional[dict]:
    """Executa um SELECT que deve retornar no máximo uma linha."""
    resultados = consultar(sql, params)
    return resultados[0] if resultados else None


def escalar(sql: str, params: tuple = (), padrao: Any = 0) -> Any:
    """Executa um SELECT que retorna um único valor (ex: SUM, COUNT), com cache."""
    chave = _chave("escalar", sql, params)
    achou, valor = _do_cache(chave)
    if not achou:
        def ler(conn):
            try:
                row = conn.execute(sql, params).fetchone()
                return None if row is None else row[0]
            finally:
                _fechar(conn)
        valor = _ler_com_nova_tentativa(ler)
        _guardar(chave, valor)
    return padrao if valor is None else valor


def _fechar(conn) -> None:
    """
    Fecha a conexão — MAS só se ela for exclusiva desta consulta.

    A conexão reaproveitada (ver `database.get_connection`) fica aberta
    durante todo o carregamento da página, então fechá-la aqui anularia
    justamente o ganho de desempenho.
    """
    from database import eh_conexao_compartilhada
    if eh_conexao_compartilhada(conn):
        return
    try:
        conn.close()
    except Exception:
        pass


def formatar_moeda(valor: float) -> str:
    """
    Formata um número como moeda no padrão brasileiro (R$ 1.234,56)
    sem depender do módulo `locale` (que nem sempre está disponível
    no Windows/VSCode com o locale pt_BR instalado).
    """
    if valor is None:
        valor = 0.0
    negativo = valor < 0
    valor = abs(valor)
    inteiro, decimal = f"{valor:,.2f}".split(".")
    inteiro = inteiro.replace(",", ".")
    resultado = f"R$ {inteiro},{decimal}"
    return f"-{resultado}" if negativo else resultado


def formatar_data_br(data_iso: Optional[str]) -> str:
    """Converte 'YYYY-MM-DD' para 'DD/MM/AAAA' para exibição."""
    if not data_iso:
        return "-"
    try:
        return datetime.strptime(data_iso[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return data_iso


def resolver_periodo(periodo, padrao_ini: date, padrao_fim: date) -> tuple:
    """
    `st.date_input` com um intervalo (tupla) retorna, enquanto o usuário não
    terminou de escolher as duas datas, apenas uma data solta (não uma tupla).
    Esta função trata esse caso e sempre devolve um par (inicio, fim) válido.
    """
    if isinstance(periodo, (tuple, list)) and len(periodo) == 2:
        return periodo[0], periodo[1]
    return padrao_ini, padrao_fim


def formatar_mes_br(referencia_mes: str) -> str:
    """Converte 'YYYY-MM' para 'Mês/AAAA' (ex: 'Setembro/2026')."""
    meses = [
        "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
        "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
    ]
    try:
        ano, mes = referencia_mes.split("-")
        return f"{meses[int(mes) - 1]}/{ano}"
    except (ValueError, IndexError):
        return referencia_mes
