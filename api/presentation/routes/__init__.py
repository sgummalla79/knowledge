from api.presentation.routes.app_shell import app_shell_bp
from api.presentation.routes.applications import applications_bp
from api.presentation.routes.auth_ui import auth_ui_bp
from api.presentation.routes.categories import categories_bp
from api.presentation.routes.documents import documents_bp
from api.presentation.routes.embedding_settings import embedding_settings_bp
from api.presentation.routes.ingestion_jobs import ingestion_jobs_bp
from api.presentation.routes.mcp_settings import mcp_settings_bp
from api.presentation.routes.oauth import oauth_bp, well_known_bp
from api.presentation.routes.options import options_bp
from api.presentation.routes.orgs import orgs_bp
from api.presentation.routes.profiles import profiles_bp
from api.presentation.routes.queries import queries_bp
from api.presentation.routes.query import query_bp
from api.presentation.routes.router_query import router_query_bp
from api.presentation.routes.shelves import shelves_bp
from api.presentation.routes.stats import stats_bp
from api.presentation.routes.tags import tags_bp

ALL_BLUEPRINTS = [
    applications_bp,
    categories_bp,
    documents_bp,
    query_bp,
    router_query_bp,
    options_bp,
    embedding_settings_bp,
    mcp_settings_bp,
    oauth_bp,
    well_known_bp,
    orgs_bp,
    profiles_bp,
    shelves_bp,
    tags_bp,
    ingestion_jobs_bp,
    queries_bp,
    stats_bp,
    auth_ui_bp,
    app_shell_bp,
]
