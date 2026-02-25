import os
import asyncio
import discord
import aiohttp
import logging
from discord import app_commands, ui
from discord.ext import tasks
from dotenv import load_dotenv
from datetime import datetime, time, timezone, timedelta
from typing import Dict, Any, Optional, List

# ==================================================
# 0. LOGGING SETUP
# ==================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
# หรี่เสียง Log ของ discord ทั้งตระกูล (ตัดปัญหา PyNaCl และ Log ซ้ำซ้อนทิ้ง 100%)
logging.getLogger('discord').setLevel(logging.ERROR)

# ==================================================
# 1. CONFIGURATION
# ==================================================
load_dotenv()

class Config:
    TOKEN = os.getenv("DISCORD_BOT_TOKEN")
    CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID") or 0)
    
    ALLOWED_USERS = [
        int(uid.strip()) 
        for uid in os.getenv("ALLOWED_USER_IDS", "").split(",") 
        if uid.strip() and uid.strip().isdigit()
    ]
    
    BASE_URL = os.getenv("BANK_API_URL")
    THAI_TZ = timezone(timedelta(hours=7))
    
    @classmethod
    def validate(cls):
        if not cls.TOKEN:
            raise ValueError("❌ DISCORD_BOT_TOKEN not found in .env")
        if cls.CHANNEL_ID == 0:
            raise ValueError("❌ DISCORD_CHANNEL_ID not found or invalid in .env")
        if not cls.BASE_URL:
            raise ValueError("❌ BANK_API_URL not found in .env")
        logging.info("✅ Config validated successfully")
    
    BANKS = [
        {"code": "006", "name": "KTB (กรุงไทย)"},
        {"code": "014", "name": "SCB (ไทยพาณิชย์)"},
        {"code": "004", "name": "KBANK (กสิกร)"},
        {"code": "034", "name": "BAAC (ธกส.)"},
        {"code": "998", "name": "ThaiPost (ปณ.)"},
        {"code": "709", "name": "CS (Counter)"},
        {"code": "030", "name": "GSB (ออมสิน)"},
    ]

# ==================================================
# 2. CORE ENGINE
# ==================================================
class BankEngine:
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        # คุมคิวจำกัดการยิง API ป้องกันปัญหาคอขวดและ Timeout
        self.semaphore = asyncio.Semaphore(5)

    def _format_time(self, raw_val: str) -> str:
        try:
            if not raw_val:
                return "--:--"
            if " " in raw_val:
                return raw_val.split(" ")[1][:5]
            if len(raw_val) == 6 and raw_val.isdigit():
                return f"{raw_val[:2]}:{raw_val[2:4]}:{raw_val[4:6]}"
            return raw_val
        except Exception as e:
            logging.warning(f"Error formatting time '{raw_val}': {e}")
            return "--:--"

    async def fetch_single_bank(self, bank: Dict[str, str], date_str: str) -> Dict[str, Any]:
        params = {
            "bankid": bank["code"],
            "datestart": f"{date_str} 00:00:00",
            "dateend": f"{date_str} 23:59:59",
        }
        
        async with self.semaphore:
            try:
                # ปรับ Timeout ให้กระชับ ไม่หน่วงระบบ
                async with self.session.get(Config.BASE_URL, params=params, timeout=8) as resp:
                    if resp.status != 200:
                        return {"name": bank["name"], "error": f"HTTP {resp.status}"}
                    
                    try:
                        data = await resp.json()
                    except Exception as e:
                        logging.error(f"JSON decode error for {bank['name']}: {e}")
                        return {"name": bank["name"], "error": "Invalid JSON"}

                    rows = data.get("datareturn", [])
                    d_rows = [r for r in rows if r.get("f1") == "D"]
                    tx_count = len(d_rows)
                    
                    last_time = "--:--"
                    if tx_count > 0:
                        last_time = self._format_time(d_rows[-1].get("f2", ""))

                    trailer = next((r for r in rows if r.get("f1") == "T"), None)
                    amount = 0.0
                    if trailer:
                        try:
                            # ป้องกัน Error หาก f7 ไม่ใช่ตัวเลข
                            amount = float(trailer.get("f7", 0)) / 100
                        except (ValueError, TypeError):
                            logging.warning(f"Invalid amount format in trailer for {bank['name']}")
                            amount = 0.0
                    
                    return {
                        "name": bank["name"],
                        "tx": tx_count,
                        "amt": amount,
                        "last_time": last_time,
                        "status": "active" if tx_count > 0 else "inactive"
                    }
            except asyncio.TimeoutError:
                return {"name": bank["name"], "error": "Timeout"}
            except aiohttp.ClientConnectorError:
                logging.error(f"Cannot connect to {Config.BASE_URL}")
                return {"name": bank["name"], "error": "Connect Fail"}
            except Exception as e:
                logging.error(f"Error fetching {bank['name']}: {e}")
                return {"name": bank["name"], "error": "Error"}

    async def get_summary_report(self, date_str: str) -> List[Dict[str, Any]]:
        tasks_list = [self.fetch_single_bank(bank, date_str) for bank in Config.BANKS]
        results = await asyncio.gather(*tasks_list)
        return results

# ==================================================
# 3. UI DASHBOARD
# ==================================================
class BankDashboardView(ui.View):
    def __init__(self, bot: 'BankBot'):
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
        # ลบข้อความที่เก่ากว่า 14 วันไม่ได้ (Discord Limit) แต่ purge จะข้ามให้เอง
        await itn.channel.purge(limit=50, check=lambda m: not m.pinned) 
        await self.bot.refresh_dashboard(itn.channel)

class DateInputModal(ui.Modal, title="ระบุวันที่"):
    date_input = ui.TextInput(label="YYYY-MM-DD", placeholder="2026-02-04", min_length=10, max_length=10)

    def __init__(self, bot: 'BankBot'):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        try:
            val = self.date_input.value
            # Validate format
            datetime.strptime(val, "%Y-%m-%d")
            await self.bot.process_report_interaction(interaction, val)
        except ValueError:
            await interaction.response.send_message("❌ วันที่ผิดรูปแบบ (YYYY-MM-DD)", ephemeral=True)
        except Exception as e:
            logging.error(f"Error in date modal submission: {e}")
            await interaction.response.send_message("❌ เกิดข้อผิดพลาดในการประมวลผล", ephemeral=True)

# ==================================================
# 4. BOT MAIN
# ==================================================
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
        # ใช้ TCPConnector เพื่อลด Delay จากการทำ Handshake & DNS Lookup
        connector = aiohttp.TCPConnector(limit=10, ttl_dns_cache=300)
        self.session = aiohttp.ClientSession(connector=connector)
        
        self.engine = BankEngine(self.session)
        self.add_view(BankDashboardView(self))
        self.daily_task.start()
        await self.tree.sync()
        logging.info(f"Logged in as {self.user.name}")

    async def create_report_embed(self, date_str: str) -> discord.Embed:
        """Centralized logic to create report embed"""
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
            embed.add_field(name="🟢 รายการที่มีความเคลื่อนไหว", value=f"```yaml\n{content}\n```", inline=False)
            
        if error_list:
            error_msg = "\n".join(error_list)
            embed.add_field(name="⚠️ พบปัญหาการเชื่อมต่อ", value=f"```diff\n{error_msg}\n```", inline=False)

        if inactive_names:
            names_str = ", ".join(inactive_names)
            embed.add_field(name="💤 ยังไม่มีรายการ", value=f"```fix\n{names_str}\n```", inline=False)

        embed.add_field(
            name="📊 ยอดรวมทั้งหมด", 
            value=f"```yaml\n🧾 รายการ: {total_tx:,} tx\n💰 เงินรวม: {total_amt:,.2f} THB\n```",
            inline=False
        )
            
        return embed

    async def process_report_interaction(self, interaction: discord.Interaction, date_str: str):
        """Handle UI flow for report generation"""
        try:
            # ตอบสนองทันทีเพื่อล็อค Message ป้องกัน Error 404 (Loading State)
            await interaction.response.send_message(f"⏳ กำลังดึงข้อมูล API ของวันที่ {date_str} กรุณารอสักครู่...", ephemeral=False)
            
            embed = await self.create_report_embed(date_str)
            embed.set_footer(text=f"Checked by {interaction.user.display_name}")
            
            # ทับข้อความเดิมด้วยตารางที่เสร็จแล้ว
            await interaction.edit_original_response(content=None, embed=embed)
            
            # รีเฟรชแผงควบคุมใหม่ไว้ด้านล่างสุดเสมอ
            if isinstance(interaction.channel, discord.TextChannel):
                await self.refresh_dashboard(interaction.channel)
        except Exception as e:
            logging.error(f"Error processing report: {e}")
            try:
                await interaction.edit_original_response(content="❌ เกิดข้อผิดพลาดในการดึงข้อมูล (API ปลายทางอาจไม่ตอบสนอง)", embed=None)
            except:
                pass

    async def refresh_dashboard(self, channel: discord.TextChannel):
        if self.dashboard_msg_id:
            try:
                msg = await channel.fetch_message(self.dashboard_msg_id)
                await msg.delete()
            except discord.NotFound:
                pass # ถ้าโดนลบไปก่อนแล้ว ก็ปล่อยผ่านได้เลย
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
        time(hour=11, minute=0, tzinfo=Config.THAI_TZ),
    ])
    async def daily_task(self):
        try:
            # Use fetch_channel for better reliability
            try:
                channel = await self.fetch_channel(Config.CHANNEL_ID)
            except discord.NotFound:
                logging.error(f"Channel {Config.CHANNEL_ID} not found (NotFound Error)")
                return
            except discord.Forbidden:
                logging.error(f"Bot missing permissions to access channel {Config.CHANNEL_ID}")
                return
            except Exception as e:
                logging.error(f"Error fetching channel: {e}")
                channel = self.get_channel(Config.CHANNEL_ID) # Fallback to cache

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
# 5. RUN
# ==================================================
if __name__ == "__main__":
    try:
        Config.validate()
        bot = BankBot()
        # [แก้ตรงนี้] ใส่ log_handler=None เพื่อล็อคไม่ให้ Discord มารวน Log ของเรา
        bot.run(Config.TOKEN, log_handler=None)
    except ValueError as e:
        logging.error(str(e))
    except Exception as e:
        logging.error(f"FATAL ERROR: {e}")