"""
scripts/gerar_senha.py
-----------------------
Gera o "hash" de uma senha, no formato que o sistema espera encontrar no
cofre de segredos. Use este script sempre que precisar criar o acesso de um
sócio novo ou trocar a senha de alguém.

Como usar (na pasta do projeto, com o ambiente virtual ativado):

    python scripts/gerar_senha.py

O script pergunta o nome e a senha, e mostra a linha pronta para colar:

    - No arquivo `.streamlit/secrets.toml`, para rodar no seu computador
    - No campo "Secrets" do Streamlit Community Cloud, para o sistema publicado

A senha digitada NÃO é gravada em lugar nenhum — apenas o hash é exibido, e
não é possível voltar do hash para a senha original.
"""

import getpass
import os
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auth import gerar_hash

TAMANHO_MINIMO = 6


def _normalizar_nome(nome: str) -> str:
    """
    Deixa o nome no formato aceito como chave do arquivo de segredos:
    sem acentos e sem espaços (ex.: "Júlia Campos" -> "Julia_Campos").
    """
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFD", nome.strip())
        if unicodedata.category(c) != "Mn"
    )
    return "_".join(sem_acento.split())


def main() -> None:
    print("=" * 62)
    print("  GERADOR DE SENHA — Claquete CRM/ERP")
    print("=" * 62)
    print()

    nome = input("Nome do sócio (como aparecerá na tela de login): ").strip()
    if not nome:
        raise SystemExit("Nome não pode ficar vazio.")
    chave = _normalizar_nome(nome)

    # getpass esconde o que está sendo digitado (nada aparece na tela).
    senha = getpass.getpass("Senha desejada (não aparece enquanto digita): ")
    if len(senha) < TAMANHO_MINIMO:
        raise SystemExit(f"A senha precisa ter pelo menos {TAMANHO_MINIMO} caracteres.")

    confirmacao = getpass.getpass("Digite a senha novamente para confirmar: ")
    if senha != confirmacao:
        raise SystemExit("As senhas não conferem. Rode o script de novo.")

    hash_gerado = gerar_hash(senha)

    print()
    print("=" * 62)
    print("  COPIE A LINHA ABAIXO")
    print("=" * 62)
    print()
    print("[senhas]")
    print(f'{chave} = "{hash_gerado}"')
    print()
    print("-" * 62)
    print("ONDE COLAR:")
    print()
    print("  Para rodar no seu computador:")
    print("    no arquivo .streamlit/secrets.toml")
    print()
    print("  Para o sistema publicado:")
    print("    em Settings -> Secrets, nas configurações do app")
    print("    no Streamlit Community Cloud")
    print()
    print("A linha [senhas] aparece UMA vez só. Para vários sócios, use:")
    print()
    print("  [senhas]")
    print('  Rafael = "pbkdf2_sha256$..."')
    print('  Julia = "pbkdf2_sha256$..."')
    print('  Caio = "pbkdf2_sha256$..."')
    print("-" * 62)


if __name__ == "__main__":
    main()
