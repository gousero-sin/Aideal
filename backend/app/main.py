"""AIDEAL GoFlowOS MVP — API FastAPI principal."""

import logging
import math
import tempfile
from contextlib import asynccontextmanager
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask

from .access_control import (
    AuthenticatedSession,
    CsrfSession,
    clear_session_cookies,
    enforce_login_rate_limit,
    get_identity_service,
    get_orcamento_service,
    record_login_result,
    require_permission,
    require_permission_with_csrf,
    require_permissions,
    require_permissions_with_csrf,
    session_payload,
    set_session_cookie,
    token_from_request,
)
from .config import settings
from .contracts.common import FlowType
from .contracts.persistence import DREIndicadoresManuais, FluxoIndicadoresManuais
from .contracts.processamento import DREProcessamentoResponse
from .db.connection import db
from .db.manager import run_migrations
from .identity import (
    InvalidCredentialsError,
    InvalidIdentityInputError,
    LastOwnerError,
    UnknownPermissionError,
    UsernameAlreadyExistsError,
    UserNotFoundError,
)
from .ingestao.dre_ingestao import DREIngestaoService
from .ingestao.fluxo_caixa_ingestao import FluxoCaixaIngestaoService
from .ingestao.parser import ExcelParser
from .orcamento import (
    CodigoAlreadyExistsError,
    InvalidOrcamentoInputError,
    InvalidSituacaoTransitionError,
    OrcamentoNotFoundError,
    RevisaoNotFoundError,
    compute_dfp_summary,
    get_dfp_window_schema,
)
from .processamento import DREProcessamentoService, FluxoCaixaProcessamentoService
from .processamento.competencia import CompetenciaDetectorService
from .processamento.dashboard import DashboardResumoService
from .processamento.dre_geracao import DREGeracaoService
from .processamento.dre_geracao_completa import DREGeracaoCompletaService
from .processamento.fluxo_caixa_db import FluxoCaixaGeracaoService
from .processamento.paineis import PainelDREService, PainelFluxoCaixaService
from .runtime_compat import check_runtime_compatibility, require_runtime_compatibility
from .templates.writer import TemplateWriter
from .validacao.validators import DREValidator, FluxoCaixaValidator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


EXCEL_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class AdminLoginRequest(BaseModel):
    username: str
    password: str

    model_config = {"extra": "forbid"}


class CreateUserRequest(BaseModel):
    username: str
    display_name: str
    password: str
    permissions: list[str]
    active: bool = True
    must_change_password: bool = True

    model_config = {"extra": "forbid"}


class UpdateUserRequest(BaseModel):
    display_name: str | None = None
    password: str | None = None
    permissions: list[str] | None = None
    active: bool | None = None

    model_config = {"extra": "forbid"}


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    model_config = {"extra": "forbid"}


class RevisaoOrcamentoRequest(BaseModel):
    """Cabeçalho canônico de Orçamento.md; obrigatoriedade é validada no domínio."""

    escopo: str | None = None
    modalidade: Literal["HH", "Spot", "Rotina", "m²"] | None = None
    regiao: str | None = None
    prazo_execucao_dias: int | None = Field(default=None, strict=True, ge=1)
    saldo_mao_de_obra: float | None = Field(
        default=None, ge=0, le=1_000_000_000, allow_inf_nan=False
    )
    dados_contratante: str | None = None
    mobilizacao: str | None = None
    desmobilizacao: str | None = None
    area_unidade_base: str | None = None
    regime_tributario: str | None = None
    dfp: dict[str, Any] | None = None
    motivo: str | None = None

    model_config = {"extra": "forbid"}


class CreateOrcamentoRequest(RevisaoOrcamentoRequest):
    contratante: str

    model_config = {"extra": "forbid"}


class UpdateCabecalhoOrcamentoRequest(BaseModel):
    """Edição parcial dos campos pertencentes à revisão do orçamento."""

    escopo: str | None = None
    modalidade: Literal["HH", "Spot", "Rotina", "m²"] | None = None
    regiao: str | None = None
    prazo_execucao_dias: int | None = Field(default=None, strict=True, ge=1)
    saldo_mao_de_obra: float | None = Field(
        default=None, ge=0, le=1_000_000_000, allow_inf_nan=False
    )
    dados_contratante: str | None = None
    mobilizacao: str | None = None
    desmobilizacao: str | None = None
    area_unidade_base: str | None = None
    regime_tributario: str | None = None
    dfp: dict[str, Any] | None = None

    model_config = {"extra": "forbid"}


class SituacaoRevisaoRequest(BaseModel):
    situacao: Literal["rascunho", "em_revisao", "pronto_para_proposta", "emitido", "inativo"]
    motivo: str

    model_config = {"extra": "forbid"}


def _ensure_runtime_dirs() -> None:
    """Cria diretórios operacionais necessários para produção."""
    for path in (settings.logs_dir, settings.temp_dir, settings.output_dir, settings.data_dir):
        path.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Inicialização de produção: diretórios e migrações devem estar íntegros."""
    require_runtime_compatibility()
    _ensure_runtime_dirs()
    run_migrations()
    get_identity_service()
    logger.info("Migrações executadas com sucesso")
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description="Motor de consolidação financeira DRE e Fluxo de Caixa",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)

# Inicializa serviços
dre_service = DREProcessamentoService()
fluxo_service = FluxoCaixaProcessamentoService()
dre_ingestao_service = DREIngestaoService()
dre_geracao_service = DREGeracaoService()
dre_geracao_completa_service = DREGeracaoCompletaService()
fluxo_ingestao_service = FluxoCaixaIngestaoService()
fluxo_geracao_db_service = FluxoCaixaGeracaoService()
dashboard_resumo_service = DashboardResumoService()
dre_painel_service = PainelDREService()
fluxo_painel_service = PainelFluxoCaixaService()
competencia_detector_service = CompetenciaDetectorService()


def _nome_upload_seguro(arquivo: UploadFile) -> str:
    """Extrai apenas o nome base do upload enviado pelo navegador."""
    raw_name = arquivo.filename or ""
    name = raw_name.replace("\\", "/").split("/")[-1].strip()
    if not name:
        raise HTTPException(status_code=400, detail="Nome de arquivo não informado.")
    return name


def _validar_extensao_upload(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix not in settings.allowed_upload_extensions_set:
        allowed = ", ".join(sorted(settings.allowed_upload_extensions_set))
        raise HTTPException(
            status_code=400,
            detail=f"Formato de arquivo não permitido: {suffix or 'sem extensão'}. Use {allowed}.",
        )
    return suffix


def _validar_quantidade_uploads(uploads: list[UploadFile]) -> None:
    if len(uploads) > settings.max_files_per_batch:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Quantidade máxima de arquivos excedida: {settings.max_files_per_batch} por lote."
            ),
        )


async def _salvar_upload_temporario(arquivo: UploadFile) -> Path:
    """Salva upload em chunks, validando extensão e tamanho máximo."""
    filename = _nome_upload_seguro(arquivo)
    suffix = _validar_extensao_upload(filename)
    settings.temp_dir.mkdir(parents=True, exist_ok=True)

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=str(settings.temp_dir))
    tmp_path = Path(tmp.name)
    total_bytes = 0
    try:
        while True:
            chunk = await arquivo.read(settings.upload_chunk_size_bytes)
            if not chunk:
                break
            total_bytes += len(chunk)
            if total_bytes > settings.max_upload_size_bytes:
                raise HTTPException(
                    status_code=413,
                    detail=(
                        f"Arquivo excede o limite de {settings.max_upload_size_mb} MB por arquivo."
                    ),
                )
            tmp.write(chunk)
    except Exception:
        tmp.close()
        tmp_path.unlink(missing_ok=True)
        raise
    tmp.close()
    return tmp_path


def _exigir_confirmacao(confirmar: bool) -> None:
    if not confirmar:
        raise HTTPException(
            status_code=400,
            detail="Confirmação explícita obrigatória para executar operação administrativa.",
        )


def _validar_competencia_admin(ano: int, mes: int) -> None:
    if ano < 2000 or ano > 2100:
        raise HTTPException(status_code=400, detail="Ano deve estar entre 2000 e 2100.")
    if mes < 1 or mes > 12:
        raise HTTPException(status_code=400, detail="Mês deve estar entre 1 e 12.")


def _valor_monetario_admin(nome: str, valor: float) -> Decimal:
    if not math.isfinite(valor) or valor < 0:
        raise HTTPException(status_code=400, detail=f"{nome} deve ser um valor maior ou igual a 0.")
    return Decimal(str(valor))


def _payload_indicadores_manuais(
    registro: DREIndicadoresManuais,
    existe: bool,
) -> dict:
    return {
        "success": True,
        "existe": existe,
        "ano": registro.competencia_ano,
        "mes": registro.competencia_mes,
        "competencia": f"{registro.competencia_mes:02d}/{registro.competencia_ano}",
        "indicadores": {
            "contas_pagar": float(registro.contas_pagar),
            "contas_receber": float(registro.contas_receber),
            "total_impostos_retidos_acima_meta": float(registro.total_impostos_retidos_acima_meta),
            "total_impostos_retidos": float(registro.total_impostos_retidos),
        },
        "created_at": registro.created_at.isoformat() if existe else None,
        "updated_at": registro.updated_at.isoformat() if existe else None,
    }


def _payload_indicadores_manuais_fluxo(
    registro: FluxoIndicadoresManuais,
    existe: bool,
) -> dict:
    return {
        "success": True,
        "existe": existe,
        "ano": registro.competencia_ano,
        "indicadores": {
            "saldo_ano_anterior": float(registro.saldo_ano_anterior),
        },
        "created_at": registro.created_at.isoformat() if existe else None,
        "updated_at": registro.updated_at.isoformat() if existe else None,
    }


def _resolver_output_xlsx(arquivo_nome: str) -> Path:
    nome = arquivo_nome.replace("\\", "/")
    candidato = Path(nome)
    if candidato.is_absolute() or candidato.name != nome or ".." in candidato.parts:
        raise HTTPException(status_code=400, detail="Nome de arquivo inválido.")
    if candidato.suffix.lower() != ".xlsx":
        raise HTTPException(status_code=400, detail="Download permitido apenas para .xlsx.")

    output_dir = settings.output_dir.resolve()
    arquivo_path = (output_dir / candidato.name).resolve()
    try:
        arquivo_path.relative_to(output_dir)
    except ValueError:
        raise HTTPException(status_code=400, detail="Nome de arquivo inválido.")

    if not arquivo_path.exists():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    return arquivo_path


def _excel_file_response(
    path: Path,
    filename: str | None = None,
    *,
    remove_after_send: bool = False,
) -> FileResponse:
    if path.suffix.lower() != ".xlsx":
        raise HTTPException(status_code=400, detail="Download permitido apenas para .xlsx.")
    return FileResponse(
        path=str(path),
        filename=filename or path.name,
        media_type=EXCEL_MEDIA_TYPE,
        background=(BackgroundTask(path.unlink, missing_ok=True) if remove_after_send else None),
    )


@app.get("/")
async def root():
    index_path = settings.frontend_dist_dir / "index.html"
    if index_path.exists():
        return FileResponse(path=str(index_path), media_type="text/html")
    return {
        "app": settings.app_name,
        "version": settings.version,
        "fluxos": ["dre", "fluxo_caixa"],
        "status": "operacional",
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/ready")
async def ready():
    checks = {
        "database": False,
        "identity_database": False,
        "orcamento_database": False,
        "templates": False,
        "directories": False,
        "excel_runtime": False,
    }
    try:
        with db.get_connection() as conn:
            conn.execute("SELECT 1").fetchone()
        checks["database"] = True
    except Exception as exc:
        logger.error("Readiness database check failed: %s", exc)

    try:
        identity_service = get_identity_service()
        with identity_service.repository.database.connection() as connection:
            connection.execute("SELECT 1").fetchone()
        checks["identity_database"] = True
    except Exception as exc:
        logger.error("Readiness identity database check failed: %s", exc)

    try:
        with get_orcamento_service().repository.database.connection() as connection:
            connection.execute("SELECT 1").fetchone()
        checks["orcamento_database"] = True
    except Exception as exc:
        logger.error("Readiness orcamento database check failed: %s", exc)

    checks["templates"] = (
        settings.template_dre_path.exists() and settings.template_fluxo_path.exists()
    )
    checks["directories"] = all(
        path.exists() and path.is_dir()
        for path in (settings.logs_dir, settings.temp_dir, settings.output_dir, settings.data_dir)
    )
    runtime_mismatches = check_runtime_compatibility()
    checks["excel_runtime"] = not runtime_mismatches
    if runtime_mismatches:
        logger.error("Readiness Excel runtime check failed: %s", runtime_mismatches)

    if not all(checks.values()):
        detail = {"status": "not_ready", "checks": checks}
        if runtime_mismatches:
            detail["excel_runtime_mismatches"] = [
                {
                    "package": item.package,
                    "expected": item.expected,
                    "installed": item.installed,
                }
                for item in runtime_mismatches
            ]
        raise HTTPException(status_code=503, detail=detail)
    return {"status": "ready", "checks": checks}


def _authenticate(
    payload: AdminLoginRequest,
    request: Request,
    response: Response,
    *,
    legacy: bool = False,
):
    enforce_login_rate_limit(request, payload.username)
    try:
        service = get_identity_service()
        user = service.authenticate(payload.username, payload.password)
        credentials = service.create_session(user.id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except InvalidCredentialsError as exc:
        record_login_result(request, payload.username, authenticated=False)
        raise HTTPException(status_code=401, detail="Credenciais inválidas.") from exc
    record_login_result(request, payload.username, authenticated=True)
    set_session_cookie(response, credentials.token, include_legacy=legacy)
    return service, credentials, user


@app.post("/api/auth/login")
async def auth_login(payload: AdminLoginRequest, request: Request, response: Response):
    """Cria uma sessão global, opaca e revogável para o GoFlow."""
    service, credentials, _user = _authenticate(payload, request, response)
    return session_payload(service, credentials.token)


@app.get("/api/auth/session")
async def auth_session(request: Request, _session: AuthenticatedSession):
    """Retorna identidade, acessos e módulos visíveis da sessão atual."""
    token = token_from_request(request)
    return session_payload(get_identity_service(), str(token))


@app.post("/api/auth/logout")
async def auth_logout(request: Request, response: Response, session: CsrfSession):
    """Revoga a sessão no servidor e remove seus cookies."""
    get_identity_service().revoke_session(
        token_from_request(request), actor_user_id=session.user.id
    )
    clear_session_cookies(response)
    return {"authenticated": False}


@app.post("/api/auth/change-password")
async def change_password(
    payload: ChangePasswordRequest,
    response: Response,
    session: CsrfSession,
):
    """Substitui a senha temporária e renova a sessão do usuário."""
    try:
        service = get_identity_service()
        user = service.change_own_password(
            session.user.id,
            current_password=payload.current_password,
            new_password=payload.new_password,
        )
        credentials = service.create_session(user.id)
    except InvalidCredentialsError as exc:
        raise HTTPException(status_code=401, detail="Senha atual inválida.") from exc
    except InvalidIdentityInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    set_session_cookie(response, credentials.token)
    return session_payload(service, credentials.token)


@app.get("/api/admin/users")
async def list_users(
    session=Depends(require_permission("users.manage")),
):
    """Lista usuários e permissões para administradores autorizados."""
    users = get_identity_service().list_users(actor_user_id=session.user.id)
    return {"users": [user.to_dict() for user in users]}


def _raise_identity_http_error(exc: Exception) -> None:
    if isinstance(exc, UserNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, (UsernameAlreadyExistsError, LastOwnerError)):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if isinstance(exc, (InvalidIdentityInputError, UnknownPermissionError)):
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if isinstance(exc, InvalidCredentialsError):
        raise HTTPException(status_code=403, detail="Permissão insuficiente.") from exc
    raise exc


@app.post("/api/admin/users", status_code=201)
async def create_user(payload: CreateUserRequest, session: CsrfSession):
    """Cria um usuário com negação padrão e permissões explícitas."""
    try:
        user = get_identity_service().create_user(
            username=payload.username,
            display_name=payload.display_name,
            password=payload.password,
            permissions=tuple(payload.permissions),
            active=payload.active,
            must_change_password=payload.must_change_password,
            actor_user_id=session.user.id,
        )
        return user.to_dict()
    except (
        InvalidCredentialsError,
        InvalidIdentityInputError,
        UnknownPermissionError,
        UsernameAlreadyExistsError,
    ) as exc:
        _raise_identity_http_error(exc)


@app.patch("/api/admin/users/{user_id}")
async def update_user(user_id: str, payload: UpdateUserRequest, session: CsrfSession):
    """Atualiza dados e substitui a lista completa de acessos de um usuário."""
    try:
        service = get_identity_service()
        user = service.update_user_access(
            user_id,
            display_name=payload.display_name,
            active=payload.active,
            password=payload.password,
            permissions=payload.permissions,
            actor_user_id=session.user.id,
        )
        return user.to_dict()
    except (
        InvalidCredentialsError,
        InvalidIdentityInputError,
        LastOwnerError,
        UnknownPermissionError,
        UserNotFoundError,
    ) as exc:
        _raise_identity_http_error(exc)


def _orcamento_payload(service, orcamento, agora) -> dict:
    """Acrescenta ao payload o que falta no cabeçalho para avançar a revisão."""
    corpo = orcamento.to_dict(agora=agora)
    atual = orcamento.revisao_atual
    corpo["cabecalho_pendente"] = list(service.cabecalho_pendente(atual)) if atual else []
    corpo["dfp_summary"] = compute_dfp_summary(atual.dfp if atual else None)
    return corpo


def _raise_orcamento_http_error(exc: Exception) -> None:
    if isinstance(exc, (OrcamentoNotFoundError, RevisaoNotFoundError)):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, CodigoAlreadyExistsError):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if isinstance(exc, (InvalidOrcamentoInputError, InvalidSituacaoTransitionError)):
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    raise exc


@app.get("/api/orcamento/orcamentos")
async def listar_orcamentos(_session=Depends(require_permission("orcamento.view"))):
    """Lista orçamentos com a revisão atual de cada um."""
    service = get_orcamento_service()
    agora = service.clock()
    return {
        "orcamentos": [
            _orcamento_payload(service, item, agora) for item in service.list_orcamentos()
        ],
    }


@app.get("/api/orcamento/schema")
async def obter_schema_orcamento(
    calculation_version: int = Query(default=2, ge=1, le=2),
    _session=Depends(require_permission("orcamento.view")),
):
    """Retorna o catálogo DFP usado para montar a UI do orçamento."""
    return get_dfp_window_schema(calculation_version=calculation_version)


@app.post("/api/orcamento/orcamentos", status_code=201)
async def criar_orcamento(
    payload: CreateOrcamentoRequest,
    session=Depends(require_permissions_with_csrf("orcamento.view", "orcamento.edit")),
):
    """Cria o orçamento com código sequencial e a revisão 0 em rascunho."""
    service = get_orcamento_service()
    try:
        orcamento = service.create_orcamento(payload.model_dump(), autor_user_id=session.user.id)
    except InvalidOrcamentoInputError as exc:
        _raise_orcamento_http_error(exc)
    return _orcamento_payload(service, orcamento, service.clock())


@app.get("/api/orcamento/orcamentos/{orcamento_id}")
async def obter_orcamento(
    orcamento_id: str,
    _session=Depends(require_permission("orcamento.view")),
):
    """Retorna o orçamento com todo o histórico de revisões preservado."""
    service = get_orcamento_service()
    try:
        orcamento = service.get_orcamento(orcamento_id)
    except OrcamentoNotFoundError as exc:
        _raise_orcamento_http_error(exc)
    return _orcamento_payload(service, orcamento, service.clock())


@app.post("/api/orcamento/orcamentos/{orcamento_id}/revisoes", status_code=201)
async def criar_revisao_orcamento(
    orcamento_id: str,
    payload: RevisaoOrcamentoRequest,
    session=Depends(require_permissions_with_csrf("orcamento.view", "orcamento.edit")),
):
    """Cria a próxima revisão sem sobrescrever as anteriores."""
    service = get_orcamento_service()
    try:
        revisao = service.create_revisao(
            orcamento_id,
            payload.model_dump(exclude_unset=True),
            autor_user_id=session.user.id,
        )
    except (OrcamentoNotFoundError, InvalidOrcamentoInputError) as exc:
        _raise_orcamento_http_error(exc)
    return revisao.to_dict(agora=service.clock())


@app.patch("/api/orcamento/revisoes/{revisao_id}")
async def editar_cabecalho_revisao(
    revisao_id: str,
    payload: UpdateCabecalhoOrcamentoRequest,
    session=Depends(require_permissions_with_csrf("orcamento.view", "orcamento.edit")),
):
    """Edita o cabeçalho apenas da revisão atual enquanto estiver em rascunho."""
    service = get_orcamento_service()
    try:
        revisao = service.update_cabecalho(
            revisao_id,
            payload.model_dump(exclude_unset=True),
            responsavel_user_id=session.user.id,
        )
    except (
        InvalidOrcamentoInputError,
        InvalidSituacaoTransitionError,
        RevisaoNotFoundError,
    ) as exc:
        _raise_orcamento_http_error(exc)
    return revisao.to_dict(agora=service.clock())


@app.post("/api/orcamento/revisoes/{revisao_id}/situacao")
async def alterar_situacao_revisao(
    revisao_id: str,
    payload: SituacaoRevisaoRequest,
    session=Depends(
        require_permissions_with_csrf("orcamento.view", "orcamento.transition")
    ),
):
    """Aplica a transição de situação registrando motivo e responsável."""
    service = get_orcamento_service()
    try:
        revisao = service.alterar_situacao(
            revisao_id,
            situacao=payload.situacao,
            motivo=payload.motivo,
            responsavel_user_id=session.user.id,
        )
    except (
        InvalidOrcamentoInputError,
        InvalidSituacaoTransitionError,
        RevisaoNotFoundError,
    ) as exc:
        _raise_orcamento_http_error(exc)
    return revisao.to_dict(agora=service.clock())


@app.get("/api/orcamento/catalogo")
def obter_catalogo_orcamento(_session=Depends(require_permission("orcamento.view"))):
    return get_orcamento_service().get_catalogo()


@app.get("/api/orcamento/catalogo/historico")
def historico_catalogo_orcamento(_session=Depends(require_permission("orcamento.view"))):
    """Expõe as versões e vigências do catálogo para auditoria do orçamento."""
    return {"historico": list(get_orcamento_service().list_catalogo_historico())}


@app.post("/api/orcamento/catalogo")
def salvar_catalogo_orcamento(
    payload: dict[str, Any],
    session=Depends(require_permissions_with_csrf("orcamento.view", "orcamento.edit")),
):
    try:
        return get_orcamento_service().save_catalogo(payload, responsavel_user_id=session.user.id)
    except InvalidOrcamentoInputError as exc:
        _raise_orcamento_http_error(exc)


@app.get("/api/orcamento/orcamentos/{orcamento_id}/historico")
def historico_orcamento(
    orcamento_id: str,
    _session=Depends(require_permission("orcamento.view")),
):
    try:
        service = get_orcamento_service()
        service.get_orcamento(orcamento_id)
        return {"historico": list(service.list_historico(orcamento_id))}
    except OrcamentoNotFoundError as exc:
        _raise_orcamento_http_error(exc)


@app.get("/api/orcamento/revisoes/{revisao_id}/exportar")
def exportar_orcamento(
    revisao_id: str,
    formato: Literal["docx", "pdf"] = "pdf",
    _session=Depends(require_permission("orcamento.view")),
):
    from .orcamento.documents import export_orcamento_document

    service = get_orcamento_service()
    try:
        revisao = service.get_revisao(revisao_id)
        orcamento = service.get_orcamento(revisao.orcamento_id)
        content, media_type, filename = export_orcamento_document(
            orcamento.to_dict(agora=service.clock()),
            revisao.to_dict(agora=service.clock()),
            formato,
        )
    except (RevisaoNotFoundError, OrcamentoNotFoundError, InvalidOrcamentoInputError) as exc:
        _raise_orcamento_http_error(exc)
    return Response(content, media_type=media_type, headers={
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Cache-Control": "no-store",
    })


# Rotas legadas temporárias: mantêm clientes antigos usando a nova sessão persistida.
@app.post("/api/admin/login")
async def admin_login(payload: AdminLoginRequest, request: Request, response: Response):
    _service, _credentials, user = _authenticate(payload, request, response, legacy=True)
    return {"authenticated": True, "username": user.username}


@app.get("/api/admin/session")
async def admin_session(request: Request):
    try:
        session = get_identity_service().resolve_session(token_from_request(request))
    except RuntimeError:
        session = None
    has_admin_access = session is not None and "admin_banco.use" in session.user.permissions
    return {
        "authenticated": has_admin_access,
        "username": session.user.username if has_admin_access else None,
    }


@app.post("/api/admin/logout")
async def admin_logout(request: Request, response: Response):
    try:
        get_identity_service().revoke_session(token_from_request(request))
    except RuntimeError:
        pass
    clear_session_cookies(response)
    return {"authenticated": False}


@app.get(
    "/api/dashboard/resumo",
    dependencies=[Depends(require_permissions("dre.view", "fluxo.view"))],
)
async def dashboard_resumo(
    ano: int | None = Query(None, description="Ano de referência (ex: 2025)"),
    mes: int | None = Query(None, description="Mês de referência 1..12"),
):
    """Retorna o resumo executivo do dashboard GoFlowOS."""
    try:
        if ano is None and mes is None:
            ano_ref, mes_ref = dashboard_resumo_service.obter_periodo_padrao()
        else:
            hoje = date.today()
            ano_ref = ano or hoje.year
            mes_ref = mes or hoje.month
        return dashboard_resumo_service.obter_resumo(ano=ano_ref, mes=mes_ref)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("Erro ao obter resumo do dashboard: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/dre/painel", dependencies=[Depends(require_permission("dre.view"))])
async def painel_dre(
    ano: int | None = Query(None, description="Ano de referência (ex: 2025)"),
    meses: list[int] | None = Query(None, description="Meses a incluir, repetível"),
    centro_custo: list[str] | None = Query(None, description="Obras/centros de custo"),
    natureza: list[str] | None = Query(
        None,
        description="Centros de custos (campo tecnico natureza normalizada)",
    ),
    escopo_periodo: str | None = Query(
        None,
        description="Use 'projeto_completo' para ignorar ano/meses quando houver obra filtrada",
    ),
):
    """Retorna a página analítica completa do DRE."""
    try:
        return dre_painel_service.obter_painel(
            ano=ano,
            meses=meses,
            centro_custo=centro_custo,
            natureza=natureza,
            escopo_periodo=escopo_periodo,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("Erro ao obter painel DRE: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.get(
    "/api/fluxo_caixa/painel",
    dependencies=[Depends(require_permission("fluxo.view"))],
)
async def painel_fluxo_caixa(
    ano: int | None = Query(None, description="Ano de referência (ex: 2025)"),
    meses: list[int] | None = Query(None, description="Meses a incluir, repetível"),
    banco: list[str] | None = Query(None, description="Bancos de origem"),
    tipo: list[str] | None = Query(None, description="Tipos de movimento"),
    classificacao: list[str] | None = Query(None, description="Classificações/contas gerenciais"),
):
    """Retorna a página analítica completa do Fluxo de Caixa."""
    try:
        return fluxo_painel_service.obter_painel(
            ano=ano,
            meses=meses,
            banco=banco,
            tipo=tipo,
            classificacao=classificacao,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("Erro ao obter painel Fluxo de Caixa: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post(
    "/api/detectar-competencia/{fluxo}",
    dependencies=[Depends(require_permission_with_csrf("admin_banco.use"))],
)
async def detectar_competencia(
    fluxo: FlowType,
    arquivo: UploadFile | None = File(None),
    arquivos: list[UploadFile] | None = File(None),
):
    """Detecta automaticamente a competência pelo conteúdo do(s) arquivo(s)."""
    tmp_paths: list[Path] = []
    try:
        uploads = arquivos or ([arquivo] if arquivo is not None else [])
        if not uploads:
            raise HTTPException(status_code=400, detail="Envie ao menos um arquivo.")
        _validar_quantidade_uploads(uploads)

        arquivos_detector: list[tuple[Path, str]] = []
        for upload in uploads:
            tmp_path = await _salvar_upload_temporario(upload)
            tmp_paths.append(tmp_path)
            arquivos_detector.append((tmp_path, _nome_upload_seguro(upload)))

        return competencia_detector_service.detectar(
            fluxo=fluxo.value,
            arquivos=arquivos_detector,
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("Erro ao detectar competência: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        for path in tmp_paths:
            if path.exists():
                path.unlink()


@app.post(
    "/api/validar/{fluxo}",
    dependencies=[Depends(require_permission_with_csrf("admin_banco.use"))],
)
async def validar_arquivo(
    fluxo: FlowType,
    arquivo: UploadFile = File(...),
    competencia: str | None = Form(None),
    modo_cumulativo: bool | None = Form(None),
):
    """Valida estrutura de um arquivo de entrada (DRE ou Fluxo de Caixa).

    Retorna resultado detalhado com erros bloqueantes e warnings.
    """
    tmp_path = None
    try:
        tmp_path = await _salvar_upload_temporario(arquivo)

        # Parse
        flow_key = "dre" if fluxo == FlowType.DRE else "fluxo"
        parser = ExcelParser(flow_key)
        dados = parser.ler_arquivo(tmp_path)

        # Validar
        if fluxo == FlowType.DRE:
            validator = DREValidator()
            result = validator.validar(
                dados,
                competencia=competencia,
                modo_cumulativo=modo_cumulativo,
            )
        else:
            validator = FluxoCaixaValidator()
            result = validator.validar(dados)

        return result.model_dump(mode="json")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro na validação: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink()


@app.post(
    "/api/processar/dre",
    response_model=DREProcessamentoResponse,
    dependencies=[Depends(require_permission_with_csrf("admin_banco.use"))],
)
async def processar_dre(
    arquivo: UploadFile = File(...),
    competencia: str = Form(...),
    modo_cumulativo: bool | None = Form(None),
):
    """[LEGADO] Processa o DRE ponta a ponta e gera o arquivo final.

    Mantido para compatibilidade temporária. Prefira:
      POST /api/dre/ingestoes  — para persistir o mês no banco
      POST /api/dre/gerar      — para gerar o DRE a partir do banco
    """
    logger.warning(
        "LEGADO: /api/processar/dre chamado para competência=%s. "
        "Migre para /api/dre/ingestoes + /api/dre/gerar.",
        competencia,
    )
    tmp_path = None
    try:
        tmp_path = await _salvar_upload_temporario(arquivo)
        resultado = dre_service.processar(
            tmp_path,
            _nome_upload_seguro(arquivo),
            competencia,
            modo_cumulativo=modo_cumulativo,
        )
        return resultado.model_dump(mode="json")
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Erro no processamento DRE (legado): {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink()


@app.post(
    "/api/processar/fluxo_caixa",
    response_model=DREProcessamentoResponse,
    dependencies=[Depends(require_permission_with_csrf("admin_banco.use"))],
)
async def processar_fluxo_caixa(
    arquivos: list[UploadFile] = File(...),
    periodo: str = Form(..., description="Período no formato MM/AAAA (ex: 05/2025)"),
):
    """Processa lote de extratos bancários e gera Fluxo de Caixa consolidado."""
    tmp_paths: list[Path] = []
    try:
        _validar_quantidade_uploads(arquivos)
        arquivos_lote: list[tuple[Path, str]] = []
        for arquivo in arquivos:
            tmp_path = await _salvar_upload_temporario(arquivo)
            tmp_paths.append(tmp_path)
            arquivos_lote.append((tmp_path, _nome_upload_seguro(arquivo)))

        resultado = fluxo_service.processar_lote(arquivos=arquivos_lote, periodo=periodo)
        return resultado.model_dump(mode="json")

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Erro no processamento Fluxo de Caixa: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        for path in tmp_paths:
            if path.exists():
                path.unlink()


@app.post(
    "/api/fluxo_caixa/gerar",
    dependencies=[Depends(require_permission_with_csrf("admin_banco.use"))],
)
async def gerar_fluxo_caixa(
    arquivos: list[UploadFile] | None = File(
        None,
        description="Compatibilidade: se informado, gera diretamente do upload",
    ),
    periodo: str | None = Form(None, description="Período legado no formato MM/AAAA"),
    competencia: str | None = Form(None, description="Competência alvo no formato MM/AAAA"),
    modo_teste: bool = Form(False, description="Se True, apenas verifica sem gerar arquivo"),
    meses_incluir: list[int] | None = Form(
        None,
        description="Lista opcional de meses (1..12) para incluir na geração",
    ),
    ano_todo: bool = Form(
        False,
        description="Se True, usa todos os meses disponíveis no banco para o ano",
    ),
):
    """Gera Fluxo de Caixa a partir do banco, com fallback legado por upload."""
    if arquivos:
        if not periodo:
            periodo = competencia
        if not periodo:
            raise HTTPException(status_code=400, detail="Informe 'periodo' ou 'competencia'.")
        return await processar_fluxo_caixa(arquivos=arquivos, periodo=periodo)

    if not competencia:
        raise HTTPException(status_code=400, detail="Informe 'competencia' para gerar do banco.")

    try:
        verificacao = fluxo_geracao_db_service.verificar_dados(
            competencia=competencia,
            meses_incluir=meses_incluir,
            ano_todo=ano_todo,
        )
        if not verificacao["valido"]:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": verificacao.get("error", "Dados insuficientes para geração"),
                    "verificacao": verificacao,
                },
            )
        if modo_teste:
            return {
                "modo_teste": True,
                "verificacao": verificacao,
                "message": "Verificação concluída. Use modo_teste=False para gerar arquivo.",
            }

        resultado = fluxo_geracao_db_service.gerar_arquivo(
            competencia=competencia,
            meses_incluir=meses_incluir,
            ano_todo=ano_todo,
        )
        if "total_lancamentos" not in resultado and "total_movimentos" in resultado:
            resultado["total_lancamentos"] = resultado["total_movimentos"]
        return {
            "success": True,
            "competencia": competencia,
            **resultado,
        }

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as exc:
        logger.error("Erro na geração Fluxo de Caixa do banco: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post(
    "/api/validar/fluxo_caixa/lote",
    dependencies=[Depends(require_permission_with_csrf("admin_banco.use"))],
)
async def validar_lote_fluxo(
    arquivos: list[UploadFile] = File(...),
):
    """Valida múltiplos arquivos do Fluxo de Caixa em lote."""
    tmp_paths = []
    try:
        _validar_quantidade_uploads(arquivos)
        parser = ExcelParser("fluxo")
        lista_dados = []

        for arquivo in arquivos:
            tmp_path = await _salvar_upload_temporario(arquivo)
            tmp_paths.append(tmp_path)

            dados = parser.ler_arquivo(tmp_path)
            # Sobrescrever nome para preservar original
            dados["arquivo"] = _nome_upload_seguro(arquivo)
            lista_dados.append(dados)

        validator = FluxoCaixaValidator()
        result = validator.validar_lote(lista_dados)
        return result.model_dump(mode="json")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro na validação de lote: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        for p in tmp_paths:
            if p.exists():
                p.unlink()


@app.get(
    "/api/templates/info/{fluxo}", dependencies=[Depends(require_permission("admin_banco.use"))]
)
async def info_template(fluxo: FlowType):
    """Retorna informações estruturais do template oficial."""
    try:
        if fluxo == FlowType.DRE:
            template_path = settings.template_dre_path
        else:
            template_path = settings.template_fluxo_path

        if not template_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Template não encontrado: {template_path.name}",
            )

        writer = TemplateWriter(template_path)
        writer.abrir()

        sheets_info = []
        for sheet in writer.listar_sheets():
            sheets_info.append(writer.obter_info_sheet(sheet))

        writer.fechar()

        return {
            "fluxo": fluxo.value,
            "template": template_path.name,
            "sheets": sheets_info,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao ler template: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/config/{fluxo}", dependencies=[Depends(require_permission("admin_banco.use"))])
async def get_config(fluxo: FlowType):
    """Retorna configuração de mapeamento do fluxo."""
    import json

    flow_key = "dre" if fluxo == FlowType.DRE else "fluxo"
    mapping_path = settings.config_dir / f"{flow_key}_mapping.json"

    if not mapping_path.exists():
        raise HTTPException(status_code=404, detail="Configuração não encontrada")

    with open(mapping_path, encoding="utf-8") as f:
        config = json.load(f)

    return config


@app.get("/api/logs", dependencies=[Depends(require_permission("admin_banco.use"))])
async def listar_logs():
    """Lista logs de processamento disponíveis."""
    logs = []
    if settings.logs_dir.exists():
        for f in sorted(settings.logs_dir.glob("log_*.json"), reverse=True):
            import json

            with open(f, encoding="utf-8") as fh:
                logs.append(json.load(fh))
    return {"total": len(logs), "logs": logs[:50]}


@app.get(
    "/api/processamentos/{processamento_id}",
    response_model=DREProcessamentoResponse,
    dependencies=[Depends(require_permission("admin_banco.use"))],
)
async def obter_processamento(processamento_id: str):
    """Consulta o status persistido de um processamento (DRE ou Fluxo)."""
    resultado = dre_service.obter_processamento(processamento_id)
    if not resultado:
        resultado = fluxo_service.obter_processamento(processamento_id)
    if not resultado:
        raise HTTPException(status_code=404, detail="Processamento nao encontrado")
    return resultado.model_dump(mode="json")


@app.get(
    "/api/processamentos/{processamento_id}/download",
    dependencies=[Depends(require_permission("admin_banco.use"))],
)
async def download_processamento(processamento_id: str):
    """Baixa o arquivo final gerado por um processamento (DRE ou Fluxo)."""
    arquivo_saida = dre_service.obter_arquivo_saida(processamento_id)
    if not arquivo_saida:
        arquivo_saida = fluxo_service.obter_arquivo_saida(processamento_id)
    if not arquivo_saida:
        raise HTTPException(status_code=404, detail="Arquivo de saida nao encontrado")
    return _excel_file_response(arquivo_saida)


@app.get("/api/etapa1/status", dependencies=[Depends(require_permission("admin_banco.use"))])
async def status_etapa1():
    """Resumo de prontidão da Etapa 1 (fundação e arquitetura)."""
    baseline_dir = settings.config_dir / "template_baselines"
    dre_baseline = baseline_dir / "dre_template_baseline.json"
    fluxo_baseline = baseline_dir / "fluxo_template_baseline.json"

    return {
        "etapa": 1,
        "fundacao_backend": {
            "api_online": True,
            "config_dre": (settings.config_dir / "dre_mapping.json").exists(),
            "config_fluxo": (settings.config_dir / "fluxo_mapping.json").exists(),
        },
        "templates": {
            "dre_template": settings.template_dre_path.exists(),
            "fluxo_template": settings.template_fluxo_path.exists(),
            "dre_baseline": dre_baseline.exists(),
            "fluxo_baseline": fluxo_baseline.exists(),
        },
    }


# ============================================================================
# ENDPOINTS DE PERSISTÊNCIA DRE (NOVOS - Fase B/C)
# ============================================================================


@app.post(
    "/api/dre/ingestoes",
    dependencies=[Depends(require_permission_with_csrf("admin_banco.use"))],
)
async def ingestao_dre(
    arquivo: UploadFile = File(...),
    competencia: str = Form(..., description="Competência no formato MM/AAAA (ex: 05/2025)"),
    replace: bool = Form(True, description="Substituir competência existente se houver"),
):
    """
    Ingestão mensal de DRE para persistência no banco.

    - Valida o arquivo
    - Persiste lançamentos no banco
    - Substitui competência existente se replace=True
    """
    tmp_path = None
    try:
        tmp_path = await _salvar_upload_temporario(arquivo)

        resultado = dre_ingestao_service.ingestar(
            arquivo_path=tmp_path,
            arquivo_nome=_nome_upload_seguro(arquivo),
            competencia=competencia,
            replace=replace,
        )

        if not resultado["success"]:
            status_code = 400 if resultado.get("status") == "validation_error" else 500
            raise HTTPException(status_code=status_code, detail=resultado)

        return resultado

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Erro na ingestão DRE: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink()


@app.get(
    "/api/dre/ingestoes/{upload_id}", dependencies=[Depends(require_permission("admin_banco.use"))]
)
async def obter_status_ingestao(upload_id: str):
    """Consulta o status de uma ingestão DRE."""
    resultado = dre_ingestao_service.obter_status(upload_id)
    if not resultado:
        raise HTTPException(status_code=404, detail="Ingestão não encontrada")
    return resultado


@app.get("/api/dre/ingestoes", dependencies=[Depends(require_permission("admin_banco.use"))])
async def listar_ingestoes(
    ano: int | None = None,
    mes: int | None = None,
    limit: int = 100,
):
    """Lista ingestões DRE com filtros opcionais."""
    ingestoes = dre_ingestao_service.listar_ingestoes(ano, mes, limit)
    return {
        "total": len(ingestoes),
        "ingestoes": ingestoes,
    }


@app.post(
    "/api/dre/admin/limpar",
    dependencies=[Depends(require_permission_with_csrf("admin_banco.use"))],
)
async def limpar_base_dre(
    ano: int | None = Form(None, description="Ano opcional (ex: 2025)"),
    mes: int | None = Form(None, description="Mês opcional 1..12 (requer ano)"),
    confirmar: bool = Form(False, description="Confirmação explícita da limpeza"),
):
    """Limpa dados persistidos de DRE (global, por ano, ou por competência)."""
    try:
        _exigir_confirmacao(confirmar)
        if mes is not None and ano is None:
            raise HTTPException(
                status_code=400,
                detail="Parametro 'mes' exige o parametro 'ano'.",
            )
        if mes is not None and (mes < 1 or mes > 12):
            raise HTTPException(
                status_code=400,
                detail="Parametro 'mes' deve estar entre 1 e 12.",
            )

        resultado = dre_geracao_service.repository.limpar_dados(ano=ano, mes=mes)
        return {
            "success": True,
            "ano": ano,
            "mes": mes,
            **resultado,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Erro ao limpar base DRE: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.get(
    "/api/dre/admin/indicadores",
    dependencies=[Depends(require_permission_with_csrf("admin_banco.use"))],
)
async def consultar_indicadores_manuais_dre(
    ano: int = Query(..., description="Ano da competência"),
    mes: int = Query(..., description="Mês da competência"),
):
    """Consulta indicadores manuais DRE da competência selecionada na ADM."""
    _validar_competencia_admin(ano, mes)
    registro = dre_painel_service.indicadores_manuais.get_by_competencia(ano, mes)
    existe = registro is not None
    if registro is None:
        registro = DREIndicadoresManuais(competencia_ano=ano, competencia_mes=mes)
    return _payload_indicadores_manuais(registro, existe)


@app.post(
    "/api/dre/admin/indicadores", dependencies=[Depends(require_permission("admin_banco.use"))]
)
async def salvar_indicadores_manuais_dre(
    ano: int = Form(..., description="Ano da competência"),
    mes: int = Form(..., description="Mês da competência"),
    contas_pagar: float = Form(0, description="Contas a pagar"),
    contas_receber: float = Form(0, description="Contas a receber"),
    total_impostos_retidos_acima_meta: float = Form(
        0,
        description="Total de impostos retidos acima da meta",
    ),
    total_impostos_retidos: float = Form(0, description="Total de impostos retidos"),
    confirmar: bool = Form(False, description="Confirmação explícita do salvamento"),
):
    """Salva ou atualiza indicadores manuais DRE da competência selecionada."""
    _exigir_confirmacao(confirmar)
    _validar_competencia_admin(ano, mes)
    registro = DREIndicadoresManuais(
        competencia_ano=ano,
        competencia_mes=mes,
        contas_pagar=_valor_monetario_admin("Contas a pagar", contas_pagar),
        contas_receber=_valor_monetario_admin("Contas a receber", contas_receber),
        total_impostos_retidos_acima_meta=_valor_monetario_admin(
            "Total de impostos retidos acima da meta",
            total_impostos_retidos_acima_meta,
        ),
        total_impostos_retidos=_valor_monetario_admin(
            "Total de impostos retidos",
            total_impostos_retidos,
        ),
    )
    salvo = dre_painel_service.indicadores_manuais.upsert(registro)
    return _payload_indicadores_manuais(salvo, True)


@app.get(
    "/api/fluxo_caixa/admin/indicadores",
    dependencies=[Depends(require_permission_with_csrf("admin_banco.use"))],
)
async def consultar_indicadores_manuais_fluxo(
    ano: int = Query(..., description="Ano de referência do Fluxo de Caixa"),
):
    """Consulta indicadores manuais anuais do Fluxo de Caixa na ADM."""
    _validar_competencia_admin(ano, 1)
    registro = fluxo_painel_service.indicadores_manuais.get_by_ano(ano)
    existe = registro is not None
    if registro is None:
        registro = FluxoIndicadoresManuais(competencia_ano=ano)
    return _payload_indicadores_manuais_fluxo(registro, existe)


@app.post(
    "/api/fluxo_caixa/admin/indicadores",
    dependencies=[Depends(require_permission("admin_banco.use"))],
)
async def salvar_indicadores_manuais_fluxo(
    ano: int = Form(..., description="Ano de referência do Fluxo de Caixa"),
    saldo_ano_anterior: float = Form(0, description="Saldo do ano anterior"),
    confirmar: bool = Form(False, description="Confirmação explícita do salvamento"),
):
    """Salva ou atualiza indicadores manuais anuais do Fluxo de Caixa."""
    _exigir_confirmacao(confirmar)
    _validar_competencia_admin(ano, 1)
    registro = FluxoIndicadoresManuais(
        competencia_ano=ano,
        saldo_ano_anterior=_valor_monetario_admin(
            "Saldo do ano anterior",
            saldo_ano_anterior,
        ),
    )
    salvo = fluxo_painel_service.indicadores_manuais.upsert(registro)
    return _payload_indicadores_manuais_fluxo(salvo, True)


# ============================================================================
# ENDPOINTS DE PERSISTÊNCIA FLUXO DE CAIXA
# ============================================================================


@app.post(
    "/api/fluxo_caixa/ingestoes",
    dependencies=[Depends(require_permission_with_csrf("admin_banco.use"))],
)
async def ingestao_fluxo_caixa(
    arquivos: list[UploadFile] = File(...),
    competencia: str = Form(..., description="Competência no formato MM/AAAA (ex: 08/2025)"),
    replace: bool = Form(True, description="Substituir competência existente se houver"),
    replace_scope: str = Form(
        "bancos",
        description="bancos preserva fontes não reenviadas; competencia substitui o mês inteiro",
    ),
):
    """Ingestão mensal de extratos do Fluxo de Caixa para persistência no banco."""
    tmp_paths: list[Path] = []
    try:
        _validar_quantidade_uploads(arquivos)
        arquivos_lote: list[tuple[Path, str]] = []
        for arquivo in arquivos:
            tmp_path = await _salvar_upload_temporario(arquivo)
            tmp_paths.append(tmp_path)
            arquivos_lote.append((tmp_path, _nome_upload_seguro(arquivo)))

        resultado = fluxo_ingestao_service.ingestar_lote(
            arquivos=arquivos_lote,
            competencia=competencia,
            replace=replace,
            replace_scope=replace_scope,
        )
        if not resultado["success"]:
            status_code = 400 if resultado.get("status") == "validation_error" else 500
            raise HTTPException(status_code=status_code, detail=resultado)
        return resultado

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Erro na ingestão Fluxo de Caixa: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        for path in tmp_paths:
            if path.exists():
                path.unlink()


@app.get(
    "/api/fluxo_caixa/ingestoes", dependencies=[Depends(require_permission("admin_banco.use"))]
)
async def listar_ingestoes_fluxo_caixa(
    ano: int | None = None,
    mes: int | None = None,
    limit: int = 100,
):
    """Lista ingestões do Fluxo de Caixa com filtros opcionais."""
    ingestoes = fluxo_ingestao_service.listar_ingestoes(ano, mes, limit)
    return {
        "total": len(ingestoes),
        "ingestoes": ingestoes,
    }


@app.post(
    "/api/fluxo_caixa/admin/limpar",
    dependencies=[Depends(require_permission_with_csrf("admin_banco.use"))],
)
async def limpar_base_fluxo_caixa(
    ano: int | None = Form(None, description="Ano opcional (ex: 2025)"),
    mes: int | None = Form(None, description="Mês opcional 1..12 (requer ano)"),
    confirmar: bool = Form(False, description="Confirmação explícita da limpeza"),
):
    """Limpa dados persistidos de Fluxo de Caixa."""
    try:
        _exigir_confirmacao(confirmar)
        if mes is not None and ano is None:
            raise HTTPException(
                status_code=400,
                detail="Parametro 'mes' exige o parametro 'ano'.",
            )
        if mes is not None and (mes < 1 or mes > 12):
            raise HTTPException(
                status_code=400,
                detail="Parametro 'mes' deve estar entre 1 e 12.",
            )

        resultado = fluxo_ingestao_service.repository.limpar_dados(ano=ano, mes=mes)
        return {
            "success": True,
            "ano": ano,
            "mes": mes,
            **resultado,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Erro ao limpar base Fluxo de Caixa: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post(
    "/api/dre/gerar",
    dependencies=[Depends(require_permission_with_csrf("admin_banco.use"))],
)
async def gerar_dre_cumulativo(
    competencia: str = Form(..., description="Competência alvo no formato MM/AAAA"),
    centro_custo: str | None = Form(None, description="Filtrar por obra/centro de custo"),
    modo_teste: bool = Form(False, description="Se True, apenas verifica sem gerar arquivo"),
    meses_incluir: list[int] | None = Form(
        None,
        description="Lista opcional de meses (1..12) para incluir na geração",
    ),
    ano_todo: bool = Form(
        False,
        description=(
            "Se True, ignora competência para meses e usa todos os meses disponíveis do ano"
        ),
    ),
):
    """
    Gera DRE a partir do banco de dados (fonte de verdade).

    - Não exige cumulativo completo mês a mês
    - No modo padrão, usa meses disponíveis (<= competência) automaticamente
    - Se ano_todo=True, usa todos os meses disponíveis do ano
    - Se meses_incluir informado, usa somente os meses selecionados
    - Preenche BD_FLUXO com lançamentos YTD dos meses disponíveis
    - Reescreve APOIO com agregação mês a mês
    - Oculta colunas de meses sem dados na aba DRE
    """
    try:
        # 1. Verificar dados (inclui checagem de upload completed para mês alvo)
        verificacao = dre_geracao_completa_service.verificar_dados(
            competencia=competencia,
            centro_custo=centro_custo,
            meses_incluir=meses_incluir,
            ano_todo=ano_todo,
        )

        if not verificacao["valido"]:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": verificacao.get("error", "Dados insuficientes para geração"),
                    "verificacao": verificacao,
                },
            )

        if modo_teste:
            return {
                "modo_teste": True,
                "verificacao": verificacao,
                "message": "Verificação concluída. Use modo_teste=False para gerar arquivo.",
            }

        # 2. Gerar arquivo
        resultado = dre_geracao_completa_service.gerar_arquivo(
            competencia=competencia,
            centro_custo=centro_custo,
            meses_incluir=meses_incluir,
            ano_todo=ano_todo,
        )

        return {
            "success": True,
            "competencia": competencia,
            "arquivo_saida": resultado["arquivo_saida"],
            "download_url": f"/api/dre/download/{resultado['arquivo_saida']}",
            "registros_reais": resultado.get("registros_reais", resultado["total_lancamentos"]),
            "total_lancamentos": resultado["total_lancamentos"],
            "total_credito": resultado["total_credito"],
            "total_debito": resultado["total_debito"],
            "saldo_liquido": resultado["saldo_liquido"],
            "centro_custo": centro_custo,
            "fonte_dados": resultado["fonte_dados"],
            "estrategia_meses": resultado["estrategia_meses"],
            "ano_todo": resultado["ano_todo"],
            "meses_incluir": resultado["meses_incluir"],
            "meses_disponiveis": resultado["meses_disponiveis"],
            "meses_utilizados": resultado["meses_utilizados"],
            "meses_solicitados": resultado["meses_solicitados"],
            "meses_ocultos": resultado["meses_ocultos"],
            "colunas_dre_visiveis": resultado["colunas_dre_visiveis"],
            "aba_detalhamento": resultado.get("aba_detalhamento"),
            "linhas_resumo_mensal": resultado.get("linhas_resumo_mensal", 0),
            "linhas_resumo_agrupado": resultado.get("linhas_resumo_agrupado", 0),
            "linhas_lancamentos_granulares": resultado.get("linhas_lancamentos_granulares", 0),
        }

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as exc:
        logger.error(f"Erro na geração DRE: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post(
    "/api/dre/exportar",
    dependencies=[Depends(require_permission_with_csrf("dre.view"))],
)
async def exportar_dre_por_centro_custo(
    competencia: str = Form(..., description="Competência alvo no formato MM/AAAA"),
    centro_custo: str = Form(..., description="Obra/centro de custo a exportar"),
    meses_incluir: list[int] | None = Form(None),
):
    """Gera e baixa um DRE restrito a uma única obra selecionada no painel."""
    obra = centro_custo.strip()
    if not obra:
        raise HTTPException(status_code=400, detail="Selecione uma obra para exportar o DRE.")
    try:
        verificacao = dre_geracao_completa_service.verificar_dados(
            competencia=competencia,
            centro_custo=obra,
            meses_incluir=meses_incluir,
            ano_todo=False,
        )
        if not verificacao["valido"]:
            raise HTTPException(
                status_code=400,
                detail=verificacao.get("error", "Dados insuficientes para exportação."),
            )
        resultado = dre_geracao_completa_service.gerar_arquivo(
            competencia=competencia,
            centro_custo=obra,
            meses_incluir=meses_incluir,
            ano_todo=False,
        )
        arquivo_path = _resolver_output_xlsx(resultado["arquivo_saida"])
        return _excel_file_response(
            arquivo_path,
            arquivo_path.name,
            remove_after_send=True,
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("Erro na exportação filtrada do DRE: %s", exc)
        raise HTTPException(status_code=500, detail="Não foi possível exportar o DRE.")


@app.get("/api/dre/lancamentos", dependencies=[Depends(require_permission("admin_banco.use"))])
async def listar_lancamentos(
    ano: int,
    mes: int,
    ate_mes: int | None = None,
    centro_custo: str | None = None,
    limit: int = 1000,
):
    """
    Lista lançamentos DRE do banco.

    - Se ate_mes informado: retorna acumulado YTD (jan até ate_mes)
    - Se apenas mes informado: retorna apenas aquele mês
    """
    try:
        if ate_mes:
            # Modo YTD
            from app.contracts.persistence import DRECompetenciaQuery

            query = None
            if centro_custo:
                query = DRECompetenciaQuery(ano=ano, mes=ate_mes, centro_custo=centro_custo)

            lancamentos = dre_geracao_service.repository.get_lancamentos_ytd(ano, ate_mes, query)
            competencia_label = f"01-{ate_mes:02d}/{ano}"
        else:
            # Modo mês específico
            lancamentos = dre_geracao_service.repository.lancamentos.get_by_competencia(
                ano, mes, centro_custo
            )
            competencia_label = f"{mes:02d}/{ano}"

        # Limitar resultados
        lancamentos = lancamentos[:limit]

        return {
            "competencia": competencia_label,
            "ano": ano,
            "mes": mes,
            "ate_mes": ate_mes,
            "centro_custo": centro_custo,
            "total": len(lancamentos),
            "lancamentos": [
                {
                    "id": lanc.id,
                    "data": lanc.data_lancamento,
                    "historico": lanc.historico,
                    "credito": float(lanc.credito),
                    "debito": float(lanc.debito),
                    "natureza": lanc.natureza_norm or lanc.natureza_raw,
                    "centro_custo": lanc.centro_custo,
                    "conta_pai": lanc.conta_pai,
                }
                for lanc in lancamentos
            ],
        }

    except Exception as exc:
        logger.error(f"Erro ao listar lançamentos: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/dre/resumo", dependencies=[Depends(require_permission("admin_banco.use"))])
async def resumo_dre(
    ano: int,
    mes: int | None = None,
):
    """
    Retorna resumo acumulado do DRE.

    - Se mes informado: resumo YTD até aquele mês
    - Se mes não informado: resumo de todos os lançamentos do ano
    """
    try:
        if mes:
            resumo = dre_geracao_service.repository.get_resumo_ytd(ano, mes)
            resumo["competencia"] = f"01-{mes:02d}/{ano}"
        else:
            # Resumo do ano completo
            resumo = dre_geracao_service.repository.get_resumo_ytd(ano, 12)
            resumo["competencia"] = f"{ano} (ano completo)"

        # Converter Decimal para float para serialização JSON
        for key in ["total_credito", "total_debito", "saldo_liquido"]:
            if key in resumo:
                resumo[key] = float(resumo[key])

        return resumo

    except Exception as exc:
        logger.error(f"Erro ao obter resumo: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get(
    "/api/dre/download/{arquivo_nome:path}",
    dependencies=[Depends(require_permission("admin_banco.use"))],
)
async def download_dre(arquivo_nome: str):
    """Download de arquivo DRE gerado."""
    arquivo_path = _resolver_output_xlsx(arquivo_nome)
    return _excel_file_response(arquivo_path, arquivo_path.name)


@app.get(
    "/api/fluxo_caixa/download/{arquivo_nome:path}",
    dependencies=[Depends(require_permission("admin_banco.use"))],
)
async def download_fluxo_caixa(arquivo_nome: str):
    """Download de arquivo Fluxo de Caixa gerado."""
    arquivo_path = _resolver_output_xlsx(arquivo_nome)
    return _excel_file_response(arquivo_path, arquivo_path.name)


if settings.frontend_dist_dir.exists():
    app.mount(
        "/",
        StaticFiles(directory=str(settings.frontend_dist_dir), html=True),
        name="frontend",
    )
