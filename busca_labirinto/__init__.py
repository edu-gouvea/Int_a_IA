"""
busca_labirinto — Trabalho de IA: DLS e IDS aplicadas a labirintos.

Módulos
-------
grafo         Estrutura de Grafo (lista de adjacência ponderada)
labirinto     Motor do labirinto: geração da matriz e conversão para grafo
algoritmos    DLS e IDS  ->  dls(grafo, inicial, objetivo), ids(...)
visualizador  Animação passo a passo no terminal (ANSI + time.sleep)
cenarios      Cenários da bateria de experimentos
comparacao    Métricas (tracemalloc, tempo, nós, passos, custo) e tabela
"""

from .algoritmos import ResultadoBusca, dls, ids
from .grafo import Grafo
from .labirinto import Labirinto, gerar_labirinto, labirinto_de_texto

__all__ = ["dls", "ids", "ResultadoBusca", "Grafo", "Labirinto",
           "gerar_labirinto", "labirinto_de_texto"]
