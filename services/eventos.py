"""
services/eventos.py
--------------------
Regras de negócio do CRM: clientes, eventos/projetos, divisão da receita
entre empresa e sócios, e recebimentos de clientes.

Fluxo de uso típico:
    1. Cadastra o cliente.
    2. Cria o evento/projeto vinculado ao cliente, com o valor total do contrato.
    3. Define a divisão do valor entre a empresa e os sócios envolvidos.
    4. Conforme o cliente paga, registra os recebimentos. A parte que cabe à
       EMPRESA de cada recebimento entra automaticamente no Fluxo de Caixa.
       A parte de cada SÓCIO fica registrada como "ganho" dele, disponível
       no relatório de ganhos por sócio.
"""

from typing import Optional

from db_utils import agora_iso, consultar, consultar_um, escalar, executar, hoje_iso, to_iso

STATUS_EVENTO = ["Orçamento", "Confirmado", "Em Produção", "Concluído", "Cancelado"]


# ---------------------------------------------------------------------------
# CLIENTES
# ---------------------------------------------------------------------------

def listar_clientes(busca: Optional[str] = None) -> list:
    sql = "SELECT * FROM clientes WHERE 1=1"
    params = []
    if busca:
        sql += " AND (nome LIKE ? OR empresa LIKE ?)"
        params.extend([f"%{busca}%", f"%{busca}%"])
    sql += " ORDER BY nome"
    return consultar(sql, tuple(params))


def obter_cliente(cliente_id: int) -> Optional[dict]:
    return consultar_um("SELECT * FROM clientes WHERE id = ?", (cliente_id,))


def criar_cliente(nome: str, empresa: str = "", email: str = "", telefone: str = "",
                   origem: str = "", observacao: str = "") -> int:
    return executar(
        """INSERT INTO clientes (nome, empresa, email, telefone, origem, data_cadastro, observacao)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (nome.strip(), empresa.strip(), email.strip(), telefone.strip(),
         origem.strip(), hoje_iso(), observacao.strip()),
    )


def obter_ou_criar_cliente(nome: str, empresa: str = "", email: str = "",
                            telefone: str = "", origem: str = "") -> int:
    """
    Devolve o id do cliente com esse nome; se ainda não existir, cria na hora.

    É o que permite cadastrar um projeto digitando um cliente novo direto no
    formulário do projeto, sem precisar cadastrá-lo antes em outra aba.
    """
    nome = nome.strip()
    if not nome:
        raise ValueError("O nome do cliente é obrigatório.")
    existente = consultar_um(
        "SELECT id FROM clientes WHERE LOWER(nome) = LOWER(?)", (nome,)
    )
    if existente:
        return existente["id"]
    return criar_cliente(nome, empresa, email, telefone, origem or "Cadastro via projeto")


def atualizar_cliente(cliente_id: int, nome: str, empresa: str, email: str,
                       telefone: str, origem: str, observacao: str) -> None:
    executar(
        """UPDATE clientes SET nome=?, empresa=?, email=?, telefone=?, origem=?, observacao=?
           WHERE id=?""",
        (nome.strip(), empresa.strip(), email.strip(), telefone.strip(),
         origem.strip(), observacao.strip(), cliente_id),
    )


def excluir_cliente(cliente_id: int) -> None:
    """Exclui o cliente e, em cascata, seus eventos — reaproveitando `excluir_evento`
    para garantir que os lançamentos de caixa associados também sejam removidos
    de forma consistente (em vez de depender apenas do ON DELETE CASCADE do banco)."""
    for evento in listar_eventos(cliente_id=cliente_id):
        excluir_evento(evento["id"])
    executar("DELETE FROM clientes WHERE id = ?", (cliente_id,))


def ranking_clientes_por_receita(limite: int = 10, data_ini: Optional[str] = None,
                                  data_fim: Optional[str] = None) -> list:
    sql = """
        SELECT c.id, c.nome, SUM(e.valor_total) AS receita_total,
               COALESCE(SUM(r.recebido), 0) AS recebido_total
        FROM clientes c
        JOIN eventos e ON e.cliente_id = c.id
        LEFT JOIN (
            SELECT evento_id, SUM(valor) AS recebido FROM recebimentos GROUP BY evento_id
        ) r ON r.evento_id = e.id
        WHERE 1=1
    """
    params = []
    if data_ini:
        sql += " AND e.data_evento >= ?"
        params.append(data_ini)
    if data_fim:
        sql += " AND e.data_evento <= ?"
        params.append(data_fim)
    sql += " GROUP BY c.id ORDER BY receita_total DESC LIMIT ?"
    params.append(limite)
    return consultar(sql, tuple(params))


# ---------------------------------------------------------------------------
# EVENTOS / PROJETOS
# ---------------------------------------------------------------------------

def listar_eventos(cliente_id: Optional[int] = None, status: Optional[str] = None,
                    data_ini: Optional[str] = None, data_fim: Optional[str] = None) -> list:
    """Lista eventos/projetos. Se `data_ini`/`data_fim` forem informados,
    considera apenas os eventos cuja DATA DO EVENTO cai dentro do período."""
    sql = """SELECT e.*, c.nome AS cliente_nome,
                    COALESCE((SELECT SUM(valor) FROM recebimentos r WHERE r.evento_id = e.id), 0) AS total_recebido
             FROM eventos e JOIN clientes c ON c.id = e.cliente_id WHERE 1=1"""
    params = []
    if cliente_id:
        sql += " AND e.cliente_id = ?"
        params.append(cliente_id)
    if status:
        sql += " AND e.status = ?"
        params.append(status)
    if data_ini:
        sql += " AND e.data_evento >= ?"
        params.append(data_ini)
    if data_fim:
        sql += " AND e.data_evento <= ?"
        params.append(data_fim)
    sql += " ORDER BY e.data_evento DESC"
    eventos = consultar(sql, tuple(params))
    for ev in eventos:
        ev["total_pendente"] = round(ev["valor_total"] - ev["total_recebido"], 2)
    return eventos


def obter_evento(evento_id: int) -> Optional[dict]:
    evento = consultar_um(
        """SELECT e.*, c.nome AS cliente_nome FROM eventos e
           JOIN clientes c ON c.id = e.cliente_id WHERE e.id = ?""",
        (evento_id,),
    )
    if not evento:
        return None
    evento["anexos"] = consultar(
        "SELECT * FROM anexos_evento WHERE evento_id = ? ORDER BY tipo, id",
        (evento_id,),
    )
    evento["recebimentos"] = consultar(
        "SELECT * FROM recebimentos WHERE evento_id = ? ORDER BY data DESC", (evento_id,)
    )
    evento["total_recebido"] = round(sum(r["valor"] for r in evento["recebimentos"]), 2)
    evento["total_pendente"] = round(evento["valor_total"] - evento["total_recebido"], 2)
    return evento


def criar_evento(cliente_id: int, nome: str, tipo: str, data_evento,
                  valor_total: float, status: str = "Orçamento", observacao: str = "") -> int:
    return executar(
        """INSERT INTO eventos (cliente_id, nome, tipo, data_evento, valor_total, status, observacao, criado_em)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (cliente_id, nome.strip(), tipo.strip(), to_iso(data_evento),
         valor_total, status, observacao.strip(), agora_iso()),
    )


def atualizar_evento(evento_id: int, nome: str, tipo: str, data_evento,
                      valor_total: float, status: str, observacao: str,
                      cliente_id: Optional[int] = None) -> None:
    """
    Atualiza os dados do projeto.
    """
    if cliente_id:
        executar(
            """UPDATE eventos SET cliente_id=?, nome=?, tipo=?, data_evento=?, valor_total=?,
                                  status=?, observacao=? WHERE id=?""",
            (cliente_id, nome.strip(), tipo.strip(), to_iso(data_evento), valor_total,
             status, observacao.strip(), evento_id),
        )
    else:
        executar(
            """UPDATE eventos SET nome=?, tipo=?, data_evento=?, valor_total=?, status=?, observacao=?
               WHERE id=?""",
            (nome.strip(), tipo.strip(), to_iso(data_evento), valor_total,
             status, observacao.strip(), evento_id),
        )



def atualizar_status(evento_id: int, status: str) -> None:
    """Atualiza apenas o status do projeto (usado pelo seletor rápido)."""
    executar("UPDATE eventos SET status = ? WHERE id = ?", (status, evento_id))


def excluir_evento(evento_id: int) -> None:
    recebimentos = consultar("SELECT * FROM recebimentos WHERE evento_id = ?", (evento_id,))
    for r in recebimentos:
        if r["fluxo_caixa_id"]:
            executar("DELETE FROM fluxo_caixa WHERE id = ?", (r["fluxo_caixa_id"],))
    executar("DELETE FROM eventos WHERE id = ?", (evento_id,))


def funil_status(data_ini: Optional[str] = None, data_fim: Optional[str] = None) -> list:
    sql = """SELECT status, COUNT(*) AS quantidade, COALESCE(SUM(valor_total), 0) AS valor
             FROM eventos WHERE 1=1"""
    params = []
    if data_ini:
        sql += " AND data_evento >= ?"
        params.append(data_ini)
    if data_fim:
        sql += " AND data_evento <= ?"
        params.append(data_fim)
    sql += " GROUP BY status"
    return consultar(sql, tuple(params))


# ---------------------------------------------------------------------------
# RECEBIMENTOS DE CLIENTES
# ---------------------------------------------------------------------------

def registrar_recebimento(evento_id: int, data, valor: float,
                           forma_pagamento: str = "", observacao: str = "",
                           link_recibo: str = "") -> int:
    """
    Registra um pagamento do cliente.

    O valor INTEIRO entra como entrada no Fluxo de Caixa da empresa. Os sócios
    são remunerados por pró-labore fixo (cadastrado em Custos Fixos), e não
    mais por uma fatia de cada projeto — por isso não há mais divisão de
    receita por participante.

    `link_recibo` guarda o endereço do comprovante no Drive, quando houver.
    """
    data_iso = to_iso(data)

    evento = consultar_um("SELECT nome FROM eventos WHERE id = ?", (evento_id,))
    nome_evento = evento["nome"] if evento else f"Evento #{evento_id}"

    from services import financeiro
    fluxo_id = financeiro.lancar_caixa(
        data=data_iso, tipo="Entrada", categoria="Receita de Projeto",
        descricao=f"{nome_evento} - recebimento de cliente",
        valor=valor, origem_tabela="recebimentos", origem_id=None,
    )

    recebimento_id = executar(
        """INSERT INTO recebimentos
           (evento_id, data, valor, forma_pagamento, observacao, link_recibo, fluxo_caixa_id)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (evento_id, data_iso, valor, forma_pagamento.strip(), observacao.strip(),
         link_recibo.strip(), fluxo_id),
    )

    executar("UPDATE fluxo_caixa SET origem_id = ? WHERE id = ?", (recebimento_id, fluxo_id))
    return recebimento_id


def excluir_recebimento(recebimento_id: int) -> None:
    receb = consultar_um("SELECT * FROM recebimentos WHERE id = ?", (recebimento_id,))
    if receb and receb["fluxo_caixa_id"]:
        executar("DELETE FROM fluxo_caixa WHERE id = ?", (receb["fluxo_caixa_id"],))
    executar("DELETE FROM recebimentos WHERE id = ?", (recebimento_id,))


# ---------------------------------------------------------------------------
# ANEXOS DO PROJETO (links de contratos, notas fiscais, recibos)
# ---------------------------------------------------------------------------

TIPOS_ANEXO = ["Contrato", "Nota Fiscal", "Recibo", "Briefing", "Entrega", "Outro"]


def adicionar_anexo(evento_id: int, tipo: str, url: str, descricao: str = "") -> int:
    """Guarda o LINK de um documento do projeto (o arquivo continua no Drive)."""
    url = (url or "").strip()
    if not url:
        raise ValueError("Informe o link do documento.")
    if len(url) > 2000:
        raise ValueError("O link é longo demais (máximo 2000 caracteres).")

    # Só aceitamos http/https. Isso bloqueia endereços perigosos como
    # "javascript:..." ou "data:...", que poderiam executar código no
    # navegador de quem clicasse no link.
    normalizada = url.lower().replace("\t", "").replace("\n", "").replace("\r", "")
    if not normalizada.startswith(("http://", "https://")):
        raise ValueError("O link precisa começar com http:// ou https://")
    if any(c in url for c in "()[]"):
        raise ValueError("O link não pode conter parênteses ou colchetes.")
    return executar(
        """INSERT INTO anexos_evento (evento_id, tipo, descricao, url, data_cadastro)
           VALUES (?, ?, ?, ?, ?)""",
        (evento_id, tipo, descricao.strip(), url, hoje_iso()),
    )


def listar_anexos(evento_id: int, tipo: Optional[str] = None) -> list:
    sql = "SELECT * FROM anexos_evento WHERE evento_id = ?"
    params = [evento_id]
    if tipo:
        sql += " AND tipo = ?"
        params.append(tipo)
    sql += " ORDER BY tipo, id"
    return consultar(sql, tuple(params))


def excluir_anexo(anexo_id: int) -> None:
    executar("DELETE FROM anexos_evento WHERE id = ?", (anexo_id,))
