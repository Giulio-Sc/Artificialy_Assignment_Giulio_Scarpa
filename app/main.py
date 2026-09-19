"""Application entry point."""

from fastapi import FastAPI

from app.api import router

app = FastAPI(
    title="Cleaning Robot API",
    description="Remote control for a household cleaning robot.",
    version="1.0.0",
)
app.include_router(router)
