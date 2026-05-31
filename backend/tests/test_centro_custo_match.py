"""Testes da busca complexa de centro de custo (filtro de obra)."""

from app.repository.centro_custo_match import (
    normalizar_centro_custo,
    resolver_centros_custo,
)

CENTROS = [
    "ANGLO AMERICAN",
    "CANTEIRO DE OBRA",
    "EUROCHEM SERRA DO SALITRE",
    "FOSFATO CMOC CONTRAT",
    "MOSAIC ARAXA",
    "MOSAIC UBERABA CONTRAT0 3 ANOS",
    "NIOBIO CMOC CONTRATO",
    "VLI PINTURA",
]


class TestNormalizar:
    def test_remove_acento_caixa_e_pontuacao(self):
        assert normalizar_centro_custo("Mosaic Araxá") == "MOSAIC ARAXA"
        assert normalizar_centro_custo("  Nióbio/CMOC  ") == "NIOBIO CMOC"

    def test_valor_nulo_ou_vazio(self):
        assert normalizar_centro_custo(None) == ""
        assert normalizar_centro_custo("   ") == ""


class TestResolverCentrosCusto:
    def test_match_exato(self):
        assert resolver_centros_custo("EUROCHEM SERRA DO SALITRE", CENTROS) == [
            "EUROCHEM SERRA DO SALITRE"
        ]

    def test_ignora_acento_e_caixa(self):
        assert resolver_centros_custo("eurochem serra do salitre", CENTROS) == [
            "EUROCHEM SERRA DO SALITRE"
        ]

    def test_subconjunto_de_tokens_ordem_livre(self):
        # Apenas parte do nome, em ordem diferente, ainda encontra a obra.
        assert resolver_centros_custo("salitre eurochem", CENTROS) == [
            "EUROCHEM SERRA DO SALITRE"
        ]

    def test_token_unico_encontra_obra(self):
        assert resolver_centros_custo("eurochem", CENTROS) == ["EUROCHEM SERRA DO SALITRE"]

    def test_token_compartilhado_retorna_todas_as_obras(self):
        # 'MOSAIC' casa as duas obras Mosaic — comportamento de busca por obra.
        assert resolver_centros_custo("mosaic", CENTROS) == [
            "MOSAIC ARAXA",
            "MOSAIC UBERABA CONTRAT0 3 ANOS",
        ]

    def test_match_exato_prevalece_sobre_token(self):
        # Existindo match exato, não mistura com os mais permissivos.
        assert resolver_centros_custo("MOSAIC ARAXA", CENTROS) == ["MOSAIC ARAXA"]

    def test_sem_correspondencia_retorna_vazio(self):
        assert resolver_centros_custo("OBRA INEXISTENTE XYZ", CENTROS) == []

    def test_termo_vazio_retorna_vazio(self):
        assert resolver_centros_custo("", CENTROS) == []
