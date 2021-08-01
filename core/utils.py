import re
from functools import wraps
from sanic.exceptions import abort

from dotenv import dotenv_values
from motor.motor_asyncio import AsyncIOMotorClient

RE_MONGODB = re.compile("MONGO_URI_(.*)")


class DB:
    def __init__(self):
        self.envfile = dotenv_values(".env")
        self.dbs = dict()
        self.dbs_conns = dict()

        for (key, value) in self.envfile.items():
            match = re.match(RE_MONGODB, key)
            if match:
                self.dbs[int(match.groups()[0])] = value

        for (gid, connURI) in self.dbs.items():
            self.dbs_conns[gid] = AsyncIOMotorClient(connURI).modmail_bot


def with_document():
    def decorator(func):
        @wraps(func)
        async def wrapper(request, gid, key):
            app = request.app
            if not str(gid).isdigit():
                abort(404, message="Not a guild ID", )
            db = app.ctx.dbs.dbs_conns.get(int(gid))
            if not db:
                abort(404, message="Guild Not added to this viewer", )

            document = await db.logs.find_one({"key": key})

            return await func(request, document)

        return wrapper

    return decorator
