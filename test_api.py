import os
import aiohttp
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()
# =================ตั้งค่า=================
BASE_URL = os.getenv("BANK_API_URL")

BANKS = [
    {"code": "006", "name": "KTB (กรุงไทย)"},
    {"code": "014", "name": "SCB (ไทยพาณิชย์)"},
    {"code": "004", "name": "KBANK (กสิกร)"},
    {"code": "034", "name": "BAAC (ธกส.)"},
    {"code": "998", "name": "ThaiPost (ปณ.)"},
    {"code": "709", "name": "CS (เคาน์เตอร์ฯ)"},
    {"code": "030", "name": "GSB (ออมสิน)"},
]
# ========================================

async def test_connection():
    # ใช้วันที่ปัจจุบัน
    date_str = datetime.now().strftime("%Y-%m-%d")
    print(f"🔄 กำลังทดสอบการเชื่อมต่อ API ประจำวันที่: {date_str}")
    print(f"🎯 Target: {BASE_URL}\n")
    print("-" * 60)

    async with aiohttp.ClientSession() as session:
        for bank in BANKS:
            params = {
                "bankid": bank["code"],
                "datestart": f"{date_str} 00:00:00",
                "dateend": f"{date_str} 23:59:59",
            }
            
            print(f"📡 กำลังเช็ค {bank['name']}...", end=" ")
            
            try:
                # Timeout 5 วินาทีพอ สำหรับการเทส
                async with session.get(BASE_URL, params=params, timeout=5) as resp:
                    if resp.status == 200:
                        try:
                            data = await resp.json()
                            rows = data.get("datareturn", [])
                            d_rows = [r for r in rows if r.get("f1") == "D"]
                            
                            # ดึงยอดเงิน
                            trailer = next((r for r in rows if r.get("f1") == "T"), None)
                            amount = float(trailer.get("f7", 0)) / 100 if trailer else 0.0

                            print(f"✅ OK! (เจอ {len(d_rows)} รายการ | ยอด {amount:,.2f})")
                        except:
                            print(f"⚠️ เชื่อมได้ แต่ JSON ผิดพลาด")
                    else:
                        print(f"❌ HTTP Error {resp.status}")
                        
            except asyncio.TimeoutError:
                print("❌ Timeout (ช้าเกินไป/ติดต่อไม่ได้)")
            except aiohttp.ClientConnectorError:
                print("❌ Connection Refused (หา IP ไม่เจอ/ไม่ได้ต่อ VPN)")
            except Exception as e:
                print(f"❌ Error: {e}")

    print("-" * 60)
    print("🏁 จบการทำงาน")

if __name__ == "__main__":
    try:
        asyncio.run(test_connection())
    except KeyboardInterrupt:
        pass
