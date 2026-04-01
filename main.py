from core.create_app import create_app
from core.config import get_settings
import uvicorn

app = create_app()
settings = get_settings()

if __name__ == "__main__":

    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.RELOAD,
        log_level=settings.LOG_LEVEL,
    )