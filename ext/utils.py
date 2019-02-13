import asyncio
import functools
import inspect
import random
import re

import discord
from discord.ext import commands


class InvalidTag(commands.BadArgument):
    """Raised when a tag is invalid."""

    message = 'Player tags should only contain these characters:\n' \
              '**Numbers:** 0, 2, 8, 9\n' \
              '**Letters:** P, Y, L, Q, G, R, J, C, U, V'


class InvalidBSTag(InvalidTag):
    """Raised when a brawl stars tag is invalid."""
    pass


class InvalidPlatform(commands.BadArgument):
    """Raised when a platform is invalid."""
    message = 'Platforms should only be one of the following:\n' \
              'pc, ps4, xb1'


class APIError(Exception):
    pass


class NoTag(Exception):
    pass


def has_perms():
    perms = {
        'send_messages': True,
        'embed_links': True,
        'external_emojis': True
    }

    return commands.bot_has_permissions(**perms)


def statsy_guild():
    def predicate(ctx):
        if isinstance(ctx.channel, discord.TextChannel):
            return ctx.guild.id == 444482551139008522
        return False
    return commands.check(predicate)


def developer():
    def predicate(ctx):
        return ctx.author.id in ctx.bot.developers
    return commands.check(predicate)


def random_color():
    return random.randint(0, 0xFFFFFF)


def asyncexecutor(loop=None, executor=None):
    loop = loop or asyncio.get_event_loop()

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            partial = functools.partial(func, *args, **kwargs)
            return loop.run_in_executor(executor, partial)
        return wrapper
    return decorator


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


def e(name, *, should_format=True, ctx=None):
    ctx = ctx or get_stack_variable('ctx') or get_stack_variable('self')

    name = str(name)
    if should_format:
        name = name.lower()
        replace = {
            # new: to_replace
            '': ['.', ' ', '_', '-'],
            'chestgold': 'chestgolden'
        }
        for key, value in replace.items():
            if isinstance(value, list):
                for val in value:
                    name = name.replace(val, key)
            else:
                name = name.replace(value, key)

    emoji = discord.utils.get(ctx.bot.game_emojis, name=name)
    return emoji or name


def cdir(obj):
    return [x for x in dir(obj) if not x.startswith('_')]


def lower(arg):
    return arg.lower()


def camel_case(text, split=' '):
    # from stackoverflow :p
    if text in (None, 'PvP'):
        return text
    matches = re.finditer('.+?(?:(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])|$)', text)
    return split.join(m.group(0) for m in matches).title()
