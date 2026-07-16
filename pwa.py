from pathlib import Path

from flask import Blueprint, render_template, send_from_directory

pwa_bp = Blueprint("pwa", __name__)
PWA_DIR = Path(__file__).resolve().parent / "static" / "pwa"


@pwa_bp.get("/service-worker.js")
def service_worker():
    response = send_from_directory(PWA_DIR, "service-worker.js", mimetype="application/javascript")
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Service-Worker-Allowed"] = "/"
    return response


@pwa_bp.get("/manifest.webmanifest")
def web_manifest():
    response = send_from_directory(PWA_DIR, "manifest.webmanifest", mimetype="application/manifest+json")
    response.headers["Cache-Control"] = "public, max-age=3600"
    return response


@pwa_bp.get("/offline")
def offline():
    return render_template("offline.html"), 200
