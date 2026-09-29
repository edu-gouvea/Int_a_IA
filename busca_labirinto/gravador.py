"""
gravador.py — Grava a execução de uma busca como uma sequência de quadros.

Como funciona
-------------
Os algoritmos aceitam um ``observador`` (callback) que é chamado a cada
evento da busca. O ``Gravador`` é um observador que, em vez de desenhar,
tira uma "foto" do estado da busca a cada evento e a guarda numa lista.

A busca roda inteira de uma vez (é rápida); depois a interface gráfica
"reproduz" a lista de quadros no ritmo que quiser, podendo pausar, avançar
e voltar passos sem precisar rodar o algoritmo de novo.

Eventos gravados
----------------
    "iteracao"  começou uma busca com limite L (na IDS, a cada novo L)
    "expandir"  um nó foi retirado da fronteira e expandido
    "fim"       a busca terminou (com ou sem solução)
"""

from dataclasses import dataclass
from typing import Callable, Dict, Hashable, List, Optional, Tuple

from .algoritmos import ResultadoBusca
from .grafo import Grafo

No = Hashable


@dataclass(frozen=True)
class Quadro:
    """Estado da busca em um instante (uma "foto")."""
    evento: str                         # "iteracao", "expandir" ou "fim"
    iteracao: int                       # 1, 2, 3, ... (a DLS tem só uma)
    limite: Optional[int]               # limite L da iteração corrente
    total_expandidos: int               # expansões desde o início (todas as iterações)
    no: Optional[No] = None             # nó sendo expandido ("expandir")
    profundidade: Optional[int] = None  # profundidade desse nó
    fronteira: Tuple[No, ...] = ()      # cópia da pilha (topo no final)
    ramo: Tuple[No, ...] = ()           # caminho do início até ``no``
    resultado: Optional[ResultadoBusca] = None  # só no evento "fim"


class Gravador:
    """Observador que acumula os eventos da busca em ``self.quadros``."""

    def __init__(self) -> None:
        self.quadros: List[Quadro] = []
        self._iteracao = 0
        self._limite: Optional[int] = None
        self._total = 0

    def __call__(self, evento: str, **dados) -> None:
        if evento == "iteracao":
            self._iteracao += 1
            self._limite = dados["limite"]
            self._adicionar(evento)

        elif evento == "expandir":
            self._total += 1
            no = dados["no"]
            self._adicionar(
                evento,
                no=no,
                profundidade=dados["profundidade"],
                # A fronteira e os pais continuam mudando depois deste
                # evento, então guardamos CÓPIAS (tuplas imutáveis).
                fronteira=tuple(n for n, _ in dados["fronteira"]),
                ramo=_ramo(dados["pai"], no),
            )

        elif evento == "fim":
            self._adicionar(evento, resultado=dados["resultado"])

    def _adicionar(self, evento: str, **campos) -> None:
        self.quadros.append(Quadro(evento=evento, iteracao=self._iteracao,
                                   limite=self._limite,
                                   total_expandidos=self._total, **campos))


def _ramo(pai: Dict[No, Optional[No]], no: No) -> Tuple[No, ...]:
    """Segue os ponteiros de pai de ``no`` até o início (ordem: início -> no)."""
    ramo = []
    while no is not None:
        ramo.append(no)
        no = pai.get(no)
    ramo.reverse()
    return tuple(ramo)


def gravar_busca(funcao_busca: Callable, grafo: Grafo, inicio: No,
                 objetivo: No) -> Tuple[ResultadoBusca, List[Quadro]]:
    """
    Executa ``funcao_busca`` (versão com observador de DLS ou IDS) e devolve
    o resultado junto com a lista de quadros gravados.
    """
    gravador = Gravador()
    resultado = funcao_busca(grafo, inicio, objetivo, observador=gravador)
    return resultado, gravador.quadros
