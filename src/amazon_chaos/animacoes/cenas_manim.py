"""Peças conceituais em Manim (Community Edition), no estilo da 3Blue1Brown.

Só `Text` (Pango) e números escritos à mão nos eixos: nada de `MathTex`, que exigiria LaTeX.
O Manim não entra no `uv`: o `pycairo` não tem wheel para Linux e compilá-lo pede os cabeçalhos
do cairo (sudo). Ele roda num ambiente conda do conda-forge, que traz o cairo e o pango; a CLI
chama esse Python sozinha (`MANIM_PYTHON`, por padrão `~/miniconda3/envs/manim/bin/python`).
`renderizar(cena, saida, qualidade)` grava o MP4 e o último quadro como pôster ao lado.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import av
import numpy as np
from manim import (
    DEGREES,
    DOWN,
    LEFT,
    OUT,
    PI,
    RIGHT,
    UP,
    Axes,
    Create,
    DashedLine,
    Dot,
    FadeIn,
    FadeOut,
    ImageMobject,
    Line,
    Rectangle,
    Scene,
    Text,
    ThreeDScene,
    Transform,
    ValueTracker,
    VGroup,
    VMobject,
    Write,
    always_redraw,
    linear,
    tempconfig,
)

from amazon_chaos.animacoes.tema import AR, CREME, FOGO, MATA
from amazon_chaos.nonlinear.models import MemoryMap

FONTE = "Noto Sans"  # a Inter, quando instalada, pode entrar aqui
SUAVE = "#9fb3a6"
QUALIDADES = {"previa": ("medium_quality", 30), "final": ("high_quality", 60),
              "4k": ("fourk_quality", 60)}


def texto(s: str, tamanho: float = 28, cor: str = CREME, **kw) -> Text:
    return Text(s, font=FONTE, font_size=tamanho, color=cor, **kw)


def virgula(v: float, casas: int = 2) -> str:
    return f"{v:.{casas}f}".replace(".", ",")


def potencia(e: int) -> str:
    """10 elevado a `e`, com sobrescritos Unicode (10⁻⁸)."""
    return "10" + "".join("⁻" if c == "-" else "⁰¹²³⁴⁵⁶⁷⁸⁹"[int(c)] for c in str(e))


class DuasTrajetorias(Scene):
    """B1: duas trajetórias do mapa com memória (μ = 11,5) que partem a 10⁻⁸ uma da outra."""

    MU, PASSOS, DELTA = 11.5, 100, 1e-8

    def construct(self):
        mapa = MemoryMap()
        z1, z2 = np.array([0.30, 0.31]), np.array([0.30 + self.DELTA, 0.31])
        a, b = [z1], [z2]
        for _ in range(self.PASSOS):
            z1, z2 = mapa.step(z1, self.MU), mapa.step(z2, self.MU)
            a.append(z1)
            b.append(z2)
        a, b = np.array(a), np.array(b)
        dist = np.log10(np.maximum(np.linalg.norm(b - a, axis=1), 1e-16))
        lam = mapa.lyapunov(self.MU)

        # 1. o título
        titulo = texto("Duas trajetórias", 54, weight="BOLD")
        sub = texto("o mesmo sistema, dois pontos de partida a 0,00000001 um do outro", 28,
                    SUAVE).next_to(titulo, DOWN)
        self.play(Write(titulo), FadeIn(sub, shift=UP * 0.2), run_time=1.5)
        self.wait(1.5)
        self.play(FadeOut(sub), titulo.animate.scale(0.6).to_corner(UP + LEFT, buff=0.4),
                  run_time=1)

        eixo = {"color": SUAVE, "stroke_width": 2}
        # 2. o plano de fase com o atrator, à esquerda
        fase = Axes(x_range=[0.2, 1.0, 0.2], y_range=[0.2, 1.0, 0.2], x_length=4.8,
                    y_length=4.8, tips=False, axis_config=eixo).move_to([-4.0, -0.25, 0])
        rotulos = VGroup(
            texto("xₙ₋₁", 24, SUAVE).next_to(fase.x_axis, DOWN, buff=0.2),
            texto("xₙ", 24, SUAVE).next_to(fase.y_axis, LEFT, buff=0.2),
            texto("o atrator do sistema", 22, SUAVE).next_to(fase, UP, buff=0.2),
        )
        nuvem = mapa.simulate(self.MU, n=2500, discard=500)
        atrator = VGroup(*[Dot(fase.c2p(y, x), radius=0.012, color=SUAVE, fill_opacity=0.5)
                           for x, y in nuvem])
        self.play(Create(fase), FadeIn(rotulos), run_time=1)
        self.play(FadeIn(atrator, lag_ratio=0.002), run_time=2)

        # 3. a série e a distância, à direita; a distância vai em log₁₀ deslocado de 9,
        # porque o Manim desenha o eixo horizontal no zero
        serie = Axes(x_range=[0, self.PASSOS, 20], y_range=[0.2, 1.0, 0.4], x_length=6.4,
                     y_length=1.6, tips=False, axis_config=eixo).move_to([3.4, 2.2, 0])
        distancia = Axes(x_range=[0, self.PASSOS, 20], y_range=[0, 9, 2], x_length=6.4,
                         y_length=2.8, tips=False, axis_config=eixo).move_to([3.4, -0.9, 0])
        legenda = VGroup(
            VGroup(Dot(color=FOGO), texto("trajetória A", 20)).arrange(RIGHT, buff=0.12),
            VGroup(Dot(color=AR), texto("trajetória B", 20)).arrange(RIGHT, buff=0.12),
        ).arrange(RIGHT, buff=0.4).next_to(serie, UP, buff=0.15).align_to(serie, RIGHT)
        marcas = VGroup(
            texto("xₙ das duas", 22, SUAVE).next_to(serie, UP, buff=0.15).align_to(serie, LEFT),
            texto("distância entre elas (escala log)", 22, SUAVE).next_to(
                distancia, UP, buff=0.15).align_to(distancia, LEFT),
            texto("passo n", 20, SUAVE).next_to(distancia.x_axis, DOWN, buff=0.45),
            *[texto(str(n), 18, SUAVE).next_to(distancia.c2p(n, 0), DOWN, buff=0.1)
              for n in range(0, self.PASSOS + 1, 20)],
            *[texto(potencia(e), 18, SUAVE).next_to(distancia.c2p(0, e + 9), LEFT, buff=0.12)
              for e in (-8, -6, -4, -2, 0)],
        )
        self.play(Create(serie), Create(distancia), FadeIn(marcas), FadeIn(legenda),
                  run_time=1.2)

        n = ValueTracker(0)

        def ate(k):
            return int(np.clip(np.floor(k), 0, self.PASSOS))

        def linha(eixos, ys, cor, largura=3):
            def f():
                k = ate(n.get_value())
                pts = [eixos.c2p(i, ys[i]) for i in range(k + 1)]
                m = VMobject(stroke_color=cor, stroke_width=largura)
                m.set_points_as_corners(pts if len(pts) > 1 else pts * 2)
                return m
            return always_redraw(f)

        def ponto(traj, cor):
            # o mapa é de tempo discreto e salta de um lado a outro do atrator. O ponto fica
            # parado em cada estado metade do passo e desliza até o seguinte na outra metade,
            # só para o olho acompanhar; o rastro são os estados anteriores, esmaecendo
            def f():
                v = float(np.clip(n.get_value(), 0, self.PASSOS))
                k = ate(v)
                fr = np.clip((v - k) * 2 - 1, 0, 1)
                fr = fr * fr * (3 - 2 * fr)
                k1 = min(k + 1, self.PASSOS)
                atual = (1 - fr) * traj[k] + fr * traj[k1]
                rastro = [Dot(fase.c2p(traj[i, 1], traj[i, 0]), radius=0.05, color=cor,
                              fill_opacity=0.5 - 0.1 * (k - i))
                          for i in range(max(k - 4, 0), k)]
                return VGroup(*rastro, Dot(fase.c2p(atual[1], atual[0]), radius=0.08, color=cor))
            return always_redraw(f)

        def contador():
            k = ate(n.get_value())
            d = 10 ** dist[k]
            expoente = int(np.floor(np.log10(d)))
            valor = (f"{virgula(d / 10**expoente, 1)} × {potencia(expoente)}" if expoente < -1
                     else virgula(d, 3))
            return texto(f"passo {k}  ·  distância {valor}", 24).move_to([-4.0, -3.5, 0])

        objetos = [linha(serie, a[:, 0], FOGO), linha(serie, b[:, 0], AR, 2),
                   linha(distancia, dist + 9, CREME), ponto(a, FOGO), ponto(b, AR),
                   always_redraw(contador)]
        self.add(*objetos)
        self.wait(0.5)

        # 4. o tempo anda: juntas por uns 50 passos, depois cada uma por si
        canto = distancia.c2p(100, 2.2)  # embaixo à direita, onde a curva não passa
        self.play(n.animate.set_value(45), run_time=7, rate_func=linear)
        aviso = texto("ainda indistinguíveis", 24, SUAVE).move_to(canto, aligned_edge=RIGHT)
        self.play(FadeIn(aviso), run_time=0.4)
        self.play(n.animate.set_value(self.PASSOS), run_time=8, rate_func=linear)
        self.play(FadeOut(aviso), run_time=0.3)

        # 5. a reta: a separação cresce exponencialmente, à taxa λ₁ (logaritmo natural)
        fim = (8.4 - 1) / (lam / np.log(10))
        reta = Line(distancia.c2p(0, 1), distancia.c2p(fim, 8.4), color=FOGO, stroke_width=6)
        rotulo = texto(f"λ₁ = {virgula(lam)} por passo", 26, FOGO).move_to(
            canto, aligned_edge=RIGHT)
        self.play(Create(reta), run_time=1.5)
        self.play(Write(rotulo), run_time=1)
        self.wait(1.5)

        # 6. a mensagem
        mensagem = texto("λ₁ > 0: o estado inicial é esquecido a uma taxa constante.", 32,
                         weight="BOLD").move_to([0, -3.5, 0])
        self.play(FadeOut(objetos[-1]), Write(mensagem), run_time=1.5)
        self.wait(3)


class OrdemAoCaos(Scene):
    """B2: o diagrama de bifurcação do mapa com memória, varrido em μ, com λ₁ embaixo."""

    MU = (6.0, 16.0)
    X = (0.1, 1.02)  # o ciclo de período 3 vai de 0,12 a quase 1

    def construct(self):
        mapa = MemoryMap()
        # o diagrama como imagem: para cada coluna (um μ), onde caem os valores de longo prazo
        largura, altura = 1400, 640
        imagem = np.zeros((altura, largura, 4), np.uint8)
        cor = np.array([int(CREME[i:i + 2], 16) for i in (1, 3, 5)], np.uint8)
        for j, mu in enumerate(np.linspace(*self.MU, largura)):
            xs = mapa.simulate(mu, n=1400, discard=1100)[:, 0]
            linhas = ((self.X[1] - xs) / (self.X[1] - self.X[0]) * (altura - 1)).astype(int)
            linhas = linhas[(linhas >= 0) & (linhas < altura)]
            contagem = np.bincount(linhas, minlength=altura)
            imagem[:, j, :3] = cor
            imagem[:, j, 3] = np.clip(60 + 60 * contagem, 0, 255) * (contagem > 0)
        mus = np.linspace(*self.MU, 260)
        lam = np.clip([mapa.lyapunov(m, n=4200, transient=700) for m in mus], -1.6, 0.8)

        titulo = texto("Da ordem ao caos", 54, weight="BOLD")
        sub = texto("um único parâmetro, μ, decide o comportamento do sistema", 28,
                    SUAVE).next_to(titulo, DOWN)
        self.play(Write(titulo), FadeIn(sub, shift=UP * 0.2), run_time=1.5)
        self.wait(1.2)
        self.play(FadeOut(sub), titulo.animate.scale(0.6).to_corner(UP + LEFT, buff=0.4),
                  run_time=1)

        eixo = {"color": SUAVE, "stroke_width": 2}
        bif = Axes(x_range=[*self.MU, 2], y_range=[*self.X, 0.3], x_length=11.6,
                   y_length=3.9, tips=False, axis_config=eixo).move_to([0.35, 0.55, 0])
        ly = Axes(x_range=[*self.MU, 2], y_range=[-1.6, 0.8, 0.8], x_length=11.6,
                  y_length=1.6, tips=False, axis_config=eixo,
                  x_axis_config={"stroke_opacity": 0}).move_to([0.35, -2.7, 0])
        zero = DashedLine(ly.c2p(self.MU[0], 0), ly.c2p(self.MU[1], 0), color=SUAVE,
                          stroke_width=1.5, dash_length=0.08)
        figura = ImageMobject(imagem)
        figura.stretch_to_fit_width(bif.c2p(self.MU[1], 0)[0] - bif.c2p(self.MU[0], 0)[0])
        figura.stretch_to_fit_height(bif.c2p(0, self.X[1])[1] - bif.c2p(0, self.X[0])[1])
        figura.move_to(bif.c2p(np.mean(self.MU), np.mean(self.X)))
        marcas = VGroup(
            texto("x a longo prazo", 22, SUAVE).rotate(PI / 2).next_to(bif.y_axis, LEFT,
                                                                        buff=0.25),
            texto("λ₁", 26, SUAVE).next_to(ly.y_axis, LEFT, buff=0.25),
            texto("0", 18, SUAVE).next_to(ly.c2p(self.MU[0], 0), LEFT, buff=0.12),
            texto("μ", 26, SUAVE).next_to(bif.x_axis, RIGHT, buff=0.2).shift(DOWN * 0.15),
            *[texto(str(m), 18, SUAVE).next_to(bif.c2p(m, self.X[0]), DOWN, buff=0.22)
              for m in range(6, 17, 2)],
        )
        mu = ValueTracker(self.MU[0])
        topo, base = bif.c2p(0, self.X[1])[1], bif.c2p(0, self.X[0])[1]
        direita = bif.c2p(self.MU[1], 0)[0]

        def cortina():
            esquerda = bif.c2p(mu.get_value(), 0)[0]
            w = max(direita - esquerda, 1e-3)
            r = Rectangle(width=w + 0.05, height=topo - base + 0.1, fill_color=MATA,
                          fill_opacity=1, stroke_width=0)
            return r.move_to([esquerda + w / 2 + 0.025, (topo + base) / 2, 0])

        def cursor():
            m = mu.get_value()
            return Line(bif.c2p(m, self.X[0]), ly.c2p(m, -1.6), color=SUAVE, stroke_width=1.5,
                        stroke_opacity=0.7)

        def curva():
            m = mu.get_value()
            segmentos = VGroup()
            for i in range(len(mus) - 1):
                if mus[i + 1] > m:
                    break
                segmentos.add(Line(ly.c2p(mus[i], lam[i]), ly.c2p(mus[i + 1], lam[i + 1]),
                                   color=FOGO if lam[i + 1] > 0 else AR, stroke_width=4))
            return segmentos

        self.play(Create(bif), Create(ly), Create(zero), FadeIn(marcas), run_time=1.2)
        self.add(figura, always_redraw(cortina), always_redraw(cursor), always_redraw(curva))

        legenda = texto("", 26)
        etapas = [
            (7.89, 3.0, "μ baixo: um ponto fixo; o sistema se acomoda num único valor"),
            (9.96, 3.0, "o ponto fixo se divide em dois: um ciclo de período 2"),
            (10.90, 2.5, "período 4, período 8: uma cascata de duplicações"),
            (11.90, 2.5, "caos: a faixa se preenche, e λ₁ fica positivo"),
            (13.45, 3.5, "dentro do caos há janelas de ordem, onde λ₁ volta a ser negativo"),
            (16.00, 3.5, "um ciclo de período 3 se instala, e a ordem volta"),
        ]
        for alvo, duracao, frase in etapas:
            nova = texto(frase, 26).move_to([0.35, 3.0, 0])
            self.play(FadeOut(legenda), run_time=0.25)
            self.play(FadeIn(nova), run_time=0.3)
            legenda = nova
            self.play(mu.animate.set_value(alvo), run_time=duracao, rate_func=linear)
        self.wait(0.8)

        mensagem = VGroup(
            texto("Caos é uma propriedade precisa: λ₁ > 0 numa dinâmica determinística.", 26,
                  weight="BOLD"),
            texto("Não é sinônimo de irregularidade.", 24, SUAVE),
        ).arrange(DOWN, buff=0.12).move_to([0.35, 3.15, 0])
        self.play(FadeOut(legenda), titulo.animate.set_opacity(0), FadeIn(mensagem), run_time=1)
        self.wait(3.5)


def _cubo(pontos: np.ndarray, raio: float = 1.7) -> np.ndarray:
    """Centraliza e escala uma nuvem 3D para caber num cubo de lado 2·raio."""
    centro = (pontos.max(0) + pontos.min(0)) / 2
    return (pontos - centro) * (raio / np.abs(pontos - centro).max())


def _atrasos(x: np.ndarray, tau: int) -> np.ndarray:
    return np.column_stack([x[:-2 * tau], x[tau:-tau], x[2 * tau:]])


class DeLorenzAoXingu(ThreeDScene):
    """B3: a reconstrução por atrasos (Takens), do Lorenz à temperatura do Xingu.

    Na tela, três dimensões (xₜ, xₜ₊τ, xₜ₊₂τ); nos dados do TCC, τ = 1 dia e m = 5.
    """

    TAKENS = Path("reports/animacoes/dados/xingu/takens_t2m.npz")
    DIAS = 1461  # quatro anos da série da bacia na nuvem

    def fixo(self, *mobs):
        self.add_fixed_in_frame_mobjects(*mobs)
        return mobs

    def linha3d(self, pontos, cor, largura=1.6, opacidade=0.9):
        m = VMobject(stroke_color=cor, stroke_width=largura, stroke_opacity=opacidade)
        m.set_points_as_corners(pontos)
        return m

    def tira(self, x, cor, rotulo):
        """A série observada, numa faixa fixa embaixo da tela."""
        eixos = Axes(x_range=[0, len(x), max(len(x) // 4, 1)], y_range=[x.min(), x.max(),
                     (x.max() - x.min()) / 2], x_length=11, y_length=1.1, tips=False,
                     axis_config={"color": SUAVE, "stroke_width": 1.5}).move_to([0, -3.15, 0])
        curva = VMobject(stroke_color=cor, stroke_width=1.6)
        curva.set_points_as_corners([eixos.c2p(i, v) for i, v in enumerate(x)])
        nome = texto(rotulo, 20, SUAVE).next_to(eixos, UP, buff=0.05).align_to(eixos, LEFT)
        return eixos, curva, nome

    VELOCIDADE = 0.25  # rad/s, a mesma para tudo o que gira

    def girar(self, mob):
        """Gira em torno do eixo vertical que passa pelo centro do objeto."""
        centro = mob.get_center()
        mob.add_updater(lambda m, dt: m.rotate(self.VELOCIDADE * dt, axis=OUT,
                                               about_point=centro))

    def nuvem(self, pontos, cor):
        """Um ponto por dia (o PMobject não aparece no renderizador Cairo)."""
        return VGroup(*[Dot(p, radius=0.022, color=cor, fill_opacity=0.6, stroke_width=0)
                        for p in pontos])

    def legenda(self, anterior, frase, y=2.6, tamanho=28, cor=CREME):
        nova = texto(frase, tamanho, cor).move_to([0, y, 0])
        self.add_fixed_in_frame_mobjects(nova)
        nova.set_opacity(0)
        if anterior is not None:  # uma sai antes de a outra entrar: nunca duas frases juntas
            self.play(anterior.animate.set_opacity(0), run_time=0.3)
        self.play(nova.animate.set_opacity(1), run_time=0.4)
        return nova

    def construct(self):
        from scipy.integrate import solve_ivp

        def lorenz(_, v, s=10.0, r=28.0, b=8 / 3):
            return [s * (v[1] - v[0]), v[0] * (r - v[2]) - v[1], v[0] * v[1] - b * v[2]]

        dt = 0.01
        sol = solve_ivp(lorenz, (0, 45), [1.0, 1.0, 1.0], t_eval=np.arange(0, 45, dt),
                        rtol=1e-9, atol=1e-9).y.T[500:]
        tau = 15  # 0,15 unidades de tempo
        real = _cubo(sol, 2.3)
        reconstruido = _cubo(_atrasos(sol[:, 0], tau), 2.3)
        dados = np.load(self.TAKENS)
        xingu = dados["serie"][-self.DIAS:]
        substituta = dados["substituta"][-self.DIAS:]

        self.set_camera_orientation(phi=68 * DEGREES, theta=-50 * DEGREES)
        titulo = texto("De Lorenz ao Xingu", 54, weight="BOLD")
        sub = texto("reconstruir um sistema a partir de uma única série", 28, SUAVE).next_to(
            titulo, DOWN)
        self.fixo(titulo, sub)
        self.play(Write(titulo), FadeIn(sub), run_time=1.5)
        self.wait(1.2)
        self.play(FadeOut(sub), titulo.animate.scale(0.6).to_corner(UP + LEFT, buff=0.4),
                  run_time=1)

        # 1. o sistema de Lorenz, com as três variáveis
        leg = self.legenda(None, "o sistema de Lorenz: três variáveis, x, y e z")
        atrator = self.linha3d(real, AR, 1.4).shift(-0.35 * OUT)  # abaixo da legenda
        self.girar(atrator)
        self.add(atrator)
        self.play(Create(atrator), run_time=4, rate_func=linear)

        # 2. só uma delas é observada
        leg = self.legenda(leg, "mas, num experimento, observamos só uma delas: x(t)")
        eixos, curva, nome = self.tira(sol[:2000, 0], FOGO, "x(t), a série observada")
        self.fixo(eixos, curva, nome)
        self.play(Create(eixos), FadeIn(nome), Create(curva), run_time=2.5, rate_func=linear)
        self.wait(0.5)

        # 3. a reconstrução por atrasos
        leg = self.legenda(leg, "cada ponto vira (x(t), x(t+τ), x(t+2τ)): a reconstrução por "
                           "atrasos")
        copia = self.linha3d(reconstruido, FOGO, 1.4).shift(-0.35 * OUT)
        self.girar(copia)
        self.play(FadeOut(atrator), run_time=0.6)
        self.add(copia)
        self.play(Create(copia), run_time=4, rate_func=linear)
        leg = self.legenda(leg, "uma forma equivalente, refeita só com x (o teorema de Takens)")
        self.wait(2)

        # 4. a temperatura do Xingu na mesma máquina
        leg = self.legenda(leg, "agora, a temperatura diária do Xingu, com τ = 1 dia")
        eixos2, curva2, nome2 = self.tira(xingu, CREME,
                                          "anomalia padronizada da temperatura, 2021–2024")
        self.play(FadeOut(copia), FadeOut(curva), FadeOut(nome), FadeOut(eixos), run_time=0.6)
        self.fixo(eixos2, curva2, nome2)
        nuvem = self.nuvem(_cubo(_atrasos(xingu, 1), 2.6), CREME)
        self.girar(nuvem)
        self.add(nuvem)
        self.play(Create(eixos2), FadeIn(nome2), Create(curva2),
                  FadeIn(nuvem, lag_ratio=0.002), run_time=5, rate_func=linear)
        leg = self.legenda(leg, "não aparece um atrator fino: aparece uma nuvem")
        self.wait(2.5)

        # 5. a nuvem real e a de uma substituta, lado a lado
        leg = self.legenda(leg, "à esquerda, a série real; à direita, uma substituta IAAFT")
        self.play(FadeOut(curva2), FadeOut(nome2), FadeOut(eixos2), run_time=0.5)
        # "direita" na tela, em coordenadas do mundo, para a câmera em θ
        theta = self.camera.get_theta()
        direita = np.array([-np.sin(theta), np.cos(theta), 0.0])
        # a nuvem real volta à orientação de partida, à esquerda; a substituta entra à direita
        # na mesma orientação, e as duas giram juntas daqui em diante
        nuvem.clear_updaters()
        esquerda = self.nuvem(_cubo(_atrasos(xingu, 1), 2.6), CREME).shift(-3.3 * direita)
        self.play(Transform(nuvem, esquerda), run_time=1.2)
        outra = self.nuvem(_cubo(_atrasos(substituta, 1), 2.6), AR).shift(3.3 * direita)
        self.girar(nuvem)
        self.girar(outra)
        self.add(outra)
        self.play(FadeIn(outra, lag_ratio=0.002), run_time=3, rate_func=linear)
        leg = self.legenda(leg, "a olho, as duas são quase iguais")
        self.wait(2.5)

        mensagem = VGroup(
            texto("O clima não desenha um atrator fino:", 30, weight="BOLD"),
            texto("a diferença para o acaso só aparece nas estatísticas.", 30, weight="BOLD"),
            texto("na tela, 3 dimensões; nos dados, τ = 1 dia e m = 5", 20, SUAVE),
        ).arrange(DOWN, buff=0.12).move_to([0, -3.0, 0])
        self.fixo(mensagem)
        mensagem.set_opacity(0)
        self.play(mensagem.animate.set_opacity(1), leg.animate.set_opacity(0), run_time=1)
        self.wait(4)


CENAS = {"trajetorias": DuasTrajetorias, "bifurcacao": OrdemAoCaos, "lorenz": DeLorenzAoXingu}


def renderizar(cena: type[Scene], saida: Path, qualidade: str = "previa") -> Path:
    """Renderiza a cena num diretório temporário e copia o MP4 e o pôster para `saida`."""
    saida = Path(saida)
    saida.parent.mkdir(parents=True, exist_ok=True)
    preset, fps = QUALIDADES[qualidade]
    with tempfile.TemporaryDirectory() as pasta, tempconfig({
        "quality": preset, "frame_rate": fps, "media_dir": pasta, "background_color": MATA,
        "output_file": saida.stem, "disable_caching": True, "verbosity": "WARNING",
        "progress_bar": "none",
    }):
        instancia = cena()
        instancia.render()
        shutil.copy(instancia.renderer.file_writer.movie_file_path, saida)
    with av.open(str(saida)) as video:
        for quadro in video.decode(video=0):
            ultimo = quadro
    ultimo.to_image().save(saida.with_suffix(".png"))
    return saida
