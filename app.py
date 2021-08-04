__version__ = "1.1"

import os
from dotenv import load_dotenv
from pathlib import Path

from sanic import Sanic, response
from sanic.exceptions import NotFound
from jinja2 import Environment, FileSystemLoader

from core.models import LogEntry
from core.utils import DB, with_document

load_dotenv()
app = Sanic(__name__)
jinja_env = Environment(loader=FileSystemLoader("templates"))


def render_template(name, *args, **kwargs):
    template = jinja_env.get_template(name + ".html")
    return response.html(template.render(*args, **kwargs))


app.ctx.render_template = render_template

app.static("/static", Path("static"))


@app.exception(NotFound)
async def not_found(request, exc):
    return render_template("not_found")


@app.get("/")
async def index(request):
    return render_template("index")


@app.get("/api/raw/<gid>/<key>")
@with_document()
async def get_raw_logs_file(request, document):
    """Returns the plain text rendered log entry"""
    if document is None:
        raise NotFound()

    log_entry = LogEntry(app, document)
    return log_entry.render_plain_text()


@app.get("/<gid>/<key>")
@with_document()
async def get_logs_file(request, document):
    """Returns the html rendered log entry"""
    if document is None:
        raise NotFound()

    log_entry = LogEntry(app, document)
    return log_entry.render_html()


if __name__ == "__main__":
    app.run(
        host=os.getenv("HOST", "127.0.0.1"),
        port=os.getenv("PORT", 8000),
        debug=bool(os.getenv("DEBUG", False)),
    )
