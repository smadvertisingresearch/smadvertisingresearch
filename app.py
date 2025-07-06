from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import sqlite3
import os
from contextlib import contextmanager

#hello

app = FastAPI()

app.mount("/videos", StaticFiles(directory="videos"), name="videos")
