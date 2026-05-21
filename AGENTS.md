# AGENTS.md

## Project Background

This is an AI learning platform.

- Frontend: React + Vite
- Backend: FastAPI
- Database: SQLite

The project already includes:

- Login and registration
- Chat API
- Chat history saving
- Chat history reading
- Chat history deletion
- Server deployment

## Development Rules

1. Implement only one small feature at a time.
2. Before modifying code, explain which files will be changed.
3. Do not modify `.env` files.
4. Do not read, output, or print real API keys.
5. Do not perform large-scale refactors.
6. Do not delete existing features without a clear reason.
7. After frontend changes, explain how to test with `npm run dev`.
8. After backend changes, explain how to test with `uvicorn` or `systemctl restart ai-backend`.
9. For database changes, explain whether a migration is required.
10. After each task, summarize:
    - Which files changed
    - What was implemented
    - How to test it
    - Whether there are any risks

## User Preferences

The user wants each code change to clearly state which file should be modified.
