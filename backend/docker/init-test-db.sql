-- Выполняется автоматически при первой инициализации volume postgres (docker-entrypoint-initdb.d).
-- Создаёт отдельную БД для pytest, чтобы прогон тестов (create_all/drop_all в tests/conftest.py)
-- никогда не затрагивал dev-базу "prostor".
CREATE DATABASE prostor_test OWNER prostor;
\connect prostor_test
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
