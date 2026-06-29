import importlib.util
import os
import sys
from logging.config import fileConfig

from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool
from sqlalchemy.orm import DeclarativeBase

from alembic import context

# Paths
backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
auth_backend_root = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "Auth-Backend")
)

# Load .env from Backend root
load_dotenv(os.path.join(backend_root, ".env"))


# ─── Shared Base ──────────────────────────────────────────────────────────────
# Create a single shared Base that ALL models will register on.
class Base(DeclarativeBase):
    pass


# ─── Helper to import a model file and register on shared Base ────────────────
def _load_model(model_path: str, module_name: str):
    """Load a model .py file, patching its Base import to use our shared Base."""
    spec = importlib.util.spec_from_file_location(module_name, model_path)
    module = importlib.util.module_from_spec(spec)

    # Create a fake base module that returns our shared Base
    fake_base_module_name = "src.data.models.postgres.base"
    if fake_base_module_name not in sys.modules:

        class _FakeBaseModule:
            Base = None

        sys.modules[fake_base_module_name] = _FakeBaseModule()

    sys.modules[fake_base_module_name].Base = Base
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


# ─── Import Auth-Backend models ───────────────────────────────────────────────
auth_models_dir = os.path.join(auth_backend_root, "src", "data", "models", "postgres")
auth_model_files = ["user", "role", "permission", "role_permission", "refresh_token"]

for model in auth_model_files:
    path = os.path.join(auth_models_dir, f"{model}.py")
    _load_model(path, f"auth_models.{model}")

# ─── Import Backend models ────────────────────────────────────────────────────
backend_models_dir = os.path.join(backend_root, "src", "data", "models", "postgres")
backend_model_files = [
    "department",
    "staff",
    "doctor",
    "patient",
    "appointment_type",
    "doctor_unavailability",
    "appointment",
    "notification",
    "conversation",
    "conversation_message",
    "audit_log",
]

for model in backend_model_files:
    path = os.path.join(backend_models_dir, f"{model}.py")
    _load_model(path, f"backend_models.{model}")

# ─── Alembic Config ──────────────────────────────────────────────────────────
config = context.config

# Build database URL from env vars
DATABASE_URL = (
    f"postgresql+psycopg2://"
    f"{os.getenv('POSTGRES_USER')}:"
    f"{os.getenv('POSTGRES_PASSWORD')}@"
    f"{os.getenv('POSTGRES_HOST')}:"
    f"{os.getenv('POSTGRES_PORT')}/"
    f"{os.getenv('POSTGRES_DB')}"
)
config.set_main_option("sqlalchemy.url", DATABASE_URL)

# Logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata — contains ALL tables from both Auth-Backend and Backend
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
