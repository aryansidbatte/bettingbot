import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import discord
from helpers import info_embed, error_embed, get_reply_or_cancel


class TestInfoEmbed:
    def test_returns_embed(self):
        result = info_embed("Title", "Desc")
        assert isinstance(result, discord.Embed)

    def test_title_and_description(self):
        result = info_embed("My Title", "My Desc")
        assert result.title == "My Title"
        assert result.description == "My Desc"

    def test_default_color_is_blue(self):
        result = info_embed("T", "D")
        assert result.colour == discord.Color.blue()

    def test_custom_color(self):
        result = info_embed("T", "D", discord.Color.green())
        assert result.colour == discord.Color.green()


class TestErrorEmbed:
    def test_returns_embed(self):
        result = error_embed("Something went wrong")
        assert isinstance(result, discord.Embed)

    def test_title_is_error(self):
        result = error_embed("msg")
        assert result.title == "❌ Error"

    def test_description_is_message(self):
        result = error_embed("bad input")
        assert result.description == "bad input"

    def test_color_is_red(self):
        result = error_embed("msg")
        assert result.colour == discord.Color.red()


class TestGetReplyOrCancel:
    def _make_ctx(self, author=None, channel=None):
        ctx = MagicMock()
        ctx.author = author or MagicMock()
        ctx.channel = channel or MagicMock()
        ctx.send = AsyncMock()
        return ctx

    def _make_message(self, content, ctx):
        msg = MagicMock()
        msg.content = content
        msg.author = ctx.author
        msg.channel = ctx.channel
        return msg

    def test_returns_message_on_valid_reply(self):
        async def run():
            ctx = self._make_ctx()
            bot = MagicMock()
            reply = self._make_message("my answer", ctx)
            bot.wait_for = AsyncMock(return_value=reply)
            result = await get_reply_or_cancel(bot, ctx, "What is your answer?")
            assert result is reply

        asyncio.run(run())

    def test_returns_none_on_cancel(self):
        async def run():
            ctx = self._make_ctx()
            bot = MagicMock()
            reply = self._make_message("cancel", ctx)
            bot.wait_for = AsyncMock(return_value=reply)
            result = await get_reply_or_cancel(bot, ctx, "prompt")
            assert result is None

        asyncio.run(run())

    def test_cancel_is_case_insensitive(self):
        async def run():
            ctx = self._make_ctx()
            bot = MagicMock()
            reply = self._make_message("CANCEL", ctx)
            bot.wait_for = AsyncMock(return_value=reply)
            result = await get_reply_or_cancel(bot, ctx, "prompt")
            assert result is None

        asyncio.run(run())

    def test_returns_none_on_timeout(self):
        async def run():
            ctx = self._make_ctx()
            bot = MagicMock()
            bot.wait_for = AsyncMock(side_effect=asyncio.TimeoutError())
            result = await get_reply_or_cancel(bot, ctx, "prompt", timeout=0.01)
            assert result is None

        asyncio.run(run())

    def test_sends_prompt_with_cancel_hint(self):
        async def run():
            ctx = self._make_ctx()
            bot = MagicMock()
            reply = self._make_message("answer", ctx)
            bot.wait_for = AsyncMock(return_value=reply)
            await get_reply_or_cancel(bot, ctx, "What is X?")
            sent_text = ctx.send.call_args[0][0]
            assert "cancel" in sent_text.lower()

        asyncio.run(run())
