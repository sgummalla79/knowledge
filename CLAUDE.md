# knowledge-api Project Instructions

This application is called **knowledge-api** (container/image name: `knowledge-api`, prod image
tag `knowledge-api:prod`). It only runs locally right now (no real production deployment), but the
running `api` container is what rag-desktop and any MCP clients are actively depending on — call it
**prod** to keep it unambiguous from throwaway test containers.

## Docker testing workflow — never test against the prod container

**Rule:** Never run tests, migrations, or manual verification against the `api` / `knowledge-db`
containers defined in `docker-compose.yml` (the prod stack). Rebuilding or restarting them
mid-verification can break a running client or, worse, apply an unverified migration to the real
database.

Instead:

1. `./scripts/test-image.sh` — runs `pytest` (unit tests are mocked, integration tests spin up
   their own ephemeral Postgres via testcontainers — neither touches any docker-compose container),
   then builds a separate image (`knowledge-api:testing`) and boots it as `knowledge-api-test` +
   `knowledge-db-test` (`docker-compose.test.yml`), fully isolated on port 13199 with a throwaway
   tmpfs database, under its own compose project (`knowledge-api-test`) so it's never confused with
   the prod stack. Confirms the built image actually boots (migrations run, gunicorn serves
   `/health`) before it goes anywhere near prod. Tears the isolated stack down automatically on
   exit, success or failure.
2. Only once that passes, run `./scripts/promote-image.sh` — this rebuilds and restarts the prod
   `api` container (`knowledge-api:prod`, via `docker compose up -d --build api`). This is the only
   command allowed to touch the prod container.

Do not shortcut this by running `docker compose up -d --build api` directly as a way to "just check
if it works" — that mutates the prod container immediately, with no isolated verification step
first. If you need to iterate quickly during development, iterate against
`docker-compose.test.yml` (or plain `pytest`), not the prod stack.
