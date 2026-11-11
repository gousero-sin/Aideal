# Plano — Nova tela de loading "Pinceladas Cinéticas" (AIDEAL)

Data: 2026-11-11 · Autor: planner (somente leitura) · Executor: um único agente, seguindo este documento na ordem.

Pedido do usuário: movimento muito mais incrível, **menos informação**, animação ocupando grande parte da tela, com o símbolo AIDEAL das 3 pinceladas compondo a animação, extremamente moderno e extremo em movimento.

---

## 1. Estado atual (lido no código)

| Item | Onde | Fato |
|---|---|---|
| Componente | `frontend/src/components/AidealPartnershipLoader.jsx` (126 linhas) | Exporta `default AidealPartnershipLoader` e `AidealMark` (este só é usado dentro do próprio arquivo). |
| Props | idem | `visible` (bool), `exiting` (bool), `scene` (objeto com `scene.step` numérico), `title`, `subtitle`, `steps` (array, default 4 etapas). Retorna `null` quando `!visible`. |
| Uso | `frontend/src/App.jsx` linhas 108–112 e 217–223 | `useLiquidLoaderController({ intervalMs: 3200, minVisibleMs: 1400, exitMs: 420 })` de `goflow-core`. `loader.show(1)` quando `busy` vira true, `loader.hide()` quando volta a false. `busy` vem de `onBusyChange` dos painéis (carga inicial DRE/Fluxo, exportação). |
| Ciclo de vida | controller | `visible=true` monta; ao esconder, `exiting=true` por `exitMs` e depois `visible=false` desmonta. `scene.step` avança a cada `intervalMs`. **A saída só tem `exitMs` de duração: a animação de saída precisa caber nesse valor.** |
| CSS | `frontend/src/styles/corporate.css` | Bloco do loader nas linhas ~176–490, keyframes ~3182–3280 (`aideal-loader-*`, `aideal-mark-*`), media 520px ~3495–3533, reduced motion ~3546–3567. Overlay `position: fixed; inset: 0; z-index: 990` com `backdrop-filter: blur(18px)`. |
| Não mexer | `corporate.css` | `.aideal-sr-only` (linha ~168) e `.aideal-loader` (linha ~993, spinner do `UploadPanel.jsx:709`) são de outros usos. |
| Tokens | `corporate.css :root` | `--aideal-bg: #07090d`, `--aideal-motion-ease: cubic-bezier(0.16, 1, 0.3, 1)`. |
| Testes | `npm test` = `node --test src/components/*.test.js`; e2e Playwright em `frontend/e2e` | Nenhum teste ou e2e referencia classes do loader (confirmado por busca). |
| Motion | `framer-motion ^12.28.2` instalado; o projeto importa de `'framer-motion'` | Ver decisão técnica na seção 3 (não será usado neste componente). |

Antes de codar, o executor deve abrir `frontend/node_modules/goflow-core/dist/index.js`, localizar `useLiquidLoaderController` e confirmar a semântica acima (`visible`/`exiting`/`scene`, e que `exitMs` é a janela entre `exiting=true` e desmontagem). Se divergir, ajustar apenas os números da seção 4.3.

### API pública do novo componente

Mesmas props, mesmo comportamento de montagem: `visible`, `exiting`, `scene`, `title`, `subtitle`, `steps`. `title`/`subtitle`/`steps` passam a alimentar **somente** o texto para leitor de tela. Migração em `App.jsx` restrita a: trocar o import/nome do componente e ajustar dois números do controller (`minVisibleMs: 1700`, `exitMs: 720`).

---

## 2. Direção criativa — "Pinceladas Cinéticas"

**Intenção emocional:** potência e velocidade sob controle. Personalidade *Energetic* (motion-design skill): durações curtas, ease-out-expo, overshoot nas aterrissagens.

**Micro-história:** três fitas de tinta/luz cruzam a tela em alta velocidade → batem no lugar e formam o símbolo AIDEAL gigante → enquanto carrega, cada pincelada dispara para fora e reentra pelo lado oposto em revezamento, sem parar → ao terminar, as três explodem para fora e a aplicação aparece por trás.

**Escala:** o palco é um quadrado de `min(78vmin, 820px)`; o símbolo ocupa ~74% dele (≈58vmin de largura). Linhas de velocidade e brilho ocupam 100% do viewport. Em 1440×900 o símbolo fica com ~520px (hoje tem 86px).

**Texto visível: nenhum.** Justificativa: o usuário pediu menos informação e aceitou só o símbolo; título, subtítulo, kicker e as 4 pílulas saem. Permanece um `<span className="aideal-sr-only">` com o status (acessibilidade, `role="status"`), e `data-loader-phase` continua no root. A etapa (`scene.step`) deixa de ser texto e vira cor: o brilho ambiente dominante muda a cada fase (amarelo → azul → vermelho → azul).

### Camadas

| Camada | Elementos | Papel |
|---|---|---|
| **Primária** | 3 pinceladas vetoriais (SVG) | Entrada em fita, loop de disparo/reentrada, saída explosiva. |
| **Secundária** | 2 "fantasmas" borrados por pincelada (rastro/motion blur), flash de brilho na aterrissagem, anel de impacto, inclinação 3D do palco | Dá peso e velocidade à primária. |
| **Ambiente** | 14 linhas de velocidade na mesma diagonal de −12°, 3 manchas de luz nas cores da marca, vinheta | Vida de fundo, ~20% da energia visual. |

Tudo se move no **mesmo eixo de −12°** (origem espacial única): o container das pinceladas e o das linhas de velocidade são rotacionados uma vez em −12°, e os filhos animam só `translateX`.

### Geometria do símbolo (vetor reconstruído do logo)

Um único desenho de pincelada, desenhado **horizontal**, reutilizado 3× (a inclinação vem do container rotacionado). `viewBox="0 0 640 150"`:

```
M 86 6
H 590
Q 634 6 634 48
V 60
Q 634 100 592 104
L 190 128
C 120 132 70 150 30 138
C -2 128 2 84 18 58
C 34 30 54 6 86 6 Z
```

Leitura: topo reto, ponta direita arredondada (raio ~44), base levemente convergente (afina 104→128 para a esquerda) e, à esquerda, a **cauda curva** que desce e fecha em bulbo, como no logo. Definir uma vez como `<symbol id>` num `<svg>` oculto dentro do componente e usar `<use href>` em cada pincelada; ids de gradiente/símbolo gerados com `useId()` para não colidir.

Ajuste fino obrigatório: na página de preview (seção 6), sobrepor `public/logo-aideal-peq-2.png` com 50% de opacidade ao lado do símbolo vetorial parado e corrigir pontos de controle/posições até a silhueta bater a olho. Só então seguir para a animação.

Posição de cada pincelada dentro do container rotacionado (em % do palco; largura = % do palco, altura = largura × 150/640):

| Pincelada | left | top | largura | Gradiente (esq → dir) |
|---|---|---|---|---|
| Amarela | 17% | 22% | 70% | `#FFD23F` → `#FFB800` → `#FF9500` |
| Azul | 13% | 41% | 76% | `#35C7F2` → `#1E9BF0` → `#0B6FD6` |
| Vermelha | 9% | 60% | 70% | `#FF4040` → `#E3141B` → `#B00D14` |

Fundo: `#05070B` a 96% de opacidade (sem `backdrop-filter`; blur de tela cheia sob animação contínua custa caro e o fundo já é quase opaco).

---

## 3. Abordagem técnica

**CSS keyframes + React, sem framer-motion e sem dependências novas.** Motivos:

1. O loader aparece exatamente quando a thread principal está ocupada (parse de chunk lazy, render de painel, tabelas). Keyframes CSS de `transform`/`opacity` rodam no compositor e não engasgam; animação dirigida por JS engasgaria.
2. A saída já é temporizada pelo controller (`exiting` + `exitMs`), então `AnimatePresence` não é necessário; basta a classe `is-exiting`.
3. A skill `motion` (css-or-motion) recomenda CSS para loops infinitos simples e entradas na montagem sem interrupção.

Regras de implementação:

- **Cada pincelada é um `div` HTML** contendo seu próprio `<svg>`. Animar o `div` (camada composta); nunca animar elementos dentro do SVG.
- **Wrappers aninhados, um keyframe por nível**, para intro, loop e saída não disputarem a propriedade `animation`:
  `.akl-stroke-exit` (só anima com `.is-exiting`) > `.akl-stroke-intro` (1×, `both`) > `.akl-stroke-loop` (infinito, com delay) > `.akl-stroke-body` (svg + fantasmas).
- Só `transform`, `opacity` e `filter: brightness()` (este apenas no flash de aterrissagem). Blur dos fantasmas é **estático** (`filter: blur(18px)` fixo; rasteriza uma vez e depois só translada).
- Fantasmas: `div`s com `linear-gradient` na cor da pincelada, `border-radius: 999px`, `opacity` .45/.25, atrasados 40ms e 90ms em relação à pincelada (mesmo keyframe, `animation-delay` maior) e com `scaleX` maior. Não precisam da forma exata.
- `will-change: transform, opacity` apenas em `.akl-stroke-loop` e `.akl-stage`. `contain: strict` no root; `pointer-events: all` (bloqueia a UI) e `pointer-events: none` em `.is-exiting`.
- Linhas de velocidade: array constante `SPEED_LINES` (14 itens com `top %`, `width vmin`, `duração ms`, `delay ms` negativo, `opacidade`, `cor`) no arquivo de modelo; valores fixos, nada de `Math.random()` no render. Passados por CSS custom properties inline (`--akl-top`, `--akl-w`, `--akl-dur`, `--akl-delay`, `--akl-o`).
- Sem timers nem rAF no componente → nada a limpar. O desmonte remove as animações. `useMemo` só para o texto de status.
- Unidades em `vmin`/`%`; nenhuma leitura de layout em JS.
- Reduced motion em CSS (`@media (prefers-reduced-motion: reduce)`), ver 4.4.

---

## 4. Timeline exata

Curvas:

- `--akl-out-expo: cubic-bezier(0.16, 1, 0.3, 1)` (entradas/aterrissagens)
- `--akl-in-expo: cubic-bezier(0.7, 0, 0.84, 0)` (disparos/saídas)
- `--akl-overshoot: cubic-bezier(0.34, 1.56, 0.64, 1)` (assentamento)
- `--akl-sine: cubic-bezier(0.37, 0, 0.63, 1)` (ambiente)

`translateX` em % é relativo à largura da própria pincelada.

### 4.1 Intro (0 → 1300ms)

| t (ms) | Elemento | Animação |
|---|---|---|
| 0–220 | Fundo (`.akl-backdrop`) | `opacity 0→1`, linear |
| 80–700 | Amarela | de `translateX(-260%) scaleX(2.4)`, `opacity 0` → `translateX(0) scaleX(1)`, `opacity 1` (opacidade completa aos 35%); 620ms, out-expo |
| 200–820 | Azul | igual, vindo da **direita** (`+260%`); 620ms |
| 320–940 | Vermelha | igual, vindo da esquerda; 620ms |
| aterrissagem de cada uma (+0 a +260ms) | `.akl-stroke-body` | `filter: brightness(1.9) → 1`, 260ms, ease-out |
| 300–800 | Linhas de velocidade | container `opacity 0→1` |
| 760–1360 | Anel de impacto | `scale 0.55→1.7`, `opacity 0.55→0`, 600ms, out-expo |
| 0–1300 | Palco | `scale 0.9→1`, 1300ms, out-expo |
| 1300 | — | 100ms de respiro, então começa o loop |

### 4.2 Loop (período 3200ms = `intervalMs` do controller; começa em 1300ms)

Keyframe `akl-dash` em `.akl-stroke-loop`, defasagem: amarela +0ms, azul +180ms, vermelha +360ms. Azul percorre o sentido oposto (usar `--akl-dir: -1` multiplicando os X com `calc()`).

| % | ms | transform | opacity | curva até o próximo |
|---|---|---|---|---|
| 0 | 0 | `translateX(0) scaleX(1)` | 1 | sine |
| 8 | 256 | `translateX(-7%) scaleX(0.95)` (antecipação) | 1 | in-expo |
| 21 | 672 | `translateX(190%) scaleX(1.9)` | 0 | step (teleporte invisível) |
| 21.01 | 672 | `translateX(-190%) scaleX(1.9)` | 0 | out-expo |
| 38 | 1216 | `translateX(4%) scaleX(1.05)` | 1 | overshoot |
| 46 | 1472 | `translateX(0) scaleX(1)` | 1 | — |
| 46–100 | 1472–3200 | repouso | 1 | — |

Complementos do loop:

- Flash: `brightness(1.7) → 1` entre 38% e 46% em `.akl-stroke-body` (mesmo período e defasagem).
- Anel de impacto: repete a cada 3200ms, iniciando em 38% do ciclo da azul.
- Palco (`.akl-stage`, pai com `perspective: 1200px`): `rotateX ±6°`, `rotateY ±9°`, `scale 0.98↔1.03`, 6400ms, sine, `alternate`.
- Linhas de velocidade: `translateX(-60vmax) → translateX(160vmax)`, linear, infinito, 700–1600ms cada, delays negativos para já nascerem espalhadas; 2px de altura, 18–42vmin de largura, gradiente transparente→cor→transparente, opacidade .12–.45.
- Manchas de luz (3, `radial-gradient`, 70vmin, sem blur): deriva de ±6vmin em 9s/11s/13s, sine. A mancha da fase ativa (`[data-loader-phase]`) vai a `opacity .5`, as outras a `.18`, com `transition: opacity 600ms`.

### 4.3 Saída (`.is-exiting`, 720ms — exige `exitMs: 720`)

| t (ms) | Elemento | Animação |
|---|---|---|
| 0–380 | Amarela (`.akl-stroke-exit`) | `translateX(0)→(320%)`, `scaleX 1→2.6`, `opacity 1→0` nos últimos 40%; in-expo |
| 50–430 | Azul | idem para a **esquerda** (`-320%`) |
| 100–480 | Vermelha | idem para a direita |
| 0–480 | Palco | `scale 1→1.18`, in-expo |
| 0–300 | Linhas de velocidade | `opacity →0` |
| 260–720 | Fundo + root | `opacity 1→0`, ease-in-out |

Saída ≈ 55% da intro (regra saída < entrada). `minVisibleMs: 1700` garante que a intro (1300ms) e um trecho do loop sempre apareçam antes da saída.

### 4.4 Reduced motion

Dentro de `@media (prefers-reduced-motion: reduce)`: remover todos os keyframes de translação/escala/rotação; pinceladas paradas na posição final; linhas de velocidade, fantasmas e anel com `display: none`; intro = `opacity 0→1` em 200ms; loop = pulso de `opacity 0.72↔1` em 2400ms, defasado 300ms por pincelada; saída = `opacity →0` em 200ms.

---

## 5. Arquivos

| Ação | Arquivo | Conteúdo |
|---|---|---|
| Criar | `frontend/src/components/aidealKineticLoaderModel.js` (~60 linhas) | `normalizeStep(step, total)` (copiar a lógica atual), `buildStatusText({ title, subtitle, steps, activeStep })`, `STROKES` (3 itens: id, posição %, cores, direção, delay), `SPEED_LINES` (14 itens), `STROKE_PATH`. Tudo `Object.freeze`. |
| Criar | `frontend/src/components/aidealKineticLoaderModel.test.js` | Escrever **antes** do modelo (TDD): `normalizeStep` com negativos/NaN/total 0; `buildStatusText` com e sem props; `STROKES` com 3 itens e cores esperadas; `SPEED_LINES` com 14 itens e delays ≤ 0. Roda no `npm test` existente. |
| Criar | `frontend/src/components/AidealKineticLoader.jsx` (~130 linhas) | Componente default com as mesmas props; `import '../styles/aideal-kinetic-loader.css'`. Estrutura: root `.aideal-kinetic-loader[.is-exiting]` (`role="status"`, `aria-live="polite"`, `aria-atomic`, `data-loader-phase`) > sr-only > `.akl-backdrop` > `.akl-auroras` > `.akl-speed` > `.akl-perspective` > `.akl-stage` > `.akl-ring` + `.akl-strokes` (rotate −12°) > 3 × pincelada com os 4 wrappers. Tudo decorativo com `aria-hidden`. |
| Criar | `frontend/src/styles/aideal-kinetic-loader.css` (~330 linhas) | Variáveis `--akl-*`, layout, keyframes `akl-*`, `.is-exiting`, media ≤520px (palco `86vmin`), reduced motion. |
| Editar | `frontend/src/App.jsx` | Import e JSX: `AidealPartnershipLoader` → `AidealKineticLoader` (manter as mesmas props); controller: `minVisibleMs: 1700`, `exitMs: 720`. |
| Remover | `frontend/src/components/AidealPartnershipLoader.jsx` | Depois de confirmar com `rg "AidealPartnershipLoader\|AidealMark" frontend/src` que não há outros usos. |
| Editar (limpeza, último passo) | `frontend/src/styles/corporate.css` | Remover só regras/keyframes/blocos de media cujos seletores comecem com `.aideal-partnership-`, `.aideal-loader-` (com hífen depois de `loader`) ou `.aideal-mark-`, e os keyframes `aideal-loader-*` / `aideal-mark-*`. **Manter** `.aideal-sr-only` e `.aideal-loader` (spinner). Conferir com `rg` antes e depois e rodar o build. |

Sem mudanças em backend, DRE ou Fluxo de Caixa.

---

## 6. Ordem de execução e verificação

1. Testes do modelo (vermelho) → modelo (verde): `cd frontend && npm test`.
2. Componente + CSS com o símbolo **parado**; criar preview temporário `frontend/loader-preview.html` + `frontend/src/dev/loaderPreview.jsx` que renderiza o loader com `visible`, um `setInterval` de 3200ms para `scene.step`, e parâmetros `?exitAt=<ms>` (liga `exiting` e desmonta 720ms depois) e `?overlay=1` (logo PNG a 50% para conferir a silhueta). Ajustar a geometria.
3. Implementar intro → loop → saída → reduced motion, nessa ordem, conferindo cada uma no preview.
4. Trocar em `App.jsx`, remover o componente antigo e limpar o CSS.
5. `npm run build` sem erros nem avisos novos; `npm test` verde.
6. `npm run dev` e script Playwright avulso (em `/tmp`, fora do repo) abrindo `/loader-preview.html`:
   - viewports 1440×900, 2560×1080 e 390×844;
   - capturas em 100, 400, 800, 1300, 1700, 2100, 2900 e 4500ms; com `?exitAt=3000`, capturas em 3150, 3400 e 3800ms (a última deve estar sem o loader);
   - conferir nas imagens: símbolo ocupando ≥ 50% da menor dimensão, nenhum texto visível, pinceladas em trânsito com rastro, nada cortado no mobile;
   - `page.emulateMedia({ reducedMotion: 'reduce' })`: símbolo parado e visível, sem linhas de velocidade;
   - coletar `console` e `pageerror`: zero erros;
   - fluidez: contar frames de `requestAnimationFrame` por 3s durante o loop (esperado ≥ 170) e repetir com CPU throttling 4× via CDP (esperado ≥ 150, já que a animação é do compositor).
7. Teste real: abrir o app, entrar no Painel DRE (carga inicial) e confirmar que o loader entra, faz loop e sai revelando o painel sem salto; repetir numa exportação.
8. Apagar `loader-preview.html` e `src/dev/` antes de concluir; `git status` deve mostrar só os arquivos da seção 5.

### Riscos

- **Silhueta do símbolo:** o path acima é uma reconstrução; o ajuste com overlay do passo 2 é obrigatório.
- **`scaleX` grande nos fantasmas borrados** pode criar camadas grandes em 4K: se a contagem de frames cair, reduzir o blur para 12px e os fantasmas para 1 por pincelada.
- **Cargas muito rápidas:** com `minVisibleMs: 1700` + `exitMs: 720`, toda aparição dura no mínimo ~2,4s (hoje ~1,8s). Se o usuário achar longo, reduzir a intro proporcionalmente (escala 0.8 em todos os tempos de 4.1) e voltar `minVisibleMs` para 1400.
