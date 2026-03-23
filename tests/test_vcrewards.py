import sys
import os
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# asyncio_mode = auto is set in pytest.ini — no marks needed on individual tests.


def make_member(user_id, guild_id, self_deaf=False, bot=False):
    """Build a minimal mock discord.Member."""
    member = MagicMock()
    member.id = user_id
    member.bot = bot
    guild = MagicMock()
    guild.id = guild_id
    guild.afk_channel = None
    member.guild = guild
    voice = MagicMock()
    voice.self_deaf = self_deaf
    member.voice = voice
    return member


def make_voice_state(channel=None, self_deaf=False):
    vs = MagicMock()
    vs.channel = channel
    vs.self_deaf = self_deaf
    return vs


def make_channel(channel_id):
    ch = MagicMock()
    ch.id = channel_id
    return ch


@pytest.fixture
def cog():
    """Bare VCRewards instance with __init__ bypassed (no tasks started)."""
    from cogs.vcrewards import VCRewards
    bot = MagicMock()
    bot.guilds = []
    c = VCRewards.__new__(VCRewards)
    c.bot = bot
    c.active_vc = set()
    return c


class TestOnVoiceStateUpdate:
    async def test_user_joining_vc_added_to_active(self, cog):
        channel = make_channel(999)
        member = make_member(1, 100)
        before = make_voice_state(channel=None)
        after = make_voice_state(channel=channel, self_deaf=False)

        with patch("cogs.vcrewards.get_user_monies"):
            await cog.on_voice_state_update(member, before, after)

        assert (100, 1) in cog.active_vc

    async def test_user_leaving_vc_removed_from_active(self, cog):
        cog.active_vc.add((100, 1))
        channel = make_channel(999)
        member = make_member(1, 100)
        before = make_voice_state(channel=channel)
        after = make_voice_state(channel=None)

        with patch("cogs.vcrewards.get_user_monies"):
            await cog.on_voice_state_update(member, before, after)

        assert (100, 1) not in cog.active_vc

    async def test_self_deafened_user_removed(self, cog):
        cog.active_vc.add((100, 1))
        channel = make_channel(999)
        member = make_member(1, 100)
        before = make_voice_state(channel=channel, self_deaf=False)
        after = make_voice_state(channel=channel, self_deaf=True)

        with patch("cogs.vcrewards.get_user_monies"):
            await cog.on_voice_state_update(member, before, after)

        assert (100, 1) not in cog.active_vc

    async def test_self_muted_user_stays_active(self, cog):
        channel = make_channel(999)
        member = make_member(1, 100)
        before = make_voice_state(channel=None)
        after = make_voice_state(channel=channel, self_deaf=False)

        with patch("cogs.vcrewards.get_user_monies"):
            await cog.on_voice_state_update(member, before, after)

        assert (100, 1) in cog.active_vc

    async def test_bot_user_ignored(self, cog):
        channel = make_channel(999)
        member = make_member(1, 100, bot=True)
        before = make_voice_state(channel=None)
        after = make_voice_state(channel=channel)

        with patch("cogs.vcrewards.get_user_monies"):
            await cog.on_voice_state_update(member, before, after)

        assert (100, 1) not in cog.active_vc

    async def test_afk_channel_not_added(self, cog):
        afk = make_channel(777)
        member = make_member(1, 100)
        member.guild.afk_channel = afk
        before = make_voice_state(channel=None)
        after = make_voice_state(channel=afk, self_deaf=False)

        with patch("cogs.vcrewards.get_user_monies"):
            await cog.on_voice_state_update(member, before, after)

        assert (100, 1) not in cog.active_vc

    async def test_undeafen_adds_back_to_active(self, cog):
        channel = make_channel(999)
        member = make_member(1, 100)
        before = make_voice_state(channel=channel, self_deaf=True)
        after = make_voice_state(channel=channel, self_deaf=False)

        with patch("cogs.vcrewards.get_user_monies"):
            await cog.on_voice_state_update(member, before, after)

        assert (100, 1) in cog.active_vc
