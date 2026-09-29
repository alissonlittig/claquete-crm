#!/bin/bash
# Atalho para abrir o sistema Claquete CRM/ERP com um clique duplo (Mac) ou
# rodando "./abrir_sistema_mac_linux.command" no terminal (Linux).
cd "$(dirname "$0")"

if [ ! -d "venv" ]; then
    echo "Ambiente virtual não encontrado. Rode primeiro:"
    echo "  python3 -m venv venv"
    echo "  source venv/bin/activate"
    echo "  pip install -r requirements.txt"
    read -p "Pressione Enter para sair..."
    exit 1
fi

source venv/bin/activate
streamlit run app.py
read -p "Pressione Enter para fechar..."
