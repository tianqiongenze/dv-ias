"""DV-IAS web：村民H5 / 管理端 / 指挥大屏 静态站。"""
import sys

sys.path.insert(0, "/srv")

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="dv-web")

BASE = Path(__file__).resolve().parent.parent / "static"


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(BASE / "h5" / "index.html")


@app.get("/admin", include_in_schema=False)
def admin():
    return FileResponse(BASE / "admin" / "index.html")


@app.get("/screen", include_in_schema=False)
def screen():
    return FileResponse(BASE / "screen" / "index.html")


app.mount("/static", StaticFiles(directory=BASE), name="static")
