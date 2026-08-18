from app.presentation.routes.auth_ui import auth_ui_bp
from app.presentation.routes.categories import categories_bp
from app.presentation.routes.documents import documents_bp
from app.presentation.routes.embedding_settings import embedding_settings_bp
from app.presentation.routes.options import options_bp
from app.presentation.routes.query import query_bp
from app.presentation.routes.router_query import router_query_bp
from app.presentation.routes.workspace import workspace_bp

ALL_BLUEPRINTS = [
    categories_bp,
    documents_bp,
    query_bp,
    router_query_bp,
    options_bp,
    embedding_settings_bp,
    auth_ui_bp,
    workspace_bp,
]
