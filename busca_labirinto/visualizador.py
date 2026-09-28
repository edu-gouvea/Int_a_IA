"""
visualizador.py — Animação da busca no terminal com cores ANSI.

Como funciona
-------------
Os algoritmos aceitam um ``observador`` (callback). A cada nó expandido o
algoritmo chama ``observador("expandir", ...)`` passando o nó atual, a
fronteira (pilha) e os ponteiros de pai. O visualizador usa essas
informações para redesenhar o labirinto e em seguida dorme ``atraso``
segundos (``time.sleep``), criando a animação.

Legenda de cores
----------------
    S  Início                    G  Objetivo
    ██ Parede
    Magenta   nó sendo expandido agora
    Laranja   ramo atual (caminho do início até o nó atual)
    Amarelo   fronteira (nós na pilha, aguardando expansão)
    Azul      nós já explorados
    Verde     caminho final encontrado
    Terrenos  asfalto (cinza escuro), grama (verde escuro),
              areia (marrom claro), pântano (verde oliva)
"""

import sys
import time
from typing import Callable, Dict, Hashable, Iterable, Optional, Set

from .labirinto import (AREIA, ASFALTO, CUSTO_TERRENO, GRAMA, NOME_TERRENO,
                        PANTANO, PAREDE, Labirinto)

# --------------------------------------------------------------------------- #
# Códigos ANSI (cores de 256 posições — suportadas pela maioria dos terminais)
# --------------------------------------------------------------------------- #
RESET = "\033[0m"
NEGRITO = "\033[1m"
LIMPAR_TELA = "\033[2J"
CURSOR_INICIO = "\033[H"
ESCONDER_CURSOR = "\033[?25l"
MOSTRAR_CURSOR = "\033[?25h"


def fundo(cor: int) -> str:
    """Código ANSI para cor de fundo (paleta de 256 cores)."""
    return f"\033[48;5;{cor}m"


def texto(cor: int) -> str:
    """Código ANSI para cor do texto (paleta de 256 cores)."""
    return f"\033[38;5;{cor}m"


COR_TERRENO: Dict[int, int] = {
    PAREDE: 250,
    ASFALTO: 236,
    GRAMA: 22,
    AREIA: 137,
    PANTANO: 58,
}
COR_INICIO = 21
COR_OBJETIVO = 160
COR_ATUAL = 201
COR_RAMO = 208
COR_FRONTEIRA = 220
COR_EXPLORADO = 25
COR_CAMINHO = 40


class VisualizadorTerminal:
    """
    Desenha o estado da busca no terminal.

    Parâmetros
    ----------
    labirinto : Labirinto
        O labirinto original (usado apenas para DESENHAR; a busca continua
        sendo feita sobre o grafo).
    algoritmo : str
        Nome exibido no cabeçalho ("DLS" ou "IDS").
    atraso : float
        Segundos de pausa entre dois quadros (``time.sleep``).
    pular : int
        Desenha apenas 1 a cada ``pular`` expansões (útil em labirintos
        grandes, nos quais a IDS expande milhares de nós).
    passo_a_passo : bool
        Se True, espera o usuário apertar ENTER a cada quadro.
    """

    def __init__(self, labirinto: Labirinto, algoritmo: str = "",
                 atraso: float = 0.05, pular: int = 1,
                 passo_a_passo: bool = False) -> None:
        self.labirinto = labirinto
        self.algoritmo = algoritmo
        self.atraso = atraso
        self.pular = max(1, pular)
        self.passo_a_passo = passo_a_passo

        # Estado da iteração corrente.
        self.limite: Optional[int] = None
        self.iteracao = 0
        self.explorados_iteracao: Set[Hashable] = set()
        self.total_expandidos = 0
        self.contador_quadros = 0

    # ------------------------------------------------------------------ #
    # Callback chamado pelos algoritmos
    # ------------------------------------------------------------------ #
    def __call__(self, evento: str, **dados) -> None:
        if evento == "iteracao":
            # Nova iteração (a IDS reinicia a busca a cada novo limite).
            self.limite = dados["limite"]
            self.iteracao += 1
            self.explorados_iteracao = set()
            self._desenhar(mensagem=f"Iniciando busca com limite L = {self.limite}")
            self._pausar(multiplicador=5)

        elif evento == "expandir":
            no = dados["no"]
            self.explorados_iteracao.add(no)
            self.total_expandidos += 1
            self.contador_quadros += 1
            if self.contador_quadros % self.pular != 0 and no != self.labirinto.objetivo:
                return
            fronteira = [n for n, _ in dados["fronteira"]]
            ramo = self._ramo(dados["pai"], no)
            self._desenhar(atual=no, fronteira=fronteira, ramo=ramo,
                           profundidade=dados["profundidade"])
            self._pausar()

        elif evento == "fim":
            resultado = dados["resultado"]
            caminho = resultado.caminho_encontrado
            if caminho is None:
                msg = f"{NEGRITO}{texto(COR_OBJETIVO)}Nenhuma solução encontrada.{RESET}"
            else:
                custo = self.labirinto.para_grafo().custo_caminho(caminho)
                msg = (f"{NEGRITO}{texto(COR_CAMINHO)}Solução encontrada!{RESET} "
                       f"Passos: {resultado.profundidade_da_solucao} | "
                       f"Custo: {custo:g} | "
                       f"Nós explorados: {resultado.numero_de_nos_explorados}")
            self._desenhar(caminho=caminho or [], mensagem=msg)

    # ------------------------------------------------------------------ #
    # Desenho
    # ------------------------------------------------------------------ #
    @staticmethod
    def _ramo(pai: Dict[Hashable, Optional[Hashable]], no: Hashable) -> Set[Hashable]:
        """Caminho atual (do início até ``no``) segundo os ponteiros de pai."""
        ramo = set()
        while no is not None and no not in ramo:
            ramo.add(no)
            no = pai.get(no)
        return ramo

    def _celula(self, pos, atual, fronteira, ramo, caminho) -> str:
        lab = self.labirinto
        valor = lab.terreno(pos)
        if pos == lab.inicio:
            return f"{fundo(COR_INICIO)}{NEGRITO}{texto(231)}S {RESET}"
        if pos == lab.objetivo:
            return f"{fundo(COR_OBJETIVO)}{NEGRITO}{texto(231)}G {RESET}"
        if valor == PAREDE:
            return f"{fundo(COR_TERRENO[PAREDE])}  {RESET}"
        if pos in caminho:
            cor = COR_CAMINHO
        elif pos == atual:
            cor = COR_ATUAL
        elif pos in ramo:
            cor = COR_RAMO
        elif pos in fronteira:
            cor = COR_FRONTEIRA
        elif pos in self.explorados_iteracao:
            cor = COR_EXPLORADO
        else:
            cor = COR_TERRENO[valor]
        # Nos terrenos "caros" desenhamos o custo, para lembrar o peso da aresta.
        simbolo = f"{CUSTO_TERRENO[valor]} " if valor != ASFALTO else "  "
        return f"{fundo(cor)}{texto(252)}{simbolo}{RESET}"

    def _desenhar(self, atual=None, fronteira: Iterable = (), ramo: Iterable = (),
                  caminho: Iterable = (), profundidade: Optional[int] = None,
                  mensagem: str = "") -> None:
        fronteira, ramo, caminho = set(fronteira), set(ramo), set(caminho)
        lab = self.labirinto
        linhas = []

        titulo = f" {self.algoritmo} — {lab.nome} "
        linhas.append(f"{NEGRITO}{titulo:=^{max(40, lab.colunas * 2)}}{RESET}")
        linhas.append(
            f"Limite L: {self.limite}   "
            + (f"Iteração: {self.iteracao}   " if self.algoritmo == "IDS" else "")
            + f"Profundidade atual: {profundidade if profundidade is not None else '-'}")
        linhas.append(
            f"Explorados (iteração): {len(self.explorados_iteracao):<6} "
            f"Explorados (total): {self.total_expandidos:<6} "
            f"Fronteira: {len(fronteira)}")
        linhas.append("")

        for l in range(lab.linhas):
            linhas.append("".join(
                self._celula((l, c), atual, fronteira, ramo, caminho)
                for c in range(lab.colunas)))

        linhas.append("")
        linhas.append(self._legenda())
        linhas.append(mensagem)

        # "\033[K" limpa o restante de cada linha (evita lixo de quadros anteriores).
        quadro = "\n".join(ln + "\033[K" for ln in linhas)
        sys.stdout.write(CURSOR_INICIO + quadro + "\033[J")
        sys.stdout.flush()

    def _legenda(self) -> str:
        def item(cor, nome, simbolo="  "):
            return f"{fundo(cor)}{texto(231)}{simbolo}{RESET} {nome}"

        itens = [
            item(COR_INICIO, "Início", "S "), item(COR_OBJETIVO, "Objetivo", "G "),
            item(COR_ATUAL, "Atual"), item(COR_RAMO, "Ramo atual"),
            item(COR_FRONTEIRA, "Fronteira"), item(COR_EXPLORADO, "Explorado"),
            item(COR_CAMINHO, "Caminho final"),
        ]
        legenda = "  ".join(itens)
        if self.labirinto.possui_terrenos():
            terrenos = "  ".join(
                item(COR_TERRENO[t], f"{NOME_TERRENO[t]} (custo {CUSTO_TERRENO[t]})")
                for t in (ASFALTO, GRAMA, AREIA, PANTANO))
            legenda += "\n" + terrenos
        return legenda

    def _pausar(self, multiplicador: float = 1.0) -> None:
        if self.passo_a_passo:
            input("  [ENTER] próximo passo")
        elif self.atraso > 0:
            time.sleep(self.atraso * multiplicador)


def visualizar(labirinto: Labirinto, funcao_busca: Callable, nome_algoritmo: str,
               limite: Optional[int] = None, atraso: float = 0.05, pular: int = 1,
               passo_a_passo: bool = False):
    """
    Executa ``funcao_busca`` (versão com observador de DLS ou IDS) sobre o
    grafo do labirinto, animando cada passo no terminal.

    Retorna o ``ResultadoBusca`` produzido pelo algoritmo.
    """
    grafo = labirinto.para_grafo(limite_profundidade=limite)
    vis = VisualizadorTerminal(labirinto, nome_algoritmo, atraso, pular, passo_a_passo)
    sys.stdout.write(LIMPAR_TELA + ESCONDER_CURSOR)
    try:
        resultado = funcao_busca(grafo, labirinto.inicio, labirinto.objetivo,
                                 observador=vis)
    finally:
        sys.stdout.write(MOSTRAR_CURSOR + RESET + "\n")
        sys.stdout.flush()
    return resultado
