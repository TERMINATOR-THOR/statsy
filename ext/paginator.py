import asyncio

import discord

from ext.utils import e


class Paginator:
    """
    Class that paginates a list of discord.Embed objects
    Parameters
    ------------
    ctx: discord.Context
        The context of the command.
    \*embeds: discord.Embed
        A list of entries to paginate.

    \*\*timeout: int[Optional]
        How long to wait for before the session closes
        Default: 30
    \*\*footer_text: str[Optional]
        Footer text before the page number
    \*\*edit_footer: bool[Optional]
        Whether to update the footer with page number.
        Footers only get edited if there is more than one embed
        Default: True
    \*\*dest: discord.Messageable[Optional]
        Destination to send Paginated embeds
        Default: ctx
    Methods
    -------
    start:
        Starts the paginator session
    stop:
        Stops the paginator session and deletes the embed.
    """
    def __init__(self, ctx, *embeds, **kwargs):
        """Initialises the class"""
        self.embeds = list(embeds)

        if len(self.embeds) == 0:
            raise SyntaxError('There should be at least 1 embed object provided to the paginator')

        if kwargs.get('edit_footer', True) and len(self.embeds) > 1:
            for i, em in enumerate(self.embeds):
                footer_text = f'Page {i+1} of {len(self.embeds)}'
                em.footer.text = kwargs.get('footer_text', em.footer.text)
                if em.footer.text:
                    footer_text = footer_text + ' | ' + em.footer.text

                em.set_footer(text=footer_text, icon_url=em.footer.icon_url)

        self.page = 0
        self.ctx = ctx
        self.timeout = kwargs.get('timeout', 30)
        self.running = False
        self.emojis = {
            u'\u23EE': 'track_previous',
            u'\u25C0': 'arrow_backward',
            u'\u23F9': 'stop_button',
            u'\u25B6': 'arrow_forward',
            u'\u23ED': 'track_next'
        }
        self.destination = kwargs.get('dest', ctx)

    async def start(self):
        """Starts the paginator session"""
        self.message = await self.destination.send(embed=self.embeds[0])

        if len(self.embeds) == 1:
            return

        self.running = True
        self.ctx.bot.loop.create_task(self._wait_for_reaction())
        for emoji in self.emojis:
            if emoji.startswith('<:'):
                await self.message.add_reaction(emoji[2:-1])
            else:
                await self.message.add_reaction(emoji)
            await asyncio.sleep(0.05)

    async def stop(self):
        self.running = False
        try:
            await self.message.clear_reactions()
        except (discord.NotFound, discord.Forbidden):
            pass

    async def _wait_for_reaction(self):
        """Waits for a user input reaction"""
        while self.running:
            try:
                reaction, user = await self.ctx.bot.wait_for(
                    'reaction_add',
                    check=self._reaction_check,
                    timeout=self.timeout
                )
            except asyncio.TimeoutError:
                await self.stop()
            else:
                if self.running:
                    self.ctx.bot.loop.create_task(self._reaction_action(reaction))

    def _reaction_check(self, reaction, user):
        """Checks if the reaction is from the user message and emoji is correct"""
        if not self.running:
            return True
        if user.id == self.ctx.author.id:
            if str(reaction.emoji) in self.emojis:
                if reaction.message.id == self.message.id:
                    return True
        return False

    async def _blank(self):
        pass

    async def _reaction_action(self, reaction):
        """Fires an action based on the reaction"""
        if not self.running:
            return
        to_exec = self.emojis[str(reaction.emoji)]

        await getattr(self, f'exec_{to_exec}')()
        await getattr(self, 'exec_before_edit', self._blank)()

        try:
            await self.message.edit(embed=self.embeds[self.page])
        except discord.NotFound:
            await self.stop()

        try:
            await self.message.remove_reaction(reaction.emoji, self.ctx.author)
        except (discord.Forbidden, discord.NotFound):
            pass

    async def exec_arrow_backward(self):
        if self.page != 0:
            self.page -= 1
        return True

    async def exec_arrow_forward(self):
        if self.page != len(self.embeds) - 1:
            self.page += 1
        return True

    async def exec_stop_button(self):
        await self.message.delete()
        await self.ctx.message.add_reaction('check:383917703083327489')
        return False

    async def exec_track_previous(self):
        self.page = 0

    async def exec_track_next(self):
        self.page = len(self.embeds) - 1


class WikiPaginator(Paginator):
    def __init__(self, ctx, brawler_power, *embeds, **kwargs):
        super().__init__(ctx, *embeds, **kwargs)
        self.brawler_power = brawler_power
        if self.brawler_power:
            self.emojis[str(e('28000000', ctx=self.ctx))] = 'jump_to_player'

    async def exec_jump_to_player(self):
        self.page = self.brawler_power
