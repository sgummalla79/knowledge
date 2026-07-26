from app.presentation.routes.documents import documents_bp
from app.presentation.routes.libraries import libraries_bp
from app.presentation.routes.options import options_bp
from app.presentation.routes.query import query_bp

ALL_BLUEPRINTS = [libraries_bp, documents_bp, query_bp, options_bp]
