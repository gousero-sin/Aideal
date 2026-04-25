# goflow-core

Nucleo reutilizavel do GoFlowOS para projetos React, incluindo os elementos genericos do visual GoFlow:

- `Liquid Glass` reutilizavel
- `Liquid Intelligence Loader` com fases
- `DB Connection Loader` animado
- `Skeleton shimmer`
- Flow engine (`useFlowState`) e tema (`ThemeProvider`)
- Componentes HydroUI (`FlowContainer`, `CurrentButton`, etc.)

## Instalacao

```bash
npm install goflow-core
```

Ou instalacao local via pacote `.tgz`:

```bash
npm install ./goflow-core-1.1.0.tgz
```

## Import dos estilos

Se o bundler nao injetar automaticamente o CSS da lib, importe manualmente:

```js
import 'goflow-core/styles.css';
```

## Uso rapido (Liquid Loader + controle de fluxo)

```jsx
import {
  ThemeProvider,
  LiquidIntelligenceLoader,
  useLiquidLoaderController,
  CurrentButton
} from 'goflow-core';

function Example() {
  const loader = useLiquidLoaderController();

  const runTask = async () => {
    loader.show(0);
    try {
      await new Promise((resolve) => setTimeout(resolve, 2400));
    } finally {
      loader.hide();
    }
  };

  return (
    <ThemeProvider>
      <CurrentButton onClick={runTask}>Executar</CurrentButton>
      <LiquidIntelligenceLoader
        visible={loader.visible}
        exiting={loader.exiting}
        scene={loader.scene}
      />
    </ThemeProvider>
  );
}
```

## Uso rapido (Liquid Glass + Skeleton)

```jsx
import { LiquidGlassCard, SkeletonText, SkeletonChart } from 'goflow-core';

function CardLoading() {
  return (
    <LiquidGlassCard>
      <SkeletonText style={{ width: 180, marginBottom: 12 }} />
      <SkeletonChart height={160} />
    </LiquidGlassCard>
  );
}
```

## Uso rapido (DB Connection Loader)

```jsx
import { LiquidDbConnectionLoader } from 'goflow-core';

function ConnectScreen() {
  return (
    <LiquidDbConnectionLoader
      title="Conectando ao banco..."
      subtitle="Carregando dados financeiros"
      badges={['Real-time SQL', 'Conexao segura', 'Sincronizando']}
    />
  );
}
```
