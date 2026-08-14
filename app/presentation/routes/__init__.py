from app.presentation.routes.auth_ui import auth_ui_bp
from app.presentation.routes.documents import documents_bp
from app.presentation.routes.embedding_settings import embedding_settings_bp
from app.presentation.routes.libraries import libraries_bp
from app.presentation.routes.oauth import oauth_bp
from app.presentation.routes.options import options_bp
from app.presentation.routes.query import query_bp
from app.presentation.routes.search_settings import search_settings_bp

ALL_BLUEPRINTS = [
    libraries_bp,
    documents_bp,
    query_bp,
    options_bp,
    embedding_settings_bp,
    search_settings_bp,
    auth_ui_bp,
    oauth_bp,
]
