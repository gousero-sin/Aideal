import test from 'node:test';
import assert from 'node:assert/strict';
import {
  changedSummaryEntries,
  isEditorDirty,
  isSaveShortcut,
  isXlsxFile,
  pickActiveSection,
  rebaseIfClean,
  serializeEditorForm,
  shouldBlockEnterSubmit,
} from './orcamento/editor/editorState.js';

test('formulário igual ao snapshot não fica sujo, mesmo com chaves em outra ordem', () => {
  const baseline = serializeEditorForm({ a: 1, dfp: { x: [1, 2], y: 'b' } });
  assert.equal(isEditorDirty(baseline, { dfp: { y: 'b', x: [1, 2] }, a: 1 }), false);
  assert.equal(isEditorDirty(baseline, { a: 2, dfp: { x: [1, 2], y: 'b' } }), true);
});

test('editar e desfazer volta ao estado limpo', () => {
  const form = { escopo: 'Pintura', dfp: { items: [{ id: 'a', quantity: 1 }] } };
  const baseline = serializeEditorForm(form);
  const edited = { ...form, escopo: 'Pintura e lavagem' };
  assert.equal(isEditorDirty(baseline, edited), true);
  assert.equal(isEditorDirty(baseline, { ...edited, escopo: 'Pintura' }), false);
});

test('semeadura automática do HH rebaseia só quando o formulário estava limpo', () => {
  const form = { modalidade: 'HH', dfp: {} };
  const seeded = { ...form, dfp: { hh: { meses: 12 } } };
  const baseline = serializeEditorForm(form);
  assert.equal(rebaseIfClean(baseline, form, seeded), serializeEditorForm(seeded));
  assert.equal(isEditorDirty(rebaseIfClean(baseline, form, seeded), seeded), false);

  const userChanged = { ...form, escopo: 'novo' };
  assert.equal(rebaseIfClean(baseline, userChanged, { ...userChanged, dfp: seeded.dfp }), baseline);
});

test('seção ativa segue o limiar e ativa a última no fim da rolagem', () => {
  const sections = [{ id: 'a', top: -400 }, { id: 'b', top: 40 }, { id: 'c', top: 500 }];
  const base = { sections, clientHeight: 600, scrollHeight: 2000 };
  assert.equal(pickActiveSection({ ...base, scrollTop: 300 }), 'b');
  // A última seção é curta e nunca chega ao topo: no fim da rolagem ela é a ativa.
  assert.equal(pickActiveSection({ ...base, scrollTop: 1400 }), 'c');
  assert.equal(pickActiveSection({ ...base, sections: [{ id: 'a', top: 300 }], scrollTop: 0 }), 'a');
  assert.equal(pickActiveSection({ ...base, sections: [] }), null);
});

test('conteúdo sem rolagem não força a última seção', () => {
  const sections = [{ id: 'a', top: 0 }, { id: 'b', top: 400 }];
  assert.equal(pickActiveSection({ sections, scrollTop: 0, clientHeight: 800, scrollHeight: 800 }), 'a');
});

test('atalho de salvar aceita Ctrl+S e Cmd+S', () => {
  assert.equal(isSaveShortcut({ ctrlKey: true, key: 's' }), true);
  assert.equal(isSaveShortcut({ metaKey: true, key: 'S' }), true);
  assert.equal(isSaveShortcut({ key: 's' }), false);
  assert.equal(isSaveShortcut({ ctrlKey: true, altKey: true, key: 's' }), false);
});

test('Enter em campo não envia o formulário, mas botões e áreas de texto seguem normais', () => {
  const enter = (tagName, type) => ({ key: 'Enter', target: { tagName, type } });
  assert.equal(shouldBlockEnterSubmit(enter('INPUT', 'number')), true);
  assert.equal(shouldBlockEnterSubmit(enter('INPUT', 'text')), true);
  assert.equal(shouldBlockEnterSubmit(enter('INPUT', 'checkbox')), false);
  assert.equal(shouldBlockEnterSubmit(enter('TEXTAREA')), false);
  assert.equal(shouldBlockEnterSubmit(enter('BUTTON', 'submit')), false);
  assert.equal(shouldBlockEnterSubmit({ ...enter('INPUT', 'text'), isComposing: true }), false);
  assert.equal(shouldBlockEnterSubmit({ key: 'a', target: { tagName: 'INPUT' } }), false);
});

test('importação HH aceita só .xlsx', () => {
  assert.equal(isXlsxFile({ name: 'Composição.XLSX' }), true);
  assert.equal(isXlsxFile({ name: 'composicao.xls' }), false);
  assert.equal(isXlsxFile(null), false);
});

test('resumo destaca só valores numéricos que mudaram', () => {
  const before = [['Custos diretos', 100], ['Impostos', '5%'], ['Lucro', 10]];
  const after = [['Custos diretos', 150], ['Impostos', '6%'], ['Lucro', 10]];
  assert.deepEqual(changedSummaryEntries(before, after), [['Custos diretos', 50]]);
  assert.deepEqual(changedSummaryEntries(null, after), []);
});
