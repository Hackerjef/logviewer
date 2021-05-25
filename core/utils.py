import asyncio
import datetime
import inspect
import re
from functools import wraps

from discord.enums import DefaultAvatar
from discord.utils import snowflake_time
from dotenv import dotenv_values
from motor.motor_asyncio import AsyncIOMotorClient
from sanic import response
from sanic.exceptions import abort

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

class User:
    def __init__(self, data):
        self.name = data["username"]
        self.id = int(data["id"])
        self.discriminator = data["discriminator"]
        self.avatar = data["avatar"]
        self.mfa_enabled = data.get("mfa_enabled", False)
        self.premium_type = data.get("premium_type")
        self.bot = False

    def __str__(self):
        return "{0.name}#{0.discriminator}".format(self)

    @property
    def avatar_url(self):
        return self.avatar_url_as(format=None, size=1024)

    def is_avatar_animated(self):
        return bool(self.avatar and self.avatar.startswith("a_"))

    def avatar_url_as(self, *, format=None, static_format="webp", size=1024):
        if self.avatar is None:
            return self.default_avatar_url

        if format is None:
            if self.is_avatar_animated():
                format = "gif"
            else:
                format = static_format

        # Discord has trouble animating gifs if the url does not end in `.gif`
        gif_fix = "&_=.gif" if format == "gif" else ""

        return "https://cdn.discordapp.com/avatars/{0.id}/{0.avatar}.{1}?size={2}{3}".format(
            self, format, size, gif_fix
        )

    @property
    def default_avatar(self):
        """Returns the default avatar for a given user. This is calculated by the user's discriminator"""
        return DefaultAvatar(int(self.discriminator) % len(DefaultAvatar))

    @property
    def default_avatar_url(self):
        """Returns a URL for a user's default avatar."""
        return "https://cdn.discordapp.com/embed/avatars/{}.png".format(
            self.default_avatar.value
        )

    @property
    def mention(self):
        """Returns a string that allows you to mention the given user."""
        return "<@{0.id}>".format(self)

    @property
    def created_at(self):
        """Returns the user's creation time in UTC.
        This is when the user's discord account was created."""
        return snowflake_time(self.id)


def get_stack_variable(name):
    stack = inspect.stack()
    try:
        for frames in stack:
            try:
                frame = frames[0]
                current_locals = frame.f_locals
                if name in current_locals:
                    return current_locals[name]
            finally:
                del frame
    finally:
        del stack


def authrequired():
    def decorator(func):
        @wraps(func)
        async def wrapper(request, gid, key):
            app = request.app
            if gid not in app.db.dbs_conns:
                abort(404, message="Guild Not added to this viewer", )
            db = app.db.dbs_conns.get(int(gid))
            
            if not app.using_oauth:
                return await func(request, await db.logs.find_one({"key": key}))
            elif not request["session"].get("logged_in"):
                request["session"]["from"] = request.url
                return response.redirect("/login")

            user = request["session"]["user"]

            config, document = await asyncio.gather(
                db.config.find_one({"bot_id": int(app.bot_id)}),
                db.logs.find_one({"key": key}),
            )

            whitelist = config.get("oauth_whitelist", [])
            if document:
                if str(app.bot_id) != document.get("bot_id"):
                    abort(
                        401,
                        message="Your account does not have permission to view this page.",
                    )
                whitelist.extend(document.get("oauth_whitelist", []))

            if int(user["id"]) in whitelist or "everyone" in whitelist:
                return await func(request, document)

            roles = await app.get_user_roles(user["id"])

            if any(int(r) in whitelist for r in roles):
                return await func(request, document)

            abort(
                401, message="Your account does not have permission to view this page."
            )

        return wrapper

    return decorator
