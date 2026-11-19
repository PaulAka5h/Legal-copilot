import asyncio
from logging.config import fileConfig
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import pool, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

config = context.config
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None


def get_database_url(*, offline: bool) -> str:
    bootstrap = context.get_x_argument(as_dictionary=True).get("bootstrap") == "true"
    variable = (
        "ALEMBIC_BOOTSTRAP_DATABASE_URL" if bootstrap else "ALEMBIC_DATABASE_URL"
    )
    url = os.getenv(variable)
    if url:
        return url
    if offline:
        return "postgresql+asyncpg://"
    raise RuntimeError(f"{variable} is required for online migrations")


def run_migrations_offline() -> None:
    url = get_database_url(offline=True)
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    url = get_database_url(offline=False)
    bootstrap = context.get_x_argument(as_dictionary=True).get("bootstrap") == "true"
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        if bootstrap:
            version_table = await connection.scalar(
                text("SELECT to_regclass('public.alembic_version')")
            )
            # An empty version table (left by `downgrade base`) means no
            # revision is applied, so bootstrap is still allowed.
            applied = (
                await connection.scalar(
                    text("SELECT count(*) FROM public.alembic_version")
                )
                if version_table is not None
                else 0
            )
            if applied:
                raise RuntimeError(
                    "Bootstrap credentials are only allowed before the first migration"
                )
            await connection.commit()
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
