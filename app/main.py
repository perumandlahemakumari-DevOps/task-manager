import os

import psycopg
from flask import Flask, jsonify, request
from prometheus_client import Counter, Histogram, generate_latest
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.wrappers import Response


app = Flask(__name__)

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
)


@app.before_request
def start_timer():
    request.start_time = __import__("time").perf_counter()


@app.after_request
def record_metrics(response):
    endpoint = request.endpoint or "unknown"
    elapsed = __import__("time").perf_counter() - request.start_time
    REQUEST_COUNT.labels(request.method, endpoint, response.status_code).inc()
    REQUEST_LATENCY.labels(request.method, endpoint).observe(elapsed)
    return response


def get_connection():
    database_url = os.environ["DATABASE_URL"]
    return psycopg.connect(database_url)


def init_db():
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                completed BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )


@app.get("/")
def index():
    return jsonify(message="Task Manager API", version="0.1.0")


@app.get("/healthz")
def health():
    return jsonify(status="ok"), 200


@app.get("/readyz")
def ready():
    try:
        with get_connection() as conn:
            conn.execute("SELECT 1")
        return jsonify(status="ready"), 200
    except psycopg.Error:
        return jsonify(status="database unavailable"), 503


@app.get("/tasks")
def list_tasks():
    try:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT id, title, completed, created_at FROM tasks ORDER BY id"
            ).fetchall()
        return jsonify(
            tasks=[
                {
                    "id": row[0],
                    "title": row[1],
                    "completed": row[2],
                    "created_at": row[3].isoformat(),
                }
                for row in rows
            ]
        )
    except psycopg.Error:
        return jsonify(error="database unavailable"), 503


@app.post("/tasks")
def create_task():
    payload = request.get_json(silent=True) or {}
    title = payload.get("title", "").strip()
    if not title:
        return jsonify(error="title is required"), 400

    try:
        with get_connection() as conn:
            row = conn.execute(
                "INSERT INTO tasks (title) VALUES (%s) "
                "RETURNING id, title, completed, created_at",
                (title,),
            ).fetchone()
        return jsonify(
            id=row[0],
            title=row[1],
            completed=row[2],
            created_at=row[3].isoformat(),
        ), 201
    except psycopg.Error:
        return jsonify(error="database unavailable"), 503


@app.patch("/tasks/<int:task_id>")
def update_task(task_id):
    payload = request.get_json(silent=True) or {}
    if "title" not in payload and "completed" not in payload:
        return jsonify(error="provide title or completed"), 400

    try:
        with get_connection() as conn:
            row = conn.execute(
                """
                UPDATE tasks
                SET title = COALESCE(%s, title),
                    completed = COALESCE(%s, completed)
                WHERE id = %s
                RETURNING id, title, completed, created_at
                """,
                (
                    payload.get("title"),
                    payload.get("completed"),
                    task_id,
                ),
            ).fetchone()
        if row is None:
            return jsonify(error="task not found"), 404
        return jsonify(
            id=row[0],
            title=row[1],
            completed=row[2],
            created_at=row[3].isoformat(),
        )
    except psycopg.Error:
        return jsonify(error="database unavailable"), 503


@app.delete("/tasks/<int:task_id>")
def delete_task(task_id):
    try:
        with get_connection() as conn:
            result = conn.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
        if result.rowcount == 0:
            return jsonify(error="task not found"), 404
        return "", 204
    except psycopg.Error:
        return jsonify(error="database unavailable"), 503


def metrics_app(environ, start_response):
    response = Response(generate_latest(), content_type="text/plain; version=0.0.4")
    return response(environ, start_response)


app.wsgi_app = DispatcherMiddleware(app.wsgi_app, {"/metrics": metrics_app})


with app.app_context():
    try:
        init_db()
    except psycopg.Error:
        # The app can start before PostgreSQL; /readyz will report unavailable.
        pass
