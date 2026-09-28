"""
labirinto.py — Motor do labirinto: geração da matriz (grid) e conversão
para Grafo.

O labirinto é uma matriz de caracteres/inteiros onde cada célula é:

    PAREDE  -> não pode ser atravessada (não vira nó do grafo)
    terreno -> célula livre; o tipo do terreno define o custo de entrar nela

Terrenos disponíveis (custo de entrar na célula):

    ASFALTO  = 1   (padrão; em labirintos "sem custo" tudo é asfalto)
    GRAMA    = 2
    AREIA    = 3
    PANTANO  = 5

Geração
-------
1. Algoritmo "recursive backtracker" (DFS aleatória) escava corredores nas
   posições ímpares da matriz, produzindo um labirinto PERFEITO (uma árvore:
   existe exatamente um caminho entre quaisquer duas células).
2. Em seguida removemos algumas paredes extras (``taxa_ciclos``) para criar
   CICLOS. Assim o labirinto passa a ser um grafo genérico, com múltiplos
   caminhos entre início e objetivo — cenário em que DLS e IDS se comportam
   de maneira diferente (a DLS pode achar um caminho longo, a IDS acha o
   caminho mais curto em número de passos).
3. Opcionalmente, "pintamos" manchas de terrenos com custos diferentes.

Tudo é determinístico a partir de uma ``semente`` (seed), para que os
experimentos sejam reprodutíveis.
"""

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .grafo import Grafo

Posicao = Tuple[int, int]  # (linha, coluna)

# --------------------------------------------------------------------------- #
# Tipos de célula
# --------------------------------------------------------------------------- #
PAREDE = 0
ASFALTO = 1
GRAMA = 2
AREIA = 3
PANTANO = 4

# Custo para ENTRAR em uma célula de cada terreno (peso da aresta).
CUSTO_TERRENO: Dict[int, int] = {
    ASFALTO: 1,
    GRAMA: 2,
    AREIA: 3,
    PANTANO: 5,
}

NOME_TERRENO: Dict[int, str] = {
    PAREDE: "Parede",
    ASFALTO: "Asfalto",
    GRAMA: "Grama",
    AREIA: "Areia",
    PANTANO: "Pântano",
}

# Ordem fixa de geração de vizinhos: Norte, Leste, Sul, Oeste.
# A ordem influencia QUAL caminho a busca em profundidade encontra primeiro,
# por isso ela é fixa (resultados reprodutíveis).
DIRECOES: List[Posicao] = [(-1, 0), (0, 1), (1, 0), (0, -1)]


@dataclass
class Labirinto:
    """
    Labirinto baseado em matriz.

    Atributos
    ---------
    matriz : list[list[int]]
        ``matriz[l][c]`` contém PAREDE ou um tipo de terreno.
    inicio, objetivo : Posicao
        Células de partida e de chegada.
    nome : str
        Nome descritivo (usado nos relatórios).
    """

    matriz: List[List[int]]
    inicio: Posicao
    objetivo: Posicao
    nome: str = "Labirinto"
    semente: Optional[int] = None
    extras: dict = field(default_factory=dict)

    @property
    def linhas(self) -> int:
        return len(self.matriz)

    @property
    def colunas(self) -> int:
        return len(self.matriz[0]) if self.matriz else 0

    def dentro(self, pos: Posicao) -> bool:
        l, c = pos
        return 0 <= l < self.linhas and 0 <= c < self.colunas

    def livre(self, pos: Posicao) -> bool:
        return self.dentro(pos) and self.matriz[pos[0]][pos[1]] != PAREDE

    def terreno(self, pos: Posicao) -> int:
        return self.matriz[pos[0]][pos[1]]

    def possui_terrenos(self) -> bool:
        """True se existe alguma célula livre que não seja asfalto."""
        return any(v not in (PAREDE, ASFALTO) for linha in self.matriz for v in linha)

    # ------------------------------------------------------------------ #
    # Conversão MATRIZ -> GRAFO
    # ------------------------------------------------------------------ #
    def para_grafo(self, limite_profundidade: Optional[int] = None) -> Grafo:
        """
        Converte a matriz em um Grafo.

        - Cada célula livre vira um nó identificado por (linha, coluna).
        - Existe uma aresta u -> v se v é vizinha ortogonal de u e está livre.
        - O peso da aresta u -> v é o custo de entrar no terreno de v.

        A partir daqui os algoritmos só enxergam o grafo.
        """
        grafo = Grafo(limite_profundidade=limite_profundidade)
        for l in range(self.linhas):
            for c in range(self.colunas):
                u = (l, c)
                if not self.livre(u):
                    continue
                grafo.adicionar_no(u)
                for dl, dc in DIRECOES:
                    v = (l + dl, c + dc)
                    if self.livre(v):
                        grafo.adicionar_aresta(u, v, CUSTO_TERRENO[self.terreno(v)])
        return grafo


# --------------------------------------------------------------------------- #
# Geração
# --------------------------------------------------------------------------- #
def gerar_labirinto(
    linhas: int,
    colunas: int,
    semente: Optional[int] = None,
    taxa_ciclos: float = 0.10,
    com_terrenos: bool = False,
    nome: str = "Labirinto",
) -> Labirinto:
    """
    Gera um labirinto aleatório (reprodutível pela ``semente``).

    Parâmetros
    ----------
    linhas, colunas : int
        Dimensões da matriz (incluindo as paredes da borda). Valores ímpares
        produzem labirintos mais "bonitos"; valores pares funcionam, mas a
        última linha/coluna fica toda de parede. Mínimo: 5x5.
    semente : int | None
        Semente do gerador aleatório.
    taxa_ciclos : float
        Fração (0 a 1) das paredes internas "removíveis" que serão
        derrubadas para criar ciclos. 0 => labirinto perfeito (árvore).
    com_terrenos : bool
        Se True, espalha manchas de grama, areia e pântano.
    nome : str
        Nome descritivo do labirinto.
    """
    if linhas < 5 or colunas < 5:
        raise ValueError("O labirinto deve ter pelo menos 5x5 células.")

    rng = random.Random(semente)
    matriz = [[PAREDE] * colunas for _ in range(linhas)]

    # Maior índice ímpar utilizável em cada dimensão (a borda é sempre parede).
    max_l = linhas - 2 if linhas % 2 == 1 else linhas - 3
    max_c = colunas - 2 if colunas % 2 == 1 else colunas - 3

    # 1) Recursive backtracker (versão iterativa, sem risco de estourar a
    #    pilha de recursão do Python em labirintos grandes).
    inicio = (1, 1)
    matriz[1][1] = ASFALTO
    pilha = [inicio]
    while pilha:
        l, c = pilha[-1]
        candidatos = []
        for dl, dc in DIRECOES:
            nl, nc = l + 2 * dl, c + 2 * dc
            if 1 <= nl <= max_l and 1 <= nc <= max_c and matriz[nl][nc] == PAREDE:
                candidatos.append((nl, nc, l + dl, c + dc))
        if not candidatos:
            pilha.pop()
            continue
        nl, nc, pl, pc = rng.choice(candidatos)
        matriz[pl][pc] = ASFALTO  # derruba a parede entre as duas células
        matriz[nl][nc] = ASFALTO
        pilha.append((nl, nc))

    # 2) Criação de ciclos: paredes internas que separam dois corredores
    #    (horizontal ou verticalmente) podem ser derrubadas.
    removiveis = []
    for l in range(1, max_l + 1):
        for c in range(1, max_c + 1):
            if matriz[l][c] != PAREDE:
                continue
            horizontal = matriz[l][c - 1] != PAREDE and matriz[l][c + 1] != PAREDE
            vertical = matriz[l - 1][c] != PAREDE and matriz[l + 1][c] != PAREDE
            if horizontal != vertical:  # exatamente um eixo: é uma "parede fina"
                removiveis.append((l, c))
    rng.shuffle(removiveis)
    for l, c in removiveis[: int(len(removiveis) * taxa_ciclos)]:
        matriz[l][c] = ASFALTO

    objetivo = (max_l, max_c)

    # 3) Terrenos com custos diferentes.
    if com_terrenos:
        _espalhar_terrenos(matriz, rng, protegidas={inicio, objetivo})

    return Labirinto(matriz=matriz, inicio=inicio, objetivo=objetivo,
                     nome=nome, semente=semente)


def _espalhar_terrenos(matriz: List[List[int]], rng: random.Random,
                       protegidas: set) -> None:
    """
    Pinta "manchas" circulares de grama, areia e pântano sobre as células
    livres. Início e objetivo permanecem asfalto.
    """
    linhas, colunas = len(matriz), len(matriz[0])
    area = linhas * colunas
    qtd_manchas = max(3, area // 40)
    for _ in range(qtd_manchas):
        terreno = rng.choice([GRAMA, GRAMA, AREIA, PANTANO, PANTANO])
        cl, cc = rng.randrange(linhas), rng.randrange(colunas)
        raio = rng.randint(1, max(2, min(linhas, colunas) // 6))
        for l in range(max(0, cl - raio), min(linhas, cl + raio + 1)):
            for c in range(max(0, cc - raio), min(colunas, cc + raio + 1)):
                if (l - cl) ** 2 + (c - cc) ** 2 <= raio ** 2:
                    if matriz[l][c] != PAREDE and (l, c) not in protegidas:
                        matriz[l][c] = terreno


def labirinto_de_texto(texto: str, nome: str = "Labirinto (texto)") -> Labirinto:
    """
    Cria um labirinto a partir de um desenho em texto. Útil para testes com
    casos pequenos e controlados.

    Legenda:  '#' parede   '.' asfalto   'g' grama   'a' areia   'p' pântano
              'S' início   'G' objetivo  (ambos em asfalto)
    """
    mapa = {"#": PAREDE, ".": ASFALTO, "g": GRAMA, "a": AREIA, "p": PANTANO,
            "S": ASFALTO, "G": ASFALTO}
    linhas_txt = [ln.strip() for ln in texto.strip().splitlines() if ln.strip()]
    matriz, inicio, objetivo = [], None, None
    for l, ln in enumerate(linhas_txt):
        linha = []
        for c, ch in enumerate(ln):
            if ch == "S":
                inicio = (l, c)
            elif ch == "G":
                objetivo = (l, c)
            linha.append(mapa[ch])
        matriz.append(linha)
    if inicio is None or objetivo is None:
        raise ValueError("O texto deve conter 'S' (início) e 'G' (objetivo).")
    return Labirinto(matriz=matriz, inicio=inicio, objetivo=objetivo, nome=nome)
