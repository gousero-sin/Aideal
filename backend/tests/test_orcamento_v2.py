from copy import deepcopy

import pytest

from app.orcamento.dfp import build_default_dfp_snapshot, compute_dfp_summary, normalize_dfp_payload
from app.orcamento.exceptions import InvalidOrcamentoInputError


def test_new_v2_rows_do_not_infer_execution_days_from_header_deadline():
    dfp = build_default_dfp_snapshot({'prazo_execucao_dias': 12}, calculation_version=2)
    assert dfp['metadata']['quantidade_dias_semana'] == 0
    assert dfp['mao_de_obra_direta']['items'][0]['worked_days'] is None


def scenario():
    dfp = build_default_dfp_snapshot(calculation_version=2)
    dfp['metadata'].update(quantidade_dias_semana=10, quantidade_sabado=2, quantidade_domingo=1,
                           horas_semana=8, horas_sabado=4, horas_domingo=4,
                           semana_fator=1.5, sabado_fator=1.7, domingo_fator=2)
    dfp['mao_de_obra_direta']['items'] = [{
        'id': 'pintor', 'label': 'Pintor', 'quantity': 2, 'salary_real': 2200,
        'worked_days': 10, 'saturday_days': 0, 'sunday_days': 0, 'mobilization_days': 1,
        'overtime_week_hours': 2, 'overtime_saturday_hours': 0, 'overtime_sunday_hours': 0,
    }]
    return dfp


def test_v2_zero_days_override_and_hours_are_derived():
    dfp = scenario()
    original = deepcopy(dfp)
    normalized = normalize_dfp_payload(dfp)
    row = normalized['mao_de_obra_direta']['items'][0]
    assert row['worked_hours'] == 176
    assert row['hourly_rate'] == 10
    assert compute_dfp_summary(dfp)['mao_de_obra_direta_total'] == 1820
    assert dfp == original


def test_v2_null_days_inherit_metadata_and_food_uses_person_days():
    dfp = scenario()
    row = dfp['mao_de_obra_direta']['items'][0]
    row.update(worked_days=None, saturday_days=None, sunday_days=None)
    dfp['alimentacao']['items'][0]['unit_cost'] = 25
    summary = compute_dfp_summary(dfp)
    assert summary['alimentacao_total'] == 700  # 2 people * (10+2+1+1) * 25
    assert summary['mao_de_obra_direta_total'] == 2060


def test_v2_admin_discount_and_targeted_additional():
    dfp = scenario()
    dfp['mao_de_obra_direta']['adjustments'] = [
        {'id': 'periculosidade', 'label': 'Periculosidade', 'labor_item_id': 'pintor',
         'quantity': 1, 'percent': 30, 'base': 'salary'}]
    dfp['mao_de_obra_direta']['social_charges_percent'] = 50
    dfp['mao_de_obra_direta']['discount_percent'] = 10
    dfp['custos_administrativos'].update(daily_cost=100, days=10, considered_percent=50,
                                       multiplier=2, discount_percent=10)
    summary = compute_dfp_summary(dfp)
    assert summary['mao_de_obra_direta_total'] == 2813.4
    assert summary['custos_administrativos_total'] == 900


def test_v2_rejects_fractional_people_and_excess_additional():
    dfp = scenario()
    dfp['mao_de_obra_direta']['items'][0]['quantity'] = 1.5
    with pytest.raises(InvalidOrcamentoInputError):
        normalize_dfp_payload(dfp)


def test_v2_header_metadata_survives_normalization():
    dfp = scenario()
    dfp['metadata'].update(data_inicio='2026-09-14', data_inicio_na=False,
                           contratante_override='Cliente editado')
    assert normalize_dfp_payload(dfp)['metadata']['data_inicio'] == '2026-09-14'
    assert normalize_dfp_payload(dfp)['metadata']['contratante_override'] == 'Cliente editado'


def test_v2_data_inicio_aceita_literal_na():
    dfp = scenario()
    dfp['metadata']['data_inicio'] = 'N/A'
    normalized = normalize_dfp_payload(dfp)
    assert normalized['metadata']['data_inicio_na'] is True
    assert normalized['metadata']['data_inicio'] is None


def test_v2_rejeita_ids_duplicados_em_linhas_dinamicas():
    dfp = scenario()
    dfp['equipamentos']['items'] = [
        {'id': 'duplicado', 'label': 'A', 'quantity': 1, 'unit_cost': 1},
        {'id': 'duplicado', 'label': 'B', 'quantity': 1, 'unit_cost': 1},
    ]
    with pytest.raises(InvalidOrcamentoInputError, match='identificadores duplicados'):
        normalize_dfp_payload(dfp)


@pytest.mark.parametrize('field,value,match', [
    ('id', '', r'\.id é obrigatório'),
    ('label', '   ', r'\.label é obrigatório'),
])
def test_v2_rejeita_identidade_vazia_em_linha_dinamica(field, value, match):
    dfp = scenario()
    dfp['equipamentos']['items'] = [
        {'id': 'custom', 'label': 'Equipamento customizado', 'quantity': 1, 'unit_cost': 1},
    ]
    dfp['equipamentos']['items'][0][field] = value
    with pytest.raises(InvalidOrcamentoInputError, match=match):
        normalize_dfp_payload(dfp)


def test_v2_rejeita_rotulos_duplicados_em_linhas_dinamicas():
    dfp = scenario()
    dfp['equipamentos']['items'] = [
        {'id': 'a', 'label': 'Duplicado', 'quantity': 1, 'unit_cost': 1},
        {'id': 'b', 'label': ' duplicado ', 'quantity': 1, 'unit_cost': 1},
    ]
    with pytest.raises(InvalidOrcamentoInputError, match='rótulos duplicados'):
        normalize_dfp_payload(dfp)


def test_v2_rejeita_identidade_vazia_em_adicional_dinamico():
    dfp = scenario()
    dfp['mao_de_obra_direta']['adjustments'] = [
        {'id': '', 'label': 'Adicional', 'percent': 10, 'quantity': 0},
    ]
    with pytest.raises(InvalidOrcamentoInputError, match=r'\.id é obrigatório'):
        normalize_dfp_payload(dfp)


def test_v2_tax_rows_are_not_recreated_after_deletion():
    dfp = scenario()
    dfp['impostos']['items'] = [{'id': 'iss', 'label': 'ISS', 'aliquot_percent': 5}]
    assert normalize_dfp_payload(dfp)['impostos']['items'] == [
        {'id': 'iss', 'label': 'ISS', 'aliquot_percent': 5, 'notes': ''}]


@pytest.mark.parametrize('section', ['custos_administrativos', 'bdi'])
def test_v2_rejects_items_in_scalar_sections(section):
    dfp = scenario()
    dfp[section]['items'] = []
    with pytest.raises(InvalidOrcamentoInputError, match='items'):
        normalize_dfp_payload(dfp)


def test_v2_rejects_invalid_tax_identity_before_defaults():
    dfp = scenario()
    dfp['impostos']['items'] = [{'id': '', 'label': 'ISS', 'aliquot_percent': 5}]
    with pytest.raises(InvalidOrcamentoInputError, match='id é obrigatório'):
        normalize_dfp_payload(dfp)


def test_excessive_combined_cost_has_domain_error_not_decimal_crash():
    dfp = scenario()
    dfp['equipamentos']['items'] = [
        {'id': 'a', 'label': 'A', 'quantity': 10_000_000_000_000,
         'unit_cost': 10_000_000_000_000}]
    with pytest.raises(InvalidOrcamentoInputError, match='limite'):
        compute_dfp_summary(dfp)


def test_same_additional_can_target_multiple_functions():
    dfp = scenario()
    first = dfp['mao_de_obra_direta']['items'][0]
    dfp['mao_de_obra_direta']['items'] = [first, {**first, 'id': 'ajudante', 'label': 'Ajudante'}]
    dfp['mao_de_obra_direta']['adjustments'] = [
        {'id': f'perigo_{target}', 'label': 'Periculosidade', 'labor_item_id': target,
         'quantity': 1, 'percent': 30, 'base': 'salary'}
        for target in ('pintor', 'ajudante')]
    assert compute_dfp_summary(dfp)['mao_de_obra_direta_total'] == 4168


def test_huge_integer_input_is_rejected_without_float_overflow():
    dfp = scenario()
    dfp['mao_de_obra_direta']['items'][0]['salary_real'] = 10**400
    with pytest.raises(InvalidOrcamentoInputError, match='limite'):
        normalize_dfp_payload(dfp)
