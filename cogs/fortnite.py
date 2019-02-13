import json
import time
import os
from urllib.parse import urlencode

import aiohttp
import datadog
import discord
from discord.ext import commands

from ext import utils
from ext.embeds import fortnite
from ext.paginator import Paginator

from ext.command import cog, command
from locales.i18n import Translator

_ = Translator('Fortnite', __file__)


class TagOrUser(commands.UserConverter):
    async def convert(self, ctx, argument):
        try:
            return await super().convert(ctx, argument)
        except commands.BadArgument:
            return argument


def lower(argument):
    return argument.lower()


@cog('fn')
class Fortnite:
    """Commands related to the Fortnite game"""
    def __init__(self, bot):
        self.bot = bot
        self.alias = 'fn'
        bot.loop.create_task(self.__ainit__())

    async def __ainit__(self):
        self.session = aiohttp.ClientSession(loop=self.bot.loop)

    async def __local_check(self, ctx):
        if isinstance(ctx.channel, discord.TextChannel):
            guild_info = await self.bot.mongo.config.guilds.find_one({'guild_id': str(ctx.guild.id)}) or {}
            return guild_info.get('games', {}).get(self.__class__.__name__, True)
        else:
            return True

    def __unload(self):
        self.bot.loop.create_task(self.session.close())

    async def resolve_username(self, ctx, username, platform):
        if not username:
            try:
                return await ctx.get_tag('fortnite', f'{ctx.author.id}: {platform}')
            except KeyError:
                try:
                    default_game = self.bot.default_game[ctx.guild.id]
                except AttributeError:
                    default_game = self.bot.default_game[ctx.channel.id]
                cmd_name = 'save' if default_game == self.__class__.__name__ else f'{self.alias}save'

                await ctx.send(_("You don't have a saved tag. Save one using `{}{} <platform> <username>!`").format(ctx.prefix, cmd_name))
                raise utils.NoTag
        else:
            if platform not in ('pc', 'ps4', 'xb1'):
                raise utils.InvalidPlatform
            if isinstance(username, discord.User):
                try:
                    return await ctx.get_tag('fortnite', f'{username.id}: {platform}')
                except KeyError:
                    await ctx.send(_('That person doesnt have a saved tag!'))
                    raise utils.NoTag
            else:
                if username.startswith('-'):
                    return await ctx.get_tag('fortnite', f'{username.id}: {platform}', index=username.replace('-', ''))
                return username

    async def __error(self, ctx, error):
        error = getattr(error, 'original', error)
        if isinstance(error, utils.APIError):
            await ctx.send(_('Fortnite API is currently undergoing maintenance. Please try again later.'))

    async def post(self, endpoint, payload, *, reason='command'):
        headers = {
            'Authorization': os.getenv('fortnite'),
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        speed = time.time()
        async with self.session.post(
            'https://fortnite-public-api.theapinetwork.com/prod09' + endpoint,
            data=urlencode(payload), headers=headers
        ) as resp:
            speed = speed - time.time()
            datadog.statsd.increment('statsy.api_latency', 1, [
                'game:fortnite', f'speed:{speed}', f'method:{endpoint}'
            ])
            datadog.statsd.increment('statsy.requests', 1, [
                'game:fortnite', f'code:{resp.status}', f'method:{endpoint}', f'reason:{reason}'
            ])
            if resp.status != 200:
                raise utils.APIError
            try:
                data = await resp.json()
                if not data:
                    raise utils.APIError
            except (json.JSONDecodeError, aiohttp.client_exceptions.ContentTypeError):
                raise utils.APIError
            else:
                return data

    async def get_player_uid(self, ctx, name):
        data = await self.post('/users/id', {'username': name}, reason='get_uid')
        if data.get('code') in ('1012', '1006'):
            await ctx.send(_('The username cannot be found!'))
            raise utils.NoTag

        if not data.get('uid'):
            await ctx.send('Invalid username.')
            raise utils.NoTag
        return data['uid']

    @command()
    async def save(self, ctx, platform: lower, username: str, index: str='0'):
        """Saves a Fortnite tag to your discord profile."""
        await ctx.save_tag(username, 'fortnite', f'{ctx.author.id}: {platform}', index=index.replace('-', ''))

        try:
            default_game = self.bot.default_game[ctx.guild.id]
        except AttributeError:
            default_game = self.bot.default_game[ctx.channel.id]
        cmd_name = 'profile' if default_game == self.__class__.__name__ else f'{self.alias}profile'

        if index == '0':
            prompt = _('Check your stats with `{}{}`!').format(ctx.prefix, cmd_name)
        else:
            prompt = _('Check your stats with `{}{} -{}`!').format(ctx.prefix, cmd_name, index)

        await ctx.send(_('Successfully saved tag. ') + prompt)

    @command()
    @utils.has_perms()
    async def profile(self, ctx, platform: lower, *, username: TagOrUser=None):
        """Gets the fortnite profile of a player with a provided platform"""
        async with ctx.typing():
            username = await self.resolve_username(ctx, username, platform)
            uid = await self.get_player_uid(ctx, username)
            player = await self.post('/users/public/br_stats_all', {
                'user_id': uid, 'window': 'alltime', 'platform': platform
            })

            ems = await fortnite.format_profile(ctx, platform, player)

        await Paginator(ctx, *ems, footer_text=_('Statsy - Powered by fortniteapi.com')).start()

    @command()
    @utils.has_perms()
    async def usertag(self, ctx, platform: lower, *, member: discord.User=None):
        """Checks the saved tag(s) of a member"""
        member = member or ctx.author
        tag = await ctx.get_tag('fortnite', f'{member.id}: {platform}', index='all')
        em = discord.Embed(description='Tags saved', color=utils.random_color())
        em.set_author(name=member.name, icon_url=member.avatar_url)
        for i in tag:
            em.add_field(name=f'Tag index: {i}', value=tag[i])
        await ctx.send(embed=em)


def setup(bot):
    bot.add_cog(Fortnite(bot))
