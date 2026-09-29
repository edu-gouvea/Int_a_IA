"""
comparacao.py — Módulo de comparação entre DLS e IDS.

Métricas coletadas para cada (cenário, algoritmo):

    * Memória consumida  -> pico de alocação medido com ``tracemalloc``
    * Nós explorados     -> retornado pelo próprio algoritmo
    * Tempo de execução  -> ``time.perf_counter`` (mediana de N repetições)
    * Tamanho da solução -> número de passos (arestas) do caminho
    * Custo da solução   -> soma dos pesos das arestas do caminho

Observação metodológica: o ``tracemalloc`` deixa o Python mais lento
enquanto está ativo. Por isso o TEMPO é medido em execuções separadas, com
o tracemalloc desligado, e a MEMÓRIA é medida em uma execução dedicada.
"""

import csv
import statistics
import time
import tracemalloc
from dataclasses import asdict, dataclass
from typing import Callable, List, Optional

from .algoritmos import ALGORITMOS
from .cenarios import Cenario, criar_cenarios


@dataclass
class Medicao:
    cenario: str
    algoritmo: str
    limite: Optional[int]
    profundidade_minima: Optional[int]
    encontrou: bool
    passos: Optional[int]
    custo: Optional[float]
    nos_explorados: int
    tempo_ms: float
    memoria_kib: float


def medir(cenario: Cenario, nome_algoritmo: str, algoritmo: Callable,
          repeticoes: int = 5) -> Medicao:
    """Executa um algoritmo em um cenário e coleta todas as métricas."""
    grafo, inicio, objetivo = cenario.grafo, cenario.inicio, cenario.objetivo

    # 1) Tempo: mediana de várias execuções (reduz o ruído do sistema).
    tempos = []
    resultado = None
    for _ in range(repeticoes):
        t0 = time.perf_counter()
        resultado = algoritmo(grafo, inicio, objetivo)
        tempos.append(time.perf_counter() - t0)

    # 2) Memória: pico de alocação durante UMA execução.
    tracemalloc.start()  # iniciar zera as estatísticas, inclusive o pico
    algoritmo(grafo, inicio, objetivo)
    _, pico = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    caminho, explorados, profundidade = resultado
    return Medicao(
        cenario=cenario.nome,
        algoritmo=nome_algoritmo,
        limite=grafo.limite_profundidade if nome_algoritmo == "DLS" else None,
        profundidade_minima=cenario.profundidade_minima,
        encontrou=caminho is not None,
        passos=profundidade,
        custo=grafo.custo_caminho(caminho) if caminho is not None else None,
        nos_explorados=explorados,
        tempo_ms=statistics.median(tempos) * 1000,
        memoria_kib=pico / 1024,
    )


def executar_comparacao(cenarios: Optional[List[Cenario]] = None,
                        repeticoes: int = 5) -> List[Medicao]:
    """Roda DLS e IDS em todos os cenários e devolve a lista de medições."""
    cenarios = cenarios if cenarios is not None else criar_cenarios()
    medicoes = []
    for cenario in cenarios:
        for nome, algoritmo in ALGORITMOS.items():
            medicoes.append(medir(cenario, nome, algoritmo, repeticoes))
    return medicoes


# --------------------------------------------------------------------------- #
# Saída
# --------------------------------------------------------------------------- #
def _fmt(valor, formato: str = "{}") -> str:
    return "-" if valor is None else formato.format(valor)


CABECALHO = ["Cenário", "Alg.", "L", "Ótimo", "Achou?", "Passos", "Custo",
             "Nós explorados", "Tempo (ms)", "Memória (KiB)"]


def linha_tabela(m: Medicao) -> List[str]:
    """Valores de uma medição já formatados, na ordem de ``CABECALHO``."""
    return [
        m.cenario,
        m.algoritmo,
        _fmt(m.limite) if m.algoritmo == "DLS" else "1..d",
        _fmt(m.profundidade_minima),
        "sim" if m.encontrou else "não",
        _fmt(m.passos),
        _fmt(m.custo, "{:g}"),
        str(m.nos_explorados),
        f"{m.tempo_ms:.3f}",
        f"{m.memoria_kib:.1f}",
    ]


def imprimir_tabela(medicoes: List[Medicao]) -> None:
    """Imprime as medições em uma tabela alinhada no terminal."""
    cabecalho = CABECALHO
    linhas = [linha_tabela(m) for m in medicoes]

    larguras = [max(len(str(x)) for x in col) for col in zip(cabecalho, *linhas)]
    # Colunas numéricas alinhadas à direita.
    direita = set(range(2, len(cabecalho)))

    def formatar(linha):
        celulas = [str(v).rjust(w) if i in direita else str(v).ljust(w)
                   for i, (v, w) in enumerate(zip(linha, larguras))]
        return "│ " + " │ ".join(celulas) + " │"

    def separador(esq, meio, dir_):
        return esq + meio.join("─" * (w + 2) for w in larguras) + dir_

    print(separador("┌", "┬", "┐"))
    print(formatar(cabecalho))
    print(separador("├", "┼", "┤"))
    cenario_anterior = None
    for m, linha in zip(medicoes, linhas):
        if cenario_anterior is not None and m.cenario != cenario_anterior:
            print(separador("├", "┼", "┤"))
        print(formatar(linha))
        cenario_anterior = m.cenario
    print(separador("└", "┴", "┘"))
    print("L = limite de profundidade da DLS | Ótimo = menor nº de passos possível "
          "(BFS de referência) | Custo = soma dos pesos das arestas do caminho")


def salvar_csv(medicoes: List[Medicao], caminho_arquivo: str) -> None:
    """Salva as medições em CSV (útil para gráficos no relatório)."""
    with open(caminho_arquivo, "w", newline="", encoding="utf-8") as f:
        campos = list(asdict(medicoes[0]).keys())
        escritor = csv.DictWriter(f, fieldnames=campos)
        escritor.writeheader()
        for m in medicoes:
            escritor.writerow(asdict(m))
