"""
database.py
------------
Camada de conexão e definição do schema do banco de dados.

Este módulo é o único lugar do sistema que sabe ONDE o banco de dados vive
e qual é a estrutura (schema) das tabelas. Todo o resto do sistema
(services/*.py) conversa com o banco através de `get_connection()`.

VERSÃO DE DEMONSTRAÇÃO
    O banco é um arquivo SQLite local (data/claquete_demo.db), sem nenhuma
    conta externa. Quando o arquivo não existe ou está vazio, `init_db()`
    carrega sozinho os dados fictícios de services/demo.py.

    No Streamlit Community Cloud o disco é apagado a cada reinício do app,
    então a demonstração volta ao estado inicial por conta própria.

Rodar este arquivo diretamente cria a base (e carrega a demo, se vazia):

    python database.py
"""

import os
import sqlite3
import threading
import time

# Caminho absoluto da pasta do projeto, para que o banco local seja sempre
# criado no mesmo lugar independentemente de onde o comando for executado.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "claquete_demo.db")


def descricao_banco() -> str:
    """Frase curta dizendo qual banco está em uso — exibida nos scripts."""
    return f"LOCAL (demonstração) — {DB_PATH}"


# Conexão reaproveitada por thread. O Streamlit executa cada carregamento de
# página em uma thread, e cada thread fica com a sua própria conexão.
_conexoes = threading.local()


def _abrir_conexao():
    """Abre uma conexão nova com o arquivo SQLite."""
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
    except sqlite3.Error:
        pass
    return conn


# Tempo máximo que uma conexão pode ficar parada antes de ser renovada.
# Renovar por tempo evita manter conexões ociosas abertas SEM precisar testar
# a conexão antes de cada consulta.
SEGUNDOS_OCIOSA_MAX = 45


def get_connection(nova: bool = False):
    """
    Devolve a conexão com o banco.

    POR QUE A CONEXÃO É REAPROVEITADA
        O Streamlit reexecuta a página inteira a cada clique. A conexão é
        aberta uma vez e reaproveitada enquanto estiver em uso, em vez de
        abrir e fechar uma por consulta.

    SEM "TESTE DE CONEXÃO" A CADA CONSULTA
        A conexão é simplesmente renovada quando fica parada por mais de
        SEGUNDOS_OCIOSA_MAX, e as leituras que falharem são repetidas uma vez
        com conexão nova (ver db_utils.py).

    `nova=True` força uma conexão separada (usado pelos scripts de terminal,
    que precisam controlar o fechamento eles mesmos).
    """
    if nova:
        return _abrir_conexao()

    agora = time.monotonic()
    conn = getattr(_conexoes, "conn", None)
    ultimo_uso = getattr(_conexoes, "ultimo_uso", 0.0)

    if conn is not None and agora - ultimo_uso < SEGUNDOS_OCIOSA_MAX:
        _conexoes.ultimo_uso = agora
        return conn

    descartar_conexao()
    conn = _abrir_conexao()
    _conexoes.conn = conn
    _conexoes.ultimo_uso = agora
    return conn


def descartar_conexao() -> None:
    """Fecha e esquece a conexão reaproveitada (a próxima será aberta do zero)."""
    conn = getattr(_conexoes, "conn", None)
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass
    _conexoes.conn = None


def medir_latencia_ms() -> float:
    """Tempo de uma ida e volta até o banco, em milissegundos."""
    conn = get_connection()
    inicio = time.perf_counter()
    conn.execute("SELECT 1").fetchone()
    return (time.perf_counter() - inicio) * 1000


def eh_conexao_compartilhada(conn) -> bool:
    """Informa se esta conexão é a reaproveitada (não deve ser fechada)."""
    return getattr(_conexoes, "conn", None) is conn


def fechar_conexao() -> None:
    """Fecha a conexão reaproveitada desta thread, se houver."""
    descartar_conexao()



SCHEMA_SQL = """
-- =========================================================================
-- SÓCIOS
-- =========================================================================
CREATE TABLE IF NOT EXISTS socios (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nome            TEXT NOT NULL UNIQUE,
    email           TEXT,
    telefone        TEXT,
    data_entrada    TEXT,
    ativo           INTEGER NOT NULL DEFAULT 1
);

-- Aportes: qualquer valor que o sócio investe na empresa (dinheiro em caixa
-- OU pagamento de uma despesa da empresa diretamente do próprio bolso).
CREATE TABLE IF NOT EXISTS aportes (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    socio_id          INTEGER NOT NULL REFERENCES socios(id) ON DELETE CASCADE,
    data              TEXT NOT NULL,
    descricao         TEXT NOT NULL,
    categoria         TEXT NOT NULL DEFAULT 'Dinheiro em Caixa',
    valor             REAL NOT NULL CHECK (valor > 0),
    entrou_no_caixa   INTEGER NOT NULL DEFAULT 1,
    reembolsavel      INTEGER NOT NULL DEFAULT 1,
    observacao        TEXT,
    fluxo_caixa_id    INTEGER REFERENCES fluxo_caixa(id) ON DELETE SET NULL
);

-- Reembolsos: devolução de dinheiro da empresa para o sócio, abatendo dívida.
CREATE TABLE IF NOT EXISTS reembolsos_socios (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    socio_id          INTEGER NOT NULL REFERENCES socios(id) ON DELETE CASCADE,
    data              TEXT NOT NULL,
    valor             REAL NOT NULL CHECK (valor > 0),
    descricao         TEXT,
    fluxo_caixa_id    INTEGER REFERENCES fluxo_caixa(id) ON DELETE SET NULL
);

-- =========================================================================
-- CLIENTES E EVENTOS / PROJETOS  (CRM)
-- =========================================================================
CREATE TABLE IF NOT EXISTS clientes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nome            TEXT NOT NULL,
    empresa         TEXT,
    email           TEXT,
    telefone        TEXT,
    origem          TEXT,
    data_cadastro   TEXT,
    observacao      TEXT
);

CREATE TABLE IF NOT EXISTS eventos (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id      INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
    nome            TEXT NOT NULL,
    tipo            TEXT,
    data_evento     TEXT,
    valor_total     REAL NOT NULL CHECK (valor_total >= 0),
    status          TEXT NOT NULL DEFAULT 'Orçamento',
    observacao      TEXT,
    criado_em       TEXT NOT NULL
);

-- Anexos do projeto: links para contratos, notas fiscais e outros documentos
-- guardados no Drive da produtora. Guardamos apenas o ENDEREÇO do arquivo —
-- o conteúdo continua no Drive, o que mantém o banco leve e evita perder
-- arquivos quando o servidor do sistema é reiniciado.
CREATE TABLE IF NOT EXISTS anexos_evento (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    evento_id       INTEGER NOT NULL REFERENCES eventos(id) ON DELETE CASCADE,
    tipo            TEXT NOT NULL DEFAULT 'Outro',
    descricao       TEXT,
    url             TEXT NOT NULL,
    data_cadastro   TEXT NOT NULL
);

-- Pagamentos recebidos do cliente para um evento (pode ser parcelado).
-- `link_recibo` guarda o endereço do comprovante no Drive, quando houver.
CREATE TABLE IF NOT EXISTS recebimentos (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    evento_id         INTEGER NOT NULL REFERENCES eventos(id) ON DELETE CASCADE,
    data              TEXT NOT NULL,
    valor             REAL NOT NULL CHECK (valor > 0),
    forma_pagamento   TEXT,
    observacao        TEXT,
    link_recibo       TEXT,
    fluxo_caixa_id    INTEGER REFERENCES fluxo_caixa(id) ON DELETE SET NULL
);

-- =========================================================================
-- CUSTOS FIXOS
-- =========================================================================
CREATE TABLE IF NOT EXISTS custos_fixos (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    nome             TEXT NOT NULL,
    categoria        TEXT NOT NULL DEFAULT 'Assinatura/Software',
    valor            REAL NOT NULL CHECK (valor > 0),
    dia_vencimento   INTEGER,
    data_inicio      TEXT,
    ativo            INTEGER NOT NULL DEFAULT 1,
    observacao       TEXT
);

CREATE TABLE IF NOT EXISTS custos_fixos_pagamentos (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    custo_fixo_id    INTEGER NOT NULL REFERENCES custos_fixos(id) ON DELETE CASCADE,
    referencia_mes   TEXT NOT NULL,
    data_vencimento  TEXT,
    data_pagamento   TEXT,
    valor            REAL NOT NULL,
    pago             INTEGER NOT NULL DEFAULT 0,
    fluxo_caixa_id   INTEGER REFERENCES fluxo_caixa(id) ON DELETE SET NULL,
    UNIQUE (custo_fixo_id, referencia_mes)
);

-- =========================================================================
-- INVESTIMENTOS (equipamentos e softwares - CAPEX)
-- =========================================================================
CREATE TABLE IF NOT EXISTS investimentos (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    nome               TEXT NOT NULL,
    categoria          TEXT NOT NULL DEFAULT 'Equipamento',
    valor              REAL NOT NULL CHECK (valor > 0),
    data_compra        TEXT NOT NULL,
    fornecedor         TEXT,
    vida_util_meses    INTEGER,
    forma_pagamento    TEXT NOT NULL DEFAULT 'Caixa da Empresa',
    socio_id           INTEGER REFERENCES socios(id) ON DELETE SET NULL,
    observacao         TEXT,
    fluxo_caixa_id     INTEGER REFERENCES fluxo_caixa(id) ON DELETE SET NULL,
    aporte_id          INTEGER REFERENCES aportes(id) ON DELETE SET NULL
);

-- =========================================================================
-- FLUXO DE CAIXA  (livro-razão único de todas as entradas e saídas reais)
-- =========================================================================
CREATE TABLE IF NOT EXISTS fluxo_caixa (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    data            TEXT NOT NULL,
    tipo            TEXT NOT NULL CHECK (tipo IN ('Entrada', 'Saída')),
    categoria       TEXT NOT NULL,
    descricao       TEXT NOT NULL,
    valor           REAL NOT NULL CHECK (valor > 0),
    origem_tabela   TEXT NOT NULL DEFAULT 'manual',
    origem_id       INTEGER,
    socio_id        INTEGER REFERENCES socios(id) ON DELETE SET NULL,
    criado_em       TEXT NOT NULL
);


-- =========================================================================
-- AGENDA / PLANNER  (tarefas dos sócios)
-- =========================================================================
-- O status "Atrasado" NÃO é guardado: ele é calculado na hora, comparando o
-- prazo com a data de hoje. Assim uma tarefa nunca fica marcada como atrasada
-- por engano, nem precisa de rotina para atualizar status.
CREATE TABLE IF NOT EXISTS tarefas (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo          TEXT NOT NULL,
    descricao       TEXT,
    socio_id        INTEGER REFERENCES socios(id) ON DELETE SET NULL,
    evento_id       INTEGER REFERENCES eventos(id) ON DELETE SET NULL,
    data_inicio     TEXT,
    data_prazo      TEXT,
    status          TEXT NOT NULL DEFAULT 'A Fazer',
    prioridade      TEXT NOT NULL DEFAULT 'Normal',
    concluida_em    TEXT,
    criado_em       TEXT NOT NULL
);

-- =========================================================================
-- ORÇAMENTOS  (precificação de projetos)
-- =========================================================================
-- Tabela de preços da produtora: valor por hora de cada tipo de serviço.
-- É editável na própria tela de Orçamentos.
CREATE TABLE IF NOT EXISTS precos_servicos (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nome            TEXT NOT NULL UNIQUE,
    unidade         TEXT NOT NULL DEFAULT 'hora',
    valor_unitario  REAL NOT NULL CHECK (valor_unitario >= 0),
    categoria       TEXT NOT NULL DEFAULT 'Produção',
    ativo           INTEGER NOT NULL DEFAULT 1,
    ordem           INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS orcamentos (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo            TEXT NOT NULL,
    cliente_id        INTEGER REFERENCES clientes(id) ON DELETE SET NULL,
    cliente_nome      TEXT NOT NULL,
    data              TEXT NOT NULL,
    validade_dias     INTEGER NOT NULL DEFAULT 15,
    status            TEXT NOT NULL DEFAULT 'Rascunho',
    desconto_percent  REAL NOT NULL DEFAULT 0,
    observacoes       TEXT,
    condicoes         TEXT,
    criado_em         TEXT NOT NULL,
    responsavel_nome  TEXT,
    cliente_contato   TEXT,
    cliente_email     TEXT,
    cliente_telefone  TEXT,
    data_evento       TEXT,
    prazo_entrega     TEXT,
    escopo            TEXT
);

-- Histórico de propostas EMITIDAS. Cada emissão guarda uma cópia congelada
-- do documento, exatamente como foi enviado ao cliente — se o orçamento for
-- alterado depois, a proposta antiga continua registrada como era.
CREATE TABLE IF NOT EXISTS propostas_emitidas (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    orcamento_id    INTEGER REFERENCES orcamentos(id) ON DELETE SET NULL,
    numero          TEXT NOT NULL,
    versao          INTEGER NOT NULL DEFAULT 1,
    titulo          TEXT NOT NULL,
    cliente_nome    TEXT NOT NULL,
    total           REAL NOT NULL DEFAULT 0,
    emitida_em      TEXT NOT NULL,
    emitida_por     TEXT,
    documento_html  TEXT NOT NULL
);

-- Dados da própria produtora que aparecem nas propostas (CNPJ, contato...).
-- Guardados como pares chave/valor e editáveis na tela de Orçamentos.
CREATE TABLE IF NOT EXISTS configuracoes (
    chave   TEXT PRIMARY KEY,
    valor   TEXT
);

-- Cada linha do orçamento. `quantidade` é o número de horas (ou de diárias,
-- km etc. conforme a unidade) e `pessoas` multiplica o valor quando a etapa
-- envolve mais de um profissional.
CREATE TABLE IF NOT EXISTS orcamento_itens (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    orcamento_id    INTEGER NOT NULL REFERENCES orcamentos(id) ON DELETE CASCADE,
    descricao       TEXT NOT NULL,
    categoria       TEXT NOT NULL DEFAULT 'Produção',
    unidade         TEXT NOT NULL DEFAULT 'hora',
    quantidade      REAL NOT NULL DEFAULT 0,
    pessoas         INTEGER NOT NULL DEFAULT 1,
    valor_unitario  REAL NOT NULL DEFAULT 0,
    ordem           INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_anexos_evento ON anexos_evento(evento_id);
CREATE INDEX IF NOT EXISTS idx_tarefas_socio ON tarefas(socio_id);
CREATE INDEX IF NOT EXISTS idx_tarefas_status ON tarefas(status);
CREATE INDEX IF NOT EXISTS idx_orcamento_itens ON orcamento_itens(orcamento_id);
CREATE INDEX IF NOT EXISTS idx_propostas_orcamento ON propostas_emitidas(orcamento_id);

CREATE INDEX IF NOT EXISTS idx_fluxo_data ON fluxo_caixa(data);
CREATE INDEX IF NOT EXISTS idx_aportes_socio ON aportes(socio_id);
CREATE INDEX IF NOT EXISTS idx_eventos_cliente ON eventos(cliente_id);
CREATE INDEX IF NOT EXISTS idx_recebimentos_evento ON recebimentos(evento_id);
"""


# Colunas acrescentadas depois que o sistema já estava em uso. O comando
# CREATE TABLE IF NOT EXISTS não altera tabelas que já existem, então bancos
# criados antes precisam receber essas colunas à parte.
COLUNAS_ADICIONADAS = [
    ("orcamentos", "responsavel_nome", "TEXT"),
    ("orcamentos", "cliente_contato", "TEXT"),
    ("orcamentos", "cliente_email", "TEXT"),
    ("orcamentos", "cliente_telefone", "TEXT"),
    ("orcamentos", "data_evento", "TEXT"),
    ("orcamentos", "prazo_entrega", "TEXT"),
    ("orcamentos", "escopo", "TEXT"),
]


def _aplicar_migracoes(conn) -> None:
    """
    Acrescenta colunas novas em tabelas antigas. Cada ALTER TABLE falha
    silenciosamente quando a coluna já existe — então pode rodar sempre,
    sem risco.
    """
    for tabela, coluna, tipo in COLUNAS_ADICIONADAS:
        try:
            conn.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo}")
        except Exception:
            pass  # coluna já existe

    # Regra de negócio alterada: o deslocamento deixou de ser cobrado por km
    # e passou a ser um valor fixo de R$ 50 por pessoa. Bancos criados antes
    # ainda têm o serviço cadastrado por km — este ajuste corrige uma única
    # vez (depois disso nenhuma linha corresponde e o comando não faz nada).
    # Orçamentos e propostas JÁ EMITIDOS não são alterados.
    try:
        conn.execute(
            "UPDATE precos_servicos SET unidade = 'vez', valor_unitario = 50.0 "
            "WHERE nome = 'Deslocamento' AND unidade = 'km'"
        )
    except Exception:
        pass  # tabela ainda não existe


# Marca se o schema já foi conferido neste processo. O Streamlit mantém os
# módulos carregados entre um clique e outro, então basta conferir UMA vez.
_schema_conferido = False
# Várias sessões podem abrir o app ao mesmo tempo logo depois de um reinício;
# a trava garante que o schema e os dados de demonstração sejam criados uma
# única vez.
_trava_init = threading.RLock()


def init_db(forcar: bool = False) -> None:
    """
    Cria as tabelas que faltarem, aplica as migrações e, se o banco estiver
    vazio, carrega os dados de demonstração. Idempotente.

    DESEMPENHO
        Todas as páginas chamam esta função ao abrir. A conferência acontece
        só na primeira vez que o sistema é aberto; nos cliques seguintes a
        função retorna imediatamente.

    `forcar=True` refaz a conferência (usado pelos scripts de terminal).
    """
    global _schema_conferido
    if _schema_conferido and not forcar:
        return

    with _trava_init:
        if _schema_conferido and not forcar:
            return
        conn = get_connection()
        try:
            conn.executescript(SCHEMA_SQL)
            _aplicar_migracoes(conn)
            conn.commit()
            _schema_conferido = True
        finally:
            # A conexão reaproveitada NÃO é fechada aqui — fechá-la obrigaria a
            # próxima consulta a reconectar, justamente o custo que evitamos.
            if not eh_conexao_compartilhada(conn):
                try:
                    conn.close()
                except Exception:
                    pass

        # Importação tardia: services/ depende deste módulo.
        from services import demo
        demo.popular_se_vazio()


if __name__ == "__main__":
    init_db()
    print(f"Banco de dados pronto: {descricao_banco()}")
