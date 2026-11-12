CREATE USER simple_user NOSUPERUSER NOCREATEDB PASSWORD 'simple_user';
CREATE USER admin NOSUPERUSER NOCREATEDB PASSWORD 'admin_password';--TODO: Надо бы как-то вставить пароль через hashicorp vault или другие
CREATE USER readonly NOSUPERUSER NOCREATEDB PASSWORD 'readonly';

CREATE TYPE PROVIDER_ENUM AS ENUM ('vk', 'google', 'self');
CREATE TYPE CHAT

--TODO: Необходимо создать индексы для быстрого поиска по Name и Surname

-- ============================================================
-- 1. Accounts — учётные записи (аутентификация)
-- ============================================================
CREATE TABLE accounts (
    id          BIGSERIAL PRIMARY KEY,
    email       VARCHAR(255) UNIQUE, -- NULL, если вход через OAuth
    hashed_password    VARCHAR(255), -- NULL, если вход только через OAuth
    --is_admin    BOOLEAN NOT NULL DEFAULT FALSE, --Права админа я храню в Redis
	oauth_provider    PROVIDER_ENUM,
    oauth_user_id VARCHAR(255) NOT NULL,  -- ID пользователя у провайдера
    UNIQUE (provider, external_id)
);

-- ============================================================
-- 4. Groups — группы (включая личные странички пользователей)
-- ============================================================
CREATE TABLE groups (
    id              BIGSERIAL PRIMARY KEY,
    name            VARCHAR(500) NOT NULL DEFAULT 'No name',
    description     TEXT DEFAULT 'No description',
    photo_url       VARCHAR(1024),
    is_personal     BOOLEAN NOT NULL DEFAULT FALSE  -- личная группа пользователя
    --created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- 5. Users — публичные профили
-- ============================================================
CREATE TABLE users (
    id                BIGSERIAL PRIMARY KEY,
    account_id        BIGINT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    personal_group_id BIGINT NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    name              VARCHAR(255) NOT NULL DEFAULT 'Noname',
    surname           VARCHAR(255) NOT NULL DEFAULT 'Nosurname',
    job               VARCHAR(255) DEFAULT 'Unknown job',
    rang              INTEGER NOT NULL DEFAULT 0,
    status            VARCHAR(255) DEFAULT 'Unknown status',
    subdivision       VARCHAR(500) DEFAULT 'Unknown subdivision',
    photo_url         VARCHAR(1024),
    --created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (account_id)
);

-- ============================================================
-- 6. Friends — дружеские связи (двунаправленные)
-- ============================================================
CREATE TABLE friends (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    friend_id   BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    --created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, friend_id),
    CHECK (user_id <> friend_id)
);

-- ============================================================
-- 7. Subscriptions — подписки на группы
-- ============================================================
CREATE TABLE subscriptions (
    id            BIGSERIAL PRIMARY KEY,
    user_id       BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    group_id      BIGINT NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    is_moderator  BOOLEAN NOT NULL DEFAULT FALSE,
    --created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, group_id)
);

-- ============================================================
-- 8. Pastes — записи/посты в группах
-- ============================================================
CREATE TABLE pastes (
    id          BIGSERIAL PRIMARY KEY,
    group_id    BIGINT NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    author_id   BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    text        TEXT NOT NULL
    --created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- 9. Comments — комментарии к записям
-- ============================================================
CREATE TABLE comments (
    id          BIGSERIAL PRIMARY KEY,
    paste_id    BIGINT NOT NULL REFERENCES pastes(id) ON DELETE CASCADE,
    author_id   BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    text        TEXT NOT NULL
    --created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- 10. Chats — чаты (личные и публичные)
-- ============================================================
CREATE TABLE chats (
    id          BIGSERIAL PRIMARY KEY,
    name        VARCHAR(500) NOT NULL DEFAULT 'No name',
    photo_url   VARCHAR(1024),
    chat_type   VARCHAR(20) NOT NULL DEFAULT 'personal'
                    CHECK (chat_type IN ('personal', 'public')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- 11. Chat members — участники чатов
-- ============================================================
CREATE TABLE chat_members (
    id          BIGSERIAL PRIMARY KEY,
    chat_id     BIGINT NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    is_owner    BOOLEAN NOT NULL DEFAULT FALSE,
    joined_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (chat_id, user_id)
);

-- ============================================================
-- 12. Messages — сообщения в чатах
-- ============================================================
CREATE TABLE messages (
    id              BIGSERIAL PRIMARY KEY,
    chat_id         BIGINT NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    chat_member_id  BIGINT NOT NULL REFERENCES chat_members(id) ON DELETE CASCADE,
    text            TEXT NOT NULL,
    sent_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
