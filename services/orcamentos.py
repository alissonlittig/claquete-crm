"""
services/orcamentos.py
-----------------------
Precificação de projetos e geração de propostas comerciais.

COMO O CÁLCULO FUNCIONA
    Cada linha do orçamento é uma etapa do trabalho, e seu valor é:

        quantidade  ×  pessoas  ×  valor_unitario

    Exemplos:
      - "Captação" · 6 horas · 2 pessoas · R$ 120/hora  ->  R$ 1.440
      - "Deslocamento" · 1 vez · 3 pessoas · R$ 50     ->  R$ 150
      - "Social media" · 1 mês · 1 · R$ 1.200/mês      ->  R$ 1.200

    Sobre o total pode incidir um desconto percentual.

A TABELA DE PREÇOS
    Os valores por hora/unidade ficam na tabela `precos_servicos` e são
    editáveis na própria tela. Na primeira vez, o sistema sugere uma lista
    inicial de serviços típicos de produtora — todos com valor que a produtora
    deve ajustar à sua realidade.
"""

from typing import Optional

from db_utils import agora_iso, consultar, consultar_um, escalar, executar, hoje_iso, to_iso

CATEGORIAS = ["Produção", "Pós-produção", "Logística", "Gestão", "Mídia", "Outro"]
STATUS = ["Rascunho", "Enviado", "Aprovado", "Recusado"]

# Lista inicial sugerida. Os valores são um ponto de partida — a produtora
# ajusta cada um na aba "Tabela de Preços".
PRECOS_INICIAIS = [
    ("Captação de vídeo", "hora", 180.00, "Produção", 1),
    ("Captação de fotos", "hora", 150.00, "Produção", 2),
    ("Direção / Roteiro", "hora", 170.00, "Produção", 3),
    ("Drone (diária)", "diária", 600.00, "Produção", 4),
    ("Edição de vídeo", "hora", 140.00, "Pós-produção", 5),
    ("Tratamento de fotos", "hora", 95.00, "Pós-produção", 6),
    ("Motion graphics", "hora", 190.00, "Pós-produção", 7),
    ("Trilha e mixagem de áudio", "hora", 130.00, "Pós-produção", 8),
    # Valor fixo por pessoa (e não mais por km): quantidade = nº de
    # deslocamentos, multiplicado pelas pessoas que vão.
    ("Deslocamento", "vez", 50.00, "Logística", 9),
    ("Diária de equipamento extra", "diária", 350.00, "Logística", 10),
    ("Social media (gestão mensal)", "mês", 1500.00, "Mídia", 11),
    ("Gestão de tráfego pago", "mês", 1100.00, "Mídia", 12),
    ("Reunião / Alinhamento com cliente", "hora", 110.00, "Gestão", 13),
]


# ---------------------------------------------------------------------------
# TABELA DE PREÇOS
# ---------------------------------------------------------------------------

def garantir_precos_iniciais() -> None:
    """Cria a lista sugerida de serviços na primeira vez que a tela é aberta."""
    if escalar("SELECT COUNT(*) FROM precos_servicos") > 0:
        return
    for nome, unidade, valor, categoria, ordem in PRECOS_INICIAIS:
        executar(
            """INSERT INTO precos_servicos (nome, unidade, valor_unitario, categoria, ativo, ordem)
               VALUES (?, ?, ?, ?, 1, ?)""",
            (nome, unidade, valor, categoria, ordem),
        )


def listar_precos(apenas_ativos: bool = False) -> list:
    sql = "SELECT * FROM precos_servicos"
    if apenas_ativos:
        sql += " WHERE ativo = 1"
    sql += " ORDER BY ordem, nome"
    return consultar(sql)


def criar_preco(nome: str, unidade: str, valor_unitario: float,
                 categoria: str = "Produção") -> int:
    if not nome.strip():
        raise ValueError("Informe o nome do serviço.")
    proxima_ordem = escalar("SELECT COALESCE(MAX(ordem), 0) + 1 FROM precos_servicos")
    return executar(
        """INSERT INTO precos_servicos (nome, unidade, valor_unitario, categoria, ativo, ordem)
           VALUES (?, ?, ?, ?, 1, ?)""",
        (nome.strip(), unidade.strip() or "hora", valor_unitario,
         categoria.strip() or "Outro", proxima_ordem),
    )


def atualizar_preco(preco_id: int, nome: str, unidade: str,
                     valor_unitario: float, categoria: str) -> None:
    executar(
        """UPDATE precos_servicos SET nome=?, unidade=?, valor_unitario=?, categoria=?
           WHERE id=?""",
        (nome.strip(), unidade.strip() or "hora", valor_unitario,
         categoria.strip() or "Outro", preco_id),
    )


def alternar_ativo_preco(preco_id: int, ativo: bool) -> None:
    executar("UPDATE precos_servicos SET ativo = ? WHERE id = ?",
             (1 if ativo else 0, preco_id))


def excluir_preco(preco_id: int) -> None:
    executar("DELETE FROM precos_servicos WHERE id = ?", (preco_id,))


# ---------------------------------------------------------------------------
# ORÇAMENTOS
# ---------------------------------------------------------------------------

def criar_orcamento(titulo: str, cliente_nome: str, data=None,
                     cliente_id: Optional[int] = None, validade_dias: int = 15,
                     observacoes: str = "", condicoes: str = "") -> int:
    if not titulo.strip():
        raise ValueError("Informe o título do orçamento.")
    if not cliente_nome.strip():
        raise ValueError("Informe o nome do cliente.")
    return executar(
        """INSERT INTO orcamentos
           (titulo, cliente_id, cliente_nome, data, validade_dias, status,
            desconto_percent, observacoes, condicoes, criado_em)
           VALUES (?, ?, ?, ?, ?, 'Rascunho', 0, ?, ?, ?)""",
        (titulo.strip(), cliente_id, cliente_nome.strip(),
         to_iso(data) if data else hoje_iso(), validade_dias,
         observacoes.strip(), condicoes.strip(), agora_iso()),
    )


def listar_orcamentos(status: Optional[str] = None,
                       data_ini: Optional[str] = None,
                       data_fim: Optional[str] = None) -> list:
    sql = "SELECT * FROM orcamentos WHERE 1=1"
    params = []
    if status:
        sql += " AND status = ?"
        params.append(status)
    if data_ini:
        sql += " AND data >= ?"
        params.append(data_ini)
    if data_fim:
        sql += " AND data <= ?"
        params.append(data_fim)
    sql += " ORDER BY data DESC, id DESC"

    orcamentos = consultar(sql, tuple(params))
    if not orcamentos:
        return []

    # Soma todos os itens de todos os orçamentos numa consulta só, em vez de
    # consultar item por item (o que custava caro com o banco na nuvem).
    somas = {
        linha["orcamento_id"]: linha
        for linha in consultar(
            """
            SELECT orcamento_id,
                   SUM(quantidade * pessoas * valor_unitario) AS subtotal,
                   SUM(CASE WHEN unidade = 'hora' THEN quantidade * pessoas ELSE 0 END) AS horas,
                   COUNT(*) AS itens
            FROM orcamento_itens GROUP BY orcamento_id
            """
        )
    }

    for o in orcamentos:
        soma = somas.get(o["id"], {})
        subtotal = round(soma.get("subtotal", 0) or 0, 2)
        desconto = o["desconto_percent"] or 0
        valor_desconto = round(subtotal * desconto / 100.0, 2)
        horas = round(soma.get("horas", 0) or 0, 1)
        total = round(subtotal - valor_desconto, 2)
        o.update({
            "subtotal": subtotal,
            "valor_desconto": valor_desconto,
            "total": total,
            "horas_totais": horas,
            "valor_hora_efetivo": round(total / horas, 2) if horas else 0.0,
            "quantidade_itens": soma.get("itens", 0) or 0,
        })
    return orcamentos


def obter_orcamento(orcamento_id: int) -> Optional[dict]:
    orcamento = consultar_um("SELECT * FROM orcamentos WHERE id = ?", (orcamento_id,))
    if not orcamento:
        return None
    orcamento["itens"] = listar_itens(orcamento_id)
    orcamento.update(calcular_totais(orcamento_id))
    return orcamento


def atualizar_orcamento(orcamento_id: int, titulo: str, cliente_nome: str, data,
                         validade_dias: int, status: str, desconto_percent: float,
                         observacoes: str, condicoes: str,
                         responsavel_nome: str = "", cliente_contato: str = "",
                         cliente_email: str = "", cliente_telefone: str = "",
                         data_evento=None, prazo_entrega: str = "",
                         escopo: str = "") -> None:
    executar(
        """UPDATE orcamentos SET titulo=?, cliente_nome=?, data=?, validade_dias=?,
                                 status=?, desconto_percent=?, observacoes=?, condicoes=?,
                                 responsavel_nome=?, cliente_contato=?, cliente_email=?,
                                 cliente_telefone=?, data_evento=?, prazo_entrega=?, escopo=?
           WHERE id=?""",
        (titulo.strip(), cliente_nome.strip(), to_iso(data), validade_dias,
         status, desconto_percent, observacoes.strip(), condicoes.strip(),
         (responsavel_nome or "").strip(), (cliente_contato or "").strip(),
         (cliente_email or "").strip(), (cliente_telefone or "").strip(),
         to_iso(data_evento) if data_evento else None,
         (prazo_entrega or "").strip(), (escopo or "").strip(), orcamento_id),
    )


def numero_proposta(orcamento: dict) -> str:
    """Número exibido na proposta, no formato ANO-0000 (ex.: 2026-0007)."""
    ano = (orcamento.get("data") or hoje_iso())[:4]
    return f"{ano}-{orcamento['id']:04d}"


def excluir_orcamento(orcamento_id: int) -> None:
    executar("DELETE FROM orcamentos WHERE id = ?", (orcamento_id,))


def duplicar_orcamento(orcamento_id: int, novo_titulo: str = "",
                        novo_cliente: str = "") -> int:
    """Cria uma cópia de um orçamento — útil para reaproveitar uma proposta."""
    original = obter_orcamento(orcamento_id)
    if not original:
        raise ValueError("Orçamento não encontrado.")

    novo_id = criar_orcamento(
        titulo=novo_titulo.strip() or f"{original['titulo']} (cópia)",
        cliente_nome=novo_cliente.strip() or original["cliente_nome"],
        data=hoje_iso(),
        validade_dias=original["validade_dias"],
        observacoes=original["observacoes"] or "",
        condicoes=original["condicoes"] or "",
    )
    for item in original["itens"]:
        adicionar_item(
            novo_id, item["descricao"], item["quantidade"], item["valor_unitario"],
            item["unidade"], item["pessoas"], item["categoria"],
        )
    return novo_id


# ---------------------------------------------------------------------------
# ITENS DO ORÇAMENTO
# ---------------------------------------------------------------------------

def listar_itens(orcamento_id: int) -> list:
    itens = consultar(
        "SELECT * FROM orcamento_itens WHERE orcamento_id = ? ORDER BY ordem, id",
        (orcamento_id,),
    )
    for item in itens:
        item["subtotal"] = calcular_subtotal(item)
    return itens


def calcular_subtotal(item: dict) -> float:
    """quantidade × pessoas × valor unitário."""
    return round(
        (item["quantidade"] or 0) * (item["pessoas"] or 1) * (item["valor_unitario"] or 0),
        2,
    )


def adicionar_item(orcamento_id: int, descricao: str, quantidade: float,
                    valor_unitario: float, unidade: str = "hora",
                    pessoas: int = 1, categoria: str = "Produção") -> int:
    if not descricao.strip():
        raise ValueError("Informe a descrição do item.")
    proxima_ordem = escalar(
        "SELECT COALESCE(MAX(ordem), 0) + 1 FROM orcamento_itens WHERE orcamento_id = ?",
        (orcamento_id,),
    )
    return executar(
        """INSERT INTO orcamento_itens
           (orcamento_id, descricao, categoria, unidade, quantidade, pessoas,
            valor_unitario, ordem)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (orcamento_id, descricao.strip(), categoria, unidade, quantidade,
         max(1, int(pessoas or 1)), valor_unitario, proxima_ordem),
    )


def atualizar_item(item_id: int, descricao: str, quantidade: float, pessoas: int,
                    valor_unitario: float, unidade: str, categoria: str) -> None:
    executar(
        """UPDATE orcamento_itens SET descricao=?, quantidade=?, pessoas=?,
                                      valor_unitario=?, unidade=?, categoria=?
           WHERE id=?""",
        (descricao.strip(), quantidade, max(1, int(pessoas or 1)),
         valor_unitario, unidade, categoria, item_id),
    )


def excluir_item(item_id: int) -> None:
    executar("DELETE FROM orcamento_itens WHERE id = ?", (item_id,))


def substituir_itens(orcamento_id: int, itens: list) -> int:
    """
    Grava de uma vez todas as etapas preenchidas na grade de serviços.

    Recebe uma lista de dicionários com: descricao, quantidade, pessoas,
    valor_unitario, unidade, categoria. Linhas com quantidade zero ou vazia
    são ignoradas (nenhum serviço é obrigatório).

    As etapas anteriores do orçamento são substituídas pelas novas. Devolve
    quantas etapas ficaram gravadas.
    """
    validos = [
        i for i in itens
        if (i.get("quantidade") or 0) > 0 and (i.get("valor_unitario") or 0) > 0
        and (i.get("descricao") or "").strip()
    ]
    executar("DELETE FROM orcamento_itens WHERE orcamento_id = ?", (orcamento_id,))
    for ordem, item in enumerate(validos, start=1):
        executar(
            """INSERT INTO orcamento_itens
               (orcamento_id, descricao, categoria, unidade, quantidade, pessoas,
                valor_unitario, ordem)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (orcamento_id, item["descricao"].strip(), item.get("categoria") or "Outro",
             item.get("unidade") or "hora", float(item["quantidade"]),
             max(1, int(item.get("pessoas") or 1)), float(item["valor_unitario"]), ordem),
        )
    return len(validos)


# ---------------------------------------------------------------------------
# TOTAIS
# ---------------------------------------------------------------------------

def calcular_totais(orcamento_id: int) -> dict:
    """
    Soma os itens, aplica o desconto e devolve também a abertura por categoria
    e o total de horas de trabalho envolvido.
    """
    orcamento = consultar_um(
        "SELECT desconto_percent FROM orcamentos WHERE id = ?", (orcamento_id,)
    )
    desconto_percent = (orcamento or {}).get("desconto_percent", 0) or 0

    itens = consultar(
        "SELECT * FROM orcamento_itens WHERE orcamento_id = ?", (orcamento_id,)
    )

    subtotal = 0.0
    horas_totais = 0.0
    por_categoria = {}
    for item in itens:
        valor = calcular_subtotal(item)
        subtotal += valor
        por_categoria[item["categoria"]] = por_categoria.get(item["categoria"], 0) + valor
        if item["unidade"] == "hora":
            horas_totais += (item["quantidade"] or 0) * (item["pessoas"] or 1)

    valor_desconto = round(subtotal * desconto_percent / 100.0, 2)
    total = round(subtotal - valor_desconto, 2)

    return {
        "subtotal": round(subtotal, 2),
        "desconto_percent": desconto_percent,
        "valor_desconto": valor_desconto,
        "total": total,
        "horas_totais": round(horas_totais, 1),
        "valor_hora_efetivo": round(total / horas_totais, 2) if horas_totais else 0.0,
        "por_categoria": por_categoria,
        "quantidade_itens": len(itens),
    }


# ---------------------------------------------------------------------------
# DADOS DA EMPRESA (aparecem no cabeçalho e rodapé das propostas)
# ---------------------------------------------------------------------------

CAMPOS_EMPRESA = [
    ("empresa_nome", "Nome da empresa", "Claquete Produtora Audiovisual"),
    ("empresa_cnpj", "CNPJ", ""),
    ("empresa_email", "E-mail", ""),
    ("empresa_telefone", "Telefone / WhatsApp", ""),
    ("empresa_site", "Site", ""),
    ("empresa_instagram", "Instagram", ""),
    ("empresa_cidade", "Cidade / UF", ""),
]


def obter_dados_empresa() -> dict:
    """Devolve os dados da empresa, preenchendo com o padrão o que estiver vazio."""
    salvos = {l["chave"]: l["valor"] for l in consultar("SELECT chave, valor FROM configuracoes")}
    return {chave: (salvos.get(chave) or padrao) for chave, _, padrao in CAMPOS_EMPRESA}


def salvar_dados_empresa(dados: dict) -> None:
    for chave, _, _ in CAMPOS_EMPRESA:
        valor = (dados.get(chave) or "").strip()
        executar("DELETE FROM configuracoes WHERE chave = ?", (chave,))
        executar("INSERT INTO configuracoes (chave, valor) VALUES (?, ?)", (chave, valor))


# ---------------------------------------------------------------------------
# LEITURA DE HORAS E VALORES EM FORMATO NATURAL
# ---------------------------------------------------------------------------
# Os campos da grade são de TEXTO, para aceitar a forma como as pessoas
# escrevem naturalmente ("1h30", "R$ 1.500,00") em vez de exigir decimais.

import re as _re


def interpretar_horas(texto) -> Optional[float]:
    """
    Converte o que foi digitado em horas decimais, para o cálculo.

        "2"      -> 2.0        "2h"     -> 2.0
        "1h30"   -> 1.5        "1h 30"  -> 1.5      "1h30min" -> 1.5
        "1:30"   -> 1.5        "0:45"   -> 0.75
        "45min"  -> 0.75       "45m"    -> 0.75
        "1,5"    -> 1.5        "1.5"    -> 1.5
        ""       -> None       (campo vazio = serviço não incluído)

    Levanta ValueError quando não consegue entender o texto.
    """
    if texto is None:
        return None
    t = str(texto).strip().lower().replace(" ", "")
    if not t:
        return None

    # "1:30"
    m = _re.fullmatch(r"(\d+):(\d{1,2})", t)
    if m:
        horas, minutos = int(m.group(1)), int(m.group(2))
        if minutos >= 60:
            raise ValueError(f"minutos inválidos em '{texto}'")
        return round(horas + minutos / 60, 4)

    # "1h30", "1h30min", "2h", "1h30m"
    m = _re.fullmatch(r"(\d+(?:[.,]\d+)?)h(?:(\d{1,2})(?:min|m)?)?", t)
    if m:
        horas = float(m.group(1).replace(",", "."))
        minutos = int(m.group(2)) if m.group(2) else 0
        if minutos >= 60:
            raise ValueError(f"minutos inválidos em '{texto}'")
        return round(horas + minutos / 60, 4)

    # "45min", "45m"
    m = _re.fullmatch(r"(\d+)(?:min|m)", t)
    if m:
        return round(int(m.group(1)) / 60, 4)

    # "2", "1,5", "1.5"
    m = _re.fullmatch(r"\d+(?:[.,]\d+)?", t)
    if m:
        return float(t.replace(",", "."))

    raise ValueError(f"não entendi '{texto}' — use, por exemplo, 2h, 1h30, 1:30 ou 45min")


def interpretar_numero(texto) -> Optional[float]:
    """Número simples (km, meses, diárias): aceita '80', '2,5', '2.5'."""
    if texto is None:
        return None
    t = str(texto).strip().replace(" ", "")
    if not t:
        return None
    if _re.fullmatch(r"\d+(?:[.,]\d+)?", t):
        return float(t.replace(",", "."))
    raise ValueError(f"não entendi '{texto}' — digite só o número, ex.: 80")


def interpretar_valor(texto) -> Optional[float]:
    """
    Converte valor em reais escrito em formato brasileiro.

        "150"        -> 150.0      "150,50"   -> 150.5
        "1.500"      -> 1500.0     "1.500,50" -> 1500.5
        "R$ 1.500"   -> 1500.0     ""         -> None
    """
    if texto is None:
        return None
    t = str(texto).strip().lower().replace("r$", "").replace(" ", "")
    if not t:
        return None
    if _re.fullmatch(r"\d{1,3}(\.\d{3})+(,\d{1,2})?", t):      # 1.500 / 1.500,50
        return float(t.replace(".", "").replace(",", "."))
    if _re.fullmatch(r"\d+(,\d{1,2})?", t):                     # 150 / 150,50
        return float(t.replace(",", "."))
    if _re.fullmatch(r"\d+\.\d{1,2}", t):                       # 150.50
        return float(t)
    raise ValueError(f"não entendi o valor '{texto}' — use, por exemplo, 150 ou 1.500,00")


def horas_para_texto(horas: float) -> str:
    """Formato natural para mostrar horas já salvas: 1.5 -> '1h30'."""
    horas = float(horas or 0)
    inteiras = int(horas)
    minutos = round((horas - inteiras) * 60)
    if minutos == 60:
        inteiras, minutos = inteiras + 1, 0
    if inteiras and minutos:
        return f"{inteiras}h{minutos:02d}"
    if inteiras:
        return f"{inteiras}h"
    return f"{minutos}min" if minutos else ""


def valor_para_texto(valor: float) -> str:
    """Formato brasileiro para mostrar valores já salvos: 1500.5 -> '1.500,50'."""
    return f"{float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ---------------------------------------------------------------------------
# HISTÓRICO DE PROPOSTAS EMITIDAS
# ---------------------------------------------------------------------------

_MARCADOR_LOGO = "__LOGO_CLAQUETE__"


def emitir_proposta(orcamento_id: int, documento_html: str, logo_base64: str,
                     emitida_por: str = "") -> dict:
    """
    Registra uma cópia congelada da proposta, como foi enviada ao cliente.

    Cada nova emissão do mesmo orçamento vira uma nova VERSÃO (revisão),
    e o orçamento passa para o status "Enviado" se ainda for rascunho.

    A imagem do logo é trocada por um marcador antes de gravar — ela é igual
    em todas as propostas e ocuparia espaço à toa no banco. Na hora de exibir,
    o marcador volta a ser o logo.
    """
    orc = obter_orcamento(orcamento_id)
    if not orc:
        raise ValueError("Orçamento não encontrado.")

    versao = escalar(
        "SELECT COALESCE(MAX(versao), 0) + 1 FROM propostas_emitidas WHERE orcamento_id = ?",
        (orcamento_id,),
    )
    html_compacto = documento_html.replace(logo_base64, _MARCADOR_LOGO) if logo_base64 \
        else documento_html

    proposta_id = executar(
        """INSERT INTO propostas_emitidas
           (orcamento_id, numero, versao, titulo, cliente_nome, total,
            emitida_em, emitida_por, documento_html)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (orcamento_id, numero_proposta(orc), versao, orc["titulo"], orc["cliente_nome"],
         orc["total"], agora_iso(), (emitida_por or "").strip(), html_compacto),
    )
    if orc["status"] == "Rascunho":
        executar("UPDATE orcamentos SET status = 'Enviado' WHERE id = ?", (orcamento_id,))
    return {"id": proposta_id, "versao": versao, "numero": numero_proposta(orc)}


def listar_propostas_emitidas(cliente: Optional[str] = None,
                               data_ini: Optional[str] = None,
                               data_fim: Optional[str] = None) -> list:
    """Histórico, do mais recente para o mais antigo (sem o documento em si)."""
    sql = """SELECT p.id, p.orcamento_id, p.numero, p.versao, p.titulo, p.cliente_nome,
                    p.total, p.emitida_em, p.emitida_por,
                    o.status AS status_atual
             FROM propostas_emitidas p
             LEFT JOIN orcamentos o ON o.id = p.orcamento_id
             WHERE 1=1"""
    params = []
    if cliente:
        sql += " AND p.cliente_nome = ?"
        params.append(cliente)
    if data_ini:
        sql += " AND substr(p.emitida_em, 1, 10) >= ?"
        params.append(data_ini)
    if data_fim:
        sql += " AND substr(p.emitida_em, 1, 10) <= ?"
        params.append(data_fim)
    sql += " ORDER BY p.emitida_em DESC, p.id DESC"
    propostas = consultar(sql, tuple(params))

    # Marca as versões que já foram substituídas por uma revisão mais nova.
    ultima = {}
    for p in propostas:
        chave = p["orcamento_id"]
        ultima[chave] = max(ultima.get(chave, 0), p["versao"])
    for p in propostas:
        p["substituida"] = p["versao"] < ultima.get(p["orcamento_id"], p["versao"])
    return propostas


def obter_documento_emitido(proposta_id: int, logo_base64: str) -> Optional[str]:
    linha = consultar_um(
        "SELECT documento_html FROM propostas_emitidas WHERE id = ?", (proposta_id,)
    )
    if not linha:
        return None
    return linha["documento_html"].replace(_MARCADOR_LOGO, logo_base64 or "")


def excluir_proposta_emitida(proposta_id: int) -> None:
    executar("DELETE FROM propostas_emitidas WHERE id = ?", (proposta_id,))
