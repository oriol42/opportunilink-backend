# alembic/env.py
# Alembic configuration — connects migrations to our models and database

from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# Import our settings and Base
from app.config import settings
from app.database import Base

# Import ALL models so Alembic can detect them
# If a model is not imported here, Alembic won't see it
import app.models  # This triggers __init__.py which imports all models


# ALEMBIC CONFIG


# Alembic's config object — gives access to alembic.ini values
config = context.config

# Override sqlalchemy.url with our .env value
# This is why we left it empty in alembic.ini
config.set_main_option("sqlalchemy.url", settings.database_url)

# Setup Python logging from alembic.ini config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# This is the metadata Alembic uses to detect schema changes
# Base.metadata knows about all models that inherit from Base
target_metadata = Base.metadata


# MIGRATION FUNCTIONS


def run_migrations_offline() -> None:
    """
    Run migrations without a live DB connection.
    Generates SQL scripts you can review before applying.
    Useful for production where you want to review SQL first.
    """
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
    """
    Run migrations with a live DB connection.
    This is what we use in development — changes applied immediately.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # No connection pooling during migrations
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # Tells Alembic to compare array types correctly (PostgreSQL specific)
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


# Run offline or online depending on context
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()