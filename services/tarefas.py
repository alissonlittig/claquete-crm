"""
services/tarefas.py
--------------------
Agenda/planner da equipe: tarefas atribuídas a cada sócio, com prazo e status.

REGRA IMPORTANTE SOBRE "ATRASADO"
    O status "Atrasado" não é guardado no banco — ele é CALCULADO toda vez que
    a lista é carregada, comparando o prazo com a data de hoje. Assim:

    - Uma tarefa nunca fica marcada como atrasada por engano.
    - Não é preciso nenhuma rotina automática rodando para atualizar status.
    - Basta concluir a tarefa (ou esticar o prazo) para ela deixar de constar
      como atrasada.

    Os status guardados são apenas: "A Fazer", "Em Andamento" e "Concluída".
"""

from datetime import date
from typing import Optional

from db_utils import agora_iso, consultar, consultar_um, executar, hoje_iso, to_iso

STATUS = ["A Fazer", "Em Andamento", "Concluída"]
PRIORIDADES = ["Baixa", "Normal", "Alta"]


def _enriquecer(tarefa: dict) -> dict:
    """
    Acrescenta os campos calculados de cada tarefa:
      - `atrasada`: prazo já venceu e a tarefa não foi concluída
      - `situacao`: o rótulo a exibir na tela ("Atrasada" tem prioridade)
      - `dias_restantes`: negativo quando o prazo já passou
    """
    hoje = date.today()
    prazo = None
    if tarefa.get("data_prazo"):
        try:
            prazo = date.fromisoformat(tarefa["data_prazo"][:10])
        except ValueError:
            prazo = None

    concluida = tarefa.get("status") == "Concluída"
    atrasada = bool(prazo and not concluida and prazo < hoje)

    tarefa["atrasada"] = atrasada
    tarefa["situacao"] = "Atrasada" if atrasada else tarefa.get("status", "A Fazer")
    tarefa["dias_restantes"] = (prazo - hoje).days if prazo and not concluida else None
    return tarefa


def listar_tarefas(socio_id: Optional[int] = None, status: Optional[str] = None,
                    data_ini: Optional[str] = None, data_fim: Optional[str] = None,
                    apenas_atrasadas: bool = False) -> list:
    """
    Lista as tarefas, já com os campos calculados. O filtro de período olha
    para o PRAZO da tarefa (tarefas sem prazo aparecem sempre).
    """
    sql = """SELECT t.*, s.nome AS socio_nome, e.nome AS evento_nome
             FROM tarefas t
             LEFT JOIN socios s ON s.id = t.socio_id
             LEFT JOIN eventos e ON e.id = t.evento_id
             WHERE 1=1"""
    params = []
    if socio_id:
        sql += " AND t.socio_id = ?"
        params.append(socio_id)
    if status:
        sql += " AND t.status = ?"
        params.append(status)
    if data_ini:
        sql += " AND (t.data_prazo IS NULL OR t.data_prazo >= ?)"
        params.append(data_ini)
    if data_fim:
        sql += " AND (t.data_prazo IS NULL OR t.data_prazo <= ?)"
        params.append(data_fim)
    sql += " ORDER BY (t.data_prazo IS NULL), t.data_prazo, t.id DESC"

    tarefas = [_enriquecer(t) for t in consultar(sql, tuple(params))]
    if apenas_atrasadas:
        tarefas = [t for t in tarefas if t["atrasada"]]
    return tarefas


def obter_tarefa(tarefa_id: int) -> Optional[dict]:
    tarefa = consultar_um("SELECT * FROM tarefas WHERE id = ?", (tarefa_id,))
    return _enriquecer(tarefa) if tarefa else None


def criar_tarefa(titulo: str, socio_id: Optional[int] = None, descricao: str = "",
                  data_inicio=None, data_prazo=None, status: str = "A Fazer",
                  prioridade: str = "Normal", evento_id: Optional[int] = None) -> int:
    if not titulo.strip():
        raise ValueError("A tarefa precisa de um título.")
    return executar(
        """INSERT INTO tarefas
           (titulo, descricao, socio_id, evento_id, data_inicio, data_prazo,
            status, prioridade, criado_em)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (titulo.strip(), descricao.strip(), socio_id, evento_id,
         to_iso(data_inicio) if data_inicio else None,
         to_iso(data_prazo) if data_prazo else None,
         status, prioridade, agora_iso()),
    )


def atualizar_tarefa(tarefa_id: int, titulo: str, descricao: str,
                      socio_id: Optional[int], data_inicio, data_prazo,
                      status: str, prioridade: str,
                      evento_id: Optional[int] = None) -> None:
    executar(
        """UPDATE tarefas SET titulo=?, descricao=?, socio_id=?, evento_id=?,
                              data_inicio=?, data_prazo=?, status=?, prioridade=?,
                              concluida_em = CASE WHEN ? = 'Concluída'
                                                  THEN COALESCE(concluida_em, ?)
                                                  ELSE NULL END
           WHERE id=?""",
        (titulo.strip(), descricao.strip(), socio_id, evento_id,
         to_iso(data_inicio) if data_inicio else None,
         to_iso(data_prazo) if data_prazo else None,
         status, prioridade, status, hoje_iso(), tarefa_id),
    )


def mudar_status(tarefa_id: int, status: str) -> None:
    """Atalho usado pelos botões rápidos do quadro de tarefas."""
    concluida_em = hoje_iso() if status == "Concluída" else None
    executar(
        "UPDATE tarefas SET status = ?, concluida_em = ? WHERE id = ?",
        (status, concluida_em, tarefa_id),
    )


def excluir_tarefa(tarefa_id: int) -> None:
    executar("DELETE FROM tarefas WHERE id = ?", (tarefa_id,))


def resumo_por_status(data_ini: Optional[str] = None,
                       data_fim: Optional[str] = None) -> dict:
    """Contagem de tarefas por situação, para os cartões do topo da página."""
    tarefas = listar_tarefas(data_ini=data_ini, data_fim=data_fim)
    resumo = {"A Fazer": 0, "Em Andamento": 0, "Concluída": 0, "Atrasada": 0}
    for t in tarefas:
        resumo[t["situacao"]] = resumo.get(t["situacao"], 0) + 1
    resumo["total"] = len(tarefas)
    return resumo


def resumo_por_socio(data_ini: Optional[str] = None,
                      data_fim: Optional[str] = None) -> list:
    """Quantas tarefas cada sócio tem em cada situação."""
    from services import socios as socios_service

    tarefas = listar_tarefas(data_ini=data_ini, data_fim=data_fim)
    resultado = []
    for socio in socios_service.listar_socios(apenas_ativos=True):
        do_socio = [t for t in tarefas if t["socio_id"] == socio["id"]]
        resultado.append({
            "socio_id": socio["id"],
            "nome": socio["nome"],
            "total": len(do_socio),
            "a_fazer": sum(1 for t in do_socio if t["situacao"] == "A Fazer"),
            "em_andamento": sum(1 for t in do_socio if t["situacao"] == "Em Andamento"),
            "concluidas": sum(1 for t in do_socio if t["situacao"] == "Concluída"),
            "atrasadas": sum(1 for t in do_socio if t["atrasada"]),
        })

    sem_dono = [t for t in tarefas if not t["socio_id"]]
    if sem_dono:
        resultado.append({
            "socio_id": None, "nome": "Sem responsável", "total": len(sem_dono),
            "a_fazer": sum(1 for t in sem_dono if t["situacao"] == "A Fazer"),
            "em_andamento": sum(1 for t in sem_dono if t["situacao"] == "Em Andamento"),
            "concluidas": sum(1 for t in sem_dono if t["situacao"] == "Concluída"),
            "atrasadas": sum(1 for t in sem_dono if t["atrasada"]),
        })
    return resultado
