"""Builders OOXML para slicers sobre tabelas (table slicers)."""

from dataclasses import dataclass
from uuid import uuid4

EXT_URI_SLICER_CACHE_DEFINITION = "{2F2917AC-EB37-4324-AD4E-5DD8C200BD13}"


@dataclass(frozen=True)
class ResolvedSlicerSpec:
    """Slicer já resolvido contra uma table OOXML existente."""

    cache_name: str
    slicer_name: str
    caption: str
    source_name: str
    table_id: int
    column_index: int


def sanitize_identifier(value: str) -> str:
    """Normaliza texto para identificador OOXML (ASCII seguro)."""
    out = []
    for idx, char in enumerate(value):
        if char.isalpha():
            out.append(char)
            continue
        if idx > 0 and (char.isdigit() or char == "."):
            out.append(char)
            continue
        out.append("_")
    normalized = "".join(out).strip("_")
    return normalized or "Campo"


def build_slicer_cache_xml(spec: ResolvedSlicerSpec) -> bytes:
    """Monta XML de `xl/slicerCaches/slicerCacheN.xml` para table slicer."""
    xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        "<slicerCacheDefinition "
        'xmlns="http://schemas.microsoft.com/office/spreadsheetml/2009/9/main" '
        'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
        'xmlns:x="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:x15="http://schemas.microsoft.com/office/spreadsheetml/2010/11/main" '
        'mc:Ignorable="x15" '
        f'name="{_xml_escape(spec.cache_name)}" '
        f'sourceName="{_xml_escape(spec.source_name)}">'
        "<extLst>"
        f'<x:ext uri="{EXT_URI_SLICER_CACHE_DEFINITION}">'
        f'<x15:tableSlicerCache tableId="{spec.table_id}" column="{spec.column_index}" '
        'sortOrder="ascending"/>'
        "</x:ext>"
        "</extLst>"
        "</slicerCacheDefinition>"
    )
    return xml.encode("utf-8")


def build_slicers_xml(specs: list[ResolvedSlicerSpec]) -> bytes:
    """Monta XML de `xl/slicers/slicerN.xml` com todos slicers da sheet."""
    rows = []
    for spec in specs:
        rows.append(
            "<slicer "
            f'name="{_xml_escape(spec.slicer_name)}" '
            f'cache="{_xml_escape(spec.cache_name)}" '
            f'caption="{_xml_escape(spec.caption)}" '
            'rowHeight="241300"/>'
        )
    xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<slicers xmlns="http://schemas.microsoft.com/office/spreadsheetml/2009/9/main">'
        f"{''.join(rows)}"
        "</slicers>"
    )
    return xml.encode("utf-8")


def build_drawing_slicer_anchor(
    *,
    c_nv_pr_id: int,
    slicer_name: str,
    from_col: int,
    from_row: int,
) -> str:
    """Monta anchor de slicer para `xl/drawings/drawing*.xml`."""
    creation_id = "{" + str(uuid4()).upper() + "}"
    return (
        "<xdr:oneCellAnchor>"
        "<xdr:from>"
        f"<xdr:col>{from_col}</xdr:col>"
        "<xdr:colOff>172356</xdr:colOff>"
        f"<xdr:row>{from_row}</xdr:row>"
        "<xdr:rowOff>90715</xdr:rowOff>"
        "</xdr:from>"
        '<xdr:ext cx="3429000" cy="1714500"/>'
        "<mc:AlternateContent "
        'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
        'xmlns:sle15="http://schemas.microsoft.com/office/drawing/2012/slicer">'
        '<mc:Choice Requires="sle15">'
        '<xdr:graphicFrame macro="">'
        "<xdr:nvGraphicFramePr>"
        f'<xdr:cNvPr id="{c_nv_pr_id}" name="{_xml_escape(slicer_name)}">'
        "<a:extLst>"
        '<a:ext uri="{FF2B5EF4-FFF2-40B4-BE49-F238E27FC236}">'
        '<a16:creationId xmlns:a16="http://schemas.microsoft.com/office/drawing/2014/main" '
        f'id="{creation_id}"/>'
        "</a:ext>"
        "</a:extLst>"
        "</xdr:cNvPr>"
        "<xdr:cNvGraphicFramePr/>"
        "</xdr:nvGraphicFramePr>"
        '<xdr:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/></xdr:xfrm>'
        "<a:graphic>"
        '<a:graphicData uri="http://schemas.microsoft.com/office/drawing/2010/slicer">'
        '<sle:slicer xmlns:sle="http://schemas.microsoft.com/office/drawing/2010/slicer" '
        f'name="{_xml_escape(slicer_name)}"/>'
        "</a:graphicData>"
        "</a:graphic>"
        "</xdr:graphicFrame>"
        "</mc:Choice>"
        '<mc:Fallback xmlns="">'
        '<xdr:sp macro="" textlink="">'
        "<xdr:nvSpPr>"
        f'<xdr:cNvPr id="{c_nv_pr_id}" name="{_xml_escape(slicer_name)}"/>'
        '<xdr:cNvSpPr txBox="1"/>'
        "<xdr:nvPr/>"
        "</xdr:nvSpPr>"
        "<xdr:spPr>"
        '<a:xfrm rot="0">'
        '<a:off x="2914650" y="152400"/>'
        '<a:ext cx="1828800" cy="2238375"/>'
        "</a:xfrm>"
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
        '<a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill>'
        '<a:ln w="1"><a:solidFill><a:prstClr val="black"/></a:solidFill></a:ln>'
        "</xdr:spPr>"
        "<xdr:txBody>"
        '<a:bodyPr vertOverflow="clip" horzOverflow="clip"/>'
        "<a:lstStyle/>"
        '<a:p><a:r><a:rPr lang="en-US" sz="1000"/>'
        "<a:t>This shape represents a table slicer.</a:t></a:r></a:p>"
        "</xdr:txBody>"
        "</xdr:sp>"
        "</mc:Fallback>"
        "</mc:AlternateContent>"
        '<xdr:clientData fLocksWithSheet="0" fPrintsWithSheet="1"/>'
        "</xdr:oneCellAnchor>"
    )


def _xml_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )
