# Relatório de Recursos para Hospedagem

**Aplicação:** AIDEAL GoFlowOS MVP  
**Data:** 2026-05-22  
**Objetivo:** estimar os recursos de hardware necessários para hospedar a aplicação com estabilidade, considerando backend, frontend, banco local, processamento de planilhas e crescimento operacional.

## Resumo executivo

A aplicação pode rodar em um servidor pequeno, mas não deve ser dimensionada como um site estático ou um CRUD simples. O ponto de maior consumo é o backend Python, especialmente nas rotinas de leitura, validação, consolidação e geração de arquivos Excel usando `pandas`, `xlrd` e `openpyxl`.

Para uso interno com baixa concorrência, a recomendação prática é:

| Perfil | CPU | RAM | Disco SSD | Uso indicado |
| --- | ---: | ---: | ---: | --- |
| Mínimo técnico | 1 vCPU | 2 GB | 20 GB | Demo, homologação, baixo volume, 1 processamento por vez |
| Recomendado produção MVP | 2 vCPU | 4 GB | 40 GB | Uso interno estável, painel + uploads moderados |
| Folga operacional | 4 vCPU | 8 GB | 80 GB | Arquivos maiores, mais usuários, 2+ processamentos concorrentes |

**Recomendação principal:** provisionar **2 vCPU, 4 GB RAM e 40 GB SSD** para a primeira operação em produção. Se o uso real incluir arquivos próximos de 50 MB, lotes grandes ou vários usuários processando simultaneamente, subir para **4 vCPU e 8 GB RAM**.

Este relatório dimensiona recursos de hardware. Custos em dinheiro dependem do provedor escolhido, região, tipo de instância, política de backup e contrato de suporte.

## Escopo analisado

O repositório contém:

- Backend FastAPI em Python, em `backend/app/main.py`.
- Frontend Vite/React, em `frontend/`.
- Banco SQLite em `data/aideal.db`.
- Templates oficiais de Excel em `templates/`.
- Diretórios operacionais para temporários, logs e arquivos gerados: `logs/tmp`, `logs` e `output`.

Não há Dockerfile, `docker-compose` ou configuração de Nginx versionada no repositório. O desenho abaixo assume um deploy simples em VM/VPS com proxy reverso.

## Evidências locais

Levantamento feito no workspace atual:

| Item | Medida observada |
| --- | ---: |
| Backend completo no repositório | 182 MB |
| Frontend com dependências locais | 150 MB |
| Build estático `frontend/dist` | 4.1 MB |
| Banco `data/aideal.db` | 5.1 MB |
| Templates oficiais | 2.1 MB |
| Arquivos gerados em `output` | 111 MB em 142 arquivos |
| Logs atuais | 236 KB |
| Base atual no SQLite | 4.622 lançamentos DRE + 5.202 movimentos de fluxo |
| Backend FastAPI parado, 1 worker | cerca de 110-115 MB RSS |
| Import frio do backend com pandas/openpyxl | cerca de 92-115 MB de pico |
| Build frontend de produção | JS gzipado 237 KB, CSS gzipado 17 KB |

Esses números representam o estado atual, não o limite máximo da aplicação. O pico real tende a acontecer durante upload, parse e geração de planilhas.

## Componentes de consumo

### Backend

O backend é o principal consumidor de recursos. Ele:

- recebe uploads de DRE e Fluxo de Caixa;
- salva arquivos temporários;
- lê planilhas Excel em memória;
- valida e transforma dados;
- grava registros no SQLite;
- gera novas planilhas `.xlsx` em `output`;
- serve downloads dos arquivos gerados.

Bibliotecas como `pandas` e `openpyxl` podem expandir bastante o consumo de RAM em relação ao tamanho original do arquivo. Um Excel de 10 MB pode consumir dezenas ou centenas de MB durante parse, dependendo de abas, células preenchidas, estilos e fórmulas.

### Frontend

O frontend de produção é leve. Depois do build, ele pode ser servido como arquivo estático por Nginx, Caddy, Apache ou pelo próprio servidor de aplicação, embora a opção com proxy estático seja mais robusta.

O bundle atual gerou um aviso de chunk acima de 500 KB antes de gzip, mas isso não muda de forma relevante o dimensionamento de hardware do servidor.

### Banco de dados

O banco atual é SQLite. Isso simplifica o deploy e reduz custo operacional, mas define alguns limites:

- bom para uso interno e baixa/moderada concorrência;
- sensível a muitas escritas simultâneas;
- exige backup do arquivo `data/aideal.db`;
- não é ideal para múltiplas instâncias de backend escrevendo no mesmo banco.

Para o MVP, SQLite é suficiente se houver uma única instância da aplicação e poucos processamentos simultâneos. Para operação com vários usuários ou concorrência maior, considerar migração futura para PostgreSQL.

### Disco

O disco precisa cobrir:

- código e ambiente Python;
- build estático do frontend;
- banco SQLite;
- templates;
- uploads temporários;
- arquivos gerados em `output`;
- logs;
- backups.

O diretório `output` já acumula 111 MB. Cada planilha gerada observada fica, em geral, na faixa de 0.8 MB a 1.2 MB. Sem política de retenção, esse diretório tende a crescer continuamente.

## Estimativa de capacidade por perfil

### 1. Mínimo técnico

**Recursos:** 1 vCPU, 2 GB RAM, 20 GB SSD.

Serve para:

- demonstração;
- homologação;
- um usuário por vez;
- arquivos pequenos e médios;
- baixo volume de gerações.

Riscos:

- processamento de Excel pode deixar a API lenta;
- concorrência baixa;
- pouca margem para uploads grandes;
- disco pode exigir limpeza frequente de `output`.

### 2. Produção MVP recomendada

**Recursos:** 2 vCPU, 4 GB RAM, 40 GB SSD.

Serve para:

- uso interno regular;
- painéis DRE e Fluxo de Caixa;
- ingestão mensal;
- geração de planilhas;
- um ou dois processamentos leves concorrentes, dependendo do tamanho dos arquivos.

Configuração sugerida:

- 1 instância de backend;
- 1 a 2 workers Uvicorn/Gunicorn;
- proxy reverso servindo `frontend/dist`;
- limite de upload aplicado no proxy e no backend;
- backup diário do SQLite;
- limpeza programada de arquivos antigos em `output`.

Este é o melhor ponto de partida para produção: custo moderado, boa folga e pouca complexidade.

### 3. Folga operacional

**Recursos:** 4 vCPU, 8 GB RAM, 80 GB SSD.

Serve para:

- arquivos maiores;
- lotes com muitos extratos;
- mais usuários usando painéis durante processamento;
- 2 ou mais processamentos simultâneos;
- retenção maior de arquivos gerados;
- margem para migração futura para PostgreSQL local ou containerizado.

Esse perfil reduz risco de lentidão durante parse e escrita de planilhas.

## Fórmula prática de dimensionamento

Para estimar RAM:

```text
RAM ~= sistema operacional
     + proxy reverso
     + workers_backend * 150 MB
     + processamentos_concorrentes * (300 MB + 4x a 8x o maior arquivo Excel)
     + cache/folga operacional
```

Exemplo conservador:

- SO + serviços básicos: 600 MB
- 2 workers backend: 300 MB
- 1 processamento de arquivo de 50 MB: 500 MB a 700 MB
- margem operacional: 1 GB+

Resultado: 2 GB pode funcionar, mas 4 GB é mais seguro.

Para estimar disco temporário:

```text
temp ~= max_files_per_batch * max_upload_size_mb * processamentos_concorrentes * 2
```

Com a configuração atual:

- `max_upload_size_mb = 50`
- `max_files_per_batch = 20`

Um lote teórico completo pode exigir até 1 GB apenas de entrada temporária por processamento, antes de considerar arquivos gerados e overhead. Por isso, 40 GB SSD e uma recomendação mais confortável que 20 GB.

## Configuração de deploy recomendada

Topologia simples:

```text
Internet
  -> Nginx/Caddy
      -> frontend/dist
      -> /api para FastAPI
          -> SQLite em data/aideal.db
          -> templates/
          -> logs/tmp
          -> output/
```

Processos sugeridos:

- Frontend: build estático servido pelo proxy.
- Backend: FastAPI com Uvicorn/Gunicorn.
- Banco: SQLite local em disco SSD.
- Backup: cópia diária de `data/aideal.db` e, se necessário, de `output`.

Parâmetros operacionais:

| Parâmetro | Valor inicial recomendado |
| --- | ---: |
| Workers backend | 1 ou 2 |
| Timeout de request para processamento | 120s a 300s |
| Limite de upload no proxy | 50 MB por arquivo, alinhado ao backend |
| Retenção de arquivos em `output` | 30 a 90 dias |
| Backup SQLite | Diário, com retenção mínima de 7 a 30 dias |
| Monitoramento de disco | alerta em 70% e 85% |

## Riscos e cuidados

1. **Upload lido inteiro em memória**  
   O backend salva uploads usando leitura completa do arquivo antes de escrever no temporário. Isso é simples, mas aumenta pico de RAM para arquivos grandes ou uploads concorrentes.

2. **Limites configurados precisam ser aplicados**  
   A configuração define `max_upload_size_mb = 50` e `max_files_per_batch = 20`, mas a proteção deve existir também no proxy reverso e idealmente ser validada explicitamente no backend.

3. **SQLite limita escala horizontal**  
   Não subir várias instâncias escrevendo no mesmo SQLite. Para escala real com várias instâncias, migrar para PostgreSQL.

4. **Processamento de Excel e CPU-bound**  
   Durante parse/geração de planilhas, um worker pode ocupar CPU e deixar requests interativos mais lentos. Para crescimento, considerar fila de jobs.

5. **`output` cresce continuamente**  
   Sem limpeza automática, os arquivos gerados acumulam. Hoje já existem 111 MB. Em operação, definir retenção e backup seletivo.

## Recomendação final

Para hospedar corretamente a aplicação hoje, usar:

```text
2 vCPU
4 GB RAM
40 GB SSD
1 instância backend
1-2 workers
proxy reverso servindo frontend estático
backup diário do SQLite
limpeza periódica de output/
```

Para uma operação com arquivos grandes, lotes frequentes ou mais usuários simultâneos:

```text
4 vCPU
8 GB RAM
80 GB SSD
fila de processamento para Excel
monitoramento de CPU/RAM/disco
planejamento de migração para PostgreSQL
```

## Próximo passo recomendado

Executar um teste de carga com dados reais:

- 1 usuário abrindo painéis;
- 1 upload DRE;
- 1 lote de Fluxo de Caixa;
- 1 geração de DRE;
- 1 geração de Fluxo de Caixa;
- repetir com 2 processamentos simultâneos.

Durante o teste, medir:

- pico de RAM do processo Python;
- CPU durante parse e geração;
- tempo de resposta dos painéis;
- tamanho dos temporários;
- crescimento de `output`;
- ocorrência de locks no SQLite.

Com esses dados, o dimensionamento deixa de ser estimativa e vira capacidade operacional medida.
