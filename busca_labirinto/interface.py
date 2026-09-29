"""
interface.py — Interface gráfica (Tkinter) para visualizar a DLS e a IDS e
comparar os dois algoritmos.

Organização
-----------
    Aplicacao          janela principal, com duas abas (ttk.Notebook)
    AbaVisualizador    painel de configuração + labirinto + controles
    CanvasLabirinto    Canvas que desenha o labirinto e pinta as células

O CanvasLabirinto só sabe DESENHAR: ele recebe um dicionário
{posição: cor} com as células que devem ser destacadas. Quem decide as
cores (atual, fronteira, explorado, ...) é a aba do visualizador.

Animação
--------
Ao clicar em Iniciar, a busca é executada inteira de uma vez com um
``Gravador`` (ver gravador.py), que devolve a lista de quadros. A animação
apenas percorre essa lista com ``after()`` do Tkinter, que agenda a
próxima chamada sem travar a janela. Por isso é possível pausar, voltar e
pular para qualquer quadro.
"""

import math
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List, Optional, Set

from .algoritmos import (ALGORITMOS, ResultadoBusca,
                         busca_aprofundamento_iterativo,
                         busca_profundidade_limitada)
from .cenarios import criar_cenarios, profundidade_minima_bfs
from .comparacao import CABECALHO, Medicao, linha_tabela, medir, salvar_csv
from .grafo import Grafo
from .gravador import Quadro, gravar_busca
from .labirinto import (AREIA, ASFALTO, CUSTO_TERRENO, GRAMA, NOME_TERRENO,
                        PANTANO, PAREDE, Labirinto, Posicao, gerar_labirinto)

# --------------------------------------------------------------------------- #
# Cores (as mesmas do visualizador de terminal, convertidas para hexadecimal)
# --------------------------------------------------------------------------- #
COR_FUNDO = "#1e1e1e"
COR_TERRENO: Dict[int, str] = {
    PAREDE: "#bcbcbc",
    ASFALTO: "#303030",
    GRAMA: "#005f00",
    AREIA: "#af875f",
    PANTANO: "#5f5f00",
}
COR_INICIO = "#0000ff"
COR_OBJETIVO = "#d70000"
COR_ATUAL = "#ff00ff"
COR_RAMO = "#ff8700"
COR_FRONTEIRA = "#ffd700"
COR_EXPLORADO = "#005faf"
COR_CAMINHO = "#00d700"

COR_SUCESSO = "#1a8f1a"
COR_FALHA = "#c62828"

# Legenda: (cor, descrição). Os terrenos só aparecem se o labirinto os tiver.
LEGENDA_BUSCA = [
    (COR_INICIO, "Início (S)"), (COR_OBJETIVO, "Objetivo (G)"),
    (COR_ATUAL, "Nó atual"), (COR_RAMO, "Ramo atual"),
    (COR_FRONTEIRA, "Fronteira (pilha)"), (COR_EXPLORADO, "Explorado"),
    (COR_CAMINHO, "Caminho final"),
]
LEGENDA_TERRENOS = [(COR_TERRENO[PAREDE], "Parede")] + [
    (COR_TERRENO[t], f"{NOME_TERRENO[t]} (custo {CUSTO_TERRENO[t]})")
    for t in (ASFALTO, GRAMA, AREIA, PANTANO)
]

# Linhas do painel "Estado da busca": (chave, rótulo).
CAMPOS_ESTADO = [
    ("limite", "Limite L"),
    ("iteracao", "Iteração"),
    ("profundidade", "Profundidade atual"),
    ("explorados_iteracao", "Explorados (iteração)"),
    ("explorados_total", "Explorados (total)"),
    ("fronteira", "Tamanho da fronteira"),
]

OPCAO_GERAR = "Gerar novo labirinto"

# Versões dos algoritmos que aceitam o observador (usado pelo Gravador).
FUNCOES = {
    "DLS": busca_profundidade_limitada,
    "IDS": busca_aprofundamento_iterativo,
}

# Níveis de velocidade: (milissegundos entre quadros, quadros por avanço).
# Nos níveis mais altos pulamos quadros, senão a IDS no 30x30 (~21 mil
# quadros) levaria minutos.
VELOCIDADES = [
    (600, 1), (300, 1), (150, 1), (80, 1), (40, 1),
    (15, 1), (15, 3), (15, 10), (15, 30), (15, 100),
]


# --------------------------------------------------------------------------- #
# Desenho do labirinto
# --------------------------------------------------------------------------- #
class CanvasLabirinto(tk.Canvas):
    """
    Desenha o labirinto como uma grade de retângulos.

    Cada célula é criada UMA vez (um retângulo por posição); para animar,
    só trocamos a cor de preenchimento com ``itemconfig``, o que é bem mais
    rápido do que apagar e redesenhar tudo a cada quadro.
    """

    def __init__(self, master, **kwargs) -> None:
        super().__init__(master, bg=COR_FUNDO, highlightthickness=0, **kwargs)
        self.labirinto: Optional[Labirinto] = None
        self._retangulos: Dict[Posicao, int] = {}   # posição -> id no Canvas
        self._destaques: Dict[Posicao, str] = {}    # posição -> cor atual
        # Quando a janela muda de tamanho, a grade é recalculada.
        self.bind("<Configure>", lambda _evento: self._redesenhar())

    def mostrar(self, labirinto: Labirinto) -> None:
        """Troca o labirinto exibido e limpa os destaques."""
        self.labirinto = labirinto
        self._destaques = {}
        self._redesenhar()

    def destacar(self, destaques: Dict[Posicao, str]) -> None:
        """
        Pinta as células de ``destaques`` ({posição: cor}); as que estavam
        destacadas antes e não estão mais voltam à cor do terreno.
        """
        for pos in self._destaques.keys() | destaques.keys():
            if pos in self._retangulos:
                self.itemconfig(self._retangulos[pos],
                                fill=self._cor(pos, destaques))
        self._destaques = dict(destaques)

    def _cor(self, pos: Posicao, destaques: Dict[Posicao, str]) -> str:
        lab = self.labirinto
        # Início e objetivo têm cor fixa, para nunca "sumirem" na animação.
        if pos == lab.inicio:
            return COR_INICIO
        if pos == lab.objetivo:
            return COR_OBJETIVO
        return destaques.get(pos, COR_TERRENO[lab.terreno(pos)])

    def _redesenhar(self) -> None:
        self.delete("all")
        self._retangulos = {}
        lab = self.labirinto
        if lab is None:
            return

        # Maior célula quadrada que cabe no Canvas, com a grade centralizada.
        largura, altura = self.winfo_width(), self.winfo_height()
        lado = max(2, min(largura // lab.colunas, altura // lab.linhas))
        x0 = (largura - lado * lab.colunas) // 2
        y0 = (altura - lado * lab.linhas) // 2
        fonte = ("Helvetica", max(7, int(lado * 0.45)), "bold")
        mostrar_texto = lado >= 12  # em células muito pequenas o texto polui

        for l in range(lab.linhas):
            for c in range(lab.colunas):
                pos = (l, c)
                x, y = x0 + c * lado, y0 + l * lado
                self._retangulos[pos] = self.create_rectangle(
                    x, y, x + lado, y + lado, outline="",
                    fill=self._cor(pos, self._destaques))

                if not mostrar_texto:
                    continue
                valor = lab.terreno(pos)
                if pos == lab.inicio:
                    rotulo = "S"
                elif pos == lab.objetivo:
                    rotulo = "G"
                elif valor not in (PAREDE, ASFALTO):
                    rotulo = str(CUSTO_TERRENO[valor])  # custo do terreno
                else:
                    continue
                self.create_text(x + lado / 2, y + lado / 2, text=rotulo,
                                 fill="white", font=fonte)


# --------------------------------------------------------------------------- #
# Aba do visualizador
# --------------------------------------------------------------------------- #
class AbaVisualizador(ttk.Frame):
    """Painel de configuração à esquerda; labirinto e controles à direita."""

    def __init__(self, master) -> None:
        super().__init__(master, padding=8)
        self.cenarios = criar_cenarios()
        self.labirinto: Optional[Labirinto] = None
        self.profundidade_minima: Optional[int] = None  # BFS, para comparar

        # Gravação da busca e posição da animação.
        self.grafo: Optional[Grafo] = None  # grafo usado na busca gravada
        self.quadros: List[Quadro] = []
        self.resultado: Optional[ResultadoBusca] = None
        self.indice = -1                 # quadro exibido (-1 = nenhum)
        self._inicio_iteracao: List[int] = []  # quadro[i] -> índice do "iteracao" dele
        self._agendamento: Optional[str] = None  # id do after() pendente
        # Cache dos nós explorados na iteração do quadro exibido.
        self._explorados: Set[Posicao] = set()
        self._cache_inicio = -1
        self._cache_ate = -1

        # Variáveis ligadas aos widgets (mesmas opções do visualizar.py).
        self.var_algoritmo = tk.StringVar(value="IDS")
        self.var_origem = tk.StringVar(value=self.cenarios[1].nome)
        self.var_tamanho = tk.IntVar(value=15)
        self.var_semente = tk.IntVar(value=42)
        self.var_ciclos = tk.DoubleVar(value=0.15)
        self.var_terrenos = tk.BooleanVar(value=False)
        self.var_limite = tk.StringVar()
        self.var_info = tk.StringVar()
        self.var_velocidade = tk.IntVar(value=5)
        self.var_texto_velocidade = tk.StringVar()
        self.var_posicao = tk.IntVar(value=0)
        self.var_texto_posicao = tk.StringVar()
        self.var_botao_iniciar = tk.StringVar(value="▶ Iniciar")
        # Painel de estado: uma variável por linha + mensagem final.
        self.var_estado = {chave: tk.StringVar(value="-") for chave, _ in CAMPOS_ESTADO}
        self.var_mensagem = tk.StringVar()

        painel = ttk.Frame(self, padding=(0, 0, 8, 0))
        painel.pack(side="left", fill="y")
        self._montar_painel(painel)

        direita = ttk.Frame(self)
        direita.pack(side="left", fill="both", expand=True)
        # A barra de controles é empacotada ANTES do Canvas, presa embaixo:
        # assim ela nunca é espremida e o labirinto fica com o que sobrar.
        self._montar_controles(direita)
        self.canvas = CanvasLabirinto(direita, width=600, height=480)
        self.canvas.pack(fill="both", expand=True)

        # Trocar o algoritmo ou o limite invalida a busca gravada.
        self.var_algoritmo.trace_add("write", lambda *_: self.descartar_gravacao())
        self.var_limite.trace_add("write", lambda *_: self.descartar_gravacao())
        self._instalar_atalhos()

        self._ao_mudar_velocidade()
        self._ao_trocar_origem()

    # ------------------------------------------------------------------ #
    # Construção da tela
    # ------------------------------------------------------------------ #
    def _montar_painel(self, painel: ttk.Frame) -> None:
        # Algoritmo
        caixa = ttk.LabelFrame(painel, text="Algoritmo", padding=8)
        caixa.pack(fill="x", pady=(0, 8))
        for nome in ("DLS", "IDS"):
            ttk.Radiobutton(caixa, text=nome, value=nome, takefocus=0,
                            variable=self.var_algoritmo).pack(side="left", padx=(0, 12))

        # Labirinto: um dos cenários ou um labirinto gerado
        caixa = ttk.LabelFrame(painel, text="Labirinto", padding=8)
        caixa.pack(fill="x", pady=(0, 8))
        opcoes = [c.nome for c in self.cenarios] + [OPCAO_GERAR]
        combo = ttk.Combobox(caixa, textvariable=self.var_origem, values=opcoes,
                             state="readonly", width=24)
        combo.pack(fill="x")
        combo.bind("<<ComboboxSelected>>", lambda _e: self._ao_trocar_origem())

        # Parâmetros de geração (só valem para "Gerar novo labirinto")
        self.caixa_geracao = ttk.Frame(caixa, padding=(0, 8, 0, 0))
        self.caixa_geracao.pack(fill="x")
        campos = [
            ("Tamanho", ttk.Spinbox(self.caixa_geracao, from_=5, to=61, width=6,
                                    textvariable=self.var_tamanho)),
            ("Semente", ttk.Spinbox(self.caixa_geracao, from_=0, to=99999, width=6,
                                    textvariable=self.var_semente)),
            ("Ciclos", ttk.Spinbox(self.caixa_geracao, from_=0, to=1, increment=0.05,
                                   format="%.2f", width=6, textvariable=self.var_ciclos)),
        ]
        for linha, (rotulo, widget) in enumerate(campos):
            ttk.Label(self.caixa_geracao, text=rotulo).grid(row=linha, column=0,
                                                            sticky="w", pady=2)
            widget.grid(row=linha, column=1, sticky="e", pady=2)
        ttk.Checkbutton(self.caixa_geracao, text="Terrenos (custos 2, 3 e 5)",
                        variable=self.var_terrenos).grid(row=3, column=0,
                                                         columnspan=2, sticky="w", pady=2)
        self.caixa_geracao.columnconfigure(1, weight=1)
        self.botao_gerar = ttk.Button(caixa, text="Gerar labirinto",
                                      command=self.carregar_labirinto)
        self.botao_gerar.pack(fill="x", pady=(8, 0))

        # Limite da DLS
        caixa = ttk.LabelFrame(painel, text="Limite L da DLS", padding=8)
        caixa.pack(fill="x", pady=(0, 8))
        ttk.Entry(caixa, textvariable=self.var_limite, width=8).pack(anchor="w")
        ttk.Label(caixa, text="vazio = sem limite (vira DFS)\nA IDS ignora este valor.",
                  foreground="gray").pack(anchor="w", pady=(4, 0))

        # Informações do labirinto carregado
        ttk.Label(painel, textvariable=self.var_info, justify="left").pack(anchor="w")

        # Estado da busca no quadro exibido
        caixa = ttk.LabelFrame(painel, text="Estado da busca", padding=8)
        caixa.pack(fill="x", pady=(8, 0))
        for linha, (chave, rotulo) in enumerate(CAMPOS_ESTADO):
            ttk.Label(caixa, text=rotulo).grid(row=linha, column=0, sticky="w")
            ttk.Label(caixa, textvariable=self.var_estado[chave],
                      font=("Helvetica", 12, "bold")).grid(row=linha, column=1, sticky="e")
        caixa.columnconfigure(1, weight=1)
        self.rotulo_mensagem = ttk.Label(caixa, textvariable=self.var_mensagem,
                                         wraplength=210, justify="left")
        self.rotulo_mensagem.grid(row=len(CAMPOS_ESTADO), column=0, columnspan=2,
                                  sticky="w", pady=(6, 0))

    def _montar_controles(self, pai: ttk.Frame) -> None:
        barra = ttk.Frame(pai, padding=(0, 8, 0, 0))
        barra.pack(side="bottom", fill="x")

        # Botões. takefocus=0 evita que a barra de espaço "clique" no botão
        # focado além de acionar o atalho de teclado.
        botoes = ttk.Frame(barra)
        botoes.pack()
        for texto, comando in [("⏮", self.reiniciar), ("◀ Passo", self.voltar)]:
            ttk.Button(botoes, text=texto, command=comando,
                       takefocus=0).pack(side="left", padx=2)
        ttk.Button(botoes, textvariable=self.var_botao_iniciar, width=12,
                   command=self.alternar, takefocus=0).pack(side="left", padx=2)
        for texto, comando in [("Passo ▶", self.avancar), ("⏭", self.ir_ao_fim)]:
            ttk.Button(botoes, text=texto, command=comando,
                       takefocus=0).pack(side="left", padx=2)

        # Velocidade e posição
        linha = ttk.Frame(barra, padding=(0, 6, 0, 0))
        linha.pack(fill="x")
        ttk.Label(linha, text="Velocidade").pack(side="left")
        ttk.Scale(linha, from_=1, to=len(VELOCIDADES), variable=self.var_velocidade,
                  length=120, takefocus=0,
                  command=lambda _v: self._ao_mudar_velocidade()).pack(side="left", padx=4)
        ttk.Label(linha, textvariable=self.var_texto_velocidade,
                  width=14).pack(side="left")

        ttk.Label(linha, text="Posição").pack(side="left", padx=(12, 0))
        self.escala_posicao = ttk.Scale(linha, from_=0, to=0, variable=self.var_posicao,
                                        takefocus=0, command=self._ao_arrastar_posicao)
        self.escala_posicao.pack(side="left", fill="x", expand=True, padx=4)
        ttk.Label(linha, textvariable=self.var_texto_posicao,
                  width=20).pack(side="left")

        # Legenda (a linha dos terrenos é mostrada/escondida por labirinto)
        legenda = ttk.Frame(barra, padding=(0, 8, 0, 0))
        legenda.pack()
        self._linha_legenda(legenda, LEGENDA_BUSCA).pack(anchor="center")
        self.legenda_terrenos = self._linha_legenda(legenda, LEGENDA_TERRENOS)

    @staticmethod
    def _linha_legenda(pai: ttk.Frame, itens) -> ttk.Frame:
        """Uma linha de quadradinhos coloridos com a descrição ao lado."""
        linha = ttk.Frame(pai, padding=(0, 2))
        for cor, descricao in itens:
            tk.Frame(linha, bg=cor, width=14, height=14,
                     highlightthickness=1, highlightbackground="#777777").pack(side="left")
            ttk.Label(linha, text=descricao).pack(side="left", padx=(4, 12))
        return linha

    def _instalar_atalhos(self) -> None:
        atalhos = {"<space>": self.alternar, "<Left>": self.voltar,
                   "<Right>": self.avancar, "<Home>": self.reiniciar,
                   "<End>": self.ir_ao_fim}

        def criar(acao):
            def tratar(evento):
                # Dentro de campos de texto as teclas mantêm o uso normal.
                if isinstance(evento.widget, (ttk.Entry, tk.Entry, ttk.Scale)):
                    return
                acao()
            return tratar

        janela = self.winfo_toplevel()
        for tecla, acao in atalhos.items():
            janela.bind(tecla, criar(acao))

    # ------------------------------------------------------------------ #
    # Labirinto
    # ------------------------------------------------------------------ #
    def _ao_trocar_origem(self) -> None:
        """Habilita os campos de geração só quando fazem sentido."""
        gerar = self.var_origem.get() == OPCAO_GERAR
        estado = ["!disabled"] if gerar else ["disabled"]
        for widget in self.caixa_geracao.winfo_children():
            widget.state(estado)
        self.botao_gerar.state(estado)
        # Um cenário é carregado assim que é escolhido.
        self.carregar_labirinto()

    def carregar_labirinto(self) -> None:
        """Monta o labirinto escolhido no painel e o desenha."""
        origem = self.var_origem.get()
        cenario = next((c for c in self.cenarios if c.nome == origem), None)

        if cenario is not None:
            labirinto = cenario.labirinto
            limite = cenario.grafo.limite_profundidade
            d_min = cenario.profundidade_minima
        else:
            try:
                tamanho = self.var_tamanho.get()
                semente = self.var_semente.get()
                ciclos = self.var_ciclos.get()
                if tamanho < 5 or not 0 <= ciclos <= 1:
                    raise ValueError
            except (tk.TclError, ValueError):
                messagebox.showerror("Valores inválidos",
                                     "Use tamanho >= 5, semente inteira e ciclos entre 0 e 1.")
                return
            labirinto = gerar_labirinto(tamanho, tamanho, semente=semente,
                                        taxa_ciclos=ciclos,
                                        com_terrenos=self.var_terrenos.get(),
                                        nome=f"{tamanho}x{tamanho} (semente {semente})")
            limite = None
            d_min = profundidade_minima_bfs(labirinto.para_grafo(),
                                            labirinto.inicio, labirinto.objetivo)

        self.descartar_gravacao()
        self.labirinto = labirinto
        self.profundidade_minima = d_min
        self.var_limite.set("" if limite is None else str(limite))
        nos = labirinto.para_grafo().numero_de_nos()
        self.var_info.set(f"{labirinto.nome}\n"
                          f"{labirinto.linhas}x{labirinto.colunas}, {nos} nós livres\n"
                          f"Menor caminho (BFS): {d_min if d_min is not None else '-'} passos")
        self.canvas.mostrar(labirinto)
        if labirinto.possui_terrenos():
            self.legenda_terrenos.pack(anchor="center")
        else:
            self.legenda_terrenos.pack_forget()

    # ------------------------------------------------------------------ #
    # Gravação da busca
    # ------------------------------------------------------------------ #
    def _ler_limite(self) -> Optional[int]:
        """Limite digitado (None = sem limite). ValueError se for inválido."""
        texto = self.var_limite.get().strip()
        if not texto:
            return None
        limite = int(texto)
        if limite < 0:
            raise ValueError
        return limite

    def _garantir_gravacao(self) -> bool:
        """Grava a busca se ainda não houver gravação. False se não der."""
        if self.quadros:
            return True
        if self.labirinto is None:
            return False
        algoritmo = self.var_algoritmo.get()
        limite = None
        if algoritmo == "DLS":
            try:
                limite = self._ler_limite()
            except ValueError:
                messagebox.showerror("Limite inválido",
                                     "O limite L deve ser um inteiro >= 0 (ou vazio).")
                return False

        lab = self.labirinto
        grafo = lab.para_grafo(limite_profundidade=limite)
        self.grafo = grafo
        self.resultado, self.quadros = gravar_busca(FUNCOES[algoritmo], grafo,
                                                    lab.inicio, lab.objetivo)

        # Para cada quadro, onde começou a iteração dele (usado para saber
        # quais nós já foram explorados NESTA iteração).
        self._inicio_iteracao = []
        inicio = 0
        for i, quadro in enumerate(self.quadros):
            if quadro.evento == "iteracao":
                inicio = i
            self._inicio_iteracao.append(inicio)

        self.escala_posicao.configure(to=len(self.quadros) - 1)
        return True

    def descartar_gravacao(self) -> None:
        """Esquece a busca gravada (o labirinto volta a ficar limpo)."""
        self.pausar()
        self.quadros = []
        self.resultado = None
        self.indice = -1
        self._inicio_iteracao = []
        self._explorados, self._cache_inicio, self._cache_ate = set(), -1, -1
        self.canvas.destacar({})
        self.escala_posicao.configure(to=0)
        self.var_posicao.set(0)
        self.var_texto_posicao.set("")
        self._limpar_estado()
        self._atualizar_botao()

    # ------------------------------------------------------------------ #
    # Controles da animação
    # ------------------------------------------------------------------ #
    def alternar(self) -> None:
        """Botão principal / barra de espaço: inicia ou pausa."""
        if self._agendamento is not None:
            self.pausar()
        else:
            self.iniciar()

    def iniciar(self) -> None:
        if not self._garantir_gravacao():
            return
        if self.indice >= len(self.quadros) - 1:
            self.indice = -1  # já estava no fim: recomeça
        self._tique()

    def pausar(self) -> None:
        if self._agendamento is not None:
            self.after_cancel(self._agendamento)
            self._agendamento = None
        self._atualizar_botao()

    def _tique(self) -> None:
        """Avança a animação e agenda o próximo quadro com after()."""
        atraso, salto = VELOCIDADES[self.var_velocidade.get() - 1]
        self._agendamento = None
        self.ir_para(min(self.indice + salto, len(self.quadros) - 1))
        if self.indice < len(self.quadros) - 1:
            self._agendamento = self.after(atraso, self._tique)
        self._atualizar_botao()

    def avancar(self) -> None:
        self.pausar()
        if self._garantir_gravacao():
            self.ir_para(min(self.indice + 1, len(self.quadros) - 1))

    def voltar(self) -> None:
        self.pausar()
        if self.quadros and self.indice > 0:
            self.ir_para(self.indice - 1)

    def reiniciar(self) -> None:
        """Volta ao estado antes do primeiro quadro (labirinto limpo)."""
        self.pausar()
        self.indice = -1
        self.canvas.destacar({})
        self.var_posicao.set(0)
        self.var_texto_posicao.set(f"Quadro 0 de {len(self.quadros)}" if self.quadros else "")
        self._limpar_estado()
        self._atualizar_botao()

    def ir_ao_fim(self) -> None:
        self.pausar()
        if self._garantir_gravacao():
            self.ir_para(len(self.quadros) - 1)

    def _ao_arrastar_posicao(self, valor: str) -> None:
        if not self.quadros:
            self.var_posicao.set(0)
            return
        self.pausar()
        self.ir_para(round(float(valor)))

    def _ao_mudar_velocidade(self) -> None:
        # A Scale devolve valores fracionários; arredondamos para o nível.
        nivel = round(self.var_velocidade.get())
        self.var_velocidade.set(nivel)
        atraso, salto = VELOCIDADES[nivel - 1]
        self.var_texto_velocidade.set(f"~{1000 / atraso * salto:.0f} quadros/s")

    def _atualizar_botao(self) -> None:
        if self._agendamento is not None:
            texto = "⏸ Pausar"
        elif 0 <= self.indice < len(self.quadros) - 1:
            texto = "▶ Continuar"
        else:
            texto = "▶ Iniciar"
        self.var_botao_iniciar.set(texto)

    # ------------------------------------------------------------------ #
    # Desenho de um quadro
    # ------------------------------------------------------------------ #
    def ir_para(self, indice: int) -> None:
        """Exibe o quadro ``indice`` no labirinto."""
        self.indice = indice
        quadro = self.quadros[indice]

        # A ordem importa: cada camada sobrescreve a anterior
        # (explorado < fronteira < ramo < atual < caminho final).
        destaques: Dict[Posicao, str] = {}
        for no in self._explorados_ate(indice):
            destaques[no] = COR_EXPLORADO
        for no in quadro.fronteira:
            destaques[no] = COR_FRONTEIRA
        for no in quadro.ramo:
            destaques[no] = COR_RAMO
        if quadro.no is not None:
            destaques[quadro.no] = COR_ATUAL
        if quadro.evento == "fim" and quadro.resultado.caminho_encontrado:
            for no in quadro.resultado.caminho_encontrado:
                destaques[no] = COR_CAMINHO
        self.canvas.destacar(destaques)

        self.var_posicao.set(indice)
        self.var_texto_posicao.set(f"Quadro {indice + 1} de {len(self.quadros)}")
        self._atualizar_estado(indice)
        self._atualizar_botao()

    # ------------------------------------------------------------------ #
    # Painel de estado
    # ------------------------------------------------------------------ #
    def _limpar_estado(self) -> None:
        for variavel in self.var_estado.values():
            variavel.set("-")
        self._mostrar_mensagem("Clique em Iniciar (ou aperte espaço).")

    def _mostrar_mensagem(self, texto: str, cor: str = "") -> None:
        self.var_mensagem.set(texto)
        self.rotulo_mensagem.configure(foreground=cor)

    def _atualizar_estado(self, indice: int) -> None:
        """Preenche o painel "Estado da busca" com os dados do quadro."""
        quadro = self.quadros[indice]
        ids = self.var_algoritmo.get() == "IDS"
        # Explorados na iteração = expansões desde o quadro "iteracao" dela.
        inicio = self.quadros[self._inicio_iteracao[indice]]
        valores = {
            "limite": quadro.limite,
            "iteracao": quadro.iteracao if ids else None,
            "profundidade": quadro.profundidade,
            "explorados_iteracao": quadro.total_expandidos - inicio.total_expandidos,
            "explorados_total": quadro.total_expandidos,
            "fronteira": len(quadro.fronteira) if quadro.evento == "expandir" else None,
        }
        for chave, valor in valores.items():
            self.var_estado[chave].set("-" if valor is None else str(valor))

        if quadro.evento == "iteracao":
            self._mostrar_mensagem(f"Iniciando busca com limite L = {quadro.limite}.")
        elif quadro.evento == "expandir":
            self._mostrar_mensagem("Buscando...")
        else:
            self._mostrar_resultado(quadro.resultado)

    def _mostrar_resultado(self, resultado: ResultadoBusca) -> None:
        d_min = self.profundidade_minima
        caminho = resultado.caminho_encontrado
        if caminho is None:
            texto = "Nenhuma solução encontrada."
            limite = self.grafo.limite_profundidade
            if d_min is None:
                texto += "\nO objetivo é inalcançável a partir do início."
            elif self.var_algoritmo.get() == "DLS" and limite is not None and limite < d_min:
                texto += (f"\nO limite L = {limite} é menor que o menor caminho "
                          f"({d_min} passos): a DLS corta a busca antes de chegar.")
            self._mostrar_mensagem(texto, COR_FALHA)
            return

        passos = resultado.profundidade_da_solucao
        texto = (f"Solução encontrada!\n"
                 f"Passos: {passos} (ótimo: {d_min})\n"
                 f"Custo: {self.grafo.custo_caminho(caminho):g}\n"
                 f"Nós explorados: {resultado.numero_de_nos_explorados}")
        if d_min is not None and passos > d_min:
            texto += f"\nO caminho tem {passos - d_min} passos a mais que o ótimo."
        self._mostrar_mensagem(texto, COR_SUCESSO)

    def _explorados_ate(self, indice: int) -> Set[Posicao]:
        """
        Nós expandidos desde o início da iteração do quadro ``indice`` até
        ele. Quando a animação anda para a frente dentro da mesma iteração,
        só acrescentamos os quadros novos; caso contrário, recalculamos.
        """
        inicio = self._inicio_iteracao[indice]
        if inicio != self._cache_inicio or indice < self._cache_ate:
            self._explorados = set()
            self._cache_inicio, self._cache_ate = inicio, inicio - 1
        for quadro in self.quadros[self._cache_ate + 1: indice + 1]:
            if quadro.no is not None:
                self._explorados.add(quadro.no)
        self._cache_ate = indice
        return self._explorados

    def destroy(self) -> None:
        self.pausar()  # cancela o after() pendente antes de fechar a janela
        super().destroy()


# --------------------------------------------------------------------------- #
# Aba de comparação
# --------------------------------------------------------------------------- #
# Cores do gráfico: superfície clara e as duas primeiras cores de uma paleta
# categórica validada para daltonismo (azul e laranja).
GRAFICO_FUNDO = "#fcfcfb"
GRAFICO_TEXTO = "#0b0b0b"
GRAFICO_TEXTO_SECUNDARIO = "#52514e"
GRAFICO_GRADE = "#e4e3df"
COR_SERIE = {"DLS": "#2a78d6", "IDS": "#eb6834"}

# Métricas que podem ser plotadas: (atributo da Medicao, título, formato).
METRICAS = [
    ("nos_explorados", "Nós explorados", "{:,.0f}"),
    ("tempo_ms", "Tempo (ms, mediana)", "{:.3f}"),
    ("memoria_kib", "Memória (KiB, pico)", "{:.1f}"),
    ("passos", "Passos da solução", "{:.0f}"),
    ("custo", "Custo da solução", "{:g}"),
]


def _executar_experimentos(fila: "queue.Queue", repeticoes: int) -> None:
    """
    Roda numa THREAD separada. Não pode mexer em nenhum widget (o Tkinter
    só aceita chamadas da thread principal): cada resultado é colocado na
    fila, e a interface o retira de lá com after().
    """
    try:
        cenarios = criar_cenarios()
        total = len(cenarios) * len(ALGORITMOS)
        for cenario in cenarios:
            for nome, algoritmo in ALGORITMOS.items():
                fila.put(("medicao", medir(cenario, nome, algoritmo, repeticoes), total))
        fila.put(("fim", None, total))
    except Exception as erro:  # repassa o erro para a interface mostrar
        fila.put(("erro", erro, 0))


class GraficoBarras(tk.Canvas):
    """
    Gráfico de barras agrupadas: um grupo por cenário, uma barra por
    algoritmo. Um único eixo y, linear ou logarítmico.
    """

    MARGEM_ESQ, MARGEM_DIR, MARGEM_TOPO, MARGEM_BASE = 70, 20, 44, 32
    LARGURA_BARRA = 24  # barras finas; o resto da faixa do cenário fica vazio
    ESPACO_BARRAS = 2

    def __init__(self, master, **kwargs) -> None:
        super().__init__(master, bg=GRAFICO_FUNDO, highlightthickness=0, **kwargs)
        self.medicoes: List[Medicao] = []
        self.metrica = METRICAS[0]
        self.log = True
        self._dica: Optional[tk.Toplevel] = None
        self.bind("<Configure>", lambda _e: self.desenhar())

    def atualizar(self, medicoes: List[Medicao], metrica, log: bool) -> None:
        self.medicoes, self.metrica, self.log = medicoes, metrica, log
        self.desenhar()

    # ---- escala ------------------------------------------------------- #
    def _limites(self, valores: List[float]):
        """Intervalo do eixo y (mínimo, máximo) e as posições das marcas."""
        if self.log:
            positivos = [v for v in valores if v > 0] or [1]
            baixo = math.floor(math.log10(min(positivos)))
            alto = max(baixo + 1, math.ceil(math.log10(max(positivos))))
            return 10.0 ** baixo, 10.0 ** alto, [10.0 ** e for e in range(baixo, alto + 1)]
        maximo = max(valores, default=0) or 1
        # Passo "redondo" (1, 2 ou 5 x 10^n) para ter umas 5 marcas.
        bruto = maximo / 5
        potencia = 10 ** math.floor(math.log10(bruto))
        passo = next(m * potencia for m in (1, 2, 5, 10) if m * potencia >= bruto)
        quantidade = math.ceil(maximo / passo)
        return 0.0, passo * quantidade, [passo * i for i in range(quantidade + 1)]

    def _y(self, valor: float, minimo: float, maximo: float) -> float:
        """Converte um valor para a coordenada y do Canvas."""
        base = self.winfo_height() - self.MARGEM_BASE
        altura = base - self.MARGEM_TOPO
        if self.log:
            valor = max(valor, minimo)
            fracao = ((math.log10(valor) - math.log10(minimo))
                      / (math.log10(maximo) - math.log10(minimo)))
        else:
            fracao = valor / maximo
        return base - fracao * altura

    # ---- desenho ------------------------------------------------------ #
    def desenhar(self) -> None:
        self.delete("all")
        largura, altura_total = self.winfo_width(), self.winfo_height()
        atributo, titulo, formato = self.metrica
        fonte, fonte_pequena = ("Helvetica", 12), ("Helvetica", 10)

        self.create_text(self.MARGEM_ESQ, 16, anchor="w", fill=GRAFICO_TEXTO,
                         font=("Helvetica", 13, "bold"),
                         text=titulo + ("  (escala logarítmica)" if self.log else ""))
        if not self.medicoes:
            self.create_text(largura / 2, altura_total / 2, fill=GRAFICO_TEXTO_SECUNDARIO,
                             font=fonte, text='Clique em "Rodar experimentos".')
            return

        cenarios = list(dict.fromkeys(m.cenario for m in self.medicoes))
        algoritmos = list(dict.fromkeys(m.algoritmo for m in self.medicoes))
        valores = [getattr(m, atributo) for m in self.medicoes]
        minimo, maximo, marcas = self._limites([v for v in valores if v is not None])

        x0, x1 = self.MARGEM_ESQ, largura - self.MARGEM_DIR
        base = altura_total - self.MARGEM_BASE

        # Grade e rótulos do eixo y (discretos, atrás das barras).
        for marca in marcas:
            y = self._y(marca, minimo, maximo)
            self.create_line(x0, y, x1, y, fill=GRAFICO_GRADE)
            self.create_text(x0 - 8, y, anchor="e", fill=GRAFICO_TEXTO_SECUNDARIO,
                             font=fonte_pequena, text=f"{marca:,.10g}")
        self.create_line(x0, base, x1, base, fill=GRAFICO_TEXTO_SECUNDARIO)

        # Barras: cada cenário ocupa uma "faixa" da largura do gráfico.
        faixa = (x1 - x0) / len(cenarios)
        grupo = (len(algoritmos) * self.LARGURA_BARRA
                 + (len(algoritmos) - 1) * self.ESPACO_BARRAS)
        for i, cenario in enumerate(cenarios):
            centro = x0 + faixa * (i + 0.5)
            self.create_text(centro, base + 14, fill=GRAFICO_TEXTO, font=fonte_pequena,
                             text=cenario)
            rotulo_anterior = None  # para evitar números sobrepostos no grupo
            for j, algoritmo in enumerate(algoritmos):
                m = next((m for m in self.medicoes
                          if m.cenario == cenario and m.algoritmo == algoritmo), None)
                if m is None:
                    continue
                esquerda = centro - grupo / 2 + j * (self.LARGURA_BARRA + self.ESPACO_BARRAS)
                meio = esquerda + self.LARGURA_BARRA / 2
                valor = getattr(m, atributo)
                if valor is None:  # a busca falhou: não há passos nem custo
                    self.create_text(meio, base - 10, fill=GRAFICO_TEXTO_SECUNDARIO,
                                     font=fonte_pequena, text="falhou")
                    continue
                y = self._y(valor, minimo, maximo)
                barra = self.create_rectangle(esquerda, y, esquerda + self.LARGURA_BARRA,
                                              base, fill=COR_SERIE[algoritmo], outline="")
                rotulo = self.create_text(meio, y - 8, fill=GRAFICO_TEXTO,
                                          font=fonte_pequena, text=formato.format(valor))
                # Barras de altura parecida deixam os números lado a lado e
                # encostados: nesse caso o segundo sobe acima do primeiro.
                if rotulo_anterior is not None:
                    ax0, ay0, ax1, ay1 = self.bbox(rotulo_anterior)
                    bx0, by0, _, by1 = self.bbox(rotulo)
                    if bx0 < ax1 + 4 and by0 < ay1 and by1 > ay0:
                        self.move(rotulo, 0, ay0 - by1 - 1)
                rotulo_anterior = rotulo
                dica = f"{cenario} — {algoritmo}\n{titulo}: {formato.format(valor)}"
                self.tag_bind(barra, "<Enter>", lambda e, t=dica: self._mostrar_dica(e, t))
                self.tag_bind(barra, "<Leave>", lambda _e: self._esconder_dica())

        # Legenda no canto superior direito (sempre presente com 2 séries).
        x = x1
        for algoritmo in reversed(algoritmos):
            x -= 64
            self.create_rectangle(x, 10, x + 12, 22, fill=COR_SERIE[algoritmo], outline="")
            self.create_text(x + 18, 16, anchor="w", fill=GRAFICO_TEXTO, font=fonte,
                             text=algoritmo)

    # ---- dica ao passar o mouse --------------------------------------- #
    def _mostrar_dica(self, evento, texto: str) -> None:
        self._esconder_dica()
        self._dica = tk.Toplevel(self)
        self._dica.wm_overrideredirect(True)
        self._dica.wm_geometry(f"+{evento.x_root + 12}+{evento.y_root + 12}")
        tk.Label(self._dica, text=texto, justify="left", bg="#ffffff", fg=GRAFICO_TEXTO,
                 relief="solid", borderwidth=1, padx=6, pady=4).pack()

    def _esconder_dica(self) -> None:
        if self._dica is not None:
            self._dica.destroy()
            self._dica = None


class AbaComparacao(ttk.Frame):
    """Roda a bateria de experimentos e mostra tabela + gráfico."""

    def __init__(self, master) -> None:
        super().__init__(master, padding=8)
        self.medicoes: List[Medicao] = []
        self._fila: "queue.Queue" = queue.Queue()
        self._rodando = False

        self.var_repeticoes = tk.IntVar(value=5)
        self.var_status = tk.StringVar(value="Roda DLS e IDS nos 4 cenários.")
        self.var_metrica = tk.StringVar(value=METRICAS[0][1])
        self.var_log = tk.BooleanVar(value=True)

        # Barra superior
        barra = ttk.Frame(self)
        barra.pack(fill="x")
        ttk.Label(barra, text="Repetições (tempo = mediana)").pack(side="left")
        ttk.Spinbox(barra, from_=1, to=200, width=5,
                    textvariable=self.var_repeticoes).pack(side="left", padx=(4, 12))
        self.botao_rodar = ttk.Button(barra, text="Rodar experimentos", command=self.rodar)
        self.botao_rodar.pack(side="left")
        self.botao_csv = ttk.Button(barra, text="Exportar CSV", command=self.exportar_csv)
        self.botao_csv.pack(side="left", padx=4)
        self.botao_csv.state(["disabled"])
        self.progresso = ttk.Progressbar(barra, length=140)
        self.progresso.pack(side="left", padx=12)
        ttk.Label(barra, textvariable=self.var_status).pack(side="left")

        # Tabela (mesmas colunas do comparar.py)
        self.tabela = ttk.Treeview(self, columns=CABECALHO, show="headings", height=8)
        for i, coluna in enumerate(CABECALHO):
            self.tabela.heading(coluna, text=coluna)
            self.tabela.column(coluna, anchor="w" if i < 2 else "e",
                               width=130 if i == 0 else 85, stretch=True)
        self.tabela.pack(fill="x", pady=8)

        # Escolha da métrica do gráfico
        opcoes = ttk.Frame(self)
        opcoes.pack(fill="x")
        ttk.Label(opcoes, text="Métrica do gráfico").pack(side="left")
        combo = ttk.Combobox(opcoes, textvariable=self.var_metrica, state="readonly",
                             values=[titulo for _, titulo, _ in METRICAS], width=22)
        combo.pack(side="left", padx=4)
        combo.bind("<<ComboboxSelected>>", lambda _e: self._atualizar_grafico())
        ttk.Checkbutton(opcoes, text="Escala logarítmica", variable=self.var_log,
                        command=self._atualizar_grafico).pack(side="left", padx=12)

        self.grafico = GraficoBarras(self, height=300)
        self.grafico.pack(fill="both", expand=True, pady=(8, 0))

    # ---- execução ----------------------------------------------------- #
    def rodar(self) -> None:
        if self._rodando:
            return
        try:
            repeticoes = self.var_repeticoes.get()
            if repeticoes < 1:
                raise ValueError
        except (tk.TclError, ValueError):
            messagebox.showerror("Valor inválido", "Repetições deve ser um inteiro >= 1.")
            return

        self._rodando = True
        self.medicoes = []
        self.tabela.delete(*self.tabela.get_children())
        self.botao_rodar.state(["disabled"])
        self.botao_csv.state(["disabled"])
        self.progresso.configure(value=0, maximum=1)
        self.var_status.set("Executando...")
        self._atualizar_grafico()

        # daemon=True: se a janela for fechada no meio, a thread não
        # impede o programa de terminar.
        threading.Thread(target=_executar_experimentos,
                         args=(self._fila, repeticoes), daemon=True).start()
        self.after(50, self._verificar_fila)

    def _verificar_fila(self) -> None:
        """Roda na thread principal: consome o que a thread de trabalho produziu."""
        try:
            while True:
                tipo, dado, total = self._fila.get_nowait()
                if tipo == "medicao":
                    self.medicoes.append(dado)
                    self.tabela.insert("", "end", values=linha_tabela(dado))
                    self.progresso.configure(maximum=total, value=len(self.medicoes))
                    self.var_status.set(f"{len(self.medicoes)} de {total} medições")
                    self._atualizar_grafico()
                elif tipo == "fim":
                    self._terminar(f"Concluído: {total} medições.")
                    return
                else:  # "erro"
                    self._terminar("Erro ao executar os experimentos.")
                    messagebox.showerror("Erro", str(dado))
                    return
        except queue.Empty:
            pass
        self.after(50, self._verificar_fila)

    def _terminar(self, mensagem: str) -> None:
        self._rodando = False
        self.botao_rodar.state(["!disabled"])
        if self.medicoes:
            self.botao_csv.state(["!disabled"])
        self.var_status.set(mensagem)

    def _atualizar_grafico(self) -> None:
        metrica = next(m for m in METRICAS if m[1] == self.var_metrica.get())
        self.grafico.atualizar(self.medicoes, metrica, self.var_log.get())

    def exportar_csv(self) -> None:
        caminho = filedialog.asksaveasfilename(
            title="Salvar resultados", defaultextension=".csv",
            initialfile="resultados.csv", filetypes=[("CSV", "*.csv")])
        if caminho:
            salvar_csv(self.medicoes, caminho)
            self.var_status.set(f"Resultados salvos em {caminho}")


# --------------------------------------------------------------------------- #
# Janela principal
# --------------------------------------------------------------------------- #
class Aplicacao(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Labirinto — DLS e IDS")
        self.geometry("1050x760")
        self.minsize(820, 720)

        abas = ttk.Notebook(self)
        abas.pack(fill="both", expand=True)

        self.visualizador = AbaVisualizador(abas)
        abas.add(self.visualizador, text="Visualizador")

        self.comparacao = AbaComparacao(abas)
        abas.add(self.comparacao, text="Comparação")


def main() -> None:
    Aplicacao().mainloop()
