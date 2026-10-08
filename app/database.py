from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import settings

# For SQLite, check_same_thread=False allows multi-threaded async FastAPI workers
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def ensure_schema_columns():
    """Safely apply column additions for PostgreSQL / SQLite without destroying existing data."""
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            # executions table
            try:
                conn.execute(text("ALTER TABLE executions ADD COLUMN IF NOT EXISTS session_id VARCHAR(64);"))
                conn.commit()
            except Exception:
                pass
            # conversations table
            try:
                conn.execute(text("ALTER TABLE conversations ADD COLUMN IF NOT EXISTS title VARCHAR(256) DEFAULT 'New Chat';"))
                conn.execute(text("ALTER TABLE conversations ADD COLUMN IF NOT EXISTS session_id VARCHAR(64);"))
                conn.execute(text("ALTER TABLE conversations ADD COLUMN IF NOT EXISTS user_id VARCHAR(64);"))
                conn.commit()
            except Exception:
                pass
            # memories table
            try:
                conn.execute(text("ALTER TABLE memories ADD COLUMN IF NOT EXISTS user_id VARCHAR(64);"))
                conn.commit()
            except Exception:
                pass
    except Exception:
        pass

# Run safe migration on module load
ensure_schema_columns()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
