import asyncio
import sqlite3
import logging
import requests
import json
import re
import time
import threading
from contextlib import closing
from flask import Flask

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    InlineKeyboardButton, 
    InlineKeyboardMarkup,
    CallbackQuery,
    Message,
    FSInputFile
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# Flask для Render / Keep-Alive
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()

# Botuň sazlamalary
BOT_TOKEN = '8126416818:AAHQHwo7N9FQbOwZcVDmi_R7EfAvyuKP9EE'
ADMIN_IDS = [7569831989]

# TGRASS
TGRASS_API_KEY = "5daa17ad97944e95aa242eebc2e2ba0f"
TGRASS_API_URL = "https://tgrass.space/offers"

# bot
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# RAM önbelleği
tgrass_channels_cache = []
tgrass_cache_time = 0

# FSM States
class AdminStates(StatesGroup):
    waiting_for_sponsor_channel_id = State()
    waiting_for_sponsor_link = State()
    waiting_for_remove_sponsor_id = State()
    waiting_for_start_text = State()
    waiting_for_vpn_code = State()
    waiting_for_addlist_name = State()
    waiting_for_addlist_link = State()
    waiting_for_remove_addlist_id = State()
    waiting_for_broadcast = State()
    waiting_for_sponsor_position = State()
    waiting_for_addlist_position = State()
    waiting_for_add_admin_id = State()
    waiting_for_db_upload = State()

# i'm yourdad'
EMOJI_IDS = {
    "check": "5206607081334906820",
    "lock": "5463200466391298413",
    "stats": "5936143551854285132",
    "refresh": "6030657343744644592",
    "broadcast": "6021418126061605425",
    "edit": "5359488727158634349",
    "add": "5359651386160068849",
    "remove": "5359651386160068849",
    "vpn": "5206607081334906820",
    "sponsor": "5463200466391298413",
    "addlist": "5206607081334906820",
    "users": "5936143551854285132",
    "warning": "5463200466391298413",
    "success": "5206607081334906820",
    "star": "5206607081334906820",
    "money": "5936143551854285132",
    "phone": "6021418126061605425",
    "people": "5463200466391298413",
    "history": "6030657343744644592",
    "info": "5359488727158634349",
    "telegram": "5359651386160068849",
    "thailand": "5206607081334906820",
    "austria": "5463200466391298413",
    "usa": "5359651386160068849",
    "message": "6021418126061605425",
    "time": "6030657343744644592",
    "link": "5359488727158634349",
    "tgrass": "5936143551854285132",
    "back": "5359488727158634349",
    "admin": "5463200466391298413",
    "settings": "6030657343744644592"
}

# Loglamagy sazlamak
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='bot.log'
)

logging.info(f"Admin ID: {ADMIN_IDS[0]}")

# ================= ADMIN MANAGEMENT FUNKSIÝALARY =================

def get_all_admins():
    with closing(sqlite3.connect('wwwnahnah.db')) as conn:
        try:
            cur = conn.execute("SELECT user_id FROM admins")
            admins = [row[0] for row in cur.fetchall()]
            for aid in ADMIN_IDS:
                if aid not in admins:
                    admins.append(aid)
            return admins
        except Exception as e:
            logging.error(f"Error fetching admins: {e}")
            return ADMIN_IDS

def is_admin(user_id):
    return user_id in get_all_admins()

def add_admin_db(user_id):
    with closing(sqlite3.connect('wwwnahnah.db')) as conn:
        try:
            with conn:
                conn.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (user_id,))
            return True
        except Exception as e:
            logging.error(f"Error adding admin: {e}")
            return False

def remove_admin_db(user_id):
    with closing(sqlite3.connect('wwwnahnah.db')) as conn:
        try:
            with conn:
                conn.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
            return True
        except Exception as e:
            logging.error(f"Error removing admin: {e}")
            return False

# ================= TGRASS FUNKSIÝALARY (DÜZELDILDI) =================

def get_user_language(user_id):
    with closing(sqlite3.connect('wwwnahnah.db')) as conn:
        try:
            cur = conn.execute("SELECT value FROM settings WHERE key = ?", (f"lang_{user_id}",))
            res = cur.fetchone()
            return res[0] if res else 'ru'
        except:
            return 'ru'

def tgrass_fetch_channels():
    """
    TGrass API'den genel kanal listesini çeker ve RAM'e kaydeder.
    """
    global tgrass_channels_cache, tgrass_cache_time
    
    if not get_tgrass_enabled():
        return 0, "TGrass kapalı"
    
    try:
        response = requests.post(
            TGRASS_API_URL,
            json={
                "tg_user_id": 0,
                "is_premium": False,
                "lang": "en"
            },
            headers={
                "Content-Type": "application/json",
                "accept": "application/json",
                "Auth": TGRASS_API_KEY
            },
            timeout=30
        )
        
        if response.status_code != 200:
            logging.error(f"TGrass fetch error: HTTP {response.status_code}")
            return 0, f"HTTP {response.status_code}"
        
        data = response.json()
        
        if isinstance(data, list):
            offers = data
        elif isinstance(data, dict):
            offers = data.get("offers", data.get("channels", []))
        else:
            offers = []
        
        tgrass_channels_cache = []
        count = 0
        
        for offer in offers:
            username = offer.get("username") or offer.get("login") or offer.get("channel_username") or ""
            name = offer.get("name") or offer.get("title") or username
            link = offer.get("link") or offer.get("url") or ""
            if not link and username:
                link = f"https://t.me/{username.lstrip('@')}"
            
            if username and link:
                tgrass_channels_cache.append({
                    "link": link,
                    "name": name,
                    "username": username.lstrip("@")
                })
                count += 1
        
        tgrass_cache_time = time.time()
        logging.info(f"TGrass fetch: {count} kanal RAM'e kaydedildi")
        return count, "ok"
        
    except requests.exceptions.ConnectionError as e:
        logging.error(f"TGrass fetch connection error: {e}")
        return 0, f"Bağlantı hatası: {str(e)[:60]}"
    except requests.exceptions.Timeout:
        logging.error("TGrass fetch timeout")
        return 0, "Timeout (30s)"
    except Exception as e:
        logging.error(f"TGrass fetch error: {e}")
        return 0, str(e)[:80]

def tgrass_get_offers(user):
    """
    Kullanıcıya özel TGrass tekliflerini API'den alır.
    """
    if not get_tgrass_enabled():
        return []
    
    try:
        user_id = user.id if hasattr(user, 'id') else user
        username = user.username if hasattr(user, 'username') else None
        is_premium = getattr(user, 'is_premium', False)
        lang = get_user_language(user_id)
        
        response = requests.post(
            TGRASS_API_URL,
            json={
                "tg_user_id": int(user_id),
                "tg_login": username or "",
                "lang": lang,
                "is_premium": is_premium
            },
            headers={
                "Content-Type": "application/json",
                "accept": "application/json",
                "Auth": TGRASS_API_KEY
            },
            timeout=30
        )
        
        if response.status_code != 200:
            logging.error(f"TGrass offers error: HTTP {response.status_code}")
            return []
        
        data = response.json()
        
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            if data.get("status") == "not_ok":
                return data.get("offers", [])
            return data.get("offers", data.get("channels", []))
        else:
            return []
            
    except requests.exceptions.ConnectionError as e:
        logging.error(f"TGrass offers connection error: {e}")
        return []
    except requests.exceptions.Timeout:
        logging.error("TGrass offers timeout")
        return []
    except Exception as e:
        logging.error(f"TGrass offers error: {e}")
        return []

async def check_tgrass_subscription(user):
    """
    Kullanıcının TGrass kanallarına abone olup olmadığını kontrol eder.
    Abone olunmayan kanalları [(id, link, name), ...] formatında döndürür.
    """
    if not get_tgrass_enabled():
        return []
    
    not_subscribed = []
    user_id = user.id if hasattr(user, 'id') else user
    
    try:
        offers = tgrass_get_offers(user)
        
        if offers:
            for offer in offers:
                if offer.get("type") not in ("channel", None):
                    continue
                
                if not offer.get("subscribed", True):
                    name = offer.get("name") or offer.get("title") or "TGrass Kanal"
                    link = offer.get("link") or offer.get("url") or ""
                    
                    if link:
                        not_subscribed.append((
                            f"tg_{offer.get('offer_id', offer.get('id', ''))}",
                            link,
                            name
                        ))
        else:
            global tgrass_channels_cache
            
            if not tgrass_channels_cache:
                tgrass_fetch_channels()
            
            for idx, channel in enumerate(tgrass_channels_cache):
                username = channel.get("username", "")
                if not username:
                    continue
                
                try:
                    chat_target = f"@{username}" if not username.startswith("@") else username
                    member = await bot.get_chat_member(chat_target, user_id)
                    if member.status in ("left", "kicked", "banned"):
                        not_subscribed.append((
                            str(idx),
                            channel.get("link", ""),
                            channel.get("name", "TGrass Kanal")
                        ))
                except Exception as e:
                    logging.error(f"TGrass member check error for {username}: {e}")
                    not_subscribed.append((
                        str(idx),
                        channel.get("link", ""),
                        channel.get("name", "TGrass Kanal")
                    ))
                    
    except Exception as e:
        logging.error(f"check_tgrass_subscription genel hata: {e}")
    
    return not_subscribed

def get_tgrass_enabled():
    with closing(sqlite3.connect('wwwnahnah.db')) as conn:
        try:
            cur = conn.execute("SELECT value FROM settings WHERE key = ?", ("tgrass_enabled",))
            res = cur.fetchone()
            return res[0] == '1' if res else True
        except:
            return True

def set_tgrass_enabled(enabled):
    with closing(sqlite3.connect('wwwnahnah.db')) as conn:
        try:
            with conn:
                conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", 
                            ("tgrass_enabled", "1" if enabled else "0"))
            return True
        except Exception as e:
            logging.error(f"TGrass error: {str(e)}")
            return False

def parse_premium_emoji(text):
    pattern = r'<tg-emoji emoji-id="([^"]+)">([^<]+)</tg-emoji>'
    
    def replace_emoji(match):
        emoji_id = match.group(1)
        emoji_char = match.group(2)
        return f'<tg-emoji emoji-id="{emoji_id}">{emoji_char}</tg-emoji>'
    
    return re.sub(pattern, replace_emoji, text)

def init_db():
    with closing(sqlite3.connect('wwwnahnah.db')) as conn:
        with conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS users (
                                user_id INTEGER PRIMARY KEY
                            )''')
            conn.execute('''CREATE TABLE IF NOT EXISTS sponsors (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                channel_id TEXT,
                                link TEXT,
                                position INTEGER
                            )''')
            conn.execute('''CREATE TABLE IF NOT EXISTS settings (
                                key TEXT PRIMARY KEY,
                                value TEXT
                            )''')
            conn.execute('''CREATE TABLE IF NOT EXISTS admins (
                                user_id INTEGER PRIMARY KEY
                            )''')
            for aid in ADMIN_IDS:
                conn.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (aid,))

            try:
                conn.execute('''CREATE TABLE IF NOT EXISTS addlists (
                                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                                    name TEXT,
                                    link TEXT,
                                    position INTEGER
                                )''')
            except Exception as e:
                logging.error(f"Addlists error: {str(e)}")
                conn.execute('''DROP TABLE IF EXISTS addlists''')
                conn.execute('''CREATE TABLE addlists (
                                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                                    name TEXT,
                                    link TEXT,
                                    position INTEGER
                                )''')

            conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('start_text', '')")
            conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('vpn_code', '')")
            conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('tgrass_enabled', '1')")

            try:
                cur = conn.execute("PRAGMA table_info(sponsors)")
                columns = [info[1] for info in cur.fetchall()]
                if 'position' not in columns:
                    conn.execute("ALTER TABLE sponsors ADD COLUMN position INTEGER")
                    conn.execute("UPDATE sponsors SET position = id WHERE position IS NULL")
            except Exception as e:
                logging.error(f"Sponsor migration error: {str(e)}")

            try:
                cur = conn.execute("PRAGMA table_info(addlists)")
                columns = [info[1] for info in cur.fetchall()]
                if 'position' not in columns:
                    conn.execute("ALTER TABLE addlists ADD COLUMN position INTEGER")
                    conn.execute("UPDATE addlists SET position = id WHERE position IS NULL")
            except Exception as e:
                logging.error(f"Addlist migration error: {str(e)}")

init_db()

def get_setting(key):
    with closing(sqlite3.connect('wwwnahnah.db')) as conn:
        try:
            cur = conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
            res = cur.fetchone()
            return res[0] if res else ''
        except Exception as e:
            logging.error(f"Error: {str(e)}")
            return ''

def set_setting(key, value):
    with closing(sqlite3.connect('wwwnahnah.db')) as conn:
        try:
            with conn:
                conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
        except Exception as e:
            logging.error(f"Error: {str(e)}")

def get_sponsors():
    with closing(sqlite3.connect('wwwnahnah.db')) as conn:
        try:
            cur = conn.execute("SELECT id, channel_id, link, position FROM sponsors ORDER BY position ASC")
            return cur.fetchall()
        except Exception as e:
            logging.error(f"Error: {str(e)}")
            return []

def get_addlists():
    with closing(sqlite3.connect('wwwnahnah.db')) as conn:
        try:
            cur = conn.execute("SELECT id, name, link, position FROM addlists ORDER BY position ASC")
            return cur.fetchall()
        except Exception as e:
            logging.error(f"Error: {str(e)}")
            return []

def get_all_users():
    with closing(sqlite3.connect('wwwnahnah.db')) as conn:
        try:
            cur = conn.execute("SELECT user_id FROM users")
            return [row[0] for row in cur.fetchall()]
        except Exception as e:
            logging.error(f"Error: {str(e)}")
            return []

async def is_user_subscribed(user_id, channel_id):
    try:
        member = await bot.get_chat_member(channel_id, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logging.error(f"Error: {str(e)}")
        return False

async def get_channel_name(channel_id=None, link=None):
    try:
        if channel_id:
            chat = await bot.get_chat(channel_id)
            return chat.title or f"Канал {channel_id}"
        elif link and link.startswith('https://t.me/'):
            username = link.replace('https://t.me/', '@')
            chat = await bot.get_chat(username)
            return chat.title or username
        else:
            return link.split('/')[-1] if link else "Неизвестный канал"
    except Exception as e:
        logging.error(f"Error: {str(e)}")
        return link.split('/')[-1] if link else "Неизвестный канал"

async def get_all_channels(user_id, username=None, is_premium=False):
    sponsors = get_sponsors()
    addlists = get_addlists()
    used_urls = set()
    all_channels = []

    for sponsor in sponsors:
        if sponsor[2] not in used_urls and sponsor[3] is not None:
            used_urls.add(sponsor[2])
            all_channels.append({
                'id': sponsor[0],
                'link': sponsor[2],
                'position': sponsor[3],
                'channel_id': sponsor[1],
                'type': 'sponsor',
                'name': await get_channel_name(channel_id=sponsor[1]),
                'is_tgrass': False
            })

    for addlist in addlists:
        if addlist[2] not in used_urls and addlist[3] is not None:
            used_urls.add(addlist[2])
            all_channels.append({
                'id': addlist[0],
                'link': addlist[2],
                'position': addlist[3],
                'channel_id': None,
                'type': 'addlist',
                'name': addlist[1],
                'is_tgrass': False
            })

    tgrass_enabled = get_tgrass_enabled()
    if tgrass_enabled:
        try:
            temp_user = type('User', (), {'id': user_id, 'username': username, 'is_premium': is_premium})()
            tgrass_offers = tgrass_get_offers(temp_user)
            
            if tgrass_offers:
                max_position = len(all_channels) + 1
                for i, offer in enumerate(tgrass_offers):
                    if not offer.get("subscribed", True):
                        channel_name = offer.get('name') or offer.get('title') or f"🌟 Kanal {i+1}"
                        channel_link = offer.get('link') or offer.get('url') or ""
                        
                        if channel_link:
                            all_channels.append({
                                'id': f"tgrass_{i}",
                                'link': channel_link,
                                'position': max_position + i,
                                'channel_id': None,
                                'type': 'tgrass',
                                'name': channel_name,
                                'is_tgrass': True,
                                'offer_id': offer.get('offer_id', offer.get('id', i))
                            })
        except Exception as e:
            logging.error(f"TGrass get_all_channels error: {e}")
    
    all_channels.sort(key=lambda x: x['position'])
    return all_channels

# ================= CHECK ALL SUBSCRIPTIONS (DÜZELDILDI) =================

async def check_all_subscriptions(user_id, username=None, is_premium=False):
    not_subscribed = []
    
    sponsors = get_sponsors()
    for sponsor in sponsors:
        channel_id = sponsor[1]
        if not await is_user_subscribed(user_id, channel_id):
            not_subscribed.append({
                'name': await get_channel_name(channel_id=sponsor[1]),
                'link': sponsor[2],
                'type': 'sponsor'
            })
    
    tgrass_enabled = get_tgrass_enabled()
    if tgrass_enabled:
        try:
            temp_user = type('User', (), {'id': user_id, 'username': username, 'is_premium': is_premium})()
            tgrass_not_sub = await check_tgrass_subscription(temp_user)
            
            for _, link, name in tgrass_not_sub:
                not_subscribed.append({
                    'name': name,
                    'link': link,
                    'type': 'tgrass'
                })
        except Exception as e:
            logging.error(f"TGrass check_all_subscriptions error: {e}")
    
    return len(not_subscribed) == 0, not_subscribed

# /start komut
@dp.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username
    is_premium = getattr(message.from_user, 'is_premium', False)
    
    with closing(sqlite3.connect('wwwnahnah.db')) as conn:
        try:
            with conn:
                conn.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        except Exception as e:
            logging.error(f"Error: {str(e)}")

    start_text = get_setting('start_text').strip()
    if not start_text:
        start_text = (
            f"<tg-emoji emoji-id=\"{EMOJI_IDS['lock']}\">🔐</tg-emoji> <b>Добро пожаловать!</b>\n\n"
            f"Для получения VPN кода необходимо подписаться на каналы ниже.\n\n"
            f"После подписки нажмите кнопку «Подписался»"
        )
    else:
        start_text = parse_premium_emoji(start_text)

    all_channels = await get_all_channels(user_id, username, is_premium)
    
    if not all_channels:
        await message.answer(
            f"<tg-emoji emoji-id=\"{EMOJI_IDS['warning']}\">🔐</tg-emoji> Каналы не найдены. Свяжитесь с администратором."
        )
        return

    builder = InlineKeyboardBuilder()
    for channel in all_channels:
        if channel['type'] == 'tgrass':
            builder.button(text=f"🌟 {channel['name']}", url=channel['link'], style="primary")
        else:
            builder.button(text=channel['name'], url=channel['link'], style="primary")
    
    builder.button(
        text="Подписался",
        callback_data="check_sub",
        icon_custom_emoji_id=EMOJI_IDS["check"],
        style="success"
    )
    
    # Выравниваем каналы по 2 в ряд, а кнопку «Подписался» ставим отдельно снизу
    rows = [2] * (len(all_channels) // 2)
    if len(all_channels) % 2 != 0:
        rows.append(1)
    rows.append(1)
    builder.adjust(*rows)
    
    await message.answer(start_text, reply_markup=builder.as_markup())

# Check subscription callback
@dp.callback_query(F.data == "check_sub")
async def check_sub_callback(call: CallbackQuery):
    user_id = call.from_user.id
    username = call.from_user.username
    is_premium = getattr(call.from_user, 'is_premium', False)

    is_subscribed, not_subscribed = await check_all_subscriptions(user_id, username, is_premium)

    if not is_subscribed:
        text = f"<b>Вы не подписались на следующие каналы:</b>\n\n"
        for channel in not_subscribed:
            text += f"• {channel['name']}\n"
        text += "\nПодпишитесь и нажмите кнопку снова."
        await call.answer(text=text, show_alert=True)
    else:
        await call.answer(text="✅ Вы подписались на все каналы!", show_alert=True)
        vpn_code = get_setting('vpn_code')
        if vpn_code:
            await call.message.answer(
                f"<tg-emoji emoji-id=\"{EMOJI_IDS['vpn']}\">✔️</tg-emoji> <b>Ваш VPN код:</b> <code>{vpn_code}</code>"
            )
        else:
            await call.message.answer(
                f"<tg-emoji emoji-id=\"{EMOJI_IDS['warning']}\">🔐</tg-emoji> VPN код еще не настроен администратором."
            )

# Admin panel
@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer(
            f"<tg-emoji emoji-id=\"{EMOJI_IDS['warning']}\">🔐</tg-emoji> Вы не администратор!"
        )
        return
    
    builder = InlineKeyboardBuilder()
    
    builder.button(
        text="Добавить спонсора",
        callback_data="add_sponsor",
        icon_custom_emoji_id=EMOJI_IDS["add"]
    )
    builder.button(
        text="Удалить спонсора",
        callback_data="remove_sponsor",
        icon_custom_emoji_id=EMOJI_IDS["remove"]
    )
    builder.button(
        text="Изменить start текст",
        callback_data="edit_start",
        icon_custom_emoji_id=EMOJI_IDS["edit"]
    )
    builder.button(
        text="Изменить VPN код",
        callback_data="edit_code",
        icon_custom_emoji_id=EMOJI_IDS["lock"]
    )
    builder.button(
        text="Добавить Addlist",
        callback_data="add_addlist",
        icon_custom_emoji_id=EMOJI_IDS["add"]
    )
    builder.button(
        text="Удалить Addlist",
        callback_data="remove_addlist",
        icon_custom_emoji_id=EMOJI_IDS["remove"]
    )
    builder.button(
        text="Рассылка",
        callback_data="broadcast",
        icon_custom_emoji_id=EMOJI_IDS["broadcast"]
    )
    builder.button(
        text="Статистика",
        callback_data="stats",
        icon_custom_emoji_id=EMOJI_IDS["stats"]
    )
    builder.button(
        text="TGrass настройки",
        callback_data="tgrass_settings",
        icon_custom_emoji_id=EMOJI_IDS["tgrass"]
    )
    builder.button(
        text="Добавить админа",
        callback_data="add_admin",
        icon_custom_emoji_id=EMOJI_IDS["add"]
    )
    builder.button(
        text="Снять админа",
        callback_data="remove_admin",
        icon_custom_emoji_id=EMOJI_IDS["remove"]
    )
    builder.button(
        text="Список админов",
        callback_data="list_admins",
        icon_custom_emoji_id=EMOJI_IDS["admin"]
    )
    builder.button(
        text="Скачать БД",
        callback_data="download_db",
        icon_custom_emoji_id=EMOJI_IDS["stats"]
    )
    builder.button(
        text="Поставить БД",
        callback_data="upload_db",
        icon_custom_emoji_id=EMOJI_IDS["edit"]
    )
    
    builder.adjust(2)
    
    await message.answer(
        f"<tg-emoji emoji-id=\"{EMOJI_IDS['admin']}\">👑</tg-emoji> <b>Админ панель</b>",
        reply_markup=builder.as_markup()
    )

# ================= ADMIN CALLBACK HANDLERS =================

@dp.callback_query(F.data == "add_admin")
async def add_admin_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Доступ запрещен!", show_alert=True)
        return
    
    await call.message.edit_text(
        f"<tg-emoji emoji-id=\"{EMOJI_IDS['add']}\">➕</tg-emoji> <b>Добавление администратора</b>\n\n"
        f"Отправьте Telegram ID пользователя (например: 123456789)\n"
        f"Или отправьте /cancel для отмены."
    )
    await state.set_state(AdminStates.waiting_for_add_admin_id)
    await call.answer()

@dp.message(AdminStates.waiting_for_add_admin_id)
async def process_add_admin_id(message: Message, state: FSMContext):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Операция отменена.")
        return
    
    if not message.text.strip().isdigit():
        await message.answer("❌ Ошибка: Введите корректный числовой Telegram ID.")
        return

    new_admin_id = int(message.text.strip())
    
    if is_admin(new_admin_id):
        await message.answer("⚠️ Этот пользователь уже является администратором.")
        await state.clear()
        return

    if add_admin_db(new_admin_id):
        await message.answer(
            f"<tg-emoji emoji-id=\"{EMOJI_IDS['success']}\">✅</tg-emoji> Администратор <code>{new_admin_id}</code> успешно добавлен!"
        )
    else:
        await message.answer("❌ Ошибка при добавлении администратора.")
    
    await state.clear()

@dp.callback_query(F.data == "remove_admin")
async def remove_admin_start(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Доступ запрещен!", show_alert=True)
        return
    
    admins = get_all_admins()
    if not admins:
        await call.message.edit_text("❌ Список администраторов пуст.")
        await call.answer()
        return
    
    text = f"<tg-emoji emoji-id=\"{EMOJI_IDS['remove']}\">➖</tg-emoji> <b>Выберите администратора для удаления:</b>\n\n"
    builder = InlineKeyboardBuilder()
    
    for admin_id in admins:
        builder.button(
            text=f"❌ ID: {admin_id}",
            callback_data=f"del_admin_{admin_id}"
        )
    
    builder.button(text="◀️ Назад", callback_data="back_to_admin")
    builder.adjust(1)
    
    await call.message.edit_text(text, reply_markup=builder.as_markup())
    await call.answer()

@dp.callback_query(F.data.startswith("del_admin_"))
async def delete_admin(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Доступ запрещен!", show_alert=True)
        return
    
    target_admin_id = int(call.data.replace("del_admin_", ""))
    
    if remove_admin_db(target_admin_id):
        await call.message.edit_text(
            f"<tg-emoji emoji-id=\"{EMOJI_IDS['success']}\">✅</tg-emoji> Администратор <code>{target_admin_id}</code> удален!"
        )
    else:
        await call.answer("Ошибка при удалении администратора", show_alert=True)
    
    await call.answer()

@dp.callback_query(F.data == "list_admins")
async def list_admins_show(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Доступ запрещен!", show_alert=True)
        return
    
    admins = get_all_admins()
    
    text = f"<tg-emoji emoji-id=\"{EMOJI_IDS['admin']}\">👑</tg-emoji> <b>Список администраторов:</b>\n\n"
    for idx, admin_id in enumerate(admins, 1):
        text += f"{idx}. <code>{admin_id}</code>\n"
    
    builder = InlineKeyboardBuilder()
    builder.button(text="◀️ Назад", callback_data="back_to_admin")
    
    await call.message.edit_text(text, reply_markup=builder.as_markup())
    await call.answer()

@dp.callback_query(F.data == "add_sponsor")
async def add_sponsor_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Доступ запрещен!", show_alert=True)
        return
    
    await call.message.edit_text(
        f"<tg-emoji emoji-id=\"{EMOJI_IDS['add']}\">➕</tg-emoji> <b>Добавление спонсора</b>\n\n"
        f"Отправьте ID канала (например: -1001234567890)\n"
        f"Или отправьте /cancel для отмены."
    )
    await state.set_state(AdminStates.waiting_for_sponsor_channel_id)
    await call.answer()

@dp.message(AdminStates.waiting_for_sponsor_channel_id)
async def process_sponsor_channel_id(message: Message, state: FSMContext):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Операция отменена.")
        return
    
    channel_id = message.text.strip()
    await state.update_data(channel_id=channel_id)
    
    await message.answer(
        f"<tg-emoji emoji-id=\"{EMOJI_IDS['link']}\">🔗</tg-emoji> Теперь отправьте ссылку на канал (например: https://t.me/channelname)"
    )
    await state.set_state(AdminStates.waiting_for_sponsor_link)

@dp.message(AdminStates.waiting_for_sponsor_link)
async def process_sponsor_link(message: Message, state: FSMContext):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Операция отменена.")
        return
    
    link = message.text.strip()
    data = await state.get_data()
    channel_id = data.get('channel_id')
    
    with closing(sqlite3.connect('wwwnahnah.db')) as conn:
        try:
            with conn:
                cur = conn.execute("SELECT MAX(position) FROM sponsors")
                max_pos = cur.fetchone()[0]
                new_position = (max_pos + 1) if max_pos else 1
                
                conn.execute(
                    "INSERT INTO sponsors (channel_id, link, position) VALUES (?, ?, ?)",
                    (channel_id, link, new_position)
                )
            
            await message.answer(
                f"<tg-emoji emoji-id=\"{EMOJI_IDS['success']}\">✅</tg-emoji> Спонсор успешно добавлен!\n"
                f"ID: {channel_id}\nСсылка: {link}"
            )
        except Exception as e:
            await message.answer(f"❌ Ошибка: {str(e)}")
    
    await state.clear()

@dp.callback_query(F.data == "remove_sponsor")
async def remove_sponsor_start(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Доступ запрещен!", show_alert=True)
        return
    
    sponsors = get_sponsors()
    if not sponsors:
        await call.message.edit_text("❌ Список спонсоров пуст.")
        await call.answer()
        return
    
    text = f"<tg-emoji emoji-id=\"{EMOJI_IDS['remove']}\">➖</tg-emoji> <b>Выберите спонсора для удаления:</b>\n\n"
    builder = InlineKeyboardBuilder()
    
    for sponsor in sponsors:
        name = await get_channel_name(channel_id=sponsor[1])
        builder.button(
            text=f"❌ {name}",
            callback_data=f"del_sponsor_{sponsor[0]}"
        )
    
    builder.button(text="◀️ Назад", callback_data="back_to_admin")
    builder.adjust(1)
    
    await call.message.edit_text(text, reply_markup=builder.as_markup())
    await call.answer()

@dp.callback_query(F.data.startswith("del_sponsor_"))
async def delete_sponsor(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Доступ запрещен!", show_alert=True)
        return
    
    sponsor_id = int(call.data.replace("del_sponsor_", ""))
    
    with closing(sqlite3.connect('wwwnahnah.db')) as conn:
        try:
            with conn:
                conn.execute("DELETE FROM sponsors WHERE id = ?", (sponsor_id,))
            await call.message.edit_text(
                f"<tg-emoji emoji-id=\"{EMOJI_IDS['success']}\">✅</tg-emoji> Спонсор удален!"
            )
        except Exception as e:
            await call.answer(f"Ошибка: {str(e)}", show_alert=True)
    
    await call.answer()

@dp.callback_query(F.data == "edit_start")
async def edit_start_text(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Доступ запрещен!", show_alert=True)
        return
    
    current_text = get_setting('start_text')
    
    await call.message.edit_text(
        f"<tg-emoji emoji-id=\"{EMOJI_IDS['edit']}\">✏️</tg-emoji> <b>Изменение стартового сообщения</b>\n\n"
        f"<b>Текущий текст:</b>\n{current_text if current_text else 'Стандартный текст'}\n\n"
        f"<b>Отправьте новый текст:</b>\n"
        f"Вы можете использовать HTML теги:\n"
        f"• <code>&lt;b&gt;жирный&lt;/b&gt;</code> - <b>жирный</b>\n"
        f"• <code>&lt;i&gt;курсив&lt;/i&gt;</code> - <i>курсив</i>\n"
        f"• <code>&lt;u&gt;подчеркнутый&lt;/u&gt;</code> - <u>подчеркнутый</u>\n"
        f"• <code>&lt;s&gt;зачеркнутый&lt;/s&gt;</code> - <s>зачеркнутый</s>\n"
        f"• <code>&lt;code&gt;моноширинный&lt;/code&gt;</code> - <code>моноширинный</code>\n"
        f"• <code>&lt;a href='url'&gt;ссылка&lt;/a&gt;</code> - ссылка\n\n"
        f"<b>Premium эмодзи:</b>\n"
        f"Отправьте любое premium эмодзи из Telegram, и бот автоматически сохранит его ID.\n\n"
        f"Отправьте /cancel для отмены."
    )
    await state.set_state(AdminStates.waiting_for_start_text)
    await call.answer()

@dp.message(AdminStates.waiting_for_start_text)
async def process_start_text(message: Message, state: FSMContext):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Операция отменена.")
        return
    
    new_text = message.html_text if message.html_text else message.text
    
    if message.entities:
        for entity in message.entities:
            if entity.type == "custom_emoji":
                emoji_id = entity.custom_emoji_id
                logging.info(f"Premium emoji found: {emoji_id}")
    
    set_setting('start_text', new_text)
    
    preview_text = parse_premium_emoji(new_text)
    await message.answer(
        f"<tg-emoji emoji-id=\"{EMOJI_IDS['success']}\">✅</tg-emoji> <b>Текст сохранен!</b>\n\n"
        f"<b>Предпросмотр:</b>\n{preview_text}",
        parse_mode=ParseMode.HTML
    )
    
    await state.clear()

@dp.callback_query(F.data == "edit_code")
async def edit_vpn_code(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Доступ запрещен!", show_alert=True)
        return
    
    current_code = get_setting('vpn_code')
    
    await call.message.edit_text(
        f"<tg-emoji emoji-id=\"{EMOJI_IDS['lock']}\">🔐</tg-emoji> <b>Изменение VPN кода</b>\n\n"
        f"Текущий код: <code>{current_code if current_code else 'Не установлен'}</code>\n\n"
        f"Отправьте новый VPN код или /cancel для отмены."
    )
    await state.set_state(AdminStates.waiting_for_vpn_code)
    await call.answer()

@dp.message(AdminStates.waiting_for_vpn_code)
async def process_vpn_code(message: Message, state: FSMContext):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Операция отменена.")
        return
    
    new_code = message.text.strip()
    set_setting('vpn_code', new_code)
    
    await message.answer(
        f"<tg-emoji emoji-id=\"{EMOJI_IDS['success']}\">✅</tg-emoji> VPN код сохранен: <code>{new_code}</code>"
    )
    await state.clear()

@dp.callback_query(F.data == "add_addlist")
async def add_addlist_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Доступ запрещен!", show_alert=True)
        return
    
    await call.message.edit_text(
        f"<tg-emoji emoji-id=\"{EMOJI_IDS['add']}\">➕</tg-emoji> <b>Добавление Addlist</b>\n\n"
        f"Отправьте название для отображения или /cancel для отмены."
    )
    await state.set_state(AdminStates.waiting_for_addlist_name)
    await call.answer()

@dp.message(AdminStates.waiting_for_addlist_name)
async def process_addlist_name(message: Message, state: FSMContext):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Операция отменена.")
        return
    
    name = message.text.strip()
    await state.update_data(name=name)
    
    await message.answer(
        f"<tg-emoji emoji-id=\"{EMOJI_IDS['link']}\">🔗</tg-emoji> Теперь отправьте ссылку:"
    )
    await state.set_state(AdminStates.waiting_for_addlist_link)

@dp.message(AdminStates.waiting_for_addlist_link)
async def process_addlist_link(message: Message, state: FSMContext):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Операция отменена.")
        return
    
    link = message.text.strip()
    data = await state.get_data()
    name = data.get('name')
    
    with closing(sqlite3.connect('wwwnahnah.db')) as conn:
        try:
            with conn:
                cur = conn.execute("SELECT MAX(position) FROM addlists")
                max_pos = cur.fetchone()[0]
                new_position = (max_pos + 1) if max_pos else 1
                
                conn.execute(
                    "INSERT INTO addlists (name, link, position) VALUES (?, ?, ?)",
                    (name, link, new_position)
                )
            
            await message.answer(
                f"<tg-emoji emoji-id=\"{EMOJI_IDS['success']}\">✅</tg-emoji> Addlist успешно добавлен!\n"
                f"Название: {name}\nСсылка: {link}"
            )
        except Exception as e:
            await message.answer(f"❌ Ошибка: {str(e)}")
    
    await state.clear()

@dp.callback_query(F.data == "remove_addlist")
async def remove_addlist_start(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Доступ запрещен!", show_alert=True)
        return
    
    addlists = get_addlists()
    if not addlists:
        await call.message.edit_text("❌ Список Addlist пуст.")
        await call.answer()
        return
    
    text = f"<tg-emoji emoji-id=\"{EMOJI_IDS['remove']}\">➖</tg-emoji> <b>Выберите Addlist для удаления:</b>\n\n"
    builder = InlineKeyboardBuilder()
    
    for addlist in addlists:
        builder.button(
            text=f"❌ {addlist[1]}",
            callback_data=f"del_addlist_{addlist[0]}"
        )
    
    builder.button(text="◀️ Назад", callback_data="back_to_admin")
    builder.adjust(1)
    
    await call.message.edit_text(text, reply_markup=builder.as_markup())
    await call.answer()

@dp.callback_query(F.data.startswith("del_addlist_"))
async def delete_addlist(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Доступ запрещен!", show_alert=True)
        return
    
    addlist_id = int(call.data.replace("del_addlist_", ""))
    
    with closing(sqlite3.connect('wwwnahnah.db')) as conn:
        try:
            with conn:
                conn.execute("DELETE FROM addlists WHERE id = ?", (addlist_id,))
            await call.message.edit_text(
                f"<tg-emoji emoji-id=\"{EMOJI_IDS['success']}\">✅</tg-emoji> Addlist удален!"
            )
        except Exception as e:
            await call.answer(f"Ошибка: {str(e)}", show_alert=True)
    
    await call.answer()

@dp.callback_query(F.data == "broadcast")
async def broadcast_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Доступ запрещен!", show_alert=True)
        return
    
    await call.message.edit_text(
        f"<tg-emoji emoji-id=\"{EMOJI_IDS['broadcast']}\">📢</tg-emoji> <b>Рассылка</b>\n\n"
        f"Отправьте сообщение для рассылки всем пользователям.\n"
        f"Отправьте /cancel для отмены."
    )
    await state.set_state(AdminStates.waiting_for_broadcast)
    await call.answer()

@dp.message(AdminStates.waiting_for_broadcast)
async def process_broadcast(message: Message, state: FSMContext):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Операция отменена.")
        return
    
    users = get_all_users()
    success = 0
    failed = 0
    
    await message.answer(f"📤 Начинаю рассылку для {len(users)} пользователей...")
    
    for user_id in users:
        try:
            await bot.copy_message(
                chat_id=user_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id
            )
            success += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            failed += 1
            logging.error(f"Broadcast error for {user_id}: {e}")
    
    await message.answer(
        f"<tg-emoji emoji-id=\"{EMOJI_IDS['stats']}\">📊</tg-emoji> <b>Рассылка завершена!</b>\n\n"
        f"✅ Успешно: {success}\n"
        f"❌ Ошибок: {failed}"
    )
    await state.clear()

@dp.callback_query(F.data == "stats")
async def show_stats(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Доступ запрещен!", show_alert=True)
        return
    
    users = get_all_users()
    sponsors = get_sponsors()
    addlists = get_addlists()
    tgrass_enabled = get_tgrass_enabled()
    
    text = (
        f"<tg-emoji emoji-id=\"{EMOJI_IDS['stats']}\">📊</tg-emoji> <b>Статистика бота</b>\n\n"
        f"👥 Пользователей: {len(users)}\n"
        f"📢 Спонсоров: {len(sponsors)}\n"
        f"📋 Addlist: {len(addlists)}\n"
        f"🌟 TGrass: {'✅ Включен' if tgrass_enabled else '❌ Выключен'}\n"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="◀️ Назад", callback_data="back_to_admin")
    
    await call.message.edit_text(text, reply_markup=builder.as_markup())
    await call.answer()

@dp.callback_query(F.data == "tgrass_settings")
async def tgrass_settings(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Доступ запрещен!", show_alert=True)
        return
    
    enabled = get_tgrass_enabled()
    status_text = "✅ Включен" if enabled else "❌ Выключен"
    
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✅ Включить" if not enabled else "❌ Выключить",
        callback_data="toggle_tgrass"
    )
    builder.button(
        text="🔄 Обновить каналы",
        callback_data="refresh_tgrass"
    )
    builder.button(text="◀️ Назад", callback_data="back_to_admin")
    builder.adjust(1)
    
    await call.message.edit_text(
        f"<tg-emoji emoji-id=\"{EMOJI_IDS['tgrass']}\">🌟</tg-emoji> <b>Настройки TGrass</b>\n\n"
        f"Статус: {status_text}\n\n"
        f"API: {TGRASS_API_URL}",
        reply_markup=builder.as_markup()
    )
    await call.answer()

@dp.callback_query(F.data == "toggle_tgrass")
async def toggle_tgrass(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Доступ запрещен!", show_alert=True)
        return
    
    current = get_tgrass_enabled()
    set_tgrass_enabled(not current)
    
    new_status = "✅ Включен" if not current else "❌ Выключен"
    await call.answer(f"TGrass {new_status}!", show_alert=True)
    
    await tgrass_settings(call)

@dp.callback_query(F.data == "refresh_tgrass")
async def refresh_tgrass(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Доступ запрещен!", show_alert=True)
        return
    
    await call.answer("🔄 Каналы обновляются...", show_alert=False)
    
    count, msg = tgrass_fetch_channels()
    
    if msg == "ok":
        await call.message.edit_text(
            f"<tg-emoji emoji-id=\"{EMOJI_IDS['success']}\">✅</tg-emoji> <b>TGrass каналы обновлены!</b>\n\n"
            f"📡 Каналов: {count}\n\n"
            f"🌟 {count} каналов были сохранены.",
            reply_markup=InlineKeyboardBuilder().button(text="◀️ Yza", callback_data="tgrass_settings").as_markup()
        )
    else:
        await call.message.edit_text(
            f"<tg-emoji emoji-id=\"{EMOJI_IDS['warning']}\">❌</tg-emoji> <b>TGrass ошибка соединения!</b>\n\n"
            f"Ошибка: <code>{msg}</code>\n\n"
            f"Проверьте API",
            reply_markup=InlineKeyboardBuilder().button(text="◀️ Yza", callback_data="tgrass_settings").as_markup()
        )
    
    await call.answer()

@dp.callback_query(F.data == "back_to_admin")
async def back_to_admin(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Доступ запрещен!", show_alert=True)
        return
    
    builder = InlineKeyboardBuilder()
    
    builder.button(
        text="Добавить спонсора",
        callback_data="add_sponsor",
        icon_custom_emoji_id=EMOJI_IDS["add"]
    )
    builder.button(
        text="Удалить спонсора",
        callback_data="remove_sponsor",
        icon_custom_emoji_id=EMOJI_IDS["remove"]
    )
    builder.button(
        text="Изменить start текст",
        callback_data="edit_start",
        icon_custom_emoji_id=EMOJI_IDS["edit"]
    )
    builder.button(
        text="Изменить VPN код",
        callback_data="edit_code",
        icon_custom_emoji_id=EMOJI_IDS["lock"]
    )
    builder.button(
        text="Добавить Addlist",
        callback_data="add_addlist",
        icon_custom_emoji_id=EMOJI_IDS["add"]
    )
    builder.button(
        text="Удалить Addlist",
        callback_data="remove_addlist",
        icon_custom_emoji_id=EMOJI_IDS["remove"]
    )
    builder.button(
        text="Рассылка",
        callback_data="broadcast",
        icon_custom_emoji_id=EMOJI_IDS["broadcast"]
    )
    builder.button(
        text="Статистика",
        callback_data="stats",
        icon_custom_emoji_id=EMOJI_IDS["stats"]
    )
    builder.button(
        text="TGrass настройки",
        callback_data="tgrass_settings",
        icon_custom_emoji_id=EMOJI_IDS["tgrass"]
    )
    builder.button(
        text="Добавить админа",
        callback_data="add_admin",
        icon_custom_emoji_id=EMOJI_IDS["add"]
    )
    builder.button(
        text="Снять админа",
        callback_data="remove_admin",
        icon_custom_emoji_id=EMOJI_IDS["remove"]
    )
    builder.button(
        text="Список админов",
        callback_data="list_admins",
        icon_custom_emoji_id=EMOJI_IDS["admin"]
    )
    builder.button(
        text="Скачать БД",
        callback_data="download_db",
        icon_custom_emoji_id=EMOJI_IDS["stats"]
    )
    builder.button(
        text="Поставить БД",
        callback_data="upload_db",
        icon_custom_emoji_id=EMOJI_IDS["edit"]
    )
    
    builder.adjust(2)
    
    await call.message.edit_text(
        f"<tg-emoji emoji-id=\"{EMOJI_IDS['admin']}\">👑</tg-emoji> <b>Админ панель</b>",
        reply_markup=builder.as_markup()
    )
    await call.answer()

@dp.callback_query(F.data == "download_db")
async def download_db(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Доступ запрещен!", show_alert=True)
        return

    db_file = FSInputFile('wwwnahnah.db')
    await call.message.answer_document(document=db_file, caption="📦 Резервная копия базы данных")
    await call.answer()

@dp.callback_query(F.data == "upload_db")
async def upload_db_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Доступ запрещен!", show_alert=True)
        return

    await call.message.edit_text(
        "📂 <b>Отправьте файл базы данных (.db)</b>\n\n"
        "⚠️ <i>Внимание: Текущая база данных будет полностью перезаписана!</i>\n"
        "Или отправьте /cancel для отмены."
    )
    await state.set_state(AdminStates.waiting_for_db_upload)
    await call.answer()

@dp.message(AdminStates.waiting_for_db_upload)
async def process_db_upload(message: Message, state: FSMContext):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Операция отменена.")
        return

    if not message.document:
        await message.answer("❌ Пожалуйста, отправьте файл как документ (файл .db).")
        return

    if not message.document.file_name.endswith('.db'):
        await message.answer("❌ Неверный формат файла. Ожидается файл .db")
        return

    # Загружаем файл
    file_id = message.document.file_id
    file = await bot.get_file(file_id)
    file_path = file.file_path

    # Скачиваем и перезаписываем
    await bot.download_file(file_path, destination='wwwnahnah.db')

    await message.answer("✅ База данных успешно обновлена!")
    await state.clear()

async def main():
    logging.info("Bot started")
    print("🤖 Бот работает...")
    print(f"👑 Admin ID: {ADMIN_IDS[0]}")
    print("🌟 TGrass integration active")
    print("✨ Custom emoji icons on buttons enabled")
    
    # Запуск Flask сервера для Render
    keep_alive()
    
    try:
        count, msg = tgrass_fetch_channels()
        if msg == "ok":
            print(f"📡 TGrass: {count} каналов были сохранены.")
        else:
            print(f"⚠️ TGrass: {msg}")
    except Exception as e:
        print(f"❌ TGrass init error: {e}")
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
