import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from my_memgpt import _settings as settings
async def fetch_all_tables_info(session: AsyncSession):
    # Запрос для получения всех таблиц
    tables_query = text("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
    """)

    # Запрос для получения всех столбцов таблицы
    columns_query = text("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = :table_name
    """)

    async with session.begin():
        # Выполняем запрос для получения всех таблиц
        tables_result = await session.execute(tables_query)
        tables = tables_result.fetchall()

        for table in tables:
            table_name = table[0]
            print(f"Table: {table_name}")

            # Выполняем запрос для получения всех столбцов текущей таблицы
            columns_result = await session.execute(columns_query, {'table_name': table_name})
            columns = columns_result.fetchall()

            for column in columns:
                column_name, data_type = column
                print(f"  Column: {column_name}, Type: {data_type}")

# Пример использования функции
async def main():
    DATABASE_URL = settings.SETTINGS.pg_connection
    engine = create_async_engine(DATABASE_URL, echo=True)
    async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with async_session() as session:
        await fetch_all_tables_info(session)

# Запуск асинхронной функции
if __name__ == "__main__":
    asyncio.run(main())