"""Lambda entry point. Wraps the existing FastAPI app for a Lambda Function
URL, whose event format matches API Gateway HTTP API v2.0 - Mangum handles
both without extra configuration.
"""

from mangum import Mangum

from app.main import app

handler = Mangum(app)
