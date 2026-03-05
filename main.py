import discord
import aiohttp
import logging
from discord import app_commands
from discord.ext import tasks
from datetime import datetime, time
from typing import Optional

from config import Config
from engine import BankEngine
from dashboard import BankDashboardView


class BankBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)

        self.tree = app_commands.CommandTree(self)
        self.session: Optional[aiohttp.ClientSession] = None
        self.engine: Optional[BankEngine] = None
        self.dashboard_msg_id: Optional[int] = None

    async def setup_hook(self):
        connector = aiohttp.TCPConnector(limit=10, ttl_dns_cache=300)
        self.session = aiohttp.ClientSession(connector=connector)

        self.engine = BankEngine(self.session)
        self.add_view(BankDashboardView(self))
        self.daily_task.start()
        await self.tree.sync()
        logging.info(f"Logged in as {self.user.name}")

    async def create_report_embed(self, date_str: str) -> discord.Embed:
        if not self.engine:
            raise RuntimeError("Engine not initialized")

        results = await self.engine.get_summary_report(date_str)

        total_tx = sum(r.get('tx', 0) for r in results if 'tx' in r)
        total_amt = sum(r.get('amt', 0.0) for r in results if 'amt' in r)

        embed = discord.Embed(
            title=f"🔄 การเชื่อมต่อ API: ({date_str})",
            color=0x2ecc71 if total_tx > 0 else 0x95a5a6,
            timestamp=datetime.now()
        )

        active_lines = []
        inactive_names = []
        error_list = []

        for res in results:
            if "error" in res:
                error_list.append(f"- {res['name']}: {res['error']}")
            elif res.get('status') == 'active':
                line = (
                    f"🏦 {res['name']} 🕒 {res['last_time']}\n"
                    f"   📝 เจอ {res['tx']} รายการ\n"
                    f"   💰 ยอด {res['amt']:,.2f}"
                )
                active_lines.append(line)
            else:
                inactive_names.append(res['name'])

        if active_lines:
            content = "\n\n".join(active_lines)
            embed.add_field(
                name="🟢 รายการที่มีความเคลื่อนไหว",
                value=f"```yaml\n{content}\n```",
                inline=False
            )

        if error_list:
            error_msg = "\n".join(error_list)
            embed.add_field(
                name="⚠️ พบปัญหาการเชื่อมต่อ",
                value=f"```diff\n{error_msg}\n```",
                inline=False
            )

        if inactive_names:
            names_str = ", ".join(inactive_names)
            embed.add_field(
                name="💤 ยังไม่มีรายการ",
                value=f"```fix\n{names_str}\n```",
                inline=False
            )

        embed.add_field(
            name="📊 ยอดรวมทั้งหมด",
            value=f"```yaml\n🧾 รายการ: {total_tx:,} tx\n💰 เงินรวม: {total_amt:,.2f} THB\n```",
            inline=False
        )

        return embed

    async def process_report_interaction(self, interaction: discord.Interaction, date_str: str):
        try:
            await interaction.response.send_message(
                f"⏳ กำลังดึงข้อมูล API ของวันที่ {date_str} กรุณารอสักครู่...",
                ephemeral=False
            )

            embed = await self.create_report_embed(date_str)
            embed.set_footer(text=f"Checked by {interaction.user.display_name}")

            await interaction.edit_original_response(content=None, embed=embed)

            if isinstance(interaction.channel, discord.TextChannel):
                await self.refresh_dashboard(interaction.channel)

        except Exception as e:
            logging.error(f"Error processing report: {e}")
            try:
                await interaction.edit_original_response(
                    content="❌ เกิดข้อผิดพลาดในการดึงข้อมูล (API ปลายทางอาจไม่ตอบสนอง)",
                    embed=None
                )
            except:
                pass

    async def refresh_dashboard(self, channel: discord.TextChannel):
        if self.dashboard_msg_id:
            try:
                msg = await channel.fetch_message(self.dashboard_msg_id)
                await msg.delete()
            except discord.NotFound:
                pass
            except Exception as e:
                logging.error(f"Error deleting dashboard message: {e}")

        embed = discord.Embed(
            title="🎛️ Control Panel",
            description="กดปุ่มด้านล่างเพื่อตรวจสอบสถานะ API ของธนาคาร",
            color=0x2b2d31
        )

        msg = await channel.send(embed=embed, view=BankDashboardView(self))
        self.dashboard_msg_id = msg.id

    @tasks.loop(time=[
        time(hour=7, minute=30, tzinfo=Config.THAI_TZ),
        time(hour=11, minute=15, tzinfo=Config.THAI_TZ),
    ])
    async def daily_task(self):
        try:
            try:
                channel = await self.fetch_channel(Config.CHANNEL_ID)
            except discord.NotFound:
                logging.error(f"Channel {Config.CHANNEL_ID} not found")
                return
            except discord.Forbidden:
                logging.error(f"Bot missing permissions to access channel {Config.CHANNEL_ID}")
                return
            except Exception as e:
                logging.error(f"Error fetching channel: {e}")
                channel = self.get_channel(Config.CHANNEL_ID)

            if not channel:
                logging.warning(f"Channel {Config.CHANNEL_ID} could not be retrieved")
                return

            if isinstance(channel, discord.TextChannel):
                try:
                    await channel.purge(limit=20, check=lambda m: not m.pinned)
                except Exception as e:
                    logging.error(f"Error purging channel: {e}")

                today = datetime.now(Config.THAI_TZ).strftime("%Y-%m-%d")
                logging.info(f"Running daily task for {today}")

                embed = await self.create_report_embed(today)
                embed.title = f"📢 รายงาน API อัตโนมัติ: ({today})"

                await channel.send(embed=embed)
                await self.refresh_dashboard(channel)

                logging.info("Daily task completed successfully")

        except Exception as e:
            logging.error(f"Error in daily_task: {e}")

    @daily_task.before_loop
    async def before_daily(self):
        await self.wait_until_ready()

    async def close(self):
        if self.session:
            await self.session.close()
        await super().close()


# ==================================================
# RUN
# ==================================================
if __name__ == "__main__":
    try:
        Config.validate()
        bot = BankBot()
        bot.run(Config.TOKEN, log_handler=None)
    except ValueError as e:
        logging.error(str(e))
    except Exception as e:
        logging.error(f"FATAL ERROR: {e}")