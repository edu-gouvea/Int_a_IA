"""
grafo.py — Estrutura de dados de Grafo usada pelos algoritmos de busca.

Os algoritmos (DLS e IDS) NÃO conhecem a matriz do labirinto: eles enxergam
apenas este objeto Grafo, ou seja, um conjunto de nós e uma lista de
adjacência ponderada. Isso garante que a busca seja feita rigorosamente
sobre um grafo, e não "andando" diretamente na matriz.

Representação
-------------
    adjacencia = {
        no_A: {no_B: peso_AB, no_C: peso_AC},
        no_B: {no_A: peso_BA},
        ...
    }

Os nós podem ser quaisquer objetos "hashable" (no labirinto usamos tuplas
(linha, coluna), mas o algoritmo as trata como identificadores opacos).

O grafo pode ser dirigido: o peso de A->B pode ser diferente de B->A. No
labirinto com terrenos, o peso de uma aresta é o custo de ENTRAR na célula
de destino (ex.: entrar num pântano custa mais do que entrar no asfalto).
"""

from typing import Dict, Hashable, Iterable, List, Optional, Sequence

No = Hashable


class Grafo:
    """
    Grafo ponderado representado por lista de adjacência.

    Atributos
    ---------
    adjacencia : dict
        Mapeia cada nó para um dicionário {vizinho: peso_da_aresta}.
    limite_profundidade : int | None
        Limite de profundidade associado a esta instância do problema
        ("labirinto com limite de profundidade"). É lido pela DLS, pois a
        assinatura exigida dos algoritmos tem apenas 3 parâmetros
        (grafo, estado_inicial, estado_objetivo). A IDS o ignora, já que ela
        descobre o limite sozinha, aumentando-o de 1 em 1.
    """

    def __init__(self, limite_profundidade: Optional[int] = None) -> None:
        self.adjacencia: Dict[No, Dict[No, float]] = {}
        self.limite_profundidade = limite_profundidade

    # ------------------------------------------------------------------ #
    # Construção
    # ------------------------------------------------------------------ #
    def adicionar_no(self, no: No) -> None:
        """Adiciona um nó isolado (sem arestas), se ainda não existir."""
        self.adjacencia.setdefault(no, {})

    def adicionar_aresta(self, origem: No, destino: No, peso: float = 1.0) -> None:
        """Adiciona uma aresta DIRIGIDA origem -> destino com o peso dado."""
        self.adicionar_no(origem)
        self.adicionar_no(destino)
        self.adjacencia[origem][destino] = peso

    # ------------------------------------------------------------------ #
    # Consultas usadas pelos algoritmos
    # ------------------------------------------------------------------ #
    def vizinhos(self, no: No) -> Iterable[No]:
        """Retorna os vizinhos (sucessores) de um nó, em ordem estável."""
        return self.adjacencia.get(no, {}).keys()

    def peso(self, origem: No, destino: No) -> float:
        """Retorna o peso da aresta origem -> destino (KeyError se não existir)."""
        return self.adjacencia[origem][destino]

    def existe_aresta(self, origem: No, destino: No) -> bool:
        return destino in self.adjacencia.get(origem, {})

    def custo_caminho(self, caminho: Sequence[No]) -> float:
        """
        Soma dos pesos das arestas de um caminho [n0, n1, ..., nk].
        Um caminho vazio ou com um único nó tem custo 0.
        """
        return sum(self.peso(a, b) for a, b in zip(caminho, caminho[1:]))

    def caminho_valido(self, caminho: Sequence[No]) -> bool:
        """Verifica se todos os pares consecutivos do caminho são arestas do grafo."""
        return all(self.existe_aresta(a, b) for a, b in zip(caminho, caminho[1:]))

    # ------------------------------------------------------------------ #
    # Informações gerais
    # ------------------------------------------------------------------ #
    @property
    def nos(self) -> List[No]:
        return list(self.adjacencia.keys())

    def numero_de_nos(self) -> int:
        return len(self.adjacencia)

    def numero_de_arestas(self) -> int:
        return sum(len(v) for v in self.adjacencia.values())

    def __contains__(self, no: No) -> bool:
        return no in self.adjacencia

    def __repr__(self) -> str:
        return (f"Grafo(nos={self.numero_de_nos()}, "
                f"arestas={self.numero_de_arestas()}, "
                f"limite_profundidade={self.limite_profundidade})")
