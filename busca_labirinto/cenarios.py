"""
cenarios.py — Definição dos cenários da bateria de experimentos.

Cenários
--------
1. Pequeno   (5x5)
2. Médio     (15x15)
3. Grande    (30x30)
4. Terrenos  (21x21) com custos diferentes: asfalto=1, grama=2, areia=3,
   pântano=5. DLS e IDS ignoram os pesos durante a busca, mas o grafo os
   armazena, o que permite calcular o CUSTO do caminho encontrado.

Escolha do limite L da DLS
--------------------------
O limite faz parte da instância do problema. Para que a comparação seja
justa (a DLS ter chance de encontrar a solução), usamos:

    L = profundidade_mínima + 50% de folga

onde a profundidade mínima é obtida por uma busca em largura (BFS)
auxiliar, usada APENAS para calibrar o cenário — ela não faz parte dos
algoritmos avaliados.
"""

from collections import deque
from dataclasses import dataclass
from math import ceil
from typing import Hashable, List, Optional

from .grafo import Grafo
from .labirinto import Labirinto, gerar_labirinto

FOLGA_LIMITE = 0.5  # 50% acima da profundidade mínima


@dataclass
class Cenario:
    nome: str
    labirinto: Labirinto
    grafo: Grafo
    profundidade_minima: Optional[int]

    @property
    def inicio(self):
        return self.labirinto.inicio

    @property
    def objetivo(self):
        return self.labirinto.objetivo


def profundidade_minima_bfs(grafo: Grafo, inicio: Hashable, objetivo: Hashable) -> Optional[int]:
    """BFS auxiliar: menor número de passos entre início e objetivo (ou None)."""
    if inicio not in grafo or objetivo not in grafo:
        return None
    distancia = {inicio: 0}
    fila = deque([inicio])
    while fila:
        u = fila.popleft()
        if u == objetivo:
            return distancia[u]
        for v in grafo.vizinhos(u):
            if v not in distancia:
                distancia[v] = distancia[u] + 1
                fila.append(v)
    return None


def montar_cenario(nome: str, labirinto: Labirinto,
                   limite: Optional[int] = None) -> Cenario:
    """
    Converte o labirinto em grafo e define o limite de profundidade.
    Se ``limite`` for None, ele é calculado com a folga padrão.
    """
    grafo = labirinto.para_grafo()
    d_min = profundidade_minima_bfs(grafo, labirinto.inicio, labirinto.objetivo)
    if limite is None:
        limite = ceil(d_min * (1 + FOLGA_LIMITE)) if d_min is not None else grafo.numero_de_nos()
    grafo.limite_profundidade = limite
    return Cenario(nome=nome, labirinto=labirinto, grafo=grafo, profundidade_minima=d_min)


def criar_cenarios() -> List[Cenario]:
    """Cria os 4 cenários oficiais da bateria de experimentos (reprodutíveis)."""
    return [
        montar_cenario("1. Pequeno 5x5",
                       gerar_labirinto(5, 5, semente=1, taxa_ciclos=0.5,
                                       nome="Pequeno 5x5")),
        montar_cenario("2. Médio 15x15",
                       gerar_labirinto(15, 15, semente=2, taxa_ciclos=0.15,
                                       nome="Médio 15x15")),
        montar_cenario("3. Grande 30x30",
                       gerar_labirinto(30, 30, semente=3, taxa_ciclos=0.10,
                                       nome="Grande 30x30")),
        montar_cenario("4. Terrenos 21x21",
                       gerar_labirinto(21, 21, semente=4, taxa_ciclos=0.15,
                                       com_terrenos=True, nome="Terrenos 21x21")),
    ]
