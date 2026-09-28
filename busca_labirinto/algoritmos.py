"""
algoritmos.py — Busca em Profundidade Limitada (DLS) e Busca de
Aprofundamento Iterativo (IDS).

Assinatura pública (exigida pelo trabalho)
-----------------------------------------
    dls(grafo, estado_inicial, estado_objetivo)
    ids(grafo, estado_inicial, estado_objetivo)

Ambas retornam um ``ResultadoBusca``, que é uma tupla nomeada e pode ser
desempacotada diretamente:

    caminho_encontrado, numero_de_nos_explorados, profundidade_da_solucao = dls(...)

- ``caminho_encontrado``: lista de nós [inicial, ..., objetivo] ou ``None``
  se não houver solução (dentro do limite, no caso da DLS).
- ``numero_de_nos_explorados``: quantidade de nós EXPANDIDOS (retirados da
  fronteira e testados). Na IDS é a soma de todas as iterações.
- ``profundidade_da_solucao``: número de arestas do caminho (len - 1) ou
  ``None`` se não houver solução.

Sobre o limite da DLS
---------------------
Como a DLS recebe apenas 3 parâmetros, o limite ``L`` faz parte da
instância do problema ("labirinto com limite de profundidade") e é lido de
``grafo.limite_profundidade``. Se ele for ``None``, usa-se ``N - 1`` (N =
número de nós), que é o maior comprimento possível de um caminho simples —
ou seja, a DLS vira uma busca em profundidade comum.

Detalhes de implementação
-------------------------
* A DLS é ITERATIVA, com pilha explícita (LIFO). Isso evita o limite de
  recursão do Python em labirintos grandes e, de quebra, deixa a fronteira
  visível para o modo de visualização.
* Como um labirinto com ciclos é um GRAFO (e não uma árvore), é preciso
  evitar laços infinitos. Guardamos, para cada nó, a MENOR profundidade em
  que ele já foi alcançado. Um nó só é (re)inserido na fronteira se for
  alcançado por um caminho mais raso do que antes. Isso:
    - impede ciclos (nunca se volta a um nó pela mesma profundidade ou mais
      fundo);
    - preserva a completude da DLS: se existir solução com profundidade
      <= L, ela é encontrada (um nó descoberto primeiro por um ramo muito
      fundo pode ser reaberto quando alcançado por um ramo mais raso).
* A IDS chama o mesmo núcleo da DLS com L = 0, 1, 2, ... até achar o
  objetivo. Como cada iteração explora todos os nós até a profundidade L,
  o primeiro objetivo encontrado está na MENOR profundidade possível: a IDS
  é ótima em número de passos (mas não em custo, pois ignora os pesos).
"""

from typing import Callable, Dict, Hashable, List, NamedTuple, Optional, Tuple

from .grafo import Grafo

No = Hashable
# Função opcional chamada a cada evento da busca (usada pelo visualizador).
Observador = Optional[Callable[..., None]]


class ResultadoBusca(NamedTuple):
    """Retorno dos algoritmos (desempacotável como tupla de 3 elementos)."""
    caminho_encontrado: Optional[List[No]]
    numero_de_nos_explorados: int
    profundidade_da_solucao: Optional[int]


# --------------------------------------------------------------------------- #
# API pública — exatamente 3 entradas
# --------------------------------------------------------------------------- #
def dls(grafo: Grafo, estado_inicial: No, estado_objetivo: No) -> ResultadoBusca:
    """
    Busca em Profundidade Limitada (Depth-Limited Search).

    Explora o grafo em profundidade, mas não expande nós que estejam na
    profundidade ``grafo.limite_profundidade``. Pode falhar mesmo existindo
    solução, caso ela esteja além do limite.
    """
    return busca_profundidade_limitada(grafo, estado_inicial, estado_objetivo)


def ids(grafo: Grafo, estado_inicial: No, estado_objetivo: No) -> ResultadoBusca:
    """
    Busca de Aprofundamento Iterativo (Iterative Deepening Search).

    Executa DLS com limites 0, 1, 2, ... até encontrar o objetivo ou até
    concluir que ele é inalcançável.
    """
    return busca_aprofundamento_iterativo(grafo, estado_inicial, estado_objetivo)


# --------------------------------------------------------------------------- #
# Implementações (com gancho opcional para o visualizador)
# --------------------------------------------------------------------------- #
def busca_profundidade_limitada(grafo: Grafo, estado_inicial: No, estado_objetivo: No,
                                observador: Observador = None) -> ResultadoBusca:
    """Mesma coisa que ``dls``, mas aceita um ``observador`` para visualização."""
    limite = grafo.limite_profundidade
    if limite is None:
        limite = max(0, grafo.numero_de_nos() - 1)
    if observador:
        observador("iteracao", limite=limite)
    caminho, explorados, _ = _nucleo_dls(grafo, estado_inicial, estado_objetivo,
                                         limite, observador)
    resultado = _montar_resultado(caminho, explorados)
    if observador:
        observador("fim", resultado=resultado)
    return resultado


def busca_aprofundamento_iterativo(grafo: Grafo, estado_inicial: No, estado_objetivo: No,
                                   observador: Observador = None) -> ResultadoBusca:
    """Mesma coisa que ``ids``, mas aceita um ``observador`` para visualização."""
    total_explorados = 0
    caminho = None
    # Nenhum caminho simples tem mais de N - 1 arestas, então esse é um teto
    # seguro para o limite (na prática a IDS para muito antes).
    limite_maximo = max(0, grafo.numero_de_nos() - 1)

    for limite in range(limite_maximo + 1):
        if observador:
            observador("iteracao", limite=limite)
        caminho, explorados, houve_corte = _nucleo_dls(
            grafo, estado_inicial, estado_objetivo, limite, observador)
        total_explorados += explorados
        if caminho is not None:
            break
        if not houve_corte:
            # Nenhum ramo foi interrompido pelo limite: a busca esgotou todos
            # os nós alcançáveis e o objetivo não está entre eles. Aumentar o
            # limite não adiantaria nada.
            break

    resultado = _montar_resultado(caminho, total_explorados)
    if observador:
        observador("fim", resultado=resultado)
    return resultado


def _nucleo_dls(grafo: Grafo, inicio: No, objetivo: No, limite: int,
                observador: Observador = None) -> Tuple[Optional[List[No]], int, bool]:
    """
    Núcleo da DLS, compartilhado pela DLS e pela IDS.

    Retorna (caminho | None, nós_explorados, houve_corte), onde
    ``houve_corte`` indica se algum nó deixou de ser expandido por causa do
    limite (informação usada pela IDS para decidir se vale a pena continuar).
    """
    if inicio not in grafo or objetivo not in grafo:
        return None, 0, False

    # Menor profundidade em que cada nó já foi alcançado nesta execução.
    melhor_profundidade: Dict[No, int] = {inicio: 0}
    # Ponteiros para o pai, usados para reconstruir o caminho.
    pai: Dict[No, Optional[No]] = {inicio: None}
    # Fronteira: pilha LIFO de (nó, profundidade).
    fronteira: List[Tuple[No, int]] = [(inicio, 0)]

    explorados = 0
    houve_corte = False

    while fronteira:
        no, profundidade = fronteira.pop()

        # Entrada obsoleta: o nó já foi reaberto por um caminho mais raso.
        if profundidade > melhor_profundidade[no]:
            continue

        explorados += 1
        if observador:
            observador("expandir", no=no, profundidade=profundidade,
                       fronteira=fronteira, pai=pai, explorados=explorados)

        if no == objetivo:
            return _reconstruir_caminho(pai, no), explorados, houve_corte

        if profundidade >= limite:
            # Nó no limite: não é expandido. Se ele tivesse filhos ainda não
            # alcançados (ou alcançáveis por um caminho mais raso), houve corte.
            if not houve_corte:
                houve_corte = any(
                    v not in melhor_profundidade or profundidade + 1 < melhor_profundidade[v]
                    for v in grafo.vizinhos(no))
            continue

        # Empilha os vizinhos em ordem inversa para que o PRIMEIRO vizinho
        # (ordem N, L, S, O no labirinto) seja o primeiro a ser explorado.
        nova_profundidade = profundidade + 1
        for vizinho in reversed(list(grafo.vizinhos(no))):
            if (vizinho not in melhor_profundidade
                    or nova_profundidade < melhor_profundidade[vizinho]):
                melhor_profundidade[vizinho] = nova_profundidade
                pai[vizinho] = no
                fronteira.append((vizinho, nova_profundidade))

    return None, explorados, houve_corte


def _reconstruir_caminho(pai: Dict[No, Optional[No]], no: No) -> List[No]:
    """Segue os ponteiros de pai do objetivo até o início e inverte a lista."""
    caminho = []
    while no is not None:
        caminho.append(no)
        no = pai[no]
    caminho.reverse()
    return caminho


def _montar_resultado(caminho: Optional[List[No]], explorados: int) -> ResultadoBusca:
    profundidade = len(caminho) - 1 if caminho is not None else None
    return ResultadoBusca(caminho, explorados, profundidade)


# Tabela usada pelos scripts para escolher o algoritmo pelo nome.
ALGORITMOS = {
    "DLS": dls,
    "IDS": ids,
}
