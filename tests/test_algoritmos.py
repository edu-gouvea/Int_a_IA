"""
test_algoritmos.py — Testes automatizados de DLS e IDS.

Executa os algoritmos nos 4 cenários da bateria (pequeno, médio, grande e
com terrenos) e em casos pequenos construídos à mão, verificando:

* o formato do retorno (caminho, nós explorados, profundidade);
* se o caminho é válido no grafo e liga início -> objetivo;
* se a IDS encontra o caminho com o MENOR número de passos;
* se a DLS respeita o limite (falha quando a solução está além dele);
* se o custo é calculado a partir dos pesos das arestas;
* casos de borda (início == objetivo, objetivo inalcançável).

Execução:  python3 -m unittest discover -s tests -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from busca_labirinto.algoritmos import dls, ids  # noqa: E402
from busca_labirinto.cenarios import criar_cenarios, montar_cenario  # noqa: E402
from busca_labirinto.grafo import Grafo  # noqa: E402
from busca_labirinto.labirinto import labirinto_de_texto  # noqa: E402

# Labirinto com dois caminhos: um curto (4 passos, por cima, via pântano)
# e um longo (8 passos, por baixo, só asfalto).
LABIRINTO_DOIS_CAMINHOS = """
#######
#SpppG#
#.###.#
#.....#
#######
"""


class TestCenarios(unittest.TestCase):
    """Roda DLS e IDS nos 4 cenários oficiais."""

    @classmethod
    def setUpClass(cls):
        cls.cenarios = criar_cenarios()

    def _verificar(self, cenario, resultado):
        caminho, explorados, profundidade = resultado
        self.assertIsNotNone(caminho, f"{cenario.nome}: nenhuma solução encontrada")
        self.assertEqual(caminho[0], cenario.inicio)
        self.assertEqual(caminho[-1], cenario.objetivo)
        self.assertTrue(cenario.grafo.caminho_valido(caminho), "caminho usa aresta inexistente")
        self.assertEqual(len(caminho), len(set(caminho)), "caminho repete nós")
        self.assertEqual(profundidade, len(caminho) - 1)
        self.assertGreaterEqual(explorados, len(caminho))

    def test_dls_encontra_solucao_dentro_do_limite(self):
        for cenario in self.cenarios:
            with self.subTest(cenario=cenario.nome):
                resultado = dls(cenario.grafo, cenario.inicio, cenario.objetivo)
                self._verificar(cenario, resultado)
                self.assertLessEqual(resultado.profundidade_da_solucao,
                                     cenario.grafo.limite_profundidade)

    def test_ids_encontra_caminho_mais_curto(self):
        for cenario in self.cenarios:
            with self.subTest(cenario=cenario.nome):
                resultado = ids(cenario.grafo, cenario.inicio, cenario.objetivo)
                self._verificar(cenario, resultado)
                self.assertEqual(resultado.profundidade_da_solucao,
                                 cenario.profundidade_minima)

    def test_ids_explora_pelo_menos_tanto_quanto_ultima_iteracao(self):
        # A IDS repete as iterações rasas, então explora mais nós que uma
        # DLS com L igual à profundidade da solução.
        for cenario in self.cenarios:
            with self.subTest(cenario=cenario.nome):
                r_ids = ids(cenario.grafo, cenario.inicio, cenario.objetivo)
                cenario.grafo.limite_profundidade, antigo = \
                    r_ids.profundidade_da_solucao, cenario.grafo.limite_profundidade
                try:
                    r_dls = dls(cenario.grafo, cenario.inicio, cenario.objetivo)
                finally:
                    cenario.grafo.limite_profundidade = antigo
                self.assertGreaterEqual(r_ids.numero_de_nos_explorados,
                                        r_dls.numero_de_nos_explorados)

    def test_dls_falha_com_limite_insuficiente(self):
        for cenario in self.cenarios:
            with self.subTest(cenario=cenario.nome):
                grafo = cenario.labirinto.para_grafo(
                    limite_profundidade=cenario.profundidade_minima - 1)
                caminho, explorados, profundidade = dls(grafo, cenario.inicio, cenario.objetivo)
                self.assertIsNone(caminho)
                self.assertIsNone(profundidade)
                self.assertGreater(explorados, 0)

    def test_cenario_de_terrenos_tem_custos_diferentes(self):
        cenario = self.cenarios[3]
        self.assertTrue(cenario.labirinto.possui_terrenos())
        pesos = {p for viz in cenario.grafo.adjacencia.values() for p in viz.values()}
        self.assertGreater(len(pesos), 1)
        for alg in (dls, ids):
            caminho, _, passos = alg(cenario.grafo, cenario.inicio, cenario.objetivo)
            # Custo >= passos, pois o menor peso possível é 1 (asfalto).
            self.assertGreaterEqual(cenario.grafo.custo_caminho(caminho), passos)


class TestCasosControlados(unittest.TestCase):
    """Casos pequenos desenhados à mão, com resultado conhecido."""

    def setUp(self):
        self.lab = labirinto_de_texto(LABIRINTO_DOIS_CAMINHOS)
        self.grafo = self.lab.para_grafo()

    def test_ids_escolhe_menos_passos_mesmo_com_custo_maior(self):
        caminho, _, passos = ids(self.grafo, self.lab.inicio, self.lab.objetivo)
        self.assertEqual(passos, 4)
        # 3 células de pântano (5 cada) + objetivo em asfalto (1) = 16
        self.assertEqual(self.grafo.custo_caminho(caminho), 16)

    def test_dls_com_limite_entre_os_dois_caminhos(self):
        self.grafo.limite_profundidade = 5
        _, _, passos = dls(self.grafo, self.lab.inicio, self.lab.objetivo)
        self.assertEqual(passos, 4)

    def test_dls_com_limite_menor_que_o_caminho_curto(self):
        self.grafo.limite_profundidade = 3
        resultado = dls(self.grafo, self.lab.inicio, self.lab.objetivo)
        self.assertIsNone(resultado.caminho_encontrado)

    def test_inicio_igual_ao_objetivo(self):
        for alg in (dls, ids):
            caminho, explorados, passos = alg(self.grafo, self.lab.inicio, self.lab.inicio)
            self.assertEqual(caminho, [self.lab.inicio])
            self.assertEqual(passos, 0)
            self.assertEqual(explorados, 1)

    def test_objetivo_inalcancavel(self):
        grafo = Grafo()
        grafo.adicionar_aresta("A", "B")
        grafo.adicionar_aresta("B", "A")
        grafo.adicionar_no("C")  # isolado
        for alg in (dls, ids):
            caminho, explorados, passos = alg(grafo, "A", "C")
            self.assertIsNone(caminho)
            self.assertIsNone(passos)

    def test_grafo_generico_nao_labirinto(self):
        # Os algoritmos funcionam em qualquer grafo, não só em labirintos.
        grafo = Grafo(limite_profundidade=10)
        for u, v in [("A", "B"), ("A", "C"), ("B", "D"), ("C", "D"), ("D", "E"), ("B", "A")]:
            grafo.adicionar_aresta(u, v)
        self.assertEqual(ids(grafo, "A", "E").caminho_encontrado, ["A", "B", "D", "E"])
        self.assertEqual(dls(grafo, "A", "E").profundidade_da_solucao, 3)

    def test_ciclos_nao_causam_laco_infinito(self):
        grafo = Grafo(limite_profundidade=50)
        nos = list(range(6))
        for u in nos:  # grafo completo: cheio de ciclos
            for v in nos:
                if u != v:
                    grafo.adicionar_aresta(u, v)
        grafo.adicionar_no(99)
        self.assertIsNone(dls(grafo, 0, 99).caminho_encontrado)
        self.assertIsNone(ids(grafo, 0, 99).caminho_encontrado)


class TestLimiteAutomatico(unittest.TestCase):
    def test_limite_do_cenario_tem_folga(self):
        lab = labirinto_de_texto(LABIRINTO_DOIS_CAMINHOS)
        cenario = montar_cenario("teste", lab)
        self.assertEqual(cenario.profundidade_minima, 4)
        self.assertEqual(cenario.grafo.limite_profundidade, 6)


if __name__ == "__main__":
    unittest.main(verbosity=2)
