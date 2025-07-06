from fastapi import FastAPI
from gateway.endpoints import router

app = FastAPI()
app.include_router(router)