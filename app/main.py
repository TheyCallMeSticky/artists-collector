from fastapi import FastAPI
from app.api.artists import router as artists_router
from app.api.collection import router as collection_router
from app.api.scoring import router as scoring_router
from app.db.database import engine, Base

# Créer les tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Artists Collector API",
    description="API pour collecter et analyser les données d'artistes hip-hop émergents",
    version="1.0.0"
)

# Inclure les routes
app.include_router(artists_router)
app.include_router(collection_router)
app.include_router(scoring_router)

@app.get("/")
def read_root():
    return {"message": "Welcome to the Artists Collector API"}

@app.get("/health")
def health_check():
    return {"status": "ok"}
