"""
services/financeiro.py
-----------------------
Regras de negócio para o Fluxo de Caixa (livro-razão único), Custos Fixos
e Investimentos (equipamentos e softwares).
"""

import calendar
from datetime import date
from typing import Optional

from db_utils import agora_iso, consultar, consultar_um, escalar, executar, hoje_iso, to_iso


# ---------------------------------------------------------------------------
# FLUXO DE CAIXA (livro-razão)
# ---------------------------------------------------------------------------

def lancar_caixa(data, tipo: str, categoria: str, descricao: str, valor: float,
                  origem_tabela: str = "manual", origem_id: Optional[int] = None,
                  socio_id: Optional[int] = None) -> int:
    """
    Insere um lançamento no Fluxo de Caixa. Esta é a ÚNICA função do sistema
    que deve escrever na tabela `fluxo_caixa` — todas as automações
    (aportes, recebimentos, custos fixos pagos, investimentos) passam por ela,
    garantindo que o caixa da empresa seja sempre uma fonte única da verdade.
    """
    assert tipo in ("Entrada", "Saída"), "tipo deve ser 'Entrada' ou 'Saída'"
    assert valor > 0, "valor do lançamento deve ser positivo"
    return executar(
        """INSERT INTO fluxo_caixa
           (data, tipo, categoria, descricao, valor, origem_tabela, origem_id, socio_id, criado_em)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (to_iso(data), tipo, categoria, descricao.strip(), valor,
         origem_tabela, origem_id, socio_id, agora_iso()),
    )


def lancamento_manual(data, tipo: str, categoria: str, descricao: str, valor: float) -> int:
    """Atalho para lançar uma movimentação de caixa manual (fora das automações)."""
    return lancar_caixa(data, tipo, categoria, descricao, valor, origem_tabela="manual")


def excluir_lancamento(fluxo_id: int) -> None:
    executar("DELETE FROM fluxo_caixa WHERE id = ?", (fluxo_id,))


def listar_fluxo(data_ini: Optional[str] = None, data_fim: Optional[str] = None,
                  tipo: Optional[str] = None, categoria: Optional[str] = None) -> list:
    sql = "SELECT * FROM fluxo_caixa WHERE 1=1"
    params = []
    if data_ini:
        sql += " AND data >= ?"
        params.append(data_ini)
    if data_fim:
        sql += " AND data <= ?"
        params.append(data_fim)
    if tipo:
        sql += " AND tipo = ?"
        params.append(tipo)
    if categoria:
        sql += " AND categoria = ?"
        params.append(categoria)
    sql += " ORDER BY data DESC, id DESC"
    return consultar(sql, tuple(params))


def categorias_existentes() -> list:
    linhas = consultar("SELECT DISTINCT categoria FROM fluxo_caixa ORDER BY categoria")
    return [l["categoria"] for l in linhas]


def saldo_caixa(ate_data: Optional[str] = None) -> float:
    sql_entrada = "SELECT SUM(valor) FROM fluxo_caixa WHERE tipo = 'Entrada'"
    sql_saida = "SELECT SUM(valor) FROM fluxo_caixa WHERE tipo = 'Saída'"
    params = ()
    if ate_data:
        sql_entrada += " AND data <= ?"
        sql_saida += " AND data <= ?"
        params = (ate_data,)
    entradas = escalar(sql_entrada, params)
    saidas = escalar(sql_saida, params)
    return round(entradas - saidas, 2)


def totais_periodo(data_ini: str, data_fim: str) -> dict:
    entradas = escalar(
        "SELECT SUM(valor) FROM fluxo_caixa WHERE tipo='Entrada' AND data BETWEEN ? AND ?",
        (data_ini, data_fim),
    )
    saidas = escalar(
        "SELECT SUM(valor) FROM fluxo_caixa WHERE tipo='Saída' AND data BETWEEN ? AND ?",
        (data_ini, data_fim),
    )
    return {"entradas": round(entradas, 2), "saidas": round(saidas, 2),
            "saldo": round(entradas - saidas, 2)}


def evolucao_mensal(meses: Optional[int] = 12, data_ini: Optional[str] = None,
                     data_fim: Optional[str] = None) -> list:
    """
    Retorna, mês a mês, o total de entradas, saídas e o saldo acumulado.

    O saldo acumulado é sempre calculado desde o primeiro lançamento da
    empresa (para refletir o caixa real), mas apenas os meses dentro do
    período escolhido são devolvidos para o gráfico.
    """
    linhas = consultar(
        """
        SELECT strftime('%Y-%m', data) AS mes,
               SUM(CASE WHEN tipo = 'Entrada' THEN valor ELSE 0 END) AS entradas,
               SUM(CASE WHEN tipo = 'Saída' THEN valor ELSE 0 END) AS saidas
        FROM fluxo_caixa
        GROUP BY mes
        ORDER BY mes
        """
    )
    saldo_acumulado = 0.0
    for linha in linhas:
        saldo_acumulado += linha["entradas"] - linha["saidas"]
        linha["saldo_acumulado"] = round(saldo_acumulado, 2)

    if data_ini or data_fim:
        mes_ini = data_ini[:7] if data_ini else "0000-00"
        mes_fim = data_fim[:7] if data_fim else "9999-99"
        linhas = [l for l in linhas if mes_ini <= l["mes"] <= mes_fim]

    if meses and len(linhas) > meses:
        linhas = linhas[-meses:]
    return linhas


def distribuicao_saidas_por_categoria(data_ini: Optional[str] = None,
                                       data_fim: Optional[str] = None) -> list:
    sql = """SELECT categoria, SUM(valor) AS total FROM fluxo_caixa
             WHERE tipo = 'Saída'"""
    params = []
    if data_ini:
        sql += " AND data >= ?"
        params.append(data_ini)
    if data_fim:
        sql += " AND data <= ?"
        params.append(data_fim)
    sql += " GROUP BY categoria ORDER BY total DESC"
    return consultar(sql, tuple(params))


# ---------------------------------------------------------------------------
# CUSTOS FIXOS
# ---------------------------------------------------------------------------

def listar_custos_fixos(apenas_ativos: bool = False) -> list:
    sql = "SELECT * FROM custos_fixos"
    if apenas_ativos:
        sql += " WHERE ativo = 1"
    sql += " ORDER BY nome"
    return consultar(sql)


def criar_custo_fixo(nome: str, categoria: str, valor: float,
                      dia_vencimento: int, data_inicio=None, observacao: str = "") -> int:
    data_inicio = to_iso(data_inicio) if data_inicio else hoje_iso()
    return executar(
        """INSERT INTO custos_fixos
           (nome, categoria, valor, dia_vencimento, data_inicio, ativo, observacao)
           VALUES (?, ?, ?, ?, ?, 1, ?)""",
        (nome.strip(), categoria, valor, dia_vencimento, data_inicio, observacao.strip()),
    )


def atualizar_custo_fixo(custo_id: int, nome: str, categoria: str, valor: float,
                          dia_vencimento: int, observacao: str = "") -> None:
    executar(
        """UPDATE custos_fixos SET nome=?, categoria=?, valor=?, dia_vencimento=?, observacao=?
           WHERE id=?""",
        (nome.strip(), categoria, valor, dia_vencimento, observacao.strip(), custo_id),
    )


def alternar_ativo_custo_fixo(custo_id: int, ativo: bool) -> None:
    executar("UPDATE custos_fixos SET ativo = ? WHERE id = ?", (1 if ativo else 0, custo_id))


def excluir_custo_fixo(custo_id: int) -> dict:
    """
    Exclui um custo fixo e todas as contas mensais geradas a partir dele.

    Contas que já foram PAGAS também têm o lançamento removido do Fluxo de
    Caixa, para o saldo continuar batendo. Devolve um resumo do que foi
    apagado, para a tela poder avisar o usuário antes/depois.
    """
    pagamentos = consultar(
        "SELECT * FROM custos_fixos_pagamentos WHERE custo_fixo_id = ?", (custo_id,)
    )
    pagos = [p for p in pagamentos if p["pago"]]
    for pagamento in pagamentos:
        if pagamento["fluxo_caixa_id"]:
            executar("DELETE FROM fluxo_caixa WHERE id = ?", (pagamento["fluxo_caixa_id"],))
    executar("DELETE FROM custos_fixos_pagamentos WHERE custo_fixo_id = ?", (custo_id,))
    executar("DELETE FROM custos_fixos WHERE id = ?", (custo_id,))
    return {
        "contas_removidas": len(pagamentos),
        "pagamentos_estornados": len(pagos),
        "valor_estornado": round(sum(p["valor"] for p in pagos), 2),
    }


def contar_pagamentos_do_custo(custo_id: int) -> dict:
    """Quantas contas existem para um custo fixo (usado para avisar antes de excluir)."""
    total = escalar(
        "SELECT COUNT(*) FROM custos_fixos_pagamentos WHERE custo_fixo_id = ?", (custo_id,)
    )
    pagas = escalar(
        "SELECT COUNT(*) FROM custos_fixos_pagamentos WHERE custo_fixo_id = ? AND pago = 1",
        (custo_id,),
    )
    return {"total": total, "pagas": pagas}


def categorias_custos_existentes() -> list:
    """Categorias já usadas, para sugerir na hora de cadastrar um custo novo."""
    linhas = consultar(
        "SELECT DISTINCT categoria FROM custos_fixos WHERE categoria <> '' ORDER BY categoria"
    )
    return [l["categoria"] for l in linhas]


def gerar_lancamentos_do_mes(referencia_mes: str) -> int:
    """
    Automação: cria (se ainda não existir) a "conta a pagar" do mês de
    referência ('YYYY-MM') para cada custo fixo ativo. Retorna quantos
    lançamentos novos foram criados. Pode ser chamado manualmente pela
    interface ou agendado via cron/Agendador de Tarefas (ver README).
    """
    ano, mes = (int(p) for p in referencia_mes.split("-"))
    ultimo_dia_mes = calendar.monthrange(ano, mes)[1]
    criados = 0
    for custo in listar_custos_fixos(apenas_ativos=True):
        ja_existe = consultar_um(
            "SELECT id FROM custos_fixos_pagamentos WHERE custo_fixo_id=? AND referencia_mes=?",
            (custo["id"], referencia_mes),
        )
        if ja_existe:
            continue
        dia = min(custo["dia_vencimento"] or 5, ultimo_dia_mes)
        vencimento = date(ano, mes, dia).isoformat()
        executar(
            """INSERT INTO custos_fixos_pagamentos
               (custo_fixo_id, referencia_mes, data_vencimento, valor, pago)
               VALUES (?, ?, ?, ?, 0)""",
            (custo["id"], referencia_mes, vencimento, custo["valor"]),
        )
        criados += 1
    return criados


def marcar_pagamento(pagamento_id: int, data_pagamento=None) -> None:
    """Marca uma conta de custo fixo como paga e lança a saída no caixa."""
    pagamento = consultar_um(
        "SELECT p.*, c.nome AS custo_nome, c.categoria AS custo_categoria "
        "FROM custos_fixos_pagamentos p JOIN custos_fixos c ON c.id = p.custo_fixo_id "
        "WHERE p.id = ?",
        (pagamento_id,),
    )
    if not pagamento or pagamento["pago"]:
        return
    data_pagamento = to_iso(data_pagamento) if data_pagamento else hoje_iso()
    fluxo_id = lancar_caixa(
        data=data_pagamento,
        tipo="Saída",
        categoria="Custo Fixo",
        descricao=f"{pagamento['custo_nome']} ({pagamento['referencia_mes']})",
        valor=pagamento["valor"],
        origem_tabela="custos_fixos_pagamentos",
        origem_id=pagamento_id,
    )
    executar(
        "UPDATE custos_fixos_pagamentos SET pago=1, data_pagamento=?, fluxo_caixa_id=? WHERE id=?",
        (data_pagamento, fluxo_id, pagamento_id),
    )


def desmarcar_pagamento(pagamento_id: int) -> None:
    """
    Desfaz o pagamento de uma conta de custo fixo: remove o lançamento de
    saída correspondente do Fluxo de Caixa e devolve a conta para "pendente".
    Útil quando alguém marca como pago por engano.
    """
    pagamento = consultar_um(
        "SELECT * FROM custos_fixos_pagamentos WHERE id = ?", (pagamento_id,)
    )
    if not pagamento or not pagamento["pago"]:
        return
    if pagamento["fluxo_caixa_id"]:
        executar("DELETE FROM fluxo_caixa WHERE id = ?", (pagamento["fluxo_caixa_id"],))
    executar(
        """UPDATE custos_fixos_pagamentos
           SET pago = 0, data_pagamento = NULL, fluxo_caixa_id = NULL WHERE id = ?""",
        (pagamento_id,),
    )


def atualizar_pagamento(pagamento_id: int, valor: float, data_vencimento) -> None:
    """
    Edita o valor e o vencimento de uma conta do mês. Se a conta já estiver
    paga, o lançamento no Fluxo de Caixa é atualizado junto, para o caixa
    continuar batendo.
    """
    pagamento = consultar_um(
        "SELECT * FROM custos_fixos_pagamentos WHERE id = ?", (pagamento_id,)
    )
    if not pagamento:
        return
    data_venc_iso = to_iso(data_vencimento)
    executar(
        "UPDATE custos_fixos_pagamentos SET valor = ?, data_vencimento = ? WHERE id = ?",
        (valor, data_venc_iso, pagamento_id),
    )
    if pagamento["pago"] and pagamento["fluxo_caixa_id"]:
        executar(
            "UPDATE fluxo_caixa SET valor = ? WHERE id = ?",
            (valor, pagamento["fluxo_caixa_id"]),
        )


def excluir_pagamento(pagamento_id: int) -> None:
    """Remove a conta do mês (e o lançamento de caixa, se já estava paga)."""
    pagamento = consultar_um(
        "SELECT * FROM custos_fixos_pagamentos WHERE id = ?", (pagamento_id,)
    )
    if not pagamento:
        return
    if pagamento["fluxo_caixa_id"]:
        executar("DELETE FROM fluxo_caixa WHERE id = ?", (pagamento["fluxo_caixa_id"],))
    executar("DELETE FROM custos_fixos_pagamentos WHERE id = ?", (pagamento_id,))


def listar_pagamentos_custos_fixos(referencia_mes: Optional[str] = None,
                                    apenas_pendentes: bool = False) -> list:
    sql = """SELECT p.*, c.nome AS custo_nome, c.categoria AS custo_categoria
             FROM custos_fixos_pagamentos p JOIN custos_fixos c ON c.id = p.custo_fixo_id
             WHERE 1=1"""
    params = []
    if referencia_mes:
        sql += " AND p.referencia_mes = ?"
        params.append(referencia_mes)
    if apenas_pendentes:
        sql += " AND p.pago = 0"
    sql += " ORDER BY p.referencia_mes DESC, c.nome"
    return consultar(sql, tuple(params))


def total_custos_fixos_mensais(apenas_ativos: bool = True) -> float:
    """Soma o valor mensal comprometido com custos fixos (visão 'orçamento')."""
    return escalar(
        f"SELECT SUM(valor) FROM custos_fixos {'WHERE ativo = 1' if apenas_ativos else ''}"
    )


# ---------------------------------------------------------------------------
# INVESTIMENTOS (equipamentos e softwares)
# ---------------------------------------------------------------------------

def criar_investimento(nome: str, categoria: str, valor: float, data_compra,
                        fornecedor: str = "", vida_util_meses: Optional[int] = None,
                        forma_pagamento: str = "Caixa da Empresa",
                        socio_id: Optional[int] = None, observacao: str = "") -> int:
    """
    Registra a compra de um equipamento/software.

    - forma_pagamento = 'Caixa da Empresa': gera SAÍDA no fluxo de caixa.
    - forma_pagamento = 'Sócio': não mexe no caixa da empresa; em vez disso
      gera automaticamente um APORTE (não reembolsado em dinheiro, mas que
      conta como dívida da empresa com aquele sócio) — exatamente como
      quando um sócio compra um equipamento do próprio bolso.
    """
    data_iso = to_iso(data_compra)
    fluxo_id = None
    aporte_id = None

    if forma_pagamento == "Caixa da Empresa":
        fluxo_id = lancar_caixa(
            data=data_iso, tipo="Saída", categoria="Investimento",
            descricao=f"{categoria}: {nome}", valor=valor,
            origem_tabela="investimentos", origem_id=None,
        )
    elif forma_pagamento == "Sócio":
        if not socio_id:
            raise ValueError("socio_id é obrigatório quando forma_pagamento='Sócio'")
        from services import socios as socios_service
        aporte_id = socios_service.registrar_aporte(
            socio_id=socio_id, data=data_iso,
            descricao=f"Compra de {categoria.lower()}: {nome}",
            valor=valor, categoria="Investimento",
            entrou_no_caixa=False, reembolsavel=True,
            observacao=observacao,
        )

    investimento_id = executar(
        """INSERT INTO investimentos
           (nome, categoria, valor, data_compra, fornecedor, vida_util_meses,
            forma_pagamento, socio_id, observacao, fluxo_caixa_id, aporte_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (nome.strip(), categoria, valor, data_iso, fornecedor.strip(),
         vida_util_meses, forma_pagamento, socio_id, observacao.strip(),
         fluxo_id, aporte_id),
    )

    if fluxo_id:
        executar("UPDATE fluxo_caixa SET origem_id = ? WHERE id = ?", (investimento_id, fluxo_id))

    return investimento_id


def listar_investimentos(categoria: Optional[str] = None,
                          data_ini: Optional[str] = None,
                          data_fim: Optional[str] = None) -> list:
    sql = """SELECT i.*, s.nome AS socio_nome FROM investimentos i
             LEFT JOIN socios s ON s.id = i.socio_id WHERE 1=1"""
    params = []
    if categoria:
        sql += " AND i.categoria = ?"
        params.append(categoria)
    if data_ini:
        sql += " AND i.data_compra >= ?"
        params.append(data_ini)
    if data_fim:
        sql += " AND i.data_compra <= ?"
        params.append(data_fim)
    sql += " ORDER BY i.data_compra DESC"
    return consultar(sql, tuple(params))


def excluir_investimento(investimento_id: int) -> None:
    inv = consultar_um("SELECT * FROM investimentos WHERE id = ?", (investimento_id,))
    if not inv:
        return
    if inv["fluxo_caixa_id"]:
        executar("DELETE FROM fluxo_caixa WHERE id = ?", (inv["fluxo_caixa_id"],))
    if inv["aporte_id"]:
        from services import socios as socios_service
        socios_service.excluir_aporte(inv["aporte_id"])
    executar("DELETE FROM investimentos WHERE id = ?", (investimento_id,))


def total_investido(categoria: Optional[str] = None,
                     data_ini: Optional[str] = None, data_fim: Optional[str] = None) -> float:
    sql = "SELECT SUM(valor) FROM investimentos WHERE 1=1"
    params = []
    if categoria:
        sql += " AND categoria = ?"
        params.append(categoria)
    if data_ini:
        sql += " AND data_compra >= ?"
        params.append(data_ini)
    if data_fim:
        sql += " AND data_compra <= ?"
        params.append(data_fim)
    return escalar(sql, tuple(params))


def depreciacao_mensal_total() -> float:
    """Soma da depreciação mensal (linear) de todos os investimentos com vida útil definida."""
    linhas = consultar(
        "SELECT valor, vida_util_meses FROM investimentos WHERE vida_util_meses > 0"
    )
    return round(sum(l["valor"] / l["vida_util_meses"] for l in linhas), 2)
