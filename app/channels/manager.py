"""Channel manager — discovers and runs all configured channel adapters.

For each active agent, reads its channels config and starts adapters
for IRC, Telegram, Discord as configured.

Runs as a standalone process: python -m app.channels.manager
Also available as a Docker service in compose.yaml.
"""

import asyncio
import logging
import os

import httpx
from sqlalchemy import select

from app.channels.base import BaseChannelAdapter
from app.channels.base import ChannelConfig
from app.channels.discord import DiscordAdapter
from app.channels.irc import IRCAdapter
from app.channels.telegram import TelegramAdapter
from app.db import async_session
from app.models import Agent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger("learnharness.channels.manager")

API_BASE = os.environ.get("API_BASE_URL", "http://api:8000")


async def get_channel_configs() -> list[tuple[ChannelConfig, dict, str]]:
    """Query the DB for all active agents with channel configurations.

    Returns list of (ChannelConfig, platform_config, platform_name) tuples.
    """
    configs = []

    async with async_session() as db:
        stmt = select(Agent).where(Agent.active == True)  # noqa: E712
        agents = (await db.execute(stmt)).scalars().all()

        for agent in agents:
            channels = agent.channels or {}
            for platform, platform_config in channels.items():
                if platform not in ("irc", "telegram", "discord"):
                    log.warning("Unknown channel '%s' on agent '%s'", platform, agent.name)
                    continue
                if not platform_config:
                    continue

                cc = ChannelConfig(
                    agent_id=agent.id,
                    agent_name=agent.name,
                    master_prompt=agent.master_prompt,
                    api_base=API_BASE,
                    llm_model=agent.llm_model,
                )
                configs.append((cc, platform_config, platform))

    return configs


async def run_adapter(cc: ChannelConfig, platform_config: dict, platform: str) -> None:
    """Start and run a single adapter until it stops."""
    adapter: BaseChannelAdapter | None = None
    try:
        if platform == "irc":
            adapter = IRCAdapter(cc, platform_config)
        elif platform == "telegram":
            adapter = TelegramAdapter(cc, platform_config)
        elif platform == "discord":
            adapter = DiscordAdapter(cc, platform_config)
        else:
            return

        await adapter.start()

        # Join channels for IRC
        if isinstance(adapter, IRCAdapter):
            await adapter.join_channels()

        # Run the listen loop
        await adapter.listen()

    except Exception:
        log.exception("Adapter '%s/%s' crashed", platform, cc.agent_name)
    finally:
        if adapter:
            await adapter.stop()


async def main():
    """Main entry point — start all adapters."""
    log.info("Channel manager starting...")

    # Wait for API to be ready
    api_ready = False
    for i in range(30):
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{API_BASE}/v1/agents")
                if resp.is_success:
                    api_ready = True
                    break
        except Exception:
            log.debug("API not ready, retrying...")
        log.info("Waiting for API... (%d/30)", i + 1)
        await asyncio.sleep(2)

    if not api_ready:
        log.error("API not available after 30 retries, exiting")
        raise RuntimeError("API not available")

    while True:
        try:
            configs = await get_channel_configs()

            if not configs:
                log.info("No channels configured. Waiting 60s...")
                await asyncio.sleep(60)
                continue

            log.info("Starting %d adapter(s):", len(configs))
            tasks = []
            for cc, platform_config, platform in configs:
                log.info(
                    "  %s — %s — agent '%s'",
                    platform,
                    platform_config.get("nick", platform_config.get("token", "")[:8] + "..."),
                    cc.agent_name,
                )
                task = asyncio.create_task(
                    run_adapter(cc, platform_config, platform),
                    name=f"{platform}-{cc.agent_id[:8]}",
                )
                tasks.append(task)

            # Wait for all adapters (they run forever)
            await asyncio.gather(*tasks, return_exceptions=True)

        except KeyboardInterrupt:
            log.info("Shutting down...")
            break
        except Exception:
            log.exception("Manager error")
            await asyncio.sleep(10)

        # Re-check config every 5 minutes for new agents
        log.info("Adapters ended. Restarting in 30s...")
        await asyncio.sleep(30)


if __name__ == "__main__":
    asyncio.run(main())
