"""Composição HH: paridade com a planilha MODELO COMPOSIÇÃO DE CUSTO, validação e importação."""

from copy import deepcopy
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.main import app
from app.orcamento.dfp import compute_dfp_summary, get_dfp_window_schema, normalize_dfp_payload
from app.orcamento.documents import export_orcamento_document
from app.orcamento.exceptions import InvalidOrcamentoInputError
from app.orcamento.hh import build_default_hh, compute_hh, compute_hh_summary, normalize_hh
from app.orcamento.hh_import import import_hh_workbook

# Valores calculados pelo Excel na planilha de referência (aba Composição M.O Fixa).
PLANILHA = {
    "encarregado": {
        "total_unitario": 17118.557286858326,  # BJ8
        "hora_normal": 77.8116240311742,  # BP8
        "horas_extras": (103.2358348135151, 116.14031416520447, 129.04479351689386),
        "adicional_noturno_hora": 15.562324806234841,  # BT8
        "hora_noturna": 93.37394883740905,  # BU8
        "horas_extras_noturnas": (123.88300177621812, 139.36837699824537, 154.85375222027264),
        "subtotal_a2": 10736.486074974,  # P8
        "subtotal_b": 3119.93,  # AM8
        "subtotal_c": 859.0977966483881,  # AT8
        "subtotal_d": 2403.043415235936,  # BG8
    },
    "total_grupo_1_36_meses": 2622557.1295356806,  # BN12
    "total_grupo_2_36_meses": 1757495.8482996314,  # BN16
    "total_mensal_grupo_1": 72848.8091537689,  # BL12
    "encargos_percent": 125.57586000000003,  # Encargos!I50
}


def _cents(value):
    return round(value + 1e-9, 2)


def test_modelo_padrao_reproduz_a_planilha_celula_a_celula():
    calculo = compute_hh(None)
    linha = calculo["grupos"][0]["funcoes"][0]
    esperado = PLANILHA["encarregado"]
    for chave in ("total_unitario", "hora_normal", "adicional_noturno_hora", "hora_noturna",
                  "subtotal_a2", "subtotal_b", "subtotal_c", "subtotal_d"):
        assert linha[chave] == _cents(esperado[chave]), chave
    assert linha["horas_extras"] == [_cents(v) for v in esperado["horas_extras"]]
    assert linha["horas_extras_noturnas"] == [
        _cents(v) for v in esperado["horas_extras_noturnas"]
    ]
    assert calculo["grupos"][0]["total_estimado"] == _cents(PLANILHA["total_grupo_1_36_meses"])
    assert calculo["grupos"][1]["total_estimado"] == _cents(PLANILHA["total_grupo_2_36_meses"])
    assert calculo["grupos"][0]["total_mensal"] == _cents(PLANILHA["total_mensal_grupo_1"])
    assert calculo["totais"]["total_estimado"] == _cents(
        PLANILHA["total_grupo_1_36_meses"] + PLANILHA["total_grupo_2_36_meses"]
    )
    assert calculo["encargos"]["total_percent"] == pytest.approx(PLANILHA["encargos_percent"])
    assert calculo["totais"]["colaboradores"] == 10


def test_encargos_grupo_d_deriva_de_a_b_e_fgts():
    encargos = compute_hh(None)["encargos"]
    assert encargos["grupos"]["A"] == pytest.approx(37.8)
    assert encargos["grupos"]["B"] == pytest.approx(39.17)
    assert encargos["grupos"]["C"] == pytest.approx(32.75)
    assert encargos["derivados"]["d1"] == pytest.approx(37.8 * 39.17 / 100)
    assert encargos["derivados"]["d3"] == pytest.approx(8 * 13.12 / 100)


def test_periculosidade_e_noturno_entram_no_subtotal_a1():
    hh = build_default_hh()
    funcao = hh["grupos"][0]["funcoes"][0]
    funcao.update(periculosidade=True, adicional_noturno_percent=20, salario_base=1000)
    linha = compute_hh(hh)["grupos"][0]["funcoes"][0]
    assert linha["periculosidade_valor"] == 300
    assert linha["adicional_noturno_valor"] == 200
    assert linha["subtotal_a1"] == 1500


def test_hora_extra_exclui_custos_que_nao_acompanham_a_hora():
    hh = build_default_hh()
    funcao = hh["grupos"][0]["funcoes"][0]
    funcao["custos"] = {**funcao["custos"], "transporte": 0, "outros": 0}
    sem = compute_hh(hh)["grupos"][0]["funcoes"][0]
    com = compute_hh(None)["grupos"][0]["funcoes"][0]
    # Transporte e "Outros" ficam fora da base da hora extra; só o BDI/tributos sobre eles mudam.
    assert com["hora_normal"] > sem["hora_normal"]
    assert com["horas_extras"][0] - sem["horas_extras"][0] < (
        com["hora_normal"] - sem["hora_normal"]
    )


def test_horas_zeradas_nao_dividem_por_zero():
    hh = build_default_hh()
    hh["grupos"][0]["funcoes"][0]["horas_mes"] = 0
    linha = compute_hh(hh)["grupos"][0]["funcoes"][0]
    assert linha["hora_normal"] == 0 and linha["horas_extras"] == [0, 0, 0]


@pytest.mark.parametrize(
    ("mutacao", "mensagem"),
    [
        (lambda hh: hh["tributos"][0].update(percent=99), "soma dos tributos"),
        (lambda hh: hh["grupos"][0]["funcoes"][0]["custos"].update(cafe=1), "custo desconhecido"),
        (lambda hh: hh["encargos"][0].update(id="z9"), "item inválido"),
        (lambda hh: hh["grupos"][0]["funcoes"][0].update(salario_base=-1), "não negativo"),
        (lambda hh: hh["grupos"][0]["funcoes"][0].update(quantidade=True), "numérico"),
        (lambda hh: hh["grupos"][1]["funcoes"][0].update(id=hh["grupos"][0]["funcoes"][0]["id"]),
         "duplicados"),
        (lambda hh: hh["grupos"][0]["funcoes"][0].update(label=" "), "nome da função"),
        (lambda hh: hh["bdi"].update(lucro_percent=100), "menor que 100"),
        (lambda hh: hh.update(horas_extras_percentuais=[60]), "três percentuais"),
        (lambda hh: hh["grupos"][0].update(funcoes=[{"label": "x"}] * 251), "excede"),
    ],
)
def test_normalizacao_recusa_entradas_invalidas(mutacao, mensagem):
    hh = build_default_hh()
    mutacao(hh)
    with pytest.raises(InvalidOrcamentoInputError, match=mensagem):
        normalize_hh(hh)


def test_normalizacao_nao_muta_a_entrada():
    hh = build_default_hh()
    original = deepcopy(hh)
    normalize_hh(hh)
    assert hh == original


def test_dfp_preserva_bloco_hh_e_resumo_segue_a_modalidade():
    dfp = normalize_dfp_payload({"calculation_version": 2, "hh": build_default_hh()})
    assert dfp["hh"]["grupos"][0]["funcoes"][0]["label"].startswith("Encarregado")
    hh_summary = compute_dfp_summary(dfp, modalidade="HH")
    assert hh_summary["preco_total_faturamento"] == 4380052.98
    assert hh_summary == compute_hh_summary(dfp["hh"])
    assert compute_dfp_summary(dfp, modalidade="Spot")["preco_total_faturamento"] == 0
    sem_hh = normalize_dfp_payload({"calculation_version": 2})
    assert "hh" not in sem_hh
    # HH sem composição salva não exibe o modelo padrão como valor do orçamento.
    assert compute_dfp_summary(sem_hh, modalidade="HH")["preco_total_faturamento"] == 0


def test_schema_v2_entrega_modelo_hh():
    schema = get_dfp_window_schema(calculation_version=2)
    assert schema["hh"]["defaults"] == build_default_hh()
    assert [coluna["id"] for coluna in schema["hh"]["custo_colunas"]][:3] == [
        "mobilizacao", "exames_medicos", "treinamentos",
    ]


def _planilha_modelo() -> bytes:
    livro = Workbook()
    composicao = livro.active
    composicao.title = "Composição M.O Fixa"
    composicao["I3"], composicao["J3"] = "% Noturno", 0.2
    composicao["I4"], composicao["J4"] = "Salário Mínimo", "1.621,00."
    cabecalho = {"B5": "FUNÇÃO", "C5": "QTDE (Por função)", "D5": "HORAS TRABALHADAS\n(Mês)",
                 "E5": "SALÁRIO BASE (R$)", "G5": "PERICULOSIDADE (R$)",
                 "I5": "ADICNIONAL NOTURNO", "T5": "Exames Médicos", "V5": "Transporte",
                 "AB5": "EPI", "AG5": "Veiculos", "BN5": "Total Estimado 24 meses"}
    for celula, valor in cabecalho.items():
        composicao[celula] = valor
    composicao["B7"] = "1 - Pintura"
    composicao["B8"], composicao["C8"], composicao["D8"], composicao["E8"] = "Pintor", 2, 220, 2500
    composicao["G8"], composicao["I8"] = 0.3, 0.2
    composicao["B12"], composicao["C12"], composicao["E12"] = "Soldador", 1, 3000
    composicao["G12"] = 0.2  # planilha só aplica periculosidade quando G = 30%
    composicao["T8"], composicao["V8"], composicao["AB8"], composicao["AG8"] = 20, 1500, 100, 300
    composicao["C9"] = "=SUM(C8)"
    composicao["B10"] = "Isolamento"
    composicao["B11"], composicao["C11"], composicao["E11"] = "Isolador", 1, 2400
    composicao["B13"] = "Total Geral"  # linha 12 (Soldador) ainda entra no grupo Isolamento
    composicao["B14"], composicao["C14"], composicao["E14"] = "Depois do total", 9, 9999
    encargos = livro.create_sheet("Encargos")
    encargos["C5"], encargos["D5"], encargos["H5"] = "A.1", "INSS", 0.2
    encargos["C6"], encargos["D6"], encargos["H6"] = "A.2", "FGTS", 0.08
    encargos["C20"], encargos["D20"], encargos["H20"] = "B.2*", "FÉRIAS", 0.1
    # Fora do total na planilha (I48 = SOMA(H44; H46)): não pode entrar nos encargos.
    encargos["C45"], encargos["D45"], encargos["H45"] = "D.2", "REINCIDÊNCIA DE A2", 0.01
    bdi = livro.create_sheet("BDI")
    bdi["B9"], bdi["D9"] = "1   LUCRO", 0.05
    bdi["B11"], bdi["D11"] = "2   DESPESAS INDIRETAS (Overhead).", 0.03
    bdi["B14"], bdi["D14"] = "ISS", 0.02
    bdi["B17"], bdi["D17"] = "I.R.", 0.048
    saida = BytesIO()
    livro.save(saida)
    return saida.getvalue()


def test_importa_planilha_no_formato_do_modelo():
    hh = import_hh_workbook(_planilha_modelo())
    assert [grupo["label"] for grupo in hh["grupos"]] == ["1 - Pintura", "Isolamento"]
    pintor = hh["grupos"][0]["funcoes"][0]
    assert pintor["quantidade"] == 2 and pintor["salario_base"] == 2500
    assert pintor["periculosidade"] is True and pintor["adicional_noturno_percent"] == 20
    assert pintor["custos"]["exames_medicos"] == 20 and pintor["custos"]["veiculos"] == 300
    assert hh["grupos"][1]["funcoes"][0]["horas_mes"] == 220  # célula vazia usa 220
    assert hh["meses"] == 24 and hh["percentual_noturno"] == 20 and hh["salario_minimo"] == 1621
    encargos = {item["id"]: item["percent"] for item in hh["encargos"]}
    assert encargos["a1"] == 20 and encargos["b2"] == 10 and "d2" not in encargos
    assert hh["grupos"][1]["funcoes"][1]["periculosidade"] is False
    # Linhas de encargo ausentes no arquivo mantêm o padrão do modelo.
    assert encargos["b1"] == 22.9
    assert hh["bdi"] == {"despesas_indiretas_percent": 3, "lucro_percent": 5}
    tributos = {item["id"]: item["percent"] for item in hh["tributos"]}
    assert tributos == {"iss": 2, "pis": 0, "cofins": 0, "csll": 0, "ir": 4.8}


@pytest.mark.parametrize("conteudo", [b"", b"nao e zip", b"PK\x03\x04quebrado"])
def test_importacao_recusa_arquivo_invalido(conteudo):
    with pytest.raises(InvalidOrcamentoInputError):
        import_hh_workbook(conteudo)


def test_importacao_recusa_planilha_sem_cabecalho():
    livro = Workbook()
    livro.active["A1"] = "qualquer coisa"
    saida = BytesIO()
    livro.save(saida)
    with pytest.raises(InvalidOrcamentoInputError, match="FUNÇÃO"):
        import_hh_workbook(saida.getvalue())


@pytest.fixture
def client():
    client = TestClient(app)
    response = client.post("/api/auth/login", json={
        "username": "Eduardo", "password": "senha-admin-teste",
    })
    assert response.status_code == 200
    client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    return client


def test_api_importa_planilha_sem_gravar(client):
    response = client.post("/api/orcamento/hh/importar", content=_planilha_modelo(), headers={
        "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    })
    assert response.status_code == 200, response.text
    assert response.json()["hh"]["grupos"][0]["funcoes"][0]["label"] == "Pintor"
    assert client.get("/api/orcamento/orcamentos").json()["orcamentos"] == []


def test_api_importacao_exige_csrf_e_limita_tamanho(client):
    sem_csrf = TestClient(app)
    sem_csrf.cookies = client.cookies
    assert sem_csrf.post("/api/orcamento/hh/importar", content=b"x").status_code == 403
    grande = client.post("/api/orcamento/hh/importar", content=b"0" * (5 * 1024 * 1024 + 1))
    assert grande.status_code == 413
    assert client.post("/api/orcamento/hh/importar", content=b"x").status_code == 422


def test_api_orcamento_hh_salva_composicao_e_resumo_usa_hh(client):
    criado = client.post("/api/orcamento/orcamentos", json={
        "contratante": "Cliente HH", "modalidade": "HH",
    }).json()
    assert criado["dfp_summary"]["preco_total_faturamento"] == 0
    revisao = criado["revisao_atual"]
    dfp = {**revisao["dfp"], "hh": build_default_hh()}
    resposta = client.patch(f"/api/orcamento/revisoes/{revisao['id']}", json={"dfp": dfp})
    assert resposta.status_code == 200, resposta.text
    salvo = client.get(f"/api/orcamento/orcamentos/{criado['id']}").json()
    assert salvo["revisao_atual"]["dfp"]["hh"]["meses"] == 36
    assert salvo["dfp_summary"]["preco_total_faturamento"] == 4380052.98
    invalido = {**dfp, "hh": {**dfp["hh"], "meses": -1}}
    assert client.patch(f"/api/orcamento/revisoes/{revisao['id']}",
                        json={"dfp": invalido}).status_code == 422


@pytest.mark.parametrize("formato", ["docx", "pdf"])
def test_exporta_orcamento_hh(formato):
    dfp = normalize_dfp_payload({"calculation_version": 2, "hh": build_default_hh()})
    conteudo, _tipo, nome = export_orcamento_document(
        {"codigo": "ORC-0007"}, {"numero": 0, "modalidade": "HH", "dfp": dfp}, formato,
    )
    assert nome == f"ORC-0007-R0.{formato}"
    assert len(conteudo) > 1000


def test_fixture_do_frontend_acompanha_o_modelo_padrao():
    """O teste de paridade do frontend usa este JSON; se o modelo mudar, ele precisa mudar junto."""
    import json
    from pathlib import Path

    fixture = (Path(__file__).resolve().parents[2] / "frontend" / "src" / "components"
               / "__fixtures__" / "hhModeloPadrao.json")
    assert json.loads(fixture.read_text(encoding="utf-8")) == build_default_hh()


def test_campo_apagado_vale_zero_como_na_previa_e_ausente_usa_o_modelo():
    hh = build_default_hh()
    hh["meses"] = ""
    hh["grupos"][0]["funcoes"][0]["horas_mes"] = ""
    normalizado = normalize_hh(hh)
    assert normalizado["meses"] == 0
    assert normalizado["grupos"][0]["funcoes"][0]["horas_mes"] == 0
    assert compute_hh_summary(hh)["preco_total_faturamento"] == 0
    sem_chave = build_default_hh()
    del sem_chave["meses"]
    assert normalize_hh(sem_chave)["meses"] == 36


@pytest.mark.parametrize(
    "mutacao",
    [
        lambda hh: hh["encargos"][0].update(id=["a1"]),
        lambda hh: hh["tributos"][0].update(id={}),
        lambda hh: hh["grupos"][0]["funcoes"][0].update(horas_mes="1e-25"),
        lambda hh: hh["grupos"][0]["funcoes"][0].update(horas_mes=800),
        lambda hh: hh["grupos"][0]["funcoes"][0].update(quantidade=1e10),
        lambda hh: hh["grupos"][0]["funcoes"][0].update(salario_base=1e13),
    ],
)
def test_entradas_fora_do_dominio_viram_erro_de_validacao_e_nao_500(mutacao):
    hh = build_default_hh()
    mutacao(hh)
    with pytest.raises(InvalidOrcamentoInputError):
        compute_hh_summary(hh)


def test_limites_maximos_ainda_calculam_sem_estourar_decimal():
    hh = build_default_hh()
    funcao = hh["grupos"][0]["funcoes"][0]
    funcao.update(quantidade=100000, salario_base=1e9, horas_mes=1)
    funcao["custos"] = {chave: 1e9 for chave in funcao["custos"]}
    hh["meses"] = 1200
    assert compute_hh_summary(hh)["preco_total_faturamento"] > 0


def _xlsx_com_aba_corrompida() -> bytes:
    import zipfile

    original = zipfile.ZipFile(BytesIO(_planilha_modelo()))
    saida = BytesIO()
    with zipfile.ZipFile(saida, "w") as destino:
        for info in original.infolist():
            dados = original.read(info.filename)
            if info.filename == "xl/worksheets/sheet1.xml":
                dados = dados[: len(dados) // 2]
            destino.writestr(info, dados)
    return saida.getvalue()


def test_importacao_com_xml_quebrado_vira_erro_de_validacao():
    with pytest.raises(InvalidOrcamentoInputError, match="Não foi possível ler"):
        import_hh_workbook(_xlsx_com_aba_corrompida())


def test_importacao_recusa_parte_inflada():
    import zipfile

    saida = BytesIO()
    with zipfile.ZipFile(saida, "w", zipfile.ZIP_DEFLATED) as arquivo:
        arquivo.writestr("xl/worksheets/sheet1.xml", "<c><v>1</v></c>" * 300_000)
    with pytest.raises(InvalidOrcamentoInputError, match="grande demais"):
        import_hh_workbook(saida.getvalue())


def test_pdf_hh_escapa_rotulo_do_grupo():
    hh = build_default_hh()
    hh["grupos"][0]["label"] = 'X<img src="http://127.0.0.1:9/ssrf"/> a<b'
    dfp = normalize_dfp_payload({"calculation_version": 2, "hh": hh})
    conteudo, _tipo, _nome = export_orcamento_document(
        {"codigo": "ORC-0007"}, {"numero": 0, "modalidade": "HH", "dfp": dfp}, "pdf",
    )
    assert conteudo.startswith(b"%PDF")


def test_salvar_em_hh_ainda_valida_o_dfp_guardado(client):
    dfp = {"calculation_version": 2, "hh": build_default_hh(),
           "equipamentos": {"items": [{"id": "x", "label": "Gigante",
                                        "quantity": 1e12, "unit_cost": 1e12}]}}
    resposta = client.post("/api/orcamento/orcamentos", json={
        "contratante": "Cliente HH", "modalidade": "HH", "dfp": dfp,
    })
    assert resposta.status_code == 422


def test_revisao_gravada_com_encargo_descontinuado_continua_abrindo():
    """A leitura do banco normaliza o HH: recusar a linha antiga derrubaria a carteira."""
    hh = build_default_hh()
    hh["encargos"].append({"id": "d2", "grupo": "D", "label": "Reincidência", "percent": 0.4})
    normalizado = normalize_hh(hh)
    assert "d2" not in {item["id"] for item in normalizado["encargos"]}
    assert compute_hh(hh)["encargos"]["total_percent"] == pytest.approx(125.57586)
