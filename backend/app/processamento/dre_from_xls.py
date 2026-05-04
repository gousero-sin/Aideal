"""Gera DRE diretamente a partir dos relatórios .xls mensais.

Pipeline direto (sem DB):
  1. Lê cada .xls de mês (aba "Sheet" = entradas, "Planilha1" = saídas)
  2. Expande entradas em linhas de crédito + linhas de débito por imposto
  3. Expande saídas em linhas de débito
  4. Escreve em BD_FLUXO preservando o template (slicers, pivots, fórmulas)
  5. Oculta colunas da DRE dos meses sem dados
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterable
from xml.sax.saxutils import escape as _xml_escape

import xlrd

from ..templates.writer import TemplateWriter

logger = logging.getLogger(__name__)

# Impostos da aba de entradas (coluna no source → rótulo Natureza no BD_FLUXO).
# Ordem preserva a do template (IR, ISS, INSS, PIS, COFINS, CSLL, Tarifa).
_IMPOSTOS_ENTRADA: tuple[tuple[str, str], ...] = (
    ("IR (R$)", "IR"),
    ("ISS (R$)", "ISS"),
    ("INSS (R$)", "INSS"),
    ("PIS (R$)", "PIS"),
    ("COFINS (R$)", "COFINS"),
    ("CSLL (R$)", "CSLL"),
    ("Tarifa de Antecipação (R$)", "Tarifa de Antecipação"),
)

_ABA_ENTRADAS = "Sheet"
_ABA_SAIDAS = "Planilha1"

# Nomes abreviados dos 12 meses.
_MESES_NOMES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]

# Mapeamento dos pares (valor, %) por mês na aba DRE — espelha o template.
_PARES_MENSAIS_DRE: dict[int, tuple[str, str]] = {
    1: ("B", "C"),
    2: ("D", "E"),
    3: ("F", "G"),
    4: ("J", "K"),
    5: ("L", "M"),
    6: ("N", "O"),
    7: ("R", "S"),
    8: ("T", "U"),
    9: ("V", "W"),
    10: ("Z", "AA"),
    11: ("AB", "AC"),
    12: ("AD", "AE"),
}
_COLUNAS_TRIMESTRE_DRE = ["H", "I", "P", "Q", "X", "Y", "AF", "AG"]
_COLUNAS_ANO_DRE = ["AH", "AI"]


@dataclass(frozen=True)
class LinhaBD:
    """Linha canônica do BD_FLUXO (colunas 1-7; 8-18 ficam como fórmula)."""

    data: datetime
    historico: str
    credito: float | None
    debito: float | None
    natureza: str
    centro_custo: str


# ---------------------------------------------------------------------------- #
# Leitura e parsing do .xls                                                    #
# ---------------------------------------------------------------------------- #


def _xls_data_para_datetime(valor, datemode: int) -> datetime | None:
    """Converte célula de data (Excel serial float) em datetime."""
    if valor is None or valor == "":
        return None
    if isinstance(valor, datetime):
        return valor
    if isinstance(valor, date):
        return datetime(valor.year, valor.month, valor.day)
    if isinstance(valor, (int, float)):
        try:
            tup = xlrd.xldate_as_tuple(float(valor), datemode)
            return datetime(*tup) if tup[0] else None
        except (xlrd.XLDateError, ValueError):
            return None
    if isinstance(valor, str):
        s = valor.strip()
        if not s:
            return None
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
            try:
                return datetime.strptime(s, fmt)
            except ValueError:
                continue
    return None


def _limpa_texto(valor) -> str:
    if valor is None:
        return ""
    return str(valor).replace("\n", " ").strip()


def _numero(valor) -> float:
    if valor is None or valor == "":
        return 0.0
    try:
        return float(valor)
    except (TypeError, ValueError):
        return 0.0


def _encontrar_header(sheet: xlrd.sheet.Sheet, palavras_chave: Iterable[str]) -> int | None:
    """Retorna o índice da linha de cabeçalho (contém todas as palavras-chave)."""
    alvo = {p.lower() for p in palavras_chave}
    for r in range(min(sheet.nrows, 20)):
        valores = {_limpa_texto(sheet.cell_value(r, c)).lower() for c in range(sheet.ncols)}
        if alvo.issubset(valores):
            return r
    return None


def _mapear_colunas(sheet: xlrd.sheet.Sheet, header_row: int) -> dict[str, int]:
    """Retorna dict nome_coluna_normalizado → índice."""
    mapa: dict[str, int] = {}
    for c in range(sheet.ncols):
        nome = _limpa_texto(sheet.cell_value(header_row, c))
        if nome:
            mapa[nome] = c
    return mapa


def _parse_aba_entradas(sheet: xlrd.sheet.Sheet, datemode: int) -> list[LinhaBD]:
    """Expande a aba de entradas em linhas BD (crédito + débito por imposto)."""
    header_row = _encontrar_header(
        sheet, ["Cliente", "Número", "Emissão", "C. gerencial", "Vlr.bruto (R$)"]
    )
    if header_row is None:
        logger.warning("Aba '%s': cabeçalho de entradas não encontrado", sheet.name)
        return []

    cols = _mapear_colunas(sheet, header_row)
    col_cliente = cols.get("Cliente")
    col_numero = cols.get("Número")
    col_emissao = cols.get("Emissão")
    col_obra = cols.get("Obra/ Centro custo") or cols.get("Obra/Centro custo")
    col_natureza = cols.get("C. gerencial")
    col_bruto = cols.get("Vlr.bruto (R$)")

    obrigatorias = {
        "Cliente": col_cliente,
        "Número": col_numero,
        "Emissão": col_emissao,
        "Obra/Centro custo": col_obra,
        "C. gerencial": col_natureza,
        "Vlr.bruto (R$)": col_bruto,
    }
    faltando = [k for k, v in obrigatorias.items() if v is None]
    if faltando:
        logger.warning("Aba '%s' sem colunas: %s", sheet.name, faltando)
        return []

    impostos_idx: list[tuple[int, str]] = []
    for titulo, rotulo in _IMPOSTOS_ENTRADA:
        idx = cols.get(titulo)
        if idx is not None:
            impostos_idx.append((idx, rotulo))

    linhas: list[LinhaBD] = []
    for r in range(header_row + 1, sheet.nrows):
        data_dt = _xls_data_para_datetime(sheet.cell_value(r, col_emissao), datemode)
        if data_dt is None:
            continue
        cliente = _limpa_texto(sheet.cell_value(r, col_cliente))
        if not cliente:
            continue
        numero = _limpa_texto(sheet.cell_value(r, col_numero))
        historico = f"{numero} - {cliente}" if numero else cliente
        obra = _limpa_texto(sheet.cell_value(r, col_obra))
        natureza = _limpa_texto(sheet.cell_value(r, col_natureza))
        bruto = _numero(sheet.cell_value(r, col_bruto))

        if bruto > 0 and natureza:
            linhas.append(
                LinhaBD(
                    data=data_dt,
                    historico=historico,
                    credito=bruto,
                    debito=None,
                    natureza=natureza,
                    centro_custo=obra,
                )
            )

        for col_imposto, rotulo in impostos_idx:
            val = _numero(sheet.cell_value(r, col_imposto))
            if val > 0:
                linhas.append(
                    LinhaBD(
                        data=data_dt,
                        historico=historico,
                        credito=None,
                        debito=val,
                        natureza=rotulo,
                        centro_custo=obra,
                    )
                )

    return linhas


def _parse_aba_saidas(sheet: xlrd.sheet.Sheet, datemode: int) -> list[LinhaBD]:
    """Expande a aba de saídas em linhas BD (débito único por linha)."""
    header_row = _encontrar_header(
        sheet, ["Fornecedor", "Emissão", "C. gerencial", "Total líquido (R$)"]
    )
    if header_row is None:
        logger.warning("Aba '%s': cabeçalho de saídas não encontrado", sheet.name)
        return []

    cols = _mapear_colunas(sheet, header_row)
    col_fornecedor = cols.get("Fornecedor")
    col_numero = cols.get("Número")
    col_emissao = cols.get("Emissão")
    col_obra = cols.get("Obra/ Centro custo") or cols.get("Obra/Centro custo")
    col_natureza = cols.get("C. gerencial")
    col_total = cols.get("Total líquido (R$)")

    obrigatorias = {
        "Fornecedor": col_fornecedor,
        "Emissão": col_emissao,
        "Obra/Centro custo": col_obra,
        "C. gerencial": col_natureza,
        "Total líquido (R$)": col_total,
    }
    faltando = [k for k, v in obrigatorias.items() if v is None]
    if faltando:
        logger.warning("Aba '%s' sem colunas: %s", sheet.name, faltando)
        return []

    linhas: list[LinhaBD] = []
    for r in range(header_row + 1, sheet.nrows):
        data_dt = _xls_data_para_datetime(sheet.cell_value(r, col_emissao), datemode)
        if data_dt is None:
            continue
        fornecedor = _limpa_texto(sheet.cell_value(r, col_fornecedor))
        if not fornecedor:
            continue
        numero = _limpa_texto(sheet.cell_value(r, col_numero)) if col_numero is not None else ""
        historico = f"{numero} - {fornecedor}" if numero else fornecedor
        obra = _limpa_texto(sheet.cell_value(r, col_obra))
        natureza = _limpa_texto(sheet.cell_value(r, col_natureza))
        total = _numero(sheet.cell_value(r, col_total))
        if total <= 0 or not natureza:
            continue
        linhas.append(
            LinhaBD(
                data=data_dt,
                historico=historico,
                credito=None,
                debito=total,
                natureza=natureza,
                centro_custo=obra,
            )
        )
    return linhas


def ler_xls_mes(path: Path) -> list[LinhaBD]:
    """Lê um .xls mensal e devolve linhas BD_FLUXO expandidas."""
    path = Path(path)
    wb = xlrd.open_workbook(str(path), formatting_info=False)
    linhas: list[LinhaBD] = []

    for sheet_name in wb.sheet_names():
        sheet = wb.sheet_by_name(sheet_name)
        if sheet_name.strip().lower() == _ABA_ENTRADAS.lower():
            linhas.extend(_parse_aba_entradas(sheet, wb.datemode))
        elif sheet_name.strip().lower() == _ABA_SAIDAS.lower():
            linhas.extend(_parse_aba_saidas(sheet, wb.datemode))

    logger.info("%s: %d linhas BD extraídas", path.name, len(linhas))
    return linhas


# ---------------------------------------------------------------------------- #
# Geração do BD_FLUXO em 18 colunas (fórmulas espelhando o template)           #
# ---------------------------------------------------------------------------- #

_EXCEL_EPOCH = datetime(1899, 12, 30)

# Style IDs extraídos do template BD_FLUXO row 2 (preservam formatação original).
_S_DATA = "19"  # A — data (formato dd/mm/aaaa)
_S_TEXTO = "16"  # B, J, K, L — texto geral
_S_NUMERO = "20"  # C, D, E — valores monetários
_S_NATUREZA = "1"  # F, G, N, O, P, Q, R — texto categorias/fórmulas
_S_YEAR = "63"  # H — YEAR()
_S_MONTH = "64"  # I — MONTH()
_S_SALDO = "6"  # M — saldo C-D


def _dt_para_serial(dt: datetime) -> int:
    """Converte datetime para serial Excel (epoch 1899-12-30)."""
    return (dt - _EXCEL_EPOCH).days


def _cel_num(ref: str, s: str, valor: float | None) -> str:
    if valor is None:
        return f'<c r="{ref}" s="{s}"/>'
    return f'<c r="{ref}" s="{s}"><v>{valor}</v></c>'


def _cel_str(ref: str, s: str, texto: str) -> str:
    if not texto:
        return f'<c r="{ref}" s="{s}"/>'
    return f'<c r="{ref}" s="{s}" t="inlineStr"><is><t>{_xml_escape(texto)}</t></is></c>'


def _cel_formula(ref: str, s: str, formula: str) -> str:
    return f'<c r="{ref}" s="{s}"><f>{_xml_escape(formula)}</f></c>'


def _gerar_sheetdata_bd_fluxo(linhas: list[LinhaBD]) -> str:
    """Gera <sheetData> completo para BD_FLUXO em XML puro.

    Usa style IDs do template para garantir compatibilidade com styles.xml
    preservado. Escreve strings como inlineStr (evita dependência de sharedStrings).
    Preserva o header (row 1) exatamente como no template — é injetado apenas
    nas rows de dados (2..N).
    """
    # Retorna apenas as rows de dados (sem tag <sheetData> — gerenciada pelo writer).
    partes = []
    for idx, linha in enumerate(linhas):
        r = idx + 2  # row 1 = header (preservado do template)
        serial = _dt_para_serial(linha.data)
        credito = linha.credito
        debito = linha.debito

        cells = "".join(
            [
                f'<c r="A{r}" s="{_S_DATA}"><v>{serial}</v></c>',
                _cel_str(f"B{r}", _S_TEXTO, linha.historico),
                _cel_num(f"C{r}", _S_NUMERO, credito),
                _cel_num(f"D{r}", _S_NUMERO, debito),
                f'<c r="E{r}" s="{_S_NUMERO}"/>',
                _cel_str(f"F{r}", _S_NATUREZA, linha.natureza),
                _cel_str(f"G{r}", _S_NATUREZA, linha.centro_custo),
                _cel_formula(f"H{r}", _S_YEAR, f"YEAR(A{r})"),
                _cel_formula(f"I{r}", _S_MONTH, f"MONTH(A{r})"),
                _cel_formula(f"J{r}", _S_TEXTO, f"INDEX(Meses[],BD_FLUXO!I{r},2)"),
                f'<c r="K{r}" s="{_S_TEXTO}"/>',
                f'<c r="L{r}" s="{_S_TEXTO}"/>',
                _cel_formula(f"M{r}", _S_SALDO, f"C{r}-D{r}"),
                _cel_formula(f"N{r}", _S_NATUREZA, f"VLOOKUP(F{r},PLANO_CONTAS!A:D,2,0)"),
                _cel_formula(f"O{r}", _S_NATUREZA, f"VLOOKUP(F{r},PLANO_CONTAS!$A:$D,3,FALSE)"),
                _cel_formula(f"P{r}", _S_NATUREZA, f"VLOOKUP(F{r},PLANO_CONTAS!$A:$D,4,FALSE)"),
                _cel_formula(f"Q{r}", _S_NATUREZA, f"VLOOKUP(F{r},PLANO_CONTAS!$A:$E,5,FALSE)"),
                _cel_formula(f"R{r}", _S_NATUREZA, "YEAR(BD_FLUXO1[[#This Row],[Data]])"),
            ]
        )
        partes.append(f'<row r="{r}" spans="1:18" x14ac:dyDescent="0.3">{cells}</row>')

    return "".join(partes)


def _linha_para_18_colunas(linha: LinhaBD, row_idx: int) -> list:
    """Monta uma linha BD_FLUXO completa (18 colunas) com fórmulas nas col 8-18."""
    r = row_idx
    return [
        linha.data,
        linha.historico,
        linha.credito,
        linha.debito,
        None,  # Saldo
        linha.natureza,
        linha.centro_custo,
        f"=YEAR(A{r})",
        f"=MONTH(A{r})",
        f"=INDEX(Meses[],BD_FLUXO!I{r},2)",
        None,  # Banco
        None,  # Empresa
        f"=C{r}-D{r}",
        f"=VLOOKUP(F{r},PLANO_CONTAS!A:D,2,0)",
        f"=VLOOKUP(F{r},PLANO_CONTAS!$A:$D,3,FALSE)",
        f"=VLOOKUP(F{r},PLANO_CONTAS!$A:$D,4,FALSE)",
        f"=VLOOKUP(F{r},PLANO_CONTAS!$A:$E,5,FALSE)",
        "=YEAR(BD_FLUXO1[[#This Row],[Data]])",
    ]


# ---------------------------------------------------------------------------- #
# Orquestração                                                                 #
# ---------------------------------------------------------------------------- #


def gerar_dre(
    arquivos_xls: list[Path],
    template_path: Path,
    output_path: Path,
    ano: int,
) -> Path:
    """Gera arquivo DRE preenchendo BD_FLUXO e ocultando meses sem dados na DRE.

    Args:
        arquivos_xls: relatórios mensais (.xls) a consolidar
        template_path: template DRE AIDEAL (.xlsx)
        output_path: destino do arquivo gerado
        ano: ano de referência (meses fora deste ano são ignorados)
    """
    todas_linhas: list[LinhaBD] = []
    for p in arquivos_xls:
        todas_linhas.extend(ler_xls_mes(Path(p)))

    # Filtra por ano e ordena por data (igual ao template).
    todas_linhas = [linha for linha in todas_linhas if linha.data.year == ano]
    todas_linhas.sort(key=lambda linha: linha.data)

    meses_com_dados = sorted({linha.data.month for linha in todas_linhas})
    logger.info(
        "Meses com dados: %s (%d linhas totais)",
        [_MESES_NOMES[m - 1] for m in meses_com_dados],
        len(todas_linhas),
    )

    writer = TemplateWriter(Path(template_path))
    writer.abrir()
    try:
        linhas_bd_18 = [
            _linha_para_18_colunas(linha, idx + 2) for idx, linha in enumerate(todas_linhas)
        ]
        ultima_linha = 1 + len(linhas_bd_18) if linhas_bd_18 else 1

        # BD_FLUXO: XML puro — bypassa openpyxl completamente.
        # Style IDs, row attrs e rels do template são preservados byte a byte.
        # Evita conflito de estilo entre openpyxl e styles.xml do template.
        if linhas_bd_18:
            sheetdata_xml = _gerar_sheetdata_bd_fluxo(todas_linhas)
            writer.substituir_sheetdata_xml_puro("BD_FLUXO", sheetdata_xml)
            writer.ajustar_tabela_range(
                "BD_FLUXO",
                "BD_FLUXO1",
                linha_fim=ultima_linha,
            )

        # Remove slicers do pacote final e força rebuild de cache no próximo open.
        writer.remover_slicers()
        writer.esvaziar_pivot_cache_records()

        # DRE: oculta colunas dos meses sem dados (patch OOXML direto).
        _ajustar_visibilidade_dre(writer, meses_com_dados)

        writer.salvar(Path(output_path))
    finally:
        writer.fechar()

    logger.info("DRE gerado: %s", output_path)
    return Path(output_path)


def _ajustar_visibilidade_dre(
    writer: TemplateWriter,
    meses_com_dados: list[int],
) -> None:
    """Oculta na aba DRE as colunas dos meses que não têm dados."""

    mcd_set = set(meses_com_dados)
    colunas_ocultar: list[str] = []
    colunas_exibir: list[str] = []

    for mes in range(1, 13):
        col_val, col_pct = _PARES_MENSAIS_DRE[mes]
        for letra in (col_val, col_pct):
            if mes in mcd_set:
                colunas_exibir.append(letra)
            else:
                colunas_ocultar.append(letra)

    # Trimestres permanecem ocultos; AH/AI (ANO) visíveis.
    colunas_ocultar.extend(_COLUNAS_TRIMESTRE_DRE)
    colunas_exibir.extend(c for c in _COLUNAS_ANO_DRE if c not in colunas_exibir)

    writer.ocultar_colunas_xml_patch("DRE", colunas_ocultar, True)
    writer.ocultar_colunas_xml_patch("DRE", colunas_exibir, False)


# ---------------------------------------------------------------------------- #
# CLI                                                                          #
# ---------------------------------------------------------------------------- #


def _main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Gera DRE a partir dos .xls mensais")
    parser.add_argument("--template", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--ano", required=True, type=int)
    parser.add_argument("xls", nargs="+", type=Path, help="Arquivos .xls mensais")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    gerar_dre(
        arquivos_xls=args.xls,
        template_path=args.template,
        output_path=args.output,
        ano=args.ano,
    )


if __name__ == "__main__":
    _main()
