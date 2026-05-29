# Etapa 1 — Checklist de Fundação e Arquitetura

Data de verificação: 31/03/2026

## Objetivo
Confirmar o estado real da Etapa 1 e consolidar melhorias necessárias antes da Etapa 2.

## Itens concluídos
- Estrutura base separada em backend (`FastAPI`) e frontend (`React + Vite`).
- Contratos de dados definidos para DRE e Fluxo de Caixa.
- Configurações de mapeamento inicial versionadas em JSON.
- Validação estrutural de entrada implementada (arquivo único e lote no Fluxo de Caixa).
- UI inicial operacional para seleção de fluxo, upload e validação.
- Baseline documental de etapas gerado em PDF.

## Melhorias aplicadas nesta revisão
- Criação de módulo de baseline estrutural de templates:
  - `backend/app/templates/integrity.py`
  - `scripts/template_integrity.py`
- Endpoint de status de prontidão da Etapa 1:
  - `GET /api/etapa1/status`
- Ajuste da UI para direção corporativa AIDEAL (fundo claro, cards brancos, bordas discretas, azul principal como interação).
- Adoção de tokens de tema corporativo:
  - `frontend/src/styles/corporate.css`
- Automação no setup para gerar baseline padrão dos templates:
  - `scripts/subir-producao.sh`

## Pendências intencionais (Etapa 2+)
- Mapeamento final de áreas atualizáveis dos templates (DRE/Fluxo).
- Escrita de dados final no template com regras completas de transformação.
- Consolidação de aliases completos de classificação para Fluxo de Caixa.
- Exportação final de arquivos processados.

## Critério de saída da Etapa 1
Etapa 1 considerada concluída quando:
- API de validação responde corretamente para arquivos de exemplo.
- Baselines estruturais dos templates oficiais estão capturados.
- Frontend operacional de validação está aderente ao visual corporativo base.
- Scripts de setup/dev permitem iniciar ambiente sem passos manuais ocultos.
