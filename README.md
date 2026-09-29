# Labirinto com Limite de Profundidade — DLS e IDS

Parte prática do trabalho de IA sobre algoritmos de busca: **Busca em
Profundidade Limitada (DLS)** e **Busca de Aprofundamento Iterativo (IDS)**
aplicadas a labirintos. Usa só a biblioteca padrão (Python 3.8 ou mais novo),
sem dependências externas. A interface gráfica usa o Tkinter, que também faz
parte da biblioteca padrão, mas precisa de um Python compilado com suporte a Tk
(veja [Interface gráfica](#interface-gráfica)).

## Estrutura

```
busca_labirinto/
  grafo.py         Classe Grafo (lista de adjacência ponderada)
  labirinto.py     Motor: gera o labirinto (matriz), terrenos e converte para Grafo
  algoritmos.py    dls(grafo, estado_inicial, estado_objetivo) e ids(...)
  visualizador.py  Animação passo a passo no terminal (ANSI + time.sleep)
  cenarios.py      Os 4 cenários da bateria de experimentos
  comparacao.py    Métricas (tracemalloc, tempo, nós, passos, custo) e tabela
  gravador.py      Grava a execução da busca em quadros (usado pela interface)
  interface.py     Interface gráfica em Tkinter (visualizador + comparação)
tests/
  test_algoritmos.py   Testes automatizados (unittest)
interface.py       Script da interface gráfica
visualizar.py      Script do visualizador no terminal
comparar.py        Script da tabela comparativa
```

## Como executar

Todos os comandos são rodados a partir da raiz do projeto.

### Interface gráfica

```bash
python3 interface.py
```

A janela tem duas abas.

**Visualizador**: anima a DLS ou a IDS resolvendo um labirinto.

- À esquerda ficam o algoritmo, o labirinto (um dos 4 cenários ou um gerado
  com tamanho, semente, ciclos e terrenos) e o limite L da DLS (vazio = sem
  limite). O painel *Estado da busca* mostra, a cada passo, o limite L, a
  iteração (IDS), a profundidade atual, os nós explorados na iteração e no
  total, o tamanho da fronteira e, no fim, o resultado comparado ao ótimo.
- Abaixo do labirinto ficam os controles: reiniciar, voltar um passo,
  iniciar/pausar, avançar um passo e ir para o fim, além da velocidade e de
  uma barra de posição para pular para qualquer momento da busca.
- Atalhos: **espaço** inicia/pausa, **←/→** voltam/avançam um passo,
  **Home/End** vão para o começo/fim.

**Comparação**: roda DLS e IDS nos 4 cenários (o mesmo que `comparar.py`) e
mostra a tabela e um gráfico de barras DLS × IDS. Dá para escolher a métrica
(nós explorados, tempo, memória, passos ou custo), ligar a escala logarítmica e
exportar o resultado em CSV.

Como funciona: a busca roda inteira de uma vez e o `Gravador` guarda cada
evento (nova iteração, nó expandido, fim) como um quadro. A animação só
percorre essa lista com `after()` do Tkinter, e por isso dá para pausar e voltar
sem rodar o algoritmo de novo. Na aba de comparação, os experimentos rodam numa
thread separada e mandam os resultados à janela por uma fila (`queue.Queue`),
então a interface não trava.

> **Tkinter no macOS com pyenv.** Se `python3 -c "import tkinter"` der
> `No module named '_tkinter'`, o Python foi compilado sem Tk. Instale o Tk e
> recompile o Python:
>
> ```bash
> brew install tcl-tk
> pyenv uninstall <versão> && pyenv install <versão>
> ```
>
> No Linux, instale o pacote `python3-tk` (Debian/Ubuntu).

### Visualizador no terminal

```bash
python3 visualizar.py                                  # IDS num labirinto 15x15
python3 visualizar.py --algoritmo dls --limite 40      # DLS com limite 40
python3 visualizar.py --cenario 1 --algoritmo ids      # cenário pequeno (5x5)
python3 visualizar.py --cenario 4 --algoritmo dls      # labirinto com terrenos
python3 visualizar.py --tamanho 11 --passo-a-passo     # avança com ENTER
python3 visualizar.py --cenario 3 --pular 25 --atraso 0.01   # 30x30 mais rápido
python3 visualizar.py --help                           # todas as opções
```

| Opção | Significado |
|---|---|
| `-a, --algoritmo {dls,ids}` | algoritmo (padrão: `ids`) |
| `-c, --cenario {1,2,3,4}` | usa um cenário da bateria de testes |
| `-t, --tamanho N` | lado do labirinto gerado (padrão: 15) |
| `-s, --semente N` | semente aleatória (o mesmo número gera o mesmo labirinto) |
| `--terrenos` | adiciona grama (2), areia (3) e pântano (5) |
| `--ciclos F` | fração de paredes removidas para criar ciclos (padrão: 0.15) |
| `-l, --limite N` | limite de profundidade da DLS |
| `-d, --atraso S` | segundos entre quadros (padrão: 0.05) |
| `--pular N` | desenha 1 quadro a cada N expansões |
| `--passo-a-passo` | espera ENTER a cada passo (bom para apresentar) |

Legenda das cores: **S** início (azul), **G** objetivo (vermelho),
**magenta** nó sendo expandido, **laranja** ramo atual (caminho do início até
o nó atual), **amarelo** fronteira (pilha), **azul** nós já explorados,
**verde** caminho final. No cenário com terrenos, cada célula mostra o seu
custo.

Na IDS a tela é limpa a cada nova iteração e o cabeçalho mostra o limite `L`
atual, o que deixa visível o "aprofundamento" iterativo.

> Use um terminal com suporte a 256 cores (GNOME Terminal, Konsole, o
> terminal do VS Code e o Windows Terminal servem) e com a janela grande o
> bastante: o cenário 30x30 ocupa 60 colunas por cerca de 40 linhas.

### Tabela comparativa

```bash
python3 comparar.py                        # imprime a tabela
python3 comparar.py --repeticoes 20        # mediana de 20 execuções para o tempo
python3 comparar.py --csv resultados.csv   # também salva em CSV
```

### Testes automatizados

```bash
python3 -m unittest discover -s tests -v
```

## Decisões de modelagem

- **Matriz → Grafo.** O labirinto é gerado como matriz (algoritmo *recursive
  backtracker* e remoção de algumas paredes para criar ciclos), mas
  `Labirinto.para_grafo()` o converte em um `Grafo`: cada célula livre vira
  um nó `(linha, coluna)` e cada vizinha ortogonal livre vira uma aresta. Os
  algoritmos só acessam `grafo.vizinhos(no)`, sem nenhum conhecimento da
  matriz. Eles também funcionam com grafos quaisquer; os testes incluem um
  grafo com nós `"A"`, `"B"`, ....
- **Custos.** O peso da aresta `u → v` é o custo do terreno de `v`
  (asfalto 1, grama 2, areia 3, pântano 5). DLS e IDS ignoram os pesos na
  busca; eles só entram no cálculo do **custo da solução**.
- **Assinatura com 3 entradas.** A DLS precisa de um limite `L`. Como a
  assinatura exigida é `dls(grafo, estado_inicial, estado_objetivo)`, o
  limite faz parte da instância do problema ("labirinto com limite de
  profundidade") e fica em `grafo.limite_profundidade`. A IDS não usa esse
  valor.
- **Retorno.** As funções retornam `(caminho_encontrado,
  numero_de_nos_explorados, profundidade_da_solucao)`. Se não houver solução,
  o caminho e a profundidade são `None`.
- **Ciclos.** Para não entrar em laço, cada nó guarda a menor profundidade
  em que já foi alcançado e só volta à fronteira se for alcançado por um
  caminho mais raso. Isso impede ciclos e mantém a DLS completa dentro do
  limite.
- **Limite nos cenários.** `L = profundidade mínima + 50%`, com a
  profundidade mínima obtida por uma BFS auxiliar usada só para calibrar o
  cenário.

## O que esperar dos resultados

- A **IDS** sempre encontra o caminho com **menos passos** (ótima em número
  de passos). Em compensação, explora mais nós, porque repete as iterações
  rasas.
- A **DLS** explora menos nós, mas pode devolver um caminho **mais longo**
  que o ótimo (é o primeiro caminho que cabe no limite). Se `L` for menor que
  a profundidade da solução, ela **falha**.
- Nenhuma das duas é ótima em **custo**: no cenário com terrenos, o caminho
  mais curto pode atravessar pântanos.
