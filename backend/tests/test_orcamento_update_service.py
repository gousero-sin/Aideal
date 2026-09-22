from datetime import datetime, timezone

import pytest

from app.orcamento.exceptions import InvalidOrcamentoInputError
from app.orcamento.service import create_orcamento_service


def test_revisao_zero_modalidades_e_historico(tmp_path):
    service = create_orcamento_service(tmp_path / 'orc.db')
    budget = service.create_orcamento(
        {'contratante': 'Cliente', 'modalidade': 'm²'}, autor_user_id='u1'
    )
    assert budget.revisao_atual.numero == 0
    assert budget.to_dict()['codigo_revisao'] == 'ORC-0001-R0'
    service.update_cabecalho(
        budget.revisao_atual.id, {'escopo': 'Alterado'}, responsavel_user_id='u2'
    )
    history = service.list_historico(budget.id)
    assert history[-1]['responsavel_user_id'] == 'u2'
    assert history[-1]['antes']['escopo'] == ''
    assert history[-1]['depois']['escopo'] == 'Alterado'
    assert service.create_revisao(budget.id, {}, autor_user_id='u1').numero == 1


def test_catalogo_persiste_entre_instancias(tmp_path):
    path = tmp_path / 'orc.db'
    service = create_orcamento_service(path)
    data = {
        'funcoes': [{'nome': 'Pintor', 'salario_real': 2200}],
        'itens': [{'nome': 'Almoço', 'valor_unitario': 25}],
        'custo_administrativo_diario': 200,
    }
    service.save_catalogo(data, responsavel_user_id='u1')
    assert create_orcamento_service(path).get_catalogo() == data


def test_catalogo_mantem_historico_versionado_com_vigencia(tmp_path):
    path = tmp_path / 'orc.db'
    instantes = iter([
        datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc),
        datetime(2026, 9, 15, 9, 30, tzinfo=timezone.utc),
    ])
    service = create_orcamento_service(path, clock=lambda: next(instantes))
    primeira = {'funcoes': [{'nome': 'Pintor', 'salario_real': 2200}], 'itens': [],
                'custo_administrativo_diario': 100}
    segunda = {'funcoes': [{'nome': 'Pintor', 'salario_real': 2500}], 'itens': [],
               'custo_administrativo_diario': 120}

    service.save_catalogo(primeira, responsavel_user_id='u1')
    service.save_catalogo(segunda, responsavel_user_id='u2')
    historico = service.list_catalogo_historico()

    assert [item['versao'] for item in historico] == [1, 2]
    assert historico[0]['payload'] == primeira
    assert historico[0]['vigente_desde'] == '2026-09-14T12:00:00+00:00'
    assert historico[0]['vigente_ate'] == '2026-09-15T09:30:00+00:00'
    assert historico[1]['payload'] == segunda
    assert historico[1]['responsavel_user_id'] == 'u2'
    assert historico[1]['vigente_ate'] is None
    assert create_orcamento_service(path).list_catalogo_historico() == historico


def test_catalogo_reaproveita_valores_salvos_sem_substituir_padrao_explicito(tmp_path):
    service = create_orcamento_service(tmp_path / 'orc.db')
    budget = service.create_orcamento({'contratante': 'Cliente'}, autor_user_id='u1')
    dfp = budget.revisao_atual.to_dict()['dfp']
    dfp['mao_de_obra_direta']['items'] = [{'id': 'p', 'label': 'Pintor', 'salary_real': 2300}]
    dfp['equipamentos']['items'] = [{'id': 'c', 'label': 'Compressor', 'unit_cost': 800}]
    service.update_cabecalho(budget.revisao_atual.id, {'dfp': dfp}, responsavel_user_id='u1')
    catalog = service.get_catalogo()
    assert {'nome': 'Pintor', 'salario_real': 2300} in catalog['funcoes']
    assert {'nome': 'Compressor', 'valor_unitario': 800} in catalog['itens']
    service.save_catalogo(
        {'funcoes': [{'nome': 'Pintor', 'salario_real': 2500}]}, responsavel_user_id='u1'
    )
    assert service.get_catalogo()['funcoes'] == [{'nome': 'Pintor', 'salario_real': 2500}]


def test_catalogo_uses_most_recent_edit_not_most_recent_creation(tmp_path):
    from datetime import timedelta
    start = datetime(2026, 9, 16, tzinfo=timezone.utc)
    instantes = iter(start + timedelta(minutes=index) for index in range(4))
    service = create_orcamento_service(tmp_path / 'orc.db', clock=lambda: next(instantes))
    older = service.create_orcamento({'contratante': 'Antigo'}, autor_user_id='u1')
    newer = service.create_orcamento({'contratante': 'Novo'}, autor_user_id='u1')
    for budget, salary in ((newer, 2200), (older, 3000)):
        dfp = budget.revisao_atual.to_dict()['dfp']
        dfp['mao_de_obra_direta']['items'] = [{'id': 'p', 'label': 'Pintor', 'salary_real': salary}]
        service.update_cabecalho(budget.revisao_atual.id, {'dfp': dfp}, responsavel_user_id='u1')
    assert service.get_catalogo()['funcoes'] == [{'nome': 'Pintor', 'salario_real': 3000}]


def test_invalid_combined_cost_is_not_persisted(tmp_path):
    service = create_orcamento_service(tmp_path / 'orc.db')
    budget = service.create_orcamento({'contratante': 'Cliente'}, autor_user_id='u1')
    dfp = budget.revisao_atual.to_dict()['dfp']
    dfp['equipamentos']['items'] = [
        {'id': 'e', 'label': 'Equipamento', 'quantity': 10**13, 'unit_cost': 10**13}]
    history = service.list_historico(budget.id)
    with pytest.raises(InvalidOrcamentoInputError, match='limite'):
        service.update_cabecalho(budget.revisao_atual.id, {'dfp': dfp}, responsavel_user_id='u1')
    assert service.get_orcamento(budget.id) == budget
    assert service.list_historico(budget.id) == history


@pytest.mark.parametrize('data', [
    {'funcoes': [{'nome': 'Pintor', 'salario_real': -1}]},
    {'itens': [{'nome': 'Almoço', 'valor_unitario': float('nan')}]},
    {'funcoes': [{'nome': '', 'salario_real': 100}]},
    {'funcoes': [{'nome': 'Pintor', 'salario_real': 100}, {'nome': 'pintor', 'salario_real': 200}]},
    {'custo_administrativo_diario': True},
    {'custo_administrativo_diario': 10**400},
    {'campo_desconhecido': 1},
])
def test_catalogo_rejeita_dados_invalidos_sem_sobrescrever(tmp_path, data):
    service = create_orcamento_service(tmp_path / 'orc.db')
    before = service.get_catalogo()
    history_before = service.list_catalogo_historico()
    with pytest.raises(InvalidOrcamentoInputError):
        service.save_catalogo(data, responsavel_user_id='u1')
    assert service.get_catalogo() == before
    assert service.list_catalogo_historico() == history_before


def test_edicao_dfp_persiste_e_mantem_historico_apos_reabrir(tmp_path):
    path = tmp_path / 'orc.db'
    service = create_orcamento_service(path)
    budget = service.create_orcamento(
        {'contratante': 'Cliente', 'modalidade': 'Rotina'}, autor_user_id='u1'
    )
    dfp = budget.revisao_atual.to_dict()['dfp']
    dfp['metadata']['titulo'] = 'Novo título'
    service.update_cabecalho(budget.revisao_atual.id, {'dfp': dfp}, responsavel_user_id='u2')
    restarted = create_orcamento_service(path)
    assert restarted.get_revisao(budget.revisao_atual.id).dfp['metadata']['titulo'] == 'Novo título'
    history = restarted.list_historico(budget.id)
    assert len(history) == 2
    assert history[-1]['depois']['dfp']['metadata']['titulo'] == 'Novo título'


@pytest.mark.parametrize('operation', ['create', 'revision'])
def test_service_rejeita_campos_desconhecidos(operation, tmp_path):
    service = create_orcamento_service(tmp_path / 'orc.db')
    if operation == 'create':
        with pytest.raises(InvalidOrcamentoInputError, match='desconhecidos'):
            service.create_orcamento({'contratante': 'Cliente', 'intruso': 1}, autor_user_id='u1')
        return
    budget = service.create_orcamento({'contratante': 'Cliente'}, autor_user_id='u1')
    with pytest.raises(InvalidOrcamentoInputError, match='desconhecidos'):
        service.create_revisao(budget.id, {'intruso': 1}, autor_user_id='u1')


def test_service_rejeita_identidades_vazias(tmp_path):
    service = create_orcamento_service(tmp_path / 'orc.db')
    with pytest.raises(InvalidOrcamentoInputError, match='autor_user_id'):
        service.create_orcamento({'contratante': 'Cliente'}, autor_user_id=' ')
