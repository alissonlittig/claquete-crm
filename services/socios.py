"""
services/socios.py
-------------------
Regras de negócio para sócios, aportes de capital e reembolsos.

Conceito central (dívida entre a empresa e o sócio):
    Sempre que um sócio investe algo na empresa, ele registra um "aporte".
    Um aporte pode ser de dois tipos:

    1) entrou_no_caixa=True  -> o sócio depositou dinheiro na conta da
       empresa. Isso gera automaticamente um lançamento de ENTRADA no
       Fluxo de Caixa (a empresa realmente recebeu o dinheiro).

    2) entrou_no_caixa=False -> o sócio pagou uma despesa/investimento da
       empresa diretamente do próprio bolso (ex: comprou uma lente e pagou
       com cartão pessoal). Nesse caso NÃO é gerado lançamento de caixa
       (o dinheiro da empresa não se moveu), mas o valor ainda conta como
       dívida da empresa com o sócio.

    Em ambos os casos, o valor aumenta o "saldo devedor" da empresa para
    aquele sócio, até que um reembolso seja registrado (o que gera uma
    SAÍDA no Fluxo de Caixa e reduz a dívida).
"""

from typing import Optional

from db_utils import consultar, consultar_um, escalar, executar, hoje_iso, to_iso


# ---------------------------------------------------------------------------
# CRUD de sócios
# ---------------------------------------------------------------------------

def listar_socios(apenas_ativos: bool = False) -> list:
    sql = "SELECT * FROM socios"
    if apenas_ativos:
        sql += " WHERE ativo = 1"
    sql += " ORDER BY nome"
    return consultar(sql)


def obter_socio(socio_id: int) -> Optional[dict]:
    return consultar_um("SELECT * FROM socios WHERE id = ?", (socio_id,))


def criar_socio(nome: str, email: str = "", telefone: str = "",
                 data_entrada=None) -> int:
    data_entrada = to_iso(data_entrada) if data_entrada else hoje_iso()
    return executar(
        """INSERT INTO socios (nome, email, telefone, data_entrada, ativo)
           VALUES (?, ?, ?, ?, 1)""",
        (nome.strip(), email.strip(), telefone.strip(), data_entrada),
    )


def atualizar_socio(socio_id: int, nome: str, email: str, telefone: str) -> None:
    executar(
        "UPDATE socios SET nome = ?, email = ?, telefone = ? WHERE id = ?",
        (nome.strip(), email.strip(), telefone.strip(), socio_id),
    )


def alternar_ativo(socio_id: int, ativo: bool) -> None:
    executar("UPDATE socios SET ativo = ? WHERE id = ?", (1 if ativo else 0, socio_id))


# ---------------------------------------------------------------------------
# Aportes
# ---------------------------------------------------------------------------

def registrar_aporte(socio_id: int, data, descricao: str, valor: float,
                      categoria: str = "Dinheiro em Caixa",
                      entrou_no_caixa: bool = True,
                      reembolsavel: bool = True,
                      observacao: str = "") -> int:
    """
    Registra um novo aporte. Se `entrou_no_caixa` for True, cria também
    o lançamento correspondente no Fluxo de Caixa (Entrada).
    """
    data_iso = to_iso(data)
    fluxo_id = None

    if entrou_no_caixa:
        from services import financeiro  # import local evita import circular
        fluxo_id = financeiro.lancar_caixa(
            data=data_iso,
            tipo="Entrada",
            categoria="Aporte de Sócio",
            descricao=f"Aporte de {_nome_socio(socio_id)} - {descricao}",
            valor=valor,
            origem_tabela="aportes",
            origem_id=None,
            socio_id=socio_id,
        )

    aporte_id = executar(
        """INSERT INTO aportes
           (socio_id, data, descricao, categoria, valor, entrou_no_caixa,
            reembolsavel, observacao, fluxo_caixa_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (socio_id, data_iso, descricao.strip(), categoria, valor,
         1 if entrou_no_caixa else 0, 1 if reembolsavel else 0,
         observacao.strip(), fluxo_id),
    )

    if fluxo_id:
        executar(
            "UPDATE fluxo_caixa SET origem_id = ? WHERE id = ?",
            (aporte_id, fluxo_id),
        )

    return aporte_id


def listar_aportes(socio_id: Optional[int] = None,
                    data_ini: Optional[str] = None,
                    data_fim: Optional[str] = None) -> list:
    sql = """SELECT a.*, s.nome AS socio_nome FROM aportes a
             JOIN socios s ON s.id = a.socio_id WHERE 1=1"""
    params = []
    if socio_id:
        sql += " AND a.socio_id = ?"
        params.append(socio_id)
    if data_ini:
        sql += " AND a.data >= ?"
        params.append(data_ini)
    if data_fim:
        sql += " AND a.data <= ?"
        params.append(data_fim)
    sql += " ORDER BY a.data DESC, a.id DESC"
    return consultar(sql, tuple(params))


def excluir_aporte(aporte_id: int) -> None:
    aporte = consultar_um("SELECT * FROM aportes WHERE id = ?", (aporte_id,))
    if aporte and aporte["fluxo_caixa_id"]:
        executar("DELETE FROM fluxo_caixa WHERE id = ?", (aporte["fluxo_caixa_id"],))
    executar("DELETE FROM aportes WHERE id = ?", (aporte_id,))


# ---------------------------------------------------------------------------
# Reembolsos
# ---------------------------------------------------------------------------

def registrar_reembolso(socio_id: int, data, valor: float, descricao: str = "") -> int:
    from services import financeiro

    data_iso = to_iso(data)
    fluxo_id = financeiro.lancar_caixa(
        data=data_iso,
        tipo="Saída",
        categoria="Reembolso a Sócio",
        descricao=f"Reembolso para {_nome_socio(socio_id)}" + (f" - {descricao}" if descricao else ""),
        valor=valor,
        origem_tabela="reembolsos_socios",
        origem_id=None,
        socio_id=socio_id,
    )

    reembolso_id = executar(
        """INSERT INTO reembolsos_socios (socio_id, data, valor, descricao, fluxo_caixa_id)
           VALUES (?, ?, ?, ?, ?)""",
        (socio_id, data_iso, valor, descricao.strip(), fluxo_id),
    )

    executar("UPDATE fluxo_caixa SET origem_id = ? WHERE id = ?", (reembolso_id, fluxo_id))
    return reembolso_id


def listar_reembolsos(socio_id: Optional[int] = None) -> list:
    sql = """SELECT r.*, s.nome AS socio_nome FROM reembolsos_socios r
             JOIN socios s ON s.id = r.socio_id WHERE 1=1"""
    params = []
    if socio_id:
        sql += " AND r.socio_id = ?"
        params.append(socio_id)
    sql += " ORDER BY r.data DESC, r.id DESC"
    return consultar(sql, tuple(params))


# ---------------------------------------------------------------------------
# Dívida da empresa com os sócios
# ---------------------------------------------------------------------------

def saldo_devedor(socio_id: int) -> float:
    """Quanto a empresa ainda deve a este sócio (aportes - reembolsos)."""
    total_aportado = escalar(
        "SELECT SUM(valor) FROM aportes WHERE socio_id = ? AND reembolsavel = 1",
        (socio_id,),
    )
    total_reembolsado = escalar(
        "SELECT SUM(valor) FROM reembolsos_socios WHERE socio_id = ?", (socio_id,)
    )
    return round(total_aportado - total_reembolsado, 2)


def resumo_dividas() -> list:
    """
    Para cada sócio: total aportado, total reembolsado e saldo devedor.

    DESEMPENHO
        Antes esta função fazia três consultas por sócio (um laço em Python).
        Com o banco na nuvem, cada consulta é uma ida e volta pela rede, e
        esta função é usada em três telas diferentes. Agora tudo sai em uma
        única consulta agrupada.
    """
    return consultar(
        """
        SELECT
            s.id   AS socio_id,
            s.nome AS nome,
            ROUND(COALESCE(ap.total, 0), 2)        AS total_aportado,
            ROUND(COALESCE(ap.reembolsavel, 0), 2) AS total_reembolsavel,
            ROUND(COALESCE(re.total, 0), 2)        AS total_reembolsado,
            ROUND(COALESCE(ap.reembolsavel, 0) - COALESCE(re.total, 0), 2) AS saldo_devedor
        FROM socios s
        LEFT JOIN (
            SELECT socio_id,
                   SUM(valor) AS total,
                   SUM(CASE WHEN reembolsavel = 1 THEN valor ELSE 0 END) AS reembolsavel
            FROM aportes GROUP BY socio_id
        ) ap ON ap.socio_id = s.id
        LEFT JOIN (
            SELECT socio_id, SUM(valor) AS total
            FROM reembolsos_socios GROUP BY socio_id
        ) re ON re.socio_id = s.id
        ORDER BY s.nome
        """
    )


def _nome_socio(socio_id: int) -> str:
    socio = obter_socio(socio_id)
    return socio["nome"] if socio else "Sócio"
