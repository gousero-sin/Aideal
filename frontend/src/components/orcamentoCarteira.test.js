import test from 'node:test';
import assert from 'node:assert/strict';

import { composicaoDoPreco, formatarValorCompacto, funilCarteira } from './orcamentoModel.js';

test('composição do preço trata impostos como o que sobra depois dos custos', () => {
  const partes = composicaoDoPreco({
    custosDiretosTotal: 700, custosIndiretosTotal: 100, lucroTotal: 100, precoTotalFaturamento: 1000,
  });
  assert.deepEqual(partes.map(({ key, valor }) => [key, valor]), [
    ['diretos', 700], ['indiretos', 100], ['lucro', 100], ['impostos', 100],
  ]);
  assert.ok(Math.abs(partes.reduce((acc, parte) => acc + parte.share, 0) - 1) < 1e-9);
});

test('composição do preço omite partes zeradas e orçamento sem preço', () => {
  assert.deepEqual(composicaoDoPreco({ precoTotalFaturamento: 0, custosDiretosTotal: 10 }), []);
  assert.deepEqual(composicaoDoPreco(null), []);
  const partes = composicaoDoPreco({ custosDiretosTotal: 500, precoTotalFaturamento: 500 });
  assert.deepEqual(partes.map(({ key }) => key), ['diretos']);
});

test('funil soma valor por etapa e deixa inativos de fora', () => {
  const orcamento = (situacao, preco) => ({ revisaoAtual: { situacao }, dfpSummary: { precoTotalFaturamento: preco } });
  const funil = funilCarteira([
    orcamento('rascunho', 100), orcamento('em_revisao', 200), orcamento('pronto_para_proposta', 300),
    orcamento('emitido', 400), orcamento('inativo', 9999),
  ]);
  assert.deepEqual(funil.map(({ filtro, quantidade, valor }) => [filtro, quantidade, valor]), [
    ['em_curso', 2, 300], ['pronto_para_proposta', 1, 300], ['emitido', 1, 400],
  ]);
  assert.equal(funil[2].share, 0.4);
  assert.deepEqual(funilCarteira([]).map(({ share }) => share), [0, 0, 0]);
});

test('valor compacto abrevia milhares e milhões em pt-BR', () => {
  assert.equal(formatarValorCompacto(1400160.57), 'R$ 1,4 mi');
  assert.equal(formatarValorCompacto(745617.4), 'R$ 746 mil');
  assert.equal(formatarValorCompacto(12500), 'R$ 12,5 mil');
  assert.equal(formatarValorCompacto(980), 'R$ 980');
  assert.equal(formatarValorCompacto(undefined), 'R$ 0');
});
