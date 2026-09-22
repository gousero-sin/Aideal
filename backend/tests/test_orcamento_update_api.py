"""HTTP integration for the September budget update, with isolated databases."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    client = TestClient(app)
    response = client.post('/api/auth/login', json={
        'username': 'Eduardo', 'password': 'senha-admin-teste',
    })
    assert response.status_code == 200
    client.headers['X-CSRF-Token'] = response.json()['csrf_token']
    return client


@pytest.mark.parametrize('modalidade', ['HH', 'Spot', 'Rotina', 'm²'])
def test_modalidades_novas_e_revisao_zero(client, modalidade):
    response = client.post('/api/orcamento/orcamentos', json={
        'contratante': 'Teste atualização', 'modalidade': modalidade,
    })
    assert response.status_code == 201, response.text
    assert response.json()['revisao_atual']['numero'] == 0
    assert response.json()['codigo_revisao'] == 'ORC-0001-R0'
    assert response.json()['revisao_atual']['dfp']['metadata']['codigo_dfp'] == 'ORC-0001-R0'


def test_schema_accepts_numeric_query_versions(client):
    for version in (1, 2):
        assert client.get(f'/api/orcamento/schema?calculation_version={version}').status_code == 200
    assert client.get('/api/orcamento/schema?calculation_version=3').status_code == 422


@pytest.mark.parametrize('days', [True, False, 1.5, -1, 0])
def test_prazo_requires_positive_integer_before_coercion(client, days):
    response = client.post('/api/orcamento/orcamentos', json={
        'contratante': 'Prazo inválido', 'prazo_execucao_dias': days,
    })
    assert response.status_code == 422


def test_revision_patch_rejects_boolean_days_without_mutation(client):
    created = client.post('/api/orcamento/orcamentos', json={'contratante': 'Cliente'}).json()
    revision = created['revisao_atual']
    response = client.patch(
        f"/api/orcamento/revisoes/{revision['id']}", json={'prazo_execucao_dias': True}
    )
    assert response.status_code == 422
    saved = client.get(f"/api/orcamento/orcamentos/{created['id']}").json()
    assert saved['revisao_atual']['prazo_execucao_dias'] is None


def test_catalogo_salvo_reaberto_e_protegido(client):
    payload = {'funcoes': [{'nome': 'Pintor', 'salario_real': 2200}],
               'itens': [], 'custo_administrativo_diario': 180}
    response = client.post('/api/orcamento/catalogo', json=payload)
    assert response.status_code == 200, response.text
    assert client.get('/api/orcamento/catalogo').json()['funcoes'][0]['salario_real'] == 2200
    historico = client.get('/api/orcamento/catalogo/historico')
    assert historico.status_code == 200, historico.text
    assert historico.json()['historico'][-1]['payload'] == payload
    assert historico.json()['historico'][-1]['vigente_ate'] is None
    client.headers.pop('X-CSRF-Token')
    assert client.post('/api/orcamento/catalogo', json=payload).status_code == 403
    assert TestClient(app).get('/api/orcamento/catalogo').status_code == 401
    assert TestClient(app).get('/api/orcamento/catalogo/historico').status_code == 401


def test_historico_disponivel_para_orcamento_existente(client):
    created = client.post('/api/orcamento/orcamentos', json={'contratante': 'Teste'}).json()
    response = client.get(f"/api/orcamento/orcamentos/{created['id']}/historico")
    assert response.status_code == 200, response.text
    assert response.json()['historico']
    assert client.get('/api/orcamento/orcamentos/ausente/historico').status_code == 404


@pytest.mark.parametrize('formato,signature', [('pdf', b'%PDF'), ('docx', b'PK')])
def test_exportacao_da_revisao_salva(client, formato, signature):
    created = client.post('/api/orcamento/orcamentos', json={'contratante': 'Teste'}).json()
    revision_id = created['revisao_atual']['id']
    response = client.get(f'/api/orcamento/revisoes/{revision_id}/exportar?formato={formato}')
    assert response.status_code == 200, response.text
    assert response.content.startswith(signature)
    assert f'ORC-0001-R0.{formato}' in response.headers['content-disposition']
    assert response.headers['cache-control'] == 'no-store'
    assert TestClient(app).get(f'/api/orcamento/revisoes/{revision_id}/exportar').status_code == 401


def test_exportacao_rejeita_formato_e_revisao_inexistentes(client):
    assert client.get('/api/orcamento/revisoes/ausente/exportar?formato=html').status_code == 422
    assert client.get('/api/orcamento/revisoes/ausente/exportar?formato=pdf').status_code == 404
