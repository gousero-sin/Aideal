"""Composição de custos por Homem-Hora (modalidade HH).

Reproduz a planilha "MODELO COMPOSIÇÃO DE CUSTO" (abas Composição M.O Fixa, Encargos e BDI):

- A  = salário base + periculosidade + adicional noturno, acrescido dos encargos sociais;
- B  = custos mensais por pessoa (mobilização, exames, EPI...);
- C  = despesas administrativas + lucro, ambos sobre (A + B);
- D  = tributos, cada um sobre (A + B + C), calculados "por fora";
- total unitário = A + B + C + D por pessoa/mês; × quantidade; × meses do contrato;
- valor da hora = total unitário / horas do mês, com as horas extras sobre uma base que exclui os
  custos que não acompanham a hora (coluna BQ da planilha).

O bloco fica em ``dfp["hh"]`` e só vale quando a revisão está na modalidade HH; a composição DFP
continua intacta no mesmo snapshot.
"""

from __future__ import annotations

from copy import deepcopy
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from .exceptions import InvalidOrcamentoInputError

MAX_GRUPOS = 50
MAX_FUNCOES = 250
MAX_TEXTO = 200
# Limites de domínio: folgados para qualquer contrato real e pequenos o bastante para que
# quantidade × valor × meses nunca estoure a precisão do Decimal ao arredondar centavos.
MAX_VALOR = Decimal("1000000000")
MAX_QUANTIDADE = Decimal("100000")
MAX_HORAS_MES = Decimal("744")
CENT = Decimal("0.01")
HUNDRED = Decimal("100")
ZERO = Decimal("0")

# (id, rótulo, mantém na base da hora extra). Na planilha a hora extra (BQ..BS) desconta do total
# unitário as colunas T, U, V, W, X, Y, Z, AC, AF, AG, AI, AJ e AL; as demais ficam na base.
CUSTO_COLUNAS: tuple[tuple[str, str, bool], ...] = (
    ("mobilizacao", "Mobilização", True),
    ("exames_medicos", "Exames Médicos", False),
    ("treinamentos", "Treinamentos", False),
    ("transporte", "Transporte", False),
    ("cesta_basica", "Cesta Básica", False),
    ("assistencia_medica", "Assistência Médica", False),
    ("seguro_vida", "Seguro de Vida", False),
    ("plr", "PLR", False),
    ("uniforme", "Uniforme", True),
    ("epi", "EPI", True),
    ("treinamento_racs", "Treinamento de RACs", False),
    ("materiais", "Materiais", True),
    ("ferramentas", "Ferramentas", True),
    ("equipamentos", "Equipamentos", False),
    ("veiculos", "Veículos", False),
    ("combustivel", "Combustível / Lubrificantes / Manutenção", True),
    ("comunicacao", "Comunicação (Telefone / Internet / Rádio)", False),
    ("investimentos", "Investimentos", False),
    ("desmobilizacao", "Desmobilização", True),
    ("outros", "Outros", False),
)
CUSTO_IDS = tuple(coluna[0] for coluna in CUSTO_COLUNAS)

# Grupos A, B e C da aba Encargos (percentuais editáveis). O grupo D é derivado, como em
# Encargos!I48 = SUM(H44, H46): a linha "reincidência de A.2 sobre C.2" fica fora do total.
ENCARGOS_PADRAO: tuple[tuple[str, str, str, float], ...] = (
    ("a1", "A", "INSS", 20.0),
    ("a2", "A", "FGTS", 8.0),
    ("a3", "A", "SESI/SESC", 1.5),
    ("a4", "A", "SENAI/SENAC", 1.0),
    ("a5", "A", "INCRA", 0.2),
    ("a6", "A", "Salário educação", 2.5),
    ("a7", "A", "Seguro de acidente de trabalho", 3.0),
    ("a8", "A", "SEBRAE", 0.6),
    ("a9", "A", "SECONCI", 1.0),
    ("b1", "B", "Descanso semanal remunerado", 22.9),
    ("b2", "B", "Férias", 0.0),
    ("b3", "B", "1/3 constitucional de férias", 0.0),
    ("b4", "B", "Feriados", 0.0),
    ("b5", "B", "Aviso prévio indenizado", 0.0),
    ("b6", "B", "Enfermidade", 0.79),
    ("b7", "B", "Acidentes de trabalho", 0.0),
    ("b8", "B", "Licença paternidade", 0.34),
    ("b9", "B", "13º salário", 10.57),
    ("b10", "B", "Falta justificada", 4.57),
    ("c1", "C", "Férias indenizadas", 14.06),
    ("c2", "C", "50% do FGTS nas rescisões sem justa causa", 5.57),
    ("c3", "C", "Aviso prévio indenizado", 13.12),
    ("c4", "C", "FGTS sobre aviso prévio indenizado", 0.0),
)
ENCARGO_IDS = tuple(item[0] for item in ENCARGOS_PADRAO)
# Linhas que já existiram no modelo e saíram: revisões gravadas com elas continuam abrindo
# (a leitura passa por esta normalização e um erro aqui derrubaria a carteira inteira).
ENCARGOS_DESCONTINUADOS = frozenset({"d2"})
ENCARGOS_DERIVADOS = (
    ("d1", "D", "Grupo A sobre o Grupo B"),
    ("d3", "D", "Incidência de A.2 (FGTS) sobre C.3"),
)

TRIBUTOS_PADRAO: tuple[tuple[str, str, float], ...] = (
    ("iss", "ISS", 5.0),
    ("pis", "PIS", 0.65),
    ("cofins", "COFINS", 3.0),
    ("csll", "CSLL", 2.88),
    ("ir", "IR", 4.8),
)
TRIBUTO_IDS = tuple(item[0] for item in TRIBUTOS_PADRAO)

_FUNCOES_PADRAO = (
    (
        "pintura",
        "1 - Pintura Industrial e Jato Abrasivo",
        (
            ("Encarregado de Jatamento e Pintura Industrial", 1, 4759.59, 101.05),
            ("Pintor letrista", 1, 2591.24, 127.07),
            ("Jatista Industrial", 2, 2615.23, 150.15),
            ("Pintor Industrial", 2, 2591.24, 127.07),
        ),
    ),
    (
        "isolamento",
        "Isolamento Térmico Industrial",
        (
            ("Isolador", 2, 2467.85, 360.0),
            ("Funileiro", 2, 3293.12, 365.0),
        ),
    ),
)


def _slug(texto: str) -> str:
    letras: list[str] = []
    for char in texto.casefold():
        if char.isalnum():
            letras.append(char)
        elif letras and letras[-1] != "_":
            letras.append("_")
    return "".join(letras).strip("_") or "item"


def _custos_padrao(epi: float) -> dict[str, float]:
    custos = {coluna: 0.0 for coluna in CUSTO_IDS}
    custos.update(
        exames_medicos=23.81,
        treinamentos=23.82,
        transporte=1500.0,
        assistencia_medica=40.0,
        uniforme=95.25,
        epi=epi,
        outros=1336.0,
    )
    return custos


def build_default_hh() -> dict[str, Any]:
    """Modelo padrão da planilha de composição (funções, encargos e BDI)."""
    return {
        "meses": 36.0,
        "percentual_noturno": 20.0,
        "periculosidade_percent": 30.0,
        "salario_minimo": 1621.0,
        "horas_extras_percentuais": [60.0, 80.0, 100.0],
        "encargos": [
            {"id": item_id, "grupo": grupo, "label": label, "percent": percent}
            for item_id, grupo, label, percent in ENCARGOS_PADRAO
        ],
        "bdi": {"despesas_indiretas_percent": 2.2, "lucro_percent": 4.0},
        "tributos": [
            {"id": item_id, "label": label, "percent": percent}
            for item_id, label, percent in TRIBUTOS_PADRAO
        ],
        "grupos": [
            {
                "id": grupo_id,
                "label": titulo,
                "funcoes": [
                    {
                        "id": _slug(nome),
                        "label": nome,
                        "quantidade": float(quantidade),
                        "horas_mes": 220.0,
                        "salario_base": salario,
                        "periculosidade": False,
                        "adicional_noturno_percent": 0.0,
                        "custos": _custos_padrao(epi),
                    }
                    for nome, quantidade, salario, epi in funcoes
                ],
            }
            for grupo_id, titulo, funcoes in _FUNCOES_PADRAO
        ],
    }


# ---------------------------------------------------------------------------
# Normalização
# ---------------------------------------------------------------------------


def _numero(
    valor: Any, *, campo: str, padrao: float = 0.0, maximo: Decimal = MAX_VALOR
) -> float:
    # Chave ausente usa o modelo; campo apagado no editor ('') vale zero, como na prévia.
    if valor is None:
        return float(padrao)
    if isinstance(valor, str) and not valor.strip():
        return 0.0
    if isinstance(valor, bool) or not isinstance(valor, (int, float, str, Decimal)):
        raise InvalidOrcamentoInputError(f"HH: {campo} deve ser numérico")
    try:
        numero = Decimal(str(valor).strip().replace(",", ".")) if isinstance(valor, str) else (
            Decimal(str(valor))
        )
    except ArithmeticError as exc:
        raise InvalidOrcamentoInputError(f"HH: {campo} deve ser numérico") from exc
    if not numero.is_finite() or numero < 0:
        raise InvalidOrcamentoInputError(f"HH: {campo} deve ser um número não negativo")
    if numero > maximo:
        raise InvalidOrcamentoInputError(f"HH: {campo} excede o limite permitido")
    return float(numero)


def _percentual(valor: Any, *, campo: str, padrao: float = 0.0) -> float:
    numero = _numero(valor, campo=campo, padrao=padrao)
    if numero >= 100:
        raise InvalidOrcamentoInputError(f"HH: {campo} deve ser menor que 100%")
    return numero


def _texto(valor: Any, *, campo: str, padrao: str = "") -> str:
    if valor is None:
        return padrao
    if not isinstance(valor, str):
        raise InvalidOrcamentoInputError(f"HH: {campo} deve ser texto")
    texto = " ".join(valor.split())
    if len(texto) > MAX_TEXTO:
        raise InvalidOrcamentoInputError(f"HH: {campo} excede {MAX_TEXTO} caracteres")
    return texto or padrao


def _lista(valor: Any, *, campo: str, maximo: int) -> list[dict[str, Any]]:
    if valor is None:
        return []
    if not isinstance(valor, list) or any(not isinstance(item, dict) for item in valor):
        raise InvalidOrcamentoInputError(f"HH: {campo} deve ser uma lista de objetos")
    if len(valor) > maximo:
        raise InvalidOrcamentoInputError(f"HH: {campo} excede {maximo} itens")
    return valor


def _identificador(item: dict[str, Any], *, campo: str, vistos: set[str], padrao: str) -> str:
    bruto = item.get("id", padrao)
    if not isinstance(bruto, str) or not bruto.strip() or len(bruto) > 80:
        raise InvalidOrcamentoInputError(f"HH: {campo}.id é obrigatório")
    chave = bruto.strip()
    if chave.casefold() in vistos:
        raise InvalidOrcamentoInputError(f"HH: identificadores duplicados em {campo}")
    vistos.add(chave.casefold())
    return chave


def _normalizar_percentuais_fixos(
    entrada: Any,
    padrao: list[dict[str, Any]],
    *,
    campo: str,
    descontinuados: frozenset[str] = frozenset(),
) -> list[dict[str, Any]]:
    """Linhas fixas do modelo: só o percentual é editável; ids desconhecidos são recusados."""
    if entrada is None:
        return deepcopy(padrao)
    if isinstance(entrada, list):
        entrada = [item for item in entrada
                   if not (isinstance(item, dict) and isinstance(item.get("id"), str)
                           and item["id"] in descontinuados)]
    itens = _lista(entrada, campo=campo, maximo=len(padrao))
    por_id: dict[str, dict[str, Any]] = {}
    for item in itens:
        item_id = item.get("id")
        if not isinstance(item_id, str) or item_id not in {linha["id"] for linha in padrao} \
                or item_id in por_id:
            raise InvalidOrcamentoInputError(f"HH: item inválido em {campo}")
        por_id[item_id] = item
    return [
        {
            **linha,
            "percent": _percentual(
                por_id.get(linha["id"], {}).get("percent"),
                campo=f"{campo}.{linha['id']}",
                padrao=linha["percent"] if linha["id"] not in por_id else 0.0,
            ),
        }
        for linha in padrao
    ]


def _horas_mes(valor: Any, *, campo: str) -> float:
    """Zero desliga o valor da hora; abaixo de 1 h/mês a divisão explode o resultado."""
    horas = _numero(valor, campo=campo, padrao=220.0, maximo=MAX_HORAS_MES)
    if 0 < horas < 1:
        raise InvalidOrcamentoInputError(f"HH: {campo} deve ser 0 ou ao menos 1 hora")
    return horas


def _normalizar_funcao(
    bruto: dict[str, Any], *, campo: str, vistos: set[str], padrao_id: str
) -> dict[str, Any]:
    label = _texto(bruto.get("label"), campo=f"{campo}.label")
    if not label:
        raise InvalidOrcamentoInputError(f"HH: informe o nome da função em {campo}")
    custos_brutos = bruto.get("custos") or {}
    if not isinstance(custos_brutos, dict):
        raise InvalidOrcamentoInputError(f"HH: {campo}.custos deve ser um objeto")
    desconhecidos = set(custos_brutos) - set(CUSTO_IDS)
    if desconhecidos:
        raise InvalidOrcamentoInputError(f"HH: custo desconhecido em {campo}")
    return {
        "id": _identificador(bruto, campo=campo, vistos=vistos, padrao=padrao_id),
        "label": label,
        "quantidade": _numero(bruto.get("quantidade"), campo=f"{campo}.quantidade",
                              maximo=MAX_QUANTIDADE),
        "horas_mes": _horas_mes(bruto.get("horas_mes"), campo=f"{campo}.horas_mes"),
        "salario_base": _numero(bruto.get("salario_base"), campo=f"{campo}.salario_base"),
        "periculosidade": bruto.get("periculosidade") is True,
        "adicional_noturno_percent": _percentual(
            bruto.get("adicional_noturno_percent"), campo=f"{campo}.adicional_noturno_percent"
        ),
        "custos": {
            coluna: _numero(custos_brutos.get(coluna), campo=f"{campo}.custos.{coluna}")
            for coluna in CUSTO_IDS
        },
    }


def normalize_hh(payload: Any) -> dict[str, Any]:
    """Valida o bloco HH; campos ausentes recebem o modelo padrão."""
    padrao = build_default_hh()
    if payload is None:
        return padrao
    if not isinstance(payload, dict):
        raise InvalidOrcamentoInputError("HH deve ser um objeto")
    he = payload.get("horas_extras_percentuais", padrao["horas_extras_percentuais"])
    if not isinstance(he, list) or len(he) != 3:
        raise InvalidOrcamentoInputError("HH: informe os três percentuais de hora extra")
    bdi = payload.get("bdi") or {}
    if not isinstance(bdi, dict):
        raise InvalidOrcamentoInputError("HH: bdi deve ser um objeto")
    resultado = {
        "meses": _numero(payload.get("meses"), campo="meses", padrao=padrao["meses"],
                         maximo=Decimal("1200")),
        "percentual_noturno": _percentual(
            payload.get("percentual_noturno"), campo="percentual_noturno",
            padrao=padrao["percentual_noturno"],
        ),
        "periculosidade_percent": _percentual(
            payload.get("periculosidade_percent"), campo="periculosidade_percent",
            padrao=padrao["periculosidade_percent"],
        ),
        "salario_minimo": _numero(
            payload.get("salario_minimo"), campo="salario_minimo",
            padrao=padrao["salario_minimo"],
        ),
        "horas_extras_percentuais": [
            _numero(valor, campo=f"horas_extras_percentuais[{indice}]",
                    maximo=Decimal("1000"))
            for indice, valor in enumerate(he)
        ],
        "encargos": _normalizar_percentuais_fixos(
            payload.get("encargos"), padrao["encargos"], campo="encargos",
            descontinuados=ENCARGOS_DESCONTINUADOS,
        ),
        "bdi": {
            chave: _percentual(bdi.get(chave), campo=f"bdi.{chave}",
                               padrao=padrao["bdi"][chave] if chave not in bdi else 0.0)
            for chave in ("despesas_indiretas_percent", "lucro_percent")
        },
        "tributos": _normalizar_percentuais_fixos(
            payload.get("tributos"), padrao["tributos"], campo="tributos"
        ),
    }
    if sum(item["percent"] for item in resultado["tributos"]) >= 100:
        raise InvalidOrcamentoInputError("HH: a soma dos tributos deve ser menor que 100%")
    if "grupos" not in payload:
        resultado["grupos"] = padrao["grupos"]
        return resultado
    grupos = _lista(payload.get("grupos"), campo="grupos", maximo=MAX_GRUPOS)
    ids_grupo: set[str] = set()
    ids_funcao: set[str] = set()
    total_funcoes = 0
    resultado["grupos"] = []
    for indice, grupo in enumerate(grupos):
        funcoes = _lista(grupo.get("funcoes"), campo=f"grupos[{indice}].funcoes",
                         maximo=MAX_FUNCOES)
        total_funcoes += len(funcoes)
        if total_funcoes > MAX_FUNCOES:
            raise InvalidOrcamentoInputError(f"HH: limite de {MAX_FUNCOES} funções excedido")
        resultado["grupos"].append({
            "id": _identificador(grupo, campo="grupos", vistos=ids_grupo,
                                 padrao=f"grupo_{indice + 1}"),
            "label": _texto(grupo.get("label"), campo=f"grupos[{indice}].label",
                            padrao=f"Grupo {indice + 1}"),
            "funcoes": [
                _normalizar_funcao(funcao, campo=f"grupos[{indice}].funcoes[{posicao}]",
                                   vistos=ids_funcao,
                                   padrao_id=f"funcao_{indice + 1}_{posicao + 1}")
                for posicao, funcao in enumerate(funcoes)
            ],
        })
    return resultado


# ---------------------------------------------------------------------------
# Cálculo
# ---------------------------------------------------------------------------


def _d(valor: Any) -> Decimal:
    return Decimal(str(valor or 0))


def _moeda(valor: Decimal) -> float:
    return float(valor.quantize(CENT, rounding=ROUND_HALF_UP))


def compute_encargos(hh: dict[str, Any]) -> dict[str, Any]:
    """Totais por grupo e o grupo D derivado, como na aba Encargos (em %)."""
    por_id = {item["id"]: _d(item["percent"]) for item in hh["encargos"]}
    grupos = {grupo: ZERO for grupo in "ABCD"}
    for item in hh["encargos"]:
        grupos[item["grupo"]] += _d(item["percent"])
    d1 = grupos["A"] * grupos["B"] / HUNDRED
    d3 = por_id.get("a2", ZERO) * por_id.get("c3", ZERO) / HUNDRED
    grupos["D"] += d1 + d3
    total = sum(grupos.values(), ZERO)
    return {
        "grupos": grupos,
        "derivados": {"d1": d1, "d3": d3},
        "total_percent": total,
    }


def _calcular_funcao(
    funcao: dict[str, Any], hh: dict[str, Any], encargos: Decimal
) -> dict[str, Any]:
    quantidade = _d(funcao["quantidade"])
    horas = _d(funcao["horas_mes"])
    salario = _d(funcao["salario_base"])
    meses = _d(hh["meses"])
    noturno_geral = _d(hh["percentual_noturno"]) / HUNDRED
    periculosidade = (
        salario * _d(hh["periculosidade_percent"]) / HUNDRED if funcao["periculosidade"] else ZERO
    )
    adicional_noturno = salario * _d(funcao["adicional_noturno_percent"]) / HUNDRED
    subtotal_a1 = salario + periculosidade + adicional_noturno
    encargos_valor = subtotal_a1 * encargos
    subtotal_a2 = subtotal_a1 + encargos_valor
    custos = {coluna: _d(funcao["custos"].get(coluna)) for coluna in CUSTO_IDS}
    subtotal_b = sum(custos.values(), ZERO)
    base_c = subtotal_a2 + subtotal_b
    despesas = base_c * _d(hh["bdi"]["despesas_indiretas_percent"]) / HUNDRED
    lucro = base_c * _d(hh["bdi"]["lucro_percent"]) / HUNDRED
    subtotal_c = despesas + lucro
    base_d = base_c + subtotal_c
    tributos = {item["id"]: base_d * _d(item["percent"]) / HUNDRED for item in hh["tributos"]}
    subtotal_d = sum(tributos.values(), ZERO)
    unitario = subtotal_a2 + subtotal_b + subtotal_c + subtotal_d
    fora_da_hora_extra = sum(
        (custos[coluna] for coluna, _rotulo, mantem in CUSTO_COLUNAS if not mantem), ZERO
    )
    hora_normal = unitario / horas if horas else ZERO
    base_he = (unitario - fora_da_hora_extra) / horas if horas else ZERO
    he = [_d(percentual) / HUNDRED for percentual in hh["horas_extras_percentuais"]]
    return {
        "salario_hora": salario / horas if horas else ZERO,
        "periculosidade_valor": periculosidade,
        "adicional_noturno_valor": adicional_noturno,
        "subtotal_a1": subtotal_a1,
        "encargos_valor": encargos_valor,
        "subtotal_a2": subtotal_a2,
        "total_a": subtotal_a2 * quantidade,
        "subtotal_b": subtotal_b,
        "total_b": subtotal_b * quantidade,
        "despesas_indiretas": despesas,
        "lucro": lucro,
        "subtotal_c": subtotal_c,
        "total_c": subtotal_c * quantidade,
        "tributos": tributos,
        "subtotal_d": subtotal_d,
        "total_d": subtotal_d * quantidade,
        "total_unitario": unitario,
        "total_mensal": unitario * quantidade,
        "total_estimado": unitario * quantidade * meses,
        "hora_normal": hora_normal,
        "horas_extras": [base_he * (1 + fator) for fator in he],
        "adicional_noturno_hora": hora_normal * noturno_geral,
        "hora_noturna": hora_normal * (1 + noturno_geral),
        "horas_extras_noturnas": [base_he * (1 + noturno_geral) * (1 + fator) for fator in he],
    }


def _arredondar(valores: dict[str, Any]) -> dict[str, Any]:
    resultado: dict[str, Any] = {}
    for chave, valor in valores.items():
        if isinstance(valor, dict):
            resultado[chave] = {item: _moeda(numero) for item, numero in valor.items()}
        elif isinstance(valor, list):
            resultado[chave] = [_moeda(numero) for numero in valor]
        else:
            resultado[chave] = _moeda(valor)
    return resultado


def compute_hh(hh_payload: Any) -> dict[str, Any]:
    """Calcula linha a linha e os totais do contrato; valores monetários em centavos."""
    try:
        return _compute_hh(normalize_hh(hh_payload))
    except ArithmeticError as exc:
        raise InvalidOrcamentoInputError(
            "HH: resultado calculado excede o limite permitido"
        ) from exc


def _compute_hh(hh: dict[str, Any]) -> dict[str, Any]:
    encargos = compute_encargos(hh)
    fator_encargos = encargos["total_percent"] / HUNDRED
    acumulado = {chave: ZERO for chave in (
        "total_a", "total_b", "total_c", "total_d", "total_mensal", "total_estimado",
    )}
    despesas = lucro = colaboradores = ZERO
    tributos = {item["id"]: ZERO for item in hh["tributos"]}
    grupos = []
    for grupo in hh["grupos"]:
        linhas = []
        subtotal_mensal = subtotal_estimado = quantidade_grupo = ZERO
        for funcao in grupo["funcoes"]:
            calculo = _calcular_funcao(funcao, hh, fator_encargos)
            quantidade = _d(funcao["quantidade"])
            for chave in acumulado:
                acumulado[chave] += calculo[chave]
            despesas += calculo["despesas_indiretas"] * quantidade
            lucro += calculo["lucro"] * quantidade
            for tributo_id, valor in calculo["tributos"].items():
                tributos[tributo_id] += valor * quantidade
            subtotal_mensal += calculo["total_mensal"]
            subtotal_estimado += calculo["total_estimado"]
            quantidade_grupo += quantidade
            linhas.append({"id": funcao["id"], **_arredondar(calculo)})
        colaboradores += quantidade_grupo
        grupos.append({
            "id": grupo["id"],
            "quantidade": float(quantidade_grupo),
            "total_mensal": _moeda(subtotal_mensal),
            "total_estimado": _moeda(subtotal_estimado),
            "funcoes": linhas,
        })
    meses = _d(hh["meses"])
    return {
        "encargos": {
            "grupos": {grupo: float(valor) for grupo, valor in encargos["grupos"].items()},
            "derivados": {chave: float(valor) for chave, valor in encargos["derivados"].items()},
            "total_percent": float(encargos["total_percent"]),
        },
        "grupos": grupos,
        "totais": {
            **{chave: _moeda(valor) for chave, valor in acumulado.items()},
            "despesas_indiretas_mensal": _moeda(despesas),
            "lucro_mensal": _moeda(lucro),
            "tributos_mensal": {chave: _moeda(valor) for chave, valor in tributos.items()},
            "colaboradores": float(colaboradores),
            "meses": float(meses),
        },
        "_decimal": {
            "diretos": (acumulado["total_a"] + acumulado["total_b"]) * meses,
            "despesas": despesas * meses,
            "lucro": lucro * meses,
            "estimado": acumulado["total_estimado"],
            "aliquota": sum((_d(item["percent"]) for item in hh["tributos"]), ZERO),
        },
    }


def compute_hh_summary(hh_payload: Any) -> dict[str, float]:
    """Resumo no mesmo formato do DFP, projetado para o prazo do contrato (em meses)."""
    calculo = compute_hh(hh_payload)
    bruto = calculo.pop("_decimal")
    totais = calculo["totais"]
    custos_totais = bruto["diretos"] + bruto["despesas"] + bruto["lucro"]
    return {
        "custos_diretos_total": _moeda(bruto["diretos"]),
        "custos_indiretos_total": _moeda(bruto["despesas"]),
        "lucro_total": _moeda(bruto["lucro"]),
        "custos_totais": _moeda(custos_totais),
        "aliquota_impostos_total": float(bruto["aliquota"]),
        "preco_total_faturamento": _moeda(bruto["estimado"]),
        "preco_por_area": 0.0,
        "valor_dia_colaborador": 0.0,
        "hh_total_mensal": totais["total_mensal"],
        "hh_total_estimado": totais["total_estimado"],
        "hh_meses": totais["meses"],
        "hh_colaboradores": totais["colaboradores"],
        "hh_encargos_percent": calculo["encargos"]["total_percent"],
    }
