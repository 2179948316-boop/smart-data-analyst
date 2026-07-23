"""Database engine and session factories.

Two separate databases:
- biz_engine: the e-commerce demo data (read-only target for NL2SQL)
- app_engine: application data (conversations, query history)
"""

import logging
from contextvars import ContextVar

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Workspace context (set per-request from JWT token) ──
_workspace_db_name: ContextVar[str | None] = ContextVar("workspace_db_name", default=None)


def set_workspace_db(db_name: str | None):
    """Set the current workspace database name for this request."""
    _workspace_db_name.set(db_name)


def get_workspace_db_name() -> str | None:
    """Get the current workspace database name."""
    return _workspace_db_name.get()

# ── Business Database (e-commerce data) ──
biz_engine = create_engine(
    settings.biz_database_url,
    pool_size=5,
    max_overflow=10,
    pool_recycle=3600,
    echo=False,
)
BizSessionLocal = sessionmaker(bind=biz_engine, autocommit=False, autoflush=False)


# ── Application Database (conversations, history) ──
app_engine = create_engine(
    settings.app_database_url,
    pool_size=5,
    max_overflow=10,
    pool_recycle=3600,
    echo=False,
)
AppSessionLocal = sessionmaker(bind=app_engine, autocommit=False, autoflush=False)


def get_biz_db() -> Session:
    """Dependency: get business database session."""
    db = BizSessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_app_db() -> Session:
    """Dependency: get application database session."""
    db = AppSessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_app_db():
    """Create application tables if they don't exist, and auto-migrate missing columns."""
    from app.models import Base
    Base.metadata.create_all(bind=app_engine)

    # Auto-migrate: add missing columns to existing tables
    # create_all() only creates NEW tables — it never alters existing ones.
    # When we add columns (e.g. user_id, workspace_id) to models, we need
    # to ALTER TABLE on the live database.
    from sqlalchemy import inspect
    inspector = inspect(app_engine)
    existing_tables = set(inspector.get_table_names())

    with app_engine.connect() as conn:
        for table in Base.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue
            existing_cols = {col["name"] for col in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name not in existing_cols:
                    # Build column DDL
                    col_type = column.type.compile(dialect=app_engine.dialect)
                    nullable = "NULL" if column.nullable else "NOT NULL"
                    default = ""
                    if column.default is not None and column.default.is_scalar:
                        val = column.default.arg
                        default = f"DEFAULT {val!r}" if isinstance(val, str) else f"DEFAULT {val}"
                    # Foreign key — add column without FK constraint first (simpler migration)
                    ddl = f"ALTER TABLE `{table.name}` ADD COLUMN `{column.name}` {col_type} {nullable} {default}".strip()
                    try:
                        conn.execute(text(ddl))
                        conn.commit()
                        logger.info(f"Migration: added column {table.name}.{column.name}")
                    except Exception as e:
                        logger.warning(f"Migration: failed to add {table.name}.{column.name}: {e}")


def check_db_connection() -> dict:
    """Check connectivity to both databases."""
    result = {"biz_db": False, "app_db": False}
    try:
        with biz_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        result["biz_db"] = True
    except Exception as e:
        result["biz_db_error"] = str(e)

    try:
        with app_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        result["app_db"] = True
    except Exception as e:
        result["app_db_error"] = str(e)

    return result


def get_workspace_session() -> Session:
    """Get a database session for the current workspace.

    If a workspace database is set via context var, connects to that database.
    Otherwise falls back to the default business database (ecommerce_demo).
    """
    ws_db = _workspace_db_name.get()
    if ws_db:
        url = (
            f"mysql+pymysql://{settings.biz_db_user}:{settings.biz_db_password}"
            f"@{settings.biz_db_host}:{settings.biz_db_port}/{ws_db}"
        )
        engine = create_engine(url, pool_size=2, max_overflow=5, pool_recycle=3600)
        session = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
        return session
    return BizSessionLocal()
