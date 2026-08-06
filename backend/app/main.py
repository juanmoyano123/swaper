from fastapi import FastAPI

app = FastAPI(title="10-Swaper API")


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
