# Claquete CRM/ERP (demonstração pública)

Versão pública de demonstração de um CRM/ERP com DRE para produtora audiovisual. Python + Streamlit + SQLite local. Todos os dados são fictícios.

## Estrutura
- `app.py`: dashboard (página inicial). `pages/`: uma página por arquivo.
- `services/`: regras de negócio. `services/demo.py`: dados fictícios da demonstração.
- `ui/`: tema, gráficos, componentes, proposta. `database.py`: schema e conexão.
- `scripts/`: utilitários de linha de comando (seed, senhas, logo, custos do mês).

## Rodar e testar
- `streamlit run app.py`. Login de demonstração: `demo` / `claquete`.
- O banco (`data/claquete_demo.db`) é criado e populado sozinho quando está vazio. Para voltar ao estado inicial: `python scripts/seed_demo.py`.
- Antes de dar uma tarefa por concluída: `python -m py_compile` nos arquivos alterados e abrir a página afetada.

## Regras
- Nunca colocar dados reais (nomes, e-mails, telefones, clientes, valores) no código ou nos dados de demonstração.
- Nunca commitar `.env`, `.streamlit/secrets.toml`, `data/*.db` ou `backups/`.
- Versões das bibliotecas ficam fixas no `requirements.txt`.
- Respeitar a identidade visual em `ui/theme.py` (grafite + amarelo claquete + listras). Textos da interface em português do Brasil.
- Lógica nova em `services/`, não dentro das páginas.
