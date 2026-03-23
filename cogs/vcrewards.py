import discord
from discord.ext import commands, tasks

from database import get_user_monies, add_vc_minutes


class VCRewards(commands.Cog):
    """Awards 1 carat per hour spent in eligible voice channels."""

    def __init__(self, bot):
        self.bot = bot
        self.active_vc: set[tuple] = set()  # (guild_id, user_id)
        self.vc_tick.start()

    def cog_unload(self):
        self.vc_tick.cancel()

    async def _sync_active_vc(self):
        """Populate active_vc from current voice state (called after bot is ready)."""
        for guild in self.bot.guilds:
            afk_id = guild.afk_channel.id if guild.afk_channel else None
            for vc in guild.voice_channels:
                if vc.id == afk_id:
                    continue
                for member in vc.members:
                    if member.bot or not member.voice or member.voice.self_deaf:
                        continue
                    self.active_vc.add((guild.id, member.id))
                    get_user_monies(member.id, guild.id)  # ensure row exists

    @commands.Cog.listener()
    async def on_ready(self):
        """Re-sync active_vc on reconnect so stale state is cleared."""
        self.active_vc.clear()
        await self._sync_active_vc()

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot:
            return
        guild = member.guild
        afk_id = guild.afk_channel.id if guild.afk_channel else None
        key = (guild.id, member.id)

        in_eligible = (
            after.channel is not None
            and after.channel.id != afk_id
            and not after.self_deaf
        )

        if in_eligible:
            self.active_vc.add(key)
            get_user_monies(member.id, guild.id)  # ensure row exists
        else:
            self.active_vc.discard(key)

    @tasks.loop(minutes=1)
    async def vc_tick(self):
        for guild_id, user_id in list(self.active_vc):
            add_vc_minutes(user_id, guild_id, delta=1)

    @vc_tick.before_loop
    async def before_vc_tick(self):
        await self.bot.wait_until_ready()
        await self._sync_active_vc()  # safe: bot is ready, guilds are populated


async def setup(bot):
    await bot.add_cog(VCRewards(bot))
