"""API routes for the smart data analyst."""

import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Query, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_app_db, AppSessionLocal, set_workspace_db
from app.core.auth import get_optional_user, get_current_workspace
from app.models import User, Workspace, Conversation, Message, QueryLog, DataSource
from app.services import query_service
from app.services.preview_service import preview_service
from app.scheduler.tasks import get_all_dashboard_data, get_dashboard_data

logger = logging.getLogger(__name__)
router = APIRouter()


def _set_ws_context(workspace: Workspace | None):
    """Set the workspace database context for this request."""
    if workspace and workspace.db_name:
        set_workspace_db(workspace.db_name)


# ── Request/Response Models ──

class AskRequest(BaseModel):
    question: str
    conversation_id: int | None = None


class AskResponse(BaseModel):
    answer: str
    sql: str = ""
    chart_config: dict | None = None
    cached: bool = False
    execution_time_ms: float = 0


class ConversationCreate(BaseModel):
    title: str = "新对话"


class ExecuteSqlRequest(BaseModel):
    sql: str


class DataSourceCreate(BaseModel):
    name: str
    host: str = "localhost"
    port: int = 3306
    username: str = "root"
    password: str
    database_name: str


class SqlPreviewRequest(BaseModel):
    sql: str


class SqlConfirmRequest(BaseModel):
    sql: str


# ── Health Check ──

@router.get("/health")
def health_check():
    from app.core.database import check_db_connection
    db_status = check_db_connection()
    return {"status": "ok", "databases": db_status}


@router.post("/api/execute-sql")
def execute_sql(
    req: ExecuteSqlRequest,
    workspace: Workspace | None = Depends(get_current_workspace),
):
    """Safely execute a SQL query and return structured data for chart rendering."""
    from sqlalchemy import text as sa_text
    from app.core.sql_validator import validator

    _set_ws_context(workspace)

    try:
        sql = validator.validate(req.sql)
        from app.core.database import get_workspace_session
        with get_workspace_session() as session:
            result = session.execute(sa_text(sql))
            columns = list(result.keys())
            rows = [list(row) for row in result.fetchall()]

        # Convert Decimal and datetime to JSON-serializable types
        for row in rows:
            for i, val in enumerate(row):
                if hasattr(val, '__float__'):
                    row[i] = float(val)
                elif hasattr(val, 'isoformat'):
                    row[i] = val.isoformat()

        return {"columns": columns, "rows": rows, "count": len(rows)}
    except Exception as e:
        return {"error": str(e), "columns": [], "rows": [], "count": 0}


# ── Chat / Query Endpoints ──

@router.post("/api/ask", response_model=AskResponse)
def ask_question(
    req: AskRequest,
    db: Session = Depends(get_app_db),
    user: User | None = Depends(get_optional_user),
    workspace: Workspace | None = Depends(get_current_workspace),
):
    """Ask a natural language question — synchronous response."""
    _set_ws_context(workspace)

    # Create or get conversation
    conv_id = req.conversation_id
    if not conv_id:
        conv = Conversation(
            title=req.question[:50],
            user_id=user.id if user else None,
            workspace_id=workspace.id if workspace else None,
        )
        db.add(conv)
        db.flush()
        conv_id = conv.id

    # Save user message
    user_msg = Message(conversation_id=conv_id, role="user", content=req.question)
    db.add(user_msg)
    db.commit()

    # Run query
    result = query_service.ask(req.question, conversation_id=conv_id)

    # Save assistant message
    assistant_msg = Message(
        conversation_id=conv_id,
        role="assistant",
        content=result["answer"],
        metadata_json={
            "sql": result["sql"],
            "chart_config": result.get("chart_config"),
            "cached": result["cached"],
            "execution_time_ms": result["execution_time_ms"],
        },
    )
    db.add(assistant_msg)

    # Update conversation title if it's the first message
    conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
    if conv and conv.title == "新对话":
        conv.title = req.question[:50]

    db.commit()

    return AskResponse(
        answer=result["answer"],
        sql=result["sql"],
        chart_config=result.get("chart_config"),
        cached=result["cached"],
        execution_time_ms=result["execution_time_ms"],
    )


@router.post("/api/ask/stream")
def ask_question_stream(
    req: AskRequest,
    workspace: Workspace | None = Depends(get_current_workspace),
    user: User | None = Depends(get_optional_user),
):
    """Ask a question with SSE streaming for real-time feedback."""
    _set_ws_context(workspace)
    conv_id = req.conversation_id

    # Create conversation if needed
    if not conv_id:
        with AppSessionLocal() as db:
            conv = Conversation(
                title=req.question[:50],
                user_id=user.id if user else None,
                workspace_id=workspace.id if workspace else None,
            )
            db.add(conv)
            db.commit()
            conv_id = conv.id

    def event_stream():
        full_answer = ""
        full_sql = ""

        for event in query_service.ask_stream(req.question, conversation_id=conv_id):
            if event["type"] == "answer":
                full_answer = event["data"]
            elif event["type"] == "sql":
                full_sql = event["data"]

            # Send as SSE
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

        # Save messages to DB after stream completes
        try:
            with AppSessionLocal() as db:
                user_msg = Message(conversation_id=conv_id, role="user", content=req.question)
                db.add(user_msg)
                assistant_msg = Message(
                    conversation_id=conv_id,
                    role="assistant",
                    content=full_answer,
                    metadata_json={"sql": full_sql},
                )
                db.add(assistant_msg)
                db.commit()
        except Exception as e:
            logger.warning(f"Failed to save stream messages: {e}")

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── Conversations ──

@router.get("/api/conversations")
def list_conversations(
    db: Session = Depends(get_app_db),
    workspace: Workspace | None = Depends(get_current_workspace),
):
    """List conversations for the current workspace."""
    query = db.query(Conversation)
    if workspace:
        query = query.filter(Conversation.workspace_id == workspace.id)
    convs = query.order_by(Conversation.updated_at.desc()).all()
    return [
        {
            "id": c.id,
            "title": c.title,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
            "message_count": len(c.messages),
        }
        for c in convs
    ]


@router.post("/api/conversations")
def create_conversation(
    req: ConversationCreate,
    db: Session = Depends(get_app_db),
    user: User | None = Depends(get_optional_user),
    workspace: Workspace | None = Depends(get_current_workspace),
):
    """Create a new conversation."""
    conv = Conversation(
        title=req.title,
        user_id=user.id if user else None,
        workspace_id=workspace.id if workspace else None,
    )
    db.add(conv)
    db.commit()
    return {"id": conv.id, "title": conv.title}


@router.get("/api/conversations/{conv_id}")
def get_conversation(conv_id: int, db: Session = Depends(get_app_db)):
    """Get conversation with all messages."""
    conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
    if not conv:
        return {"error": "对话不存在"}

    messages = []
    for msg in sorted(conv.messages, key=lambda m: m.created_at):
        messages.append({
            "id": msg.id,
            "role": msg.role,
            "content": msg.content,
            "metadata": msg.metadata_json,
            "created_at": msg.created_at.isoformat() if msg.created_at else None,
        })

    return {
        "id": conv.id,
        "title": conv.title,
        "messages": messages,
    }


@router.delete("/api/conversations/{conv_id}")
def delete_conversation(conv_id: int, db: Session = Depends(get_app_db)):
    """Delete a conversation and its messages."""
    conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
    if conv:
        db.delete(conv)
        db.commit()
    return {"ok": True}


# ── Query History ──

@router.get("/api/history")
def get_query_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_app_db),
):
    """Get query history with pagination."""
    total = db.query(QueryLog).count()
    logs = (
        db.query(QueryLog)
        .order_by(QueryLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": log.id,
                "question": log.question,
                "sql_query": log.sql_query,
                "result_summary": log.result_summary,
                "chart_type": log.chart_type,
                "row_count": log.row_count,
                "execution_time_ms": log.execution_time_ms,
                "cached": bool(log.cached),
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ],
    }


# ── Data Sources ──

@router.get("/api/datasources")
def list_datasources(db: Session = Depends(get_app_db)):
    """List all configured data sources."""
    sources = db.query(DataSource).order_by(DataSource.created_at.desc()).all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "host": s.host,
            "port": s.port,
            "database_name": s.database_name,
            "is_active": bool(s.is_active),
            "table_count": s.table_count,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in sources
    ]


@router.post("/api/datasources")
def create_datasource(req: DataSourceCreate, db: Session = Depends(get_app_db)):
    """Add a new data source configuration."""
    ds = DataSource(
        name=req.name,
        host=req.host,
        port=req.port,
        username=req.username,
        password=req.password,
        database_name=req.database_name,
    )
    db.add(ds)
    db.commit()

    # Test connection
    from sqlalchemy import create_engine, text
    url = f"mysql+pymysql://{req.username}:{req.password}@{req.host}:{req.port}/{req.database_name}"
    try:
        engine = create_engine(url, connect_args={"connect_timeout": 5})
        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema = :db"
            ), {"db": req.database_name})
            table_count = result.scalar()
        ds.table_count = table_count
        db.commit()
        return {"id": ds.id, "name": ds.name, "table_count": table_count, "status": "connected"}
    except Exception as e:
        return {"id": ds.id, "name": ds.name, "status": "error", "error": str(e)}


# ── Dashboard (Pre-computed Analytics) ──

@router.get("/api/dashboard/stats")
def dashboard_stats():
    """Return all pre-computed dashboard analytics from Redis."""
    data = get_all_dashboard_data()
    # Check if any data exists
    has_data = any(v is not None for v in data.values())
    return {
        "success": True,
        "has_data": has_data,
        "modules": data,
    }


@router.get("/api/dashboard/stats/{key}")
def dashboard_stat_module(key: str):
    """Return a single pre-computed dashboard module."""
    data = get_dashboard_data(key)
    if data is None:
        return {"success": False, "error": f"模块 '{key}' 暂无数据"}
    return {"success": True, "data": data}


# ── File Upload (Excel/CSV → MySQL) ──

@router.post("/api/datasources/upload")
async def upload_file(
    file: UploadFile = File(...),
    table_name: str = Form(default=""),
    if_exists: str = Form(default="rename"),
    workspace: Workspace | None = Depends(get_current_workspace),
):
    """Upload an Excel or CSV file and import it as a MySQL table.

    The file is read with pandas, column types are auto-detected,
    and data is inserted into the business database.

    Args:
        file: The uploaded file (.xlsx, .xls, .csv, .tsv)
        table_name: Custom table name (optional, defaults to filename)
        if_exists: 'rename' to auto-rename if table exists, 'replace' to overwrite
    """
    from app.services.file_import import read_file, import_to_mysql, MAX_FILE_SIZE

    _set_ws_context(workspace)

    # Validate file extension
    filename = file.filename or "upload"
    lower = filename.lower()
    if not lower.endswith((".xlsx", ".xls", ".csv", ".tsv")):
        return {
            "success": False,
            "error": f"不支持的文件格式: {filename}。请上传 .xlsx、.xls、.csv 或 .tsv 文件。",
        }

    # Read file content
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        return {
            "success": False,
            "error": f"文件过大 ({len(content) / 1024 / 1024:.1f}MB)，最大支持 {MAX_FILE_SIZE // 1024 // 1024}MB。",
        }

    try:
        # Parse file into DataFrame
        df = read_file(content, filename)

        if df.empty:
            return {"success": False, "error": "文件内容为空，没有可导入的数据。"}

        # Use custom table name or derive from filename
        name = table_name.strip() if table_name.strip() else filename

        # Import into MySQL
        result = import_to_mysql(df, name, if_exists=if_exists)

        return {
            "success": True,
            "message": f"成功导入 {result['row_count']} 行数据到表 `{result['table_name']}`",
            "table": result,
        }

    except Exception as e:
        logger.error(f"File import failed: {e}", exc_info=True)
        return {"success": False, "error": f"导入失败: {str(e)}"}


@router.get("/api/datasources/tables")
def list_business_tables(
    workspace: Workspace | None = Depends(get_current_workspace),
):
    """List all tables in the current workspace database (for Agent and UI)."""
    from sqlalchemy import text
    from app.core.database import get_workspace_session

    _set_ws_context(workspace)

    try:
        with get_workspace_session() as session:
            result = session.execute(
                text(
                    "SELECT table_name, table_rows, table_comment "
                    "FROM information_schema.tables "
                    "WHERE table_schema = DATABASE() "
                    "ORDER BY table_name"
                )
            )
            tables = []
            for row in result:
                tables.append({
                    "name": row[0],
                    "row_count": row[1] or 0,
                    "comment": row[2] or "",
                })
            return {"success": True, "tables": tables}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.delete("/api/datasources/tables/{table_name}")
def delete_table(
    table_name: str,
    workspace: Workspace | None = Depends(get_current_workspace),
):
    """Delete a table from the current workspace database."""
    from sqlalchemy import text
    from app.core.database import get_workspace_session
    import re

    _set_ws_context(workspace)

    # Safety: only allow simple table names
    if not re.match(r"^[a-zA-Z_\u4e00-\u9fff][a-zA-Z0-9_\u4e00-\u9fff]{0,63}$", table_name):
        return {"success": False, "error": "无效的表名"}

    # Don't allow deleting core demo tables
    PROTECTED = {"categories", "products", "customers", "orders", "order_items", "reviews"}
    if table_name.lower() in PROTECTED:
        return {"success": False, "error": f"不允许删除核心示例表 `{table_name}`"}

    try:
        with get_workspace_session() as session:
            session.execute(text(f"DROP TABLE IF EXISTS `{table_name}`"))
            session.commit()
        return {"success": True, "message": f"表 `{table_name}` 已删除"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── SQL Write Preview & Confirm ──

@router.post("/api/sql/preview")
def sql_preview(
    req: SqlPreviewRequest,
    workspace: Workspace | None = Depends(get_current_workspace),
):
    """
    Detect if a SQL is a write operation and return a preview of affected rows.
    If it's a SELECT, returns {"is_write": false}.
    If it's UPDATE/DELETE/INSERT, returns preview data for user confirmation.
    """
    _set_ws_context(workspace)
    op_type = preview_service.detect_write(req.sql)
    if not op_type:
        return {
            "is_write": False,
            "message": "只读查询，无需确认",
        }

    try:
        result = preview_service.generate_preview(req.sql)
        return {
            "is_write": True,
            "operation_type": result.operation_type,
            "preview_sql": result.preview_sql,
            "affected_rows": result.affected_rows,
            "sample_data": result.sample_data,
            "columns": result.columns,
            "original_sql": result.original_sql,
        }
    except ValueError as e:
        return {"is_write": False, "error": str(e)}
    except Exception as e:
        logger.error(f"Preview generation failed: {e}")
        return {
            "is_write": True,
            "operation_type": op_type,
            "error": f"预览生成失败: {str(e)}",
            "original_sql": req.sql,
        }


@router.post("/api/sql/confirm")
def sql_confirm(
    req: SqlConfirmRequest,
    workspace: Workspace | None = Depends(get_current_workspace),
):
    """
    Execute a confirmed write operation.
    Only called after the user has reviewed the preview and confirmed.
    """
    _set_ws_context(workspace)
    op_type = preview_service.detect_write(req.sql)
    if not op_type:
        return {"success": False, "error": "该 SQL 不是写操作，请使用 /api/execute-sql"}

    result = preview_service.execute_write(req.sql)
    return result


# ── SQL EXPLAIN (Execution Plan Visualization) ──

@router.post("/api/sql/explain")
def sql_explain(
    req: ExecuteSqlRequest,
    workspace: Workspace | None = Depends(get_current_workspace),
):
    """
    Run EXPLAIN on a SQL query and return the execution plan in structured format.
    Useful for understanding index usage, join strategies, and query optimization.
    """
    from sqlalchemy import text as sa_text
    from app.core.database import get_workspace_session
    from app.core.sql_validator import validator

    _set_ws_context(workspace)

    try:
        # Validate SQL first (only SELECT allowed)
        sql = validator.validate(req.sql)
        explain_sql = f"EXPLAIN {sql}"

        with get_workspace_session() as session:
            result = session.execute(sa_text(explain_sql))
            columns = list(result.keys())
            rows = [list(row) for row in result.fetchall()]

        # Convert non-serializable types
        for row in rows:
            for i, val in enumerate(row):
                if val is None:
                    row[i] = None
                elif hasattr(val, "__float__"):
                    row[i] = float(val)
                elif hasattr(val, "isoformat"):
                    row[i] = val.isoformat()
                else:
                    row[i] = str(val)

        # Parse into structured format for frontend visualization
        steps = []
        for row in rows:
            step = dict(zip(columns, row))
            # Classify access type for visual indicators
            access_type = (step.get("type") or "").upper()
            if access_type in ("ALL",):
                step["_level"] = "danger"     # Full table scan
            elif access_type in ("INDEX", "RANGE"):
                step["_level"] = "warning"    # Index scan / range
            elif access_type in ("REF", "EQ_REF", "CONST", "SYSTEM"):
                step["_level"] = "success"    # Efficient index lookup
            else:
                step["_level"] = "info"
            steps.append(step)

        return {
            "success": True,
            "columns": columns,
            "rows": rows,
            "steps": steps,
            "step_count": len(steps),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── Query Performance Comparison ──

@router.get("/api/performance/stats")
def performance_stats(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_app_db),
):
    """
    Return query performance metrics from history for comparison panel.
    Shows Agent execution time vs cache hit time for repeated queries.
    """
    logs = (
        db.query(QueryLog)
        .order_by(QueryLog.created_at.desc())
        .limit(limit)
        .all()
    )

    items = []
    agent_times = []
    cache_times = []

    for log in logs:
        item = {
            "id": log.id,
            "question": log.question[:60],
            "execution_time_ms": log.execution_time_ms,
            "cached": bool(log.cached),
            "created_at": log.created_at.isoformat() if log.created_at else None,
            "chart_type": log.chart_type,
        }
        items.append(item)

        if log.execution_time_ms is not None:
            if log.cached:
                cache_times.append(log.execution_time_ms)
            else:
                agent_times.append(log.execution_time_ms)

    # Summary statistics
    summary = {
        "total_queries": len(items),
        "agent_queries": len(agent_times),
        "cache_queries": len(cache_times),
        "avg_agent_ms": round(sum(agent_times) / max(len(agent_times), 1), 1),
        "avg_cache_ms": round(sum(cache_times) / max(len(cache_times), 1), 1),
        "max_agent_ms": round(max(agent_times), 1) if agent_times else 0,
        "max_cache_ms": round(max(cache_times), 1) if cache_times else 0,
        "speedup_ratio": round(
            (sum(agent_times) / max(len(agent_times), 1))
            / max(sum(cache_times) / max(len(cache_times), 1), 0.01),
            1
        ) if cache_times and agent_times else None,
    }

    return {
        "success": True,
        "summary": summary,
        "items": items,
    }
