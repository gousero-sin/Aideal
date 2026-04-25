from decimal import Decimal

from app.transformacao.engine import classificar_valores


def test_classificar_valores_saida_vai_para_debito():
    credito, debito = classificar_valores(Decimal("125.30"), "2 - SAIDA")

    assert credito == Decimal("0")
    assert debito == Decimal("125.30")


def test_classificar_valores_entrada_vai_para_credito():
    credito, debito = classificar_valores(Decimal("125.30"), "1 - ENTRADA")

    assert credito == Decimal("125.30")
    assert debito == Decimal("0")
