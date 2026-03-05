import discord
import logging
from discord import ui
from datetime import datetime, timedelta
from config import Config

class DateInputModal(ui.Modal, title="ระบุวันที่"):
    date_input = ui.TextInput(label="YYYY-MM-DD", placeholder="2026-02-04", min_length=10, max_length=10)

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        try:
            val = self.date_input.value
            datetime.strptime(val, "%Y-%m-%d")
            await self.bot.process_report_interaction(interaction, val)
        except ValueError:
            await interaction.response.send_message("❌ วันที่ผิดรูปแบบ (YYYY-MM-DD)", ephemeral=True)
        except Exception as e:
            logging.error(f"Error in date modal submission: {e}")
            await interaction.response.send_message("❌ เกิดข้อผิดพลาดในการประมวลผล", ephemeral=True)


class BankDashboardView(ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if Config.ALLOWED_USERS and interaction.user.id not in Config.ALLOWED_USERS:
            await interaction.response.send_message("🚫 Admin Only", ephemeral=True)
            return False
        return True

    @ui.button(label="วันนี้", emoji="☀️", style=discord.ButtonStyle.success, custom_id="btn_today")
    async def today(self, itn: discord.Interaction, _):
        d = datetime.now(Config.THAI_TZ).strftime("%Y-%m-%d")
        await self.bot.process_report_interaction(itn, d)

    @ui.button(label="เมื่อวาน", emoji="⏮️", style=discord.ButtonStyle.primary, custom_id="btn_yesterday")
    async def yesterday(self, itn: discord.Interaction, _):
        d = (datetime.now(Config.THAI_TZ) - timedelta(days=1)).strftime("%Y-%m-%d")
        await self.bot.process_report_interaction(itn, d)

    @ui.button(label="ระบุวัน", emoji="📅", style=discord.ButtonStyle.secondary, custom_id="btn_custom")
    async def custom(self, itn: discord.Interaction, _):
        await itn.response.send_modal(DateInputModal(self.bot))

    @ui.button(label="เคลียร์จอ", emoji="🧹", style=discord.ButtonStyle.danger, custom_id="btn_clear")
    async def clear(self, itn: discord.Interaction, _):
        await itn.response.defer(ephemeral=True)
        await itn.channel.purge(limit=50, check=lambda m: not m.pinned)
        await self.bot.refresh_dashboard(itn.channel)