"""uvicorn entrypoint for the scientific runtime service (dev/localhost only)."""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8101, log_level="info")
