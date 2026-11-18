-- ======================================
-- Схема бази даних для Supabase (PostgreSQL)
-- Telegram-бот для домашніх завдань
-- ======================================
-- Виконай цей SQL у Supabase SQL Editor:
-- https://supabase.com/dashboard → SQL Editor → New query
-- ======================================


-- ── Таблиця користувачів ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id          BIGSERIAL PRIMARY KEY,
    telegram_id BIGINT    UNIQUE NOT NULL,
    username    TEXT,
    full_name   TEXT,
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Індекс для швидкого пошуку за telegram_id
CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id);


-- ── Таблиця завдань ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tasks (
    id          UUID      PRIMARY KEY DEFAULT gen_random_uuid(),
    telegram_id BIGINT    NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    subject     TEXT      NOT NULL,
    description TEXT      NOT NULL,
    deadline    TIMESTAMP WITH TIME ZONE NOT NULL,
    status      TEXT      NOT NULL DEFAULT 'active'
                          CHECK (status IN ('active', 'completed')),
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Індекс для запитів по користувачу та статусу
CREATE INDEX IF NOT EXISTS idx_tasks_telegram_id_status
    ON tasks(telegram_id, status);

-- Індекс для запитів по дедлайну (для планувальника)
CREATE INDEX IF NOT EXISTS idx_tasks_deadline
    ON tasks(deadline) WHERE status = 'active';


-- ── Таблиця результатів тестів ────────────────────────────────
CREATE TABLE IF NOT EXISTS quiz_results (
    id          UUID      PRIMARY KEY DEFAULT gen_random_uuid(),
    telegram_id BIGINT    NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    task_id     UUID      REFERENCES tasks(id) ON DELETE SET NULL,
    score       INTEGER   CHECK (score >= 0 AND score <= 100),
    feedback    TEXT,
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Індекс для запитів по користувачу
CREATE INDEX IF NOT EXISTS idx_quiz_results_telegram_id
    ON quiz_results(telegram_id);


-- ── Row Level Security (RLS) — опціонально для безпеки ────────
-- Вмикаємо RLS для таблиць (рекомендовано для production)
ALTER TABLE users        ENABLE ROW LEVEL SECURITY;
ALTER TABLE tasks        ENABLE ROW LEVEL SECURITY;
ALTER TABLE quiz_results ENABLE ROW LEVEL SECURITY;

-- Дозволяємо повний доступ для service_role (використовується в коді).
-- DROP ... IF EXISTS — щоб скрипт можна було запускати повторно без помилок.
DROP POLICY IF EXISTS "service_role_users"        ON users;
DROP POLICY IF EXISTS "service_role_tasks"        ON tasks;
DROP POLICY IF EXISTS "service_role_quiz_results" ON quiz_results;
CREATE POLICY "service_role_users"        ON users        FOR ALL TO service_role USING (true);
CREATE POLICY "service_role_tasks"        ON tasks        FOR ALL TO service_role USING (true);
CREATE POLICY "service_role_quiz_results" ON quiz_results FOR ALL TO service_role USING (true);
