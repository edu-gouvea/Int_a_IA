#!/usr/bin/env python3
"""
visualizar.py — Mostra a DLS ou a IDS resolvendo um labirinto no terminal.

Exemplos
--------
    python3 visualizar.py                               # IDS, 15x15
    python3 visualizar.py --algoritmo dls --limite 40
    python3 visualizar.py --cenario 4 --algoritmo ids   # labirinto com terrenos
    python3 visualizar.py --tamanho 11 --passo-a-passo  # ENTER a cada passo
    python3 visualizar.py --cenario 3 --pular 20 --atraso 0.01

Use ``python3 visualizar.py --help`` para ver todas as opções.
"""

import argparse

from busca_labirinto.algoritmos import (busca_aprofundamento_iterativo,
                                        busca_profundidade_limitada)
from busca_labirinto.cenarios import criar_cenarios
from busca_labirinto.labirinto import gerar_labirinto
from busca_labirinto.visualizador import visualizar

FUNCOES = {
    "dls": ("DLS", busca_profundidade_limitada),
    "ids": ("IDS", busca_aprofundamento_iterativo),
}


def main() -> None:
    p = argparse.ArgumentParser(
        description="Visualização passo a passo de DLS/IDS em um labirinto.")
    p.add_argument("--algoritmo", "-a", choices=FUNCOES, default="ids",
                   help="algoritmo de busca (padrão: ids)")
    p.add_argument("--cenario", "-c", type=int, choices=[1, 2, 3, 4],
                   help="usa um dos cenários da bateria de experimentos "
                        "(1=5x5, 2=15x15, 3=30x30, 4=terrenos)")
    p.add_argument("--tamanho", "-t", type=int, default=15,
                   help="lado do labirinto gerado quando não se usa --cenario (padrão: 15)")
    p.add_argument("--semente", "-s", type=int, default=42,
                   help="semente aleatória do labirinto (padrão: 42)")
    p.add_argument("--ciclos", type=float, default=0.15,
                   help="fração de paredes removidas para criar ciclos (padrão: 0.15)")
    p.add_argument("--terrenos", action="store_true",
                   help="espalha grama/areia/pântano (custos diferentes)")
    p.add_argument("--limite", "-l", type=int,
                   help="limite de profundidade da DLS (padrão: o do cenário, "
                        "ou ilimitado para labirintos gerados)")
    p.add_argument("--atraso", "-d", type=float, default=0.05,
                   help="segundos entre quadros (padrão: 0.05)")
    p.add_argument("--pular", type=int, default=1,
                   help="desenha 1 quadro a cada N expansões (padrão: 1)")
    p.add_argument("--passo-a-passo", action="store_true",
                   help="espera ENTER a cada passo")
    args = p.parse_args()

    if args.cenario:
        cenario = criar_cenarios()[args.cenario - 1]
        labirinto = cenario.labirinto
        limite = args.limite if args.limite is not None else cenario.grafo.limite_profundidade
    else:
        labirinto = gerar_labirinto(args.tamanho, args.tamanho, semente=args.semente,
                                    taxa_ciclos=args.ciclos, com_terrenos=args.terrenos,
                                    nome=f"{args.tamanho}x{args.tamanho} (semente {args.semente})")
        limite = args.limite

    nome, funcao = FUNCOES[args.algoritmo]
    try:
        visualizar(labirinto, funcao, nome, limite=limite, atraso=args.atraso,
                   pular=args.pular, passo_a_passo=args.passo_a_passo)
    except KeyboardInterrupt:
        print("\nVisualização interrompida.")


if __name__ == "__main__":
    main()
