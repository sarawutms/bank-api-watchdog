import asyncio
import aiohttp
import logging
from typing import Dict, Any, List
from config import Config

class BankEngine:
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
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
        return await asyncio.gather(*tasks_list)