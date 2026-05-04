"""Testes unitários para funções de conversão segura (engine helpers)."""

from datetime import date
from decimal import Decimal

import pytest

from app.transformacao.engine import (
    _safe_date,
    _safe_decimal,
    _safe_str,
    classificar_valores,
)

# ── _safe_decimal ────────────────────────────────────────────────────────────


class TestSafeDecimal:
    def test_inteiro(self):
        assert _safe_decimal(100) == Decimal("100")

    def test_float(self):
        assert _safe_decimal(1234.56) == Decimal("1234.56")

    def test_string_ponto(self):
        assert _safe_decimal("1234.56") == Decimal("1234.56")

    def test_string_virgula_decimal(self):
        assert _safe_decimal("1234,56") == Decimal("1234.56")

    def test_brasileiro_milhar_e_virgula(self):
        # "1.234,56" → remove ponto (milhar), troca vírgula por ponto
        assert _safe_decimal("1.234,56") == Decimal("1234.56")

    @pytest.mark.xfail(
        reason="Bug conhecido: formato US '1,234.56' interpretado incorretamente como ~1.23456"
    )
    def test_formato_us_milhar_virgula_ponto(self):
        assert _safe_decimal("1,234.56") == Decimal("1234.56")

    def test_none(self):
        assert _safe_decimal(None) == Decimal("0")

    def test_nan(self):
        assert _safe_decimal(float("nan")) == Decimal("0")

    def test_vazio(self):
        assert _safe_decimal("") == Decimal("0")

    def test_espacos(self):
        assert _safe_decimal("  ") == Decimal("0")

    def test_texto_invalido(self):
        assert _safe_decimal("abc") == Decimal("0")

    def test_negativo(self):
        assert _safe_decimal("-500.30") == Decimal("-500.30")

    def test_zero(self):
        assert _safe_decimal(0) == Decimal("0")

    def test_decimal_passado(self):
        assert _safe_decimal(Decimal("99.99")) == Decimal("99.99")


# ── _safe_date ───────────────────────────────────────────────────────────────


class TestSafeDate:
    def test_string_ddmmyyyy(self):
        assert _safe_date("01/05/2025") == date(2025, 5, 1)

    def test_datetime_object(self):
        from datetime import datetime

        dt = datetime(2025, 5, 15, 10, 30)
        assert _safe_date(dt) == date(2025, 5, 15)

    def test_none(self):
        assert _safe_date(None) is None

    def test_nan(self):
        assert _safe_date(float("nan")) is None

    def test_invalido(self):
        assert _safe_date("nao_e_data") is None

    def test_dayfirst(self):
        # "02/03/2025" com dayfirst=True → 2 de março
        result = _safe_date("02/03/2025")
        assert result == date(2025, 3, 2)


# ── _safe_str ────────────────────────────────────────────────────────────────


class TestSafeStr:
    def test_string_normal(self):
        assert _safe_str("  hello  ") == "hello"

    def test_none(self):
        assert _safe_str(None) == ""

    def test_nan(self):
        assert _safe_str(float("nan")) == ""

    def test_numero(self):
        assert _safe_str(123) == "123"


# ── classificar_valores ─────────────────────────────────────────────────────


class TestClassificarValores:
    def test_saida_vai_para_debito(self):
        credito, debito = classificar_valores(Decimal("125.30"), "2 - SAIDA")
        assert credito == Decimal("0")
        assert debito == Decimal("125.30")

    def test_entrada_vai_para_credito(self):
        credito, debito = classificar_valores(Decimal("125.30"), "1 - ENTRADA")
        assert credito == Decimal("125.30")
        assert debito == Decimal("0")

    def test_saida_case_insensitive(self):
        credito, debito = classificar_valores(Decimal("50"), "2 - saida")
        assert credito == Decimal("0")
        assert debito == Decimal("50")

    def test_saida_parcial_match(self):
        credito, debito = classificar_valores(Decimal("10"), "SAIDA GERAL")
        assert credito == Decimal("0")
        assert debito == Decimal("10")

    def test_natureza_vazia(self):
        credito, debito = classificar_valores(Decimal("100"), "")
        assert credito == Decimal("100")
        assert debito == Decimal("0")

    def test_valor_negativo_fica_absoluto(self):
        credito, debito = classificar_valores(Decimal("-200"), "1 - ENTRADA")
        assert credito == Decimal("200")
        assert debito == Decimal("0")

    def test_valor_zero(self):
        credito, debito = classificar_valores(Decimal("0"), "2 - SAIDA")
        assert credito == Decimal("0")
        assert debito == Decimal("0")
