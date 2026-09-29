"""
services/demo.py
-----------------
Dados de DEMONSTRAÇÃO: uma produtora audiovisual fictícia com 3 sócios,
clientes, projetos, custos, investimentos, tarefas e orçamentos — para o
sistema já abrir "vivo" e todas as telas terem o que mostrar.

QUANDO É USADO
    - Automaticamente, por `database.init_db()`, sempre que o banco abre
      vazio. No Streamlit Community Cloud o arquivo do banco é apagado a cada
      reinício do app, então a demonstração se reinicia sozinha.
    - Manualmente, por `python scripts/seed_demo.py`, para voltar ao estado
      inicial a qualquer momento.

Todos os nomes, e-mails, telefones e valores são fictícios. Os e-mails usam
o domínio reservado `.example`, que não pertence a ninguém.

AS DATAS SÃO RELATIVAS A HOJE
    Os lançamentos cobrem os últimos 14 meses e alguns projetos futuros,
    sempre contados a partir da data em que o banco é criado. Assim a
    demonstração abre com números atuais em qualquer época do ano.
"""

import calendar
from datetime import date, timedelta

from database import get_connection, init_db
from db_utils import escalar, limpar_cache
from services import eventos as eventos_service
from services import financeiro
from services import orcamentos as orc_service
from services import socios as socios_service
from services import tarefas as tarefas_service

TABELAS = [
    "fluxo_caixa", "recebimentos", "anexos_evento", "tarefas", "eventos",
    "clientes", "propostas_emitidas", "orcamento_itens", "orcamentos",
    "precos_servicos", "configuracoes", "investimentos",
    "custos_fixos_pagamentos", "custos_fixos", "reembolsos_socios",
    "aportes", "socios",
]


def banco_vazio() -> bool:
    """O banco é considerado vazio quando não há nenhum sócio cadastrado."""
    return escalar("SELECT COUNT(*) FROM socios") == 0


def popular_se_vazio() -> bool:
    """Carrega a demonstração se o banco estiver vazio. Devolve True se carregou."""
    if not banco_vazio():
        return False
    seed()
    return True


def limpar_banco() -> None:
    """Apaga todos os registros de todas as tabelas (a estrutura continua)."""
    conn = get_connection(nova=True)
    try:
        for tabela in TABELAS:
            conn.execute(f"DELETE FROM {tabela}")
            conn.execute("DELETE FROM sqlite_sequence WHERE name = ?", (tabela,))
        conn.commit()
    finally:
        try:
            conn.close()
        except Exception:
            pass
        limpar_cache()


def _mes(meses_atras: int, dia: int, hoje: date) -> date:
    """Data no mês `meses_atras` antes do atual, com o dia limitado ao fim do mês."""
    ano, mes = hoje.year, hoje.month - meses_atras
    while mes < 1:
        ano, mes = ano - 1, mes + 12
    while mes > 12:
        ano, mes = ano + 1, mes - 12
    return date(ano, mes, min(dia, calendar.monthrange(ano, mes)[1]))


def seed() -> None:
    """Recria os dados de demonstração. ATENÇÃO: apaga tudo o que existe antes."""
    init_db()
    limpar_banco()

    hoje = date.today()

    def m(meses_atras: int, dia: int) -> date:
        # No mês corrente, a data nunca passa de hoje.
        d = _mes(meses_atras, dia, hoje)
        return min(d, hoje) if meses_atras == 0 else d

    # ---------------------------------------------------------------- sócios
    rafael = socios_service.criar_socio(
        "Rafael Nogueira", "rafael@claquete.example", "(11) 90000-0001", m(14, 3))
    julia = socios_service.criar_socio(
        "Júlia Campos", "julia@claquete.example", "(11) 90000-0002", m(14, 3))
    caio = socios_service.criar_socio(
        "Caio Ferraz", "caio@claquete.example", "(11) 90000-0003", m(14, 3))

    # ---------------------------------------------------------------- aportes
    # Capital inicial, depositado no caixa da empresa
    for socio in (rafael, julia, caio):
        socios_service.registrar_aporte(
            socio, m(14, 5), "Aporte inicial em dinheiro", 5000.00,
            categoria="Dinheiro em Caixa", entrou_no_caixa=True,
        )
    # Despesas pagas do próprio bolso (não passam pelo caixa da empresa)
    socios_service.registrar_aporte(
        rafael, m(13, 8), "Registro da marca", 415.00,
        categoria="Despesa Operacional", entrou_no_caixa=False,
    )
    socios_service.registrar_aporte(
        rafael, m(13, 9), "Domínio do site (2 anos)", 80.00,
        categoria="Assinatura/Software", entrou_no_caixa=False,
    )
    socios_service.registrar_aporte(
        julia, m(12, 14), "Licença de trilhas sonoras (anual)", 348.00,
        categoria="Assinatura/Software", entrou_no_caixa=False,
    )
    socios_service.registrar_aporte(
        caio, m(12, 20), "Cartões de visita e material gráfico", 190.00,
        categoria="Despesa Operacional", entrou_no_caixa=False,
    )

    # ---------------------------------------------------------------- investimentos
    # Comprados pelos sócios (viram aporte a reembolsar)
    financeiro.criar_investimento(
        "Câmera mirrorless full-frame + lente 24-70mm", "Equipamento", 13900.00, m(13, 12),
        fornecedor="Casa da Câmera", vida_util_meses=48,
        forma_pagamento="Sócio", socio_id=rafael,
        observacao="Comprada por Rafael, a ser reembolsada pela empresa",
    )
    financeiro.criar_investimento(
        "Kit de iluminação LED (3 painéis)", "Equipamento", 1650.00, m(12, 6),
        fornecedor="Luz & Cena Equipamentos", vida_util_meses=48,
        forma_pagamento="Sócio", socio_id=julia,
    )
    # Comprados com o caixa da empresa
    financeiro.criar_investimento(
        "Gimbal estabilizador", "Equipamento", 2300.00, m(12, 18),
        fornecedor="Casa da Câmera", vida_util_meses=36,
    )
    financeiro.criar_investimento(
        "Microfones de lapela sem fio (par)", "Equipamento", 1450.00, m(9, 11),
        fornecedor="Som Direto Áudio", vida_util_meses=36,
    )
    financeiro.criar_investimento(
        "Drone com câmera 4K", "Equipamento", 6800.00, m(7, 22),
        fornecedor="Casa da Câmera", vida_util_meses=36,
    )
    financeiro.criar_investimento(
        "Plugin de color grading (licença perpétua)", "Software", 890.00, m(5, 4),
        fornecedor="Loja online do desenvolvedor", vida_util_meses=24,
    )

    # Reembolsos já feitos aos sócios
    socios_service.registrar_reembolso(caio, m(10, 10), 190.00, "Reembolso via Pix")
    socios_service.registrar_reembolso(rafael, m(6, 10), 2000.00, "Reembolso parcial via Pix")
    socios_service.registrar_reembolso(julia, m(4, 10), 1998.00, "Reembolso integral via Pix")

    # ---------------------------------------------------------------- clientes
    def cliente(nome, contato, email, telefone, origem):
        return eventos_service.criar_cliente(nome, email=email, telefone=telefone,
                                             origem=origem, observacao=f"Contato: {contato}")

    c_vida = cliente("Instituto Vida Plena", "Helena Rocha",
                     "helena@vidaplena.example", "(11) 90000-1001", "Indicação")
    c_rota = cliente("Rota Invest Educação Financeira", "Bruno Salles",
                     "bruno@rotainvest.example", "(11) 90000-1002", "Instagram")
    c_brasa = cliente("Brasa & Lúpulo Gastrobar", "Tiago Mendes",
                      "tiago@brasaelupulo.example", "(11) 90000-1003", "Indicação")
    c_sorriso = cliente("Clínica Sorriso Pleno", "Dra. Paula Lima",
                        "contato@sorrisopleno.example", "(11) 90000-1004", "Site")
    c_aurora = cliente("Café Aurora", "Marina Alves",
                       "marina@cafeaurora.example", "(11) 90000-1005", "Instagram")
    c_alicerce = cliente("Construtora Alicerce", "Renato Prado",
                         "marketing@alicerce.example", "(11) 90000-1006", "Site")
    c_festival = cliente("Festival Sons do Parque", "Lívia Torres",
                         "producao@sonsdoparque.example", "(11) 90000-1007", "Indicação")
    c_pilates = cliente("Studio Equilíbrio Pilates", "Sofia Martins",
                        "sofia@equilibrio.example", "(11) 90000-1008", "Instagram")

    # ---------------------------------------------------------------- projetos
    recebido_por_mes = {}

    def projeto(cli, nome, tipo, data_evento, valor, status, recebimentos=()):
        ev = eventos_service.criar_evento(cli, nome, tipo, data_evento, valor, status=status)
        for data_rec, valor_rec, forma, obs in recebimentos:
            eventos_service.registrar_recebimento(ev, data_rec, valor_rec, forma, obs)
            chave = data_rec.strftime("%Y-%m")
            recebido_por_mes[chave] = recebido_por_mes.get(chave, 0) + valor_rec
        return ev

    projeto(c_vida, "Vídeo institucional da campanha de vacinação", "Institucional",
            m(13, 20), 6800.00, "Concluído",
            [(m(12, 2), 6800.00, "Transferência", "Pagamento único")])
    projeto(c_brasa, "Cobertura de inauguração (foto + vídeo)", "Evento",
            m(12, 15), 3200.00, "Concluído",
            [(m(12, 10), 1600.00, "Pix", "Sinal"), (m(12, 25), 1600.00, "Pix", "Entrega")])
    projeto(c_sorriso, "Vídeo institucional + fotos da equipe", "Institucional",
            m(11, 8), 5400.00, "Concluído",
            [(m(11, 20), 5400.00, "Boleto", "Pagamento único")])
    projeto(c_rota, "Série de 8 vídeos para redes sociais", "Publicidade",
            m(10, 5), 12000.00, "Concluído",
            [(m(10, 5), 4000.00, "Pix", "Parcela 1/3"), (m(9, 5), 4000.00, "Pix", "Parcela 2/3"),
             (m(8, 5), 4000.00, "Pix", "Parcela 3/3")])
    projeto(c_aurora, "Fotos do cardápio e reels de lançamento", "Publicidade",
            m(9, 18), 2800.00, "Concluído",
            [(m(9, 25), 2800.00, "Pix", "Pagamento único")])
    projeto(c_alicerce, "Vídeo de lançamento do Residencial Jardim", "Publicidade",
            m(8, 12), 15000.00, "Concluído",
            [(m(8, 1), 7500.00, "Transferência", "Sinal 50%"),
             (m(7, 3), 7500.00, "Transferência", "Entrega 50%")])
    ev_festival_1 = projeto(
        c_festival, "Cobertura do festival (2 dias)", "Evento",
        m(6, 14), 18000.00, "Concluído",
        [(m(6, 1), 9000.00, "Transferência", "Sinal 50%"),
         (m(5, 2), 9000.00, "Transferência", "Entrega 50%")])
    projeto(c_pilates, "Vídeos de aulas para a plataforma online", "Institucional",
            m(5, 20), 9600.00, "Concluído",
            [(m(4, 5), 9600.00, "Boleto", "Pagamento único")])
    projeto(c_sorriso, "Campanha de clareamento", "Publicidade",
            m(4, 15), 3600.00, "Cancelado")
    ev_doc = projeto(
        c_vida, "Minidocumentário 10 anos do instituto", "Documentário",
        m(3, 10), 24000.00, "Concluído",
        [(m(4, 12), 12000.00, "Transferência", "Sinal 50%"),
         (m(2, 8), 12000.00, "Transferência", "Entrega 50%")])
    ev_redes = projeto(
        c_rota, "Gestão de redes sociais (trimestre)", "Publicidade",
        m(2, 1), 13500.00, "Em Produção",
        [(m(2, 5), 4500.00, "Pix", "Mês 1/3"), (m(1, 5), 4500.00, "Pix", "Mês 2/3")])
    ev_verao = projeto(
        c_brasa, "Campanha de verão (reels)", "Publicidade",
        m(1, 20), 4500.00, "Em Produção",
        [(m(1, 22), 2250.00, "Pix", "Sinal 50%")])
    ev_filme = projeto(
        c_alicerce, "Filme institucional da construtora", "Institucional",
        hoje + timedelta(days=18), 16000.00, "Confirmado",
        [(m(0, 3), 4800.00, "Transferência", "Sinal 30%")])
    ev_festival_2 = projeto(
        c_festival, "Cobertura da edição de verão", "Evento",
        _mes(-2, 12, hoje), 15500.00, "Confirmado")
    projeto(c_aurora, "Vídeo de abertura da 2ª unidade", "Evento",
            _mes(-1, 25, hoje), 3900.00, "Orçamento")

    # ---------------------------------------------------------------- custos fixos
    financeiro.criar_custo_fixo("Suíte de e-mail e documentos", "Assinatura/Software", 52.00, 10, m(13, 1))
    financeiro.criar_custo_fixo("Adobe Creative Cloud", "Assinatura/Software", 275.00, 15, m(13, 1))
    financeiro.criar_custo_fixo("Armazenamento em nuvem (2 TB)", "Assinatura/Software", 35.00, 5, m(13, 1))
    financeiro.criar_custo_fixo("Contabilidade", "Serviço Contratado", 390.00, 10, m(13, 1))
    financeiro.criar_custo_fixo("Seguro dos equipamentos", "Serviço Contratado", 89.00, 20, m(13, 1))

    # Gera as contas de cada mês em ordem. O pró-labore só começa quando a
    # produtora passa a ter receita recorrente (10 meses atrás).
    for meses_atras in range(13, -1, -1):
        if meses_atras == 10:
            for nome in ("Rafael", "Júlia", "Caio"):
                financeiro.criar_custo_fixo(
                    f"Pró-labore {nome}", "Folha Salarial", 1800.00, 5, m(10, 1))
        financeiro.gerar_lancamentos_do_mes(m(meses_atras, 1).strftime("%Y-%m"))

    # Paga tudo o que já venceu; o que vence depois de hoje fica em aberto.
    for pagamento in financeiro.listar_pagamentos_custos_fixos():
        if pagamento["data_vencimento"] <= hoje.isoformat():
            financeiro.marcar_pagamento(pagamento["id"], pagamento["data_vencimento"])

    # ---------------------------------------------------------------- lançamentos manuais
    # Imposto (Simples Nacional) de 6% sobre o recebido no mês anterior.
    for meses_atras in range(12, -1, -1):
        referencia = m(meses_atras + 1, 1).strftime("%Y-%m")
        base = recebido_por_mes.get(referencia, 0)
        data_das = m(meses_atras, 20)
        if base and data_das <= hoje:
            financeiro.lancamento_manual(
                data_das, "Saída", "Impostos e Taxas",
                f"DAS Simples Nacional (competência {referencia[5:]}/{referencia[:4]})",
                round(base * 0.06, 2))

    for meses_atras in (9, 6, 3, 0):
        financeiro.lancamento_manual(
            m(meses_atras, 2), "Saída", "Marketing",
            "Impulsionamento de posts no Instagram", 250.00)
    financeiro.lancamento_manual(
        m(6, 15), "Saída", "Alimentação/Deslocamento",
        "Alimentação da equipe nos 2 dias de festival", 380.00)
    financeiro.lancamento_manual(
        m(7, 9), "Saída", "Manutenção",
        "Limpeza de sensor e revisão da câmera", 260.00)

    # ---------------------------------------------------------------- tarefas
    tarefas_service.criar_tarefa(
        "Montar o cronograma de gravação do filme institucional", rafael,
        "Confirmar locações e a disponibilidade da equipe da construtora.",
        data_prazo=hoje + timedelta(days=4), status="Em Andamento",
        prioridade="Alta", evento_id=ev_filme)
    tarefas_service.criar_tarefa(
        "Enviar o primeiro corte da campanha de verão", julia,
        data_prazo=hoje, status="Em Andamento",
        prioridade="Alta", evento_id=ev_verao)
    tarefas_service.criar_tarefa(
        "Cobrar a parcela final da gestão de redes", julia,
        data_prazo=hoje - timedelta(days=3), prioridade="Alta", evento_id=ev_redes)
    tarefas_service.criar_tarefa(
        "Agendar reunião de briefing com a produção do festival", caio,
        data_prazo=hoje - timedelta(days=1), evento_id=ev_festival_2)
    tarefas_service.criar_tarefa(
        "Revisar o orçamento da 2ª unidade do Café Aurora", caio,
        data_prazo=hoje)
    tarefas_service.criar_tarefa(
        "Enviar a proposta ao Festival Sons do Parque", julia,
        data_prazo=max(hoje.replace(day=1), hoje - timedelta(days=2)),
        status="Concluída", evento_id=ev_festival_2)
    tarefas_service.criar_tarefa(
        "Copiar os brutos do minidocumentário para o HD de arquivo", caio,
        data_prazo=hoje + timedelta(days=10), prioridade="Baixa", evento_id=ev_doc)
    tarefas_service.criar_tarefa(
        "Renovar o seguro dos equipamentos", rafael,
        data_prazo=hoje + timedelta(days=15), prioridade="Baixa")
    tarefas_service.criar_tarefa(
        "Entregar a versão final do minidocumentário", rafael,
        data_prazo=m(2, 5), status="Concluída", prioridade="Alta", evento_id=ev_doc)
    tarefas_service.criar_tarefa(
        "Publicar o aftermovie do festival", julia,
        data_prazo=m(5, 10), status="Concluída", evento_id=ev_festival_1)

    # ---------------------------------------------------------------- orçamentos
    orc_service.garantir_precos_iniciais()
    orc_service.salvar_dados_empresa({
        "empresa_nome": "Claquete Produtora Audiovisual",
        "empresa_email": "contato@claquete.example",
        "empresa_telefone": "(11) 90000-0000",
        "empresa_site": "claquete.example",
        "empresa_cidade": "São Paulo/SP",
    })

    def orcamento(titulo, cliente_id, cliente_nome, data, status, itens, desconto=0.0,
                  contato="", email="", telefone="", responsavel="", data_evento=None,
                  prazo="", escopo="",
                  condicoes="50% na assinatura do contrato e 50% na entrega final.",
                  observacoes="Inclui uma rodada de alterações sem custo adicional."):
        orc_id = orc_service.criar_orcamento(titulo, cliente_nome, data, cliente_id=cliente_id)
        orc_service.atualizar_orcamento(
            orc_id, titulo, cliente_nome, data, 15, status, desconto, observacoes, condicoes,
            responsavel_nome=responsavel, cliente_contato=contato, cliente_email=email,
            cliente_telefone=telefone, data_evento=data_evento, prazo_entrega=prazo,
            escopo=escopo)
        for descricao, qtd, valor, unidade, pessoas, categoria in itens:
            orc_service.adicionar_item(orc_id, descricao, qtd, valor, unidade, pessoas, categoria)
        return orc_id

    orcamento(
        "Vídeo de abertura da 2ª unidade", c_aurora, "Café Aurora", hoje, "Rascunho",
        [("Reunião / Alinhamento com cliente", 1, 110.00, "hora", 2, "Gestão"),
         ("Captação de vídeo", 5, 180.00, "hora", 2, "Produção"),
         ("Captação de fotos", 3, 150.00, "hora", 1, "Produção"),
         ("Edição de vídeo", 10, 140.00, "hora", 1, "Pós-produção"),
         ("Tratamento de fotos", 4, 95.00, "hora", 1, "Pós-produção"),
         ("Deslocamento", 1, 50.00, "vez", 3, "Logística")],
        contato="Marina Alves", email="marina@cafeaurora.example",
        telefone="(11) 90000-1005", responsavel="Caio Ferraz",
        data_evento=_mes(-1, 25, hoje), prazo="10 dias úteis após a captação",
        escopo=("Vídeo de 60 segundos para redes sociais sobre a abertura da nova "
                "unidade, com versões 9:16 e 16:9, e 30 fotos tratadas do espaço e "
                "do cardápio."))
    orcamento(
        "Cobertura da edição de verão", c_festival, "Festival Sons do Parque",
        m(0, 2), "Enviado",
        [("Captação de vídeo", 20, 180.00, "hora", 3, "Produção"),
         ("Drone (diária)", 2, 600.00, "diária", 1, "Produção"),
         ("Edição de vídeo", 30, 140.00, "hora", 1, "Pós-produção"),
         ("Deslocamento", 2, 50.00, "vez", 3, "Logística")],
        desconto=5.0, contato="Lívia Torres", email="producao@sonsdoparque.example",
        responsavel="Júlia Campos", data_evento=_mes(-2, 12, hoje),
        prazo="Aftermovie em 7 dias; vídeos por atração em 20 dias")
    orcamento(
        "Filme institucional da construtora", c_alicerce, "Construtora Alicerce",
        m(1, 12), "Aprovado",
        [("Direção / Roteiro", 16, 170.00, "hora", 1, "Produção"),
         ("Captação de vídeo", 24, 180.00, "hora", 2, "Produção"),
         ("Edição de vídeo", 24, 140.00, "hora", 1, "Pós-produção"),
         ("Motion graphics", 8, 190.00, "hora", 1, "Pós-produção")],
        contato="Renato Prado", email="marketing@alicerce.example",
        responsavel="Rafael Nogueira", data_evento=hoje + timedelta(days=18),
        condicoes="30% na assinatura, 40% na captação e 30% na entrega.")
    orcamento(
        "Campanha de clareamento", c_sorriso, "Clínica Sorriso Pleno", m(4, 2), "Recusado",
        [("Captação de vídeo", 6, 180.00, "hora", 2, "Produção"),
         ("Edição de vídeo", 8, 140.00, "hora", 1, "Pós-produção")],
        contato="Dra. Paula Lima", responsavel="Júlia Campos")
