import logging
import json
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
import time

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def setup_logging():
    """Setup logging configuration"""
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Request logging middleware"""
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Get request ID from state (set by RequestIDMiddleware)
        request_id = getattr(request.state, "request_id", None)
        
        # Log request
        logger.info(
            json.dumps({
                "type": "request",
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "client": request.client.host if request.client else None
            })
        )
        
        response = await call_next(request)
        
        # Calculate duration
        duration = time.time() - start_time
        
        # Log response
        logger.info(
            json.dumps({
                "type": "response",
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round(duration * 1000, 2)
            })
        )
        
        return response

