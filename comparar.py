#!/usr/bin/env python3
"""
comparar.py — Roda a bateria de experimentos e imprime a tabela comparativa
entre DLS e IDS (memória, nós explorados, tempo, passos e custo).

Uso
---
    python3 comparar.py                     # tabela no terminal
    python3 comparar.py --repeticoes 20     # mais repetições p/ medir tempo
    python3 comparar.py --csv resultados.csv
"""

import argparse

from busca_labirinto.comparacao import (executar_comparacao, imprimir_tabela,
                                        salvar_csv)


def main() -> None:
    p = argparse.ArgumentParser(description="Comparação DLS x IDS nos cenários de teste.")
    p.add_argument("--repeticoes", "-r", type=int, default=5,
                   help="execuções por medição de tempo (usa a mediana; padrão: 5)")
    p.add_argument("--csv", help="também salva os resultados neste arquivo CSV")
    args = p.parse_args()

    print("Executando experimentos...\n")
    medicoes = executar_comparacao(repeticoes=args.repeticoes)
    imprimir_tabela(medicoes)
    if args.csv:
        salvar_csv(medicoes, args.csv)
        print(f"\nResultados salvos em {args.csv}")


if __name__ == "__main__":
    main()
