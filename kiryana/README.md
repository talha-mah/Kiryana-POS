# Kiryana POS

Flask and PostgreSQL based POS system for small kiryana shops.

## Setup

1. Create a PostgreSQL database named `kiryana`.
2. Copy `.env.example` to `.env`.
3. Update `DATABASE_URL` in `.env` with your local PostgreSQL password.
4. Run `run.bat`.

Default admin login after database setup:

```text
admin@kiryana.pk / admin123
```

## Notes

- The application uses PostgreSQL as the live source of truth.
- Local files such as `.env`, `.venv_win`, cache folders, and SQLite backups are intentionally ignored by Git.
