# Vkazarme — Social Network for Fellow Servicemen

A clean-room rebuild of the educational social-network backend (OpenAPI spec v0.3),
built top-down: **API spec → tests → handlers → services → mock (in-memory)
repositories**, with the database layer deliberately left for last.

This repository implements **all six milestones**: accounts, users, friends,
subscriptions, groups, pastes (posts), comments, chats (REST), media
upload/fetch, realtime chat delivery over WebSocket, and the database layer —
SQLAlchemy 2.0 + PostgreSQL behind the same repository interfaces (the
in-memory repositories remain the default mock layer).

## View

%TODO: Здесь нужно добавить картинки 

## Architecture

```
HTTP request
  └─ app/api/            routers + dependencies (thin, HTTP-only concerns)
       └─ app/services/  business rules and permission checks (HTTP-free)
            └─ app/repositories/   interfaces (ABCs)
                 ├─ memory/            in-memory implementations (default mock layer)
                 └─ sqlalchemy_repos/  SQLAlchemy 2.0 + PostgreSQL/SQLite
                      (selected by DATABASE_URL; services do not change)
```

- **Domain models** (`app/domains/models.py`) are plain dataclasses; **DTOs**
  (`app/dto/`) are Pydantic models that validate at the boundary and convert
  with `to_entity()` / `from_entity()`.
- **DI**: `app/container.py` builds one `Container` per app instance
  (`create_app()`), so tests get a fully isolated app with fresh in-memory state.
- **Errors**: services and repositories raise typed exceptions; `app/main.py`
  maps them onto the spec's HTTP codes (400/401/403/404). FastAPI's default
  422 for malformed requests is remapped to **400** to match the spec.

## Layout

```
app/
  main.py                 app factory, exception→HTTP mapping
  container.py            composition root (repos + services)
  seed.py                 startup seeding of example accounts and groups
  settings.py             pydantic-settings (.env supported)
  admins.py               fixed admins loaded from a JSON file
  domains/models.py       framework-agnostic domain models
  dto/                    Pydantic request/response models
  repositories/
    interfaces.py         ABCs the services depend on
    memory/               in-memory implementations (the "mock" data layer)
    sqlalchemy_repos/     ORM models + async SQLAlchemy implementations
  realtime/
    hub.py                WebSocketHub: per-chat subscribers, event push
  api/
    deps.py               Depends() providers, JWT bearer extraction
    account_router.py     /account/signup, /account/signin
    users_router.py       /users, friends, subscriptions
    groups_router.py      /groups, pastes, comments
    chats_router.py       /chats, members, messages
    media_router.py       /media upload, /media/{id} fetch
  services/
    sign_service.py       registration, personal group creation, sign-in
    auth_service.py       JWT issuing/verification
    user_service.py       profile rules, friends, subscriptions
    group_service.py      group search, admin CRUD, deletion cascade
    paste_service.py      posting/deleting rules, comments
    chat_service.py       chat creation, membership rules, messages
    media_service.py      image validation and storage
    ports.py              outbound ports (ChatEventPublisher)
  realtime/
    hub.py                WebSocketHub: per-chat subscribers, event push
tests/
  unit/                   service rules against in-memory repos
  e2e/                    full HTTP tests via httpx ASGI client
```

## Implemented endpoints (milestones 1–6)

| Method | Path | Notes |
|---|---|---|
| POST | `/account/signup` | creates account + personal group + user; bcrypt hashes |
| POST | `/account/signin` | returns a JWT string; admins sign in here too |
| GET | `/users` | search by name/surname (case-insensitive substring), limit/offset |
| GET | `/users/{UserID}` | full profile |
| PATCH | `/users/{UserID}` | owner only; merge-patch semantics |
| DELETE | `/users/{UserID}` | admin only; cascades account, personal group, friends, subscriptions |
| GET/POST | `/users/{UserID}/friends` | friends are symmetric; only on your own list |
| DELETE | `/users/{UserID}/friends/{FriendID}` | |
| GET/POST | `/users/{UserID}/subscriptions` | `is_moderator` only by admin and never on personal groups |
| DELETE | `/users/{UserID}/subscriptions/{SubscriptionID}` | |
| GET | `/groups` | search by name; lists topic groups only (personal ones are found via users) |
| POST | `/groups` | admin only; creates a topic group |
| GET/PATCH/DELETE | `/groups/{GroupID}` | PATCH/DELETE admin only (a moderator may not patch) |
| GET/POST | `/groups/{GroupID}/pastes` | personal group: owner only; topic group: admin + moderators |
| GET/DELETE | `/groups/{GroupID}/pastes/{PasteID}` | delete: admin, group moderator, or personal-group owner |
| GET/POST | `/groups/{GroupID}/pastes/{PasteID}/comments` | any authenticated user; comments carry the author's `UserListItem` |
| GET/POST | `/chats` | personal 1:1 chats (idempotent create, named after the other participant) and public chats (creator becomes owner) |
| GET | `/chats/{ChatID}` | members only |
| GET/POST | `/chats/{ChatID}/members` | any member may add to a public chat; personal chats are fixed |
| DELETE | `/chats/{ChatID}/members/{MemberID}` | self-leave allowed; owner removes anyone but cannot be removed or leave |
| GET/POST | `/chats/{ChatID}/messages` | members only; `user_id` is the author |
| POST | `/media` | multipart `file` field; images only (png/jpeg/gif/webp), 5 MB limit; returns `photo_url` to attach via PATCH |
| GET | `/media/{MediaID}` | public (no token) so URLs work in `<img>` tags |
| WS | `/ws/chats/{ChatID}?token=` | realtime channel — see below |

## Realtime chat (WebSocket)

Protocol per the AsyncAPI contract (`api_specification/asyncapi.yaml`, which
follows the project's own AsyncAPI draft): connect to
`ws://localhost:9999/ws/chats/{ChatID}?token=<JWT>`, send
`{"type": "subscribe", "chatId": <ChatID>}` as the first frame, then the
server pushes envelopes:

```json
{"type": "newMessage",    "chatId": 1, "payload": {"id": 7, "user_id": 1, "text": "hello!", "time": "..."}}
{"type": "memberChange", "chatId": 1, "payload": {"action": "joined", "userId": 3, "role": "member"}}
```

REST stays the write path: `POST /chats/{ChatID}/messages` stores the message
and every subscriber's socket receives it. Keepalive via
`{"type": "ping"}` → `{"type": "pong"}`. Close codes: `4400` bad subscribe
frame, `4401` bad token, `4403` not a member, `4404` unknown chat. Delivery is
at-most-once to connected subscribers — catch up via the REST history
endpoint after reconnect.

Deleting a group (or a user, or a paste) cascades: a group takes its pastes,
their comments and the subscriptions with it; a user takes their personal
group; a paste takes its comments. Deleting a user also removes their chat
memberships and their personal chats (with messages); public chats keep
running without them.

Auth: `Authorization: Bearer <JWT>`; token claims are `sub` (user id, string),
`exp`, and `role` (`user`/`admin`) — the role claim is this implementation's
addition to the spec so the backend can verify admin rights from the token.

## Running

```bash
python3 -m venv .venv            # if python3-venv is missing: install it, or
                                 # create with --without-pip and bootstrap get-pip.py
.venv/bin/pip install -r requirements-dev.txt
cp .env.example .env             # optional; defaults work
.venv/bin/uvicorn app.main:app --port 9999 --reload
```

- Web client: <http://localhost:9999/> (served from `frontend/index.html` by
  the ASGI middleware in `app/middleware.py`, which also adds CORS headers and
  answers preflight `OPTIONS` requests)
- Swagger UI: <http://localhost:9999/docs>
- Admins are the emails listed in `admins.json`; they get the admin role at
  signup. Add your admin email there **before** signing up that account.
- All settings (secret, TTL, bcrypt rounds, admins file) come from the
  environment or `.env` — see `.env.example`.

### Example data on startup

When the application starts (including `docker compose up`), it pre-registers
the accounts from [`account_examples/`](account_examples/) (one JSON profile
per file) and creates the topic groups described in `group_examples/`:

| Email | Password | Role |
|---|---|---|
| `admin@vkazarme.com` | `Admin12345!` | administrator |
| `user1@vkazarme.com` | `User12345!` | user |
| `user2@vkazarme.com` | `User12345!` | user |

The application logs in by **email**, so `email` is the username in each
`account_examples/profile*.json` (`username` is accepted as an alias there).
Optional profile fields (`name`, `surname`, `job`, `rang`, `status`,
`subdivision`, `photo_url`) are applied only when the account is first created.

Each profile is paired with an avatar by number: `profile1.json` gets
`military1.jpeg`; any supported image extension works. A profile may also name
its avatar explicitly with `"avatar": "military1.jpeg"`. The avatar is uploaded
through the normal media service and its `/media/{id}` URL becomes the user's
`photo_url`.

Groups are read from every `*.txt` file in `group_examples/` (for example
`description1.txt`) using this format:

```text
Название группы: Ярые фанаты ОМОНа

Описание: Группа для тех, кто очень сильно хочет ловить хулиганов
```

An avatar is paired by number: `description1.txt` gets `avatar1.png`;
`avatar1.jpg`, `avatar1.webp`, etc. work too. The avatar is uploaded through
the normal media service and its `/media/{id}` URL is stored in the group's
`photo_url`.

Seeding is idempotent and best-effort: accounts are created only when their
email is unknown, groups only when a topic group with the same name is absent.
Existing profiles are not overwritten, so later profile edits and password
changes survive a restart; only a missing example avatar is filled in. A
malformed example file is logged and skipped rather than preventing the app
from starting. The admin account must also be listed in `admins.json`
(`admin@vkazarme.com` already is) — otherwise the account is created as a
regular user and groups are skipped.

Disable seeding with `SEED_ENABLED=false` (recommended outside a demo), and
change these example passwords. With the Compose volume from `pgdata`, the
data persists: use `docker compose down -v` to wipe it and seed from scratch.
The directory locations can be overridden with `ACCOUNT_EXAMPLES_DIR` and
`GROUP_EXAMPLES_DIR`.

### Data layer

By default the app runs on **in-memory repositories** (data lost on restart).
Set `DATABASE_URL` to switch to PostgreSQL — the schema is created
automatically at startup, no services change:

```bash
docker compose up -d db               # Postgres on localhost:5433
DATABASE_URL='postgresql+asyncpg://vkazarme:vkazarme@localhost:5433/vkazarme' \
  .venv/bin/uvicorn app.main:app --port 9999
```

Repository choices are made in `app/container.py`; both implementations sit
behind the same interfaces. One deliberate trade-off: each repository method
is its own short transaction, so multi-step service cascades (e.g. group
deletion) are not atomic — a unit of work would be the next hardening step.
The database enforces only the uniqueness the interfaces promise (unique
email, unique subscription per user+group, one membership per chat); all
other referential integrity is service-owned, which keeps behavior identical
across both implementations (e.g. a deleted user's messages survive in
public chats).

## Tests

```bash
.venv/bin/python -m pytest          # 285 tests, ~2 min (bcrypt rounds lowered to 4 in tests)
```

The 44 integration tests run the SQLAlchemy repository layer twice — on
SQLite (always) and on a real PostgreSQL from `testcontainers` (skipped
automatically when Docker is unavailable).

## Docker

```bash
docker compose up --build           # API on :9999, PostgreSQL schema + example data
```

The Compose file mounts `admins.json`, `account_examples/` and
`group_examples/` read-only, so editing the examples only needs
`docker compose restart api` (the database keeps already seeded rows, though).
Set `SEED_ENABLED=false` to skip seeding entirely.

## Spec inconsistencies found (for spec v0.4)

1. `POST /users/{UserID}/friends` references schema `Friend`, `POST
   /users/{UserID}/subscriptions` references `Subscription`, `/account/signup`
   references `SignUpRequest`, `POST /groups/{GroupID}/pastes` references
   `PastePost`, and the comments POST references `Comment` (whose id/time/author
   are server-side) — none of these exist in `components` as usable request
   bodies. The natural request bodies were used: `FriendPost`,
   `SubscriptionPost`, email+password, and `{text}` for both pastes and
   comments.
2. `SubscriptionListItem` has no `id`, which makes DELETE
   `/users/{UserID}/subscriptions/{SubscriptionID}` unusable from the list
   response. An `id` field was added on top of the schema.
3. `Paste` has no author field, so a feed cannot show who wrote a post (only
   the group). The domain model keeps `author_id` for permission checks;
   adding `author: UserListItem` (as `Comment` already has) is recommended
   for v0.4.
4. `GET /users/{UserID}` returns `User` without `personal_group_id`, while the
   list item has it — kept as specified.
5. `photo_url` is required everywhere but there is no way to have one before the
   media endpoint exists; it defaults to an empty string for now.
6. The spec's 403 for bad sign-in credentials is unusual (401 is conventional)
   — followed the spec.
7. The `Message` schema's property list says `chat_member_id` while its
   required list says `user_id`; responses use `user_id` (the author). The
   message POST body is `{text}` (id/author/time are server-generated).
8. The spec leaves chat membership rules open; the decisions are documented
   in the contract's `info.description` (changes #11–#12): idempotent personal
   chat creation, fixed personal chats, member-invites-member in public
   chats with `is_owner` ignored, owner cannot be removed or leave.

## Handover contract

The frontend-facing contract lives in [`api_specification/openapi.yaml`](api_specification/openapi.yaml)
(JSON twin: `api_specification/openapi.json`), with the realtime channel in
[`api_specification/asyncapi.yaml`](api_specification/asyncapi.yaml). They are
the source of truth for handover: validated against OpenAPI 3.1.0 / AsyncAPI
2.6.0 and checked to match the live app path-for-path (33 REST operations).
The FastAPI app also serves the REST contract at `GET /openapi.json`.
