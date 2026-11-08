"""Alembic environment cho Mini Crawler (P01 Item 2)."""

from __future__ import annotations

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# Alembic Config object, cung cấp quyền truy cập vào các giá trị trong file .ini.
config = context.config

# Gończy logging từ alembic.ini.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None  # Không dùng autogenerate; migration viết tay bằng SQL.


def run_migrations_offline() -> None:
    """Chạy migration ở chế độ offline (sinh SQL, không kết nối DB)."""
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
    """Chạy migration ở chế độ online (kết nối DB và thực thi)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
