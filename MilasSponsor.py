import asyncio
import sqlite3
import logging
import requests
import time
from contextlib import closing
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    InlineKeyboardButton, 
    InlineKeyboardMarkup,
    CallbackQuery,
    Message
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# Botuň sazlamalary
BOT_TOKEN = '8126416818:AAHQHwo7N9FQbOwZcVDmi_R7EfAvyuKP9EE'
ADMIN_IDS = [7569831989]

# TGRASS
TGRASS_API_KEY = "5daa17ad97944e95aa242eebc2e2ba0f"
TGRASS_API_URL = "https://tgrass.space/offers"

# Bot initialize (DefaultBotProperties hem goşuldy, we her hatda parse_mode HTML görkezildi)
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
    waiting_for_vpn_code = State()
    waiting_for_addlist_name = State()
    waiting_for_addlist_link = State()
    waiting_for_broadcast = State()
    waiting_for_add_admin_id = State()

# Premium Emojili Tekstler (Boşluklar goşuldy we HTML taglary dogry düzüldi)
START_TEXT = (
    'Salam, men @sevenvpns7 kanalynyñ body <tg-emoji id="5247133031235329609">👋</tg-emoji>\n\n'
    'Men size 7/24 işleýan vpn kodlaryny berýan <tg-emoji id="5296369303661067030">🔒</tg-emoji>\n\n'
    'Siziň etmeli işiňiz diňe sponsorlarymyza agza bolmak <tg-emoji id="4976940882071651344">🤝</tg-emoji>\n\n'
    'Boda kanal goşdyrmak üçin:\n@milas_devx <tg-emoji id="5854834168764044261">👨‍💻</tg-emoji>'
)

NOT_SUB_TEXT = 'Siz şul kanallara agza bolmadyňyz: <tg-emoji id="5319034842514499001">⚠️</tg-emoji>'

EMOJI_IDS = {
    "success": "5206607081334906820",
    "warning": "5319034842514499001",
    "admin": "5463200466391298413",
    "add": "5359651386160068849",
    "remove": "5359651386160068849",
    "link": "5359488727158634349",
    "broadcast": "6021418126061605425",
    "stats": "5936143551854285132",
    "tgrass": "5936143551854285132"
}

logging.basicConfig(level=logging.INFO, filename='bot.log')

# ================= DATABASE FUNKSIÝALARY =================

def init_db():
    with closing(sqlite3.connect('wwwnahnah.db')) as conn:
        with conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)''')
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
            conn.execute('''CREATE TABLE IF NOT EXISTS addlists (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                name TEXT,
                                link TEXT,
                                position INTEGER
                            )''')
            conn.execute('''CREATE TABLE IF NOT EXISTS admins (
                                user_id INTEGER PRIMARY KEY
                            )''')

            conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('vpn_code', '')")
            conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('tgrass_enabled', '1')")

            for admin_id in ADMIN_IDS:
                conn.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (admin_id,))

init_db()

def is_admin(user_id: int) -> bool:
    if user_id in ADMIN_IDS:
        return True
    with closing(sqlite3.connect('wwwnahnah.db')) as conn:
        cur = conn.execute("SELECT user_id FROM admins WHERE user_id = ?", (user_id,))
        return cur.fetchone() is not None

def get_all_admins():
    admins = set(ADMIN_IDS)
    with closing(sqlite3.connect('wwwnahnah.db')) as conn:
        cur = conn.execute("SELECT user_id FROM admins")
        for row in cur.fetchall():
            admins.add(row[0])
    return list(admins)

def add_admin_db(user_id: int):
    with closing(sqlite3.connect('wwwnahnah.db')) as conn:
        with conn:
            conn.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (user_id,))

def remove_admin_db(user_id: int):
    with closing(sqlite3.connect('wwwnahnah.db')) as conn:
        with conn:
            conn.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))

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
            return []

def get_addlists():
    with closing(sqlite3.connect('wwwnahnah.db')) as conn:
        try:
            cur = conn.execute("SELECT id, name, link, position FROM addlists ORDER BY position ASC")
            return cur.fetchall()
        except Exception as e:
            return []

def get_all_users():
    with closing(sqlite3.connect('wwwnahnah.db')) as conn:
        try:
            cur = conn.execute("SELECT user_id FROM users")
            return [row[0] for row in cur.fetchall()]
        except Exception as e:
            return []

# ================= TGRASS FUNKSIÝALARY =================

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
            return False

def tgrass_fetch_channels():
    global tgrass_channels_cache, tgrass_cache_time
    if not get_tgrass_enabled():
        return 0, "TGrass öçürilen"
    
    try:
        response = requests.post(
            TGRASS_API_URL,
            json={"tg_user_id": 0, "is_premium": False, "lang": "en"},
            headers={"Content-Type": "application/json", "Auth": TGRASS_API_KEY},
            timeout=30
        )
        if response.status_code != 200:
            return 0, f"HTTP {response.status_code}"
        
        data = response.json()
        offers = data if isinstance(data, list) else data.get("offers", data.get("channels", []))
        
        tgrass_channels_cache = []
        count = 0
        for offer in offers:
            username = offer.get("username") or offer.get("login") or offer.get("channel_username") or ""
            name = offer.get("name") or offer.get("title") or username
            link = offer.get("link") or offer.get("url") or ""
            if not link and username:
                link = f"https://t.me/{username.lstrip('@')}"
            
            if username and link:
                tgrass_channels_cache.append({"link": link, "name": name, "username": username.lstrip("@")})
                count += 1
        
        tgrass_cache_time = time.time()
        return count, "ok"
    except Exception as e:
        return 0, str(e)[:80]

def tgrass_get_offers(user_id, username=None, is_premium=False):
    if not get_tgrass_enabled():
        return []
    try:
        response = requests.post(
            TGRASS_API_URL,
            json={"tg_user_id": int(user_id), "tg_login": username or "", "lang": "ru", "is_premium": is_premium},
            headers={"Content-Type": "application/json", "Auth": TGRASS_API_KEY},
            timeout=30
        )
        if response.status_code != 200:
            return []
        data = response.json()
        return data if isinstance(data, list) else data.get("offers", data.get("channels", []))
    except Exception as e:
        return []

async def check_tgrass_subscription(user_id, username=None, is_premium=False):
    if not get_tgrass_enabled():
        return []
    not_subscribed = []
    try:
        offers = tgrass_get_offers(user_id, username, is_premium)
        if offers:
            for offer in offers:
                if offer.get("type") not in ("channel", None):
                    continue
                if not offer.get("subscribed", True):
                    name = offer.get("name") or offer.get("title") or "TGrass Kanal"
                    link = offer.get("link") or offer.get("url") or ""
                    if link:
                        not_subscribed.append((str(offer.get('offer_id', offer.get('id', ''))), link, name))
        else:
            global tgrass_channels_cache
            if not tgrass_channels_cache:
                tgrass_fetch_channels()
            for idx, channel in enumerate(tgrass_channels_cache):
                u_name = channel.get("username", "")
                if not u_name:
                    continue
                try:
                    chat_target = f"@{u_name}" if not u_name.startswith("@") else u_name
                    member = await bot.get_chat_member(chat_target, user_id)
                    if member.status in ("left", "kicked", "banned"):
                        not_subscribed.append((str(idx), channel.get("link", ""), channel.get("name", "TGrass Kanal")))
                except Exception:
                    not_subscribed.append((str(idx), channel.get("link", ""), channel.get("name", "TGrass Kanal")))
    except Exception as e:
        pass
    return not_subscribed

async def is_user_subscribed(user_id, channel_id):
    try:
        member = await bot.get_chat_member(channel_id, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        return False

async def get_channel_name(channel_id=None, link=None):
    try:
        if channel_id:
            chat = await bot.get_chat(channel_id)
            return chat.title or f"Kanal {channel_id}"
        elif link and link.startswith('https://t.me/'):
            username = link.replace('https://t.me/', '@')
            chat = await bot.get_chat(username)
            return chat.title or username
        else:
            return link.split('/')[-1] if link else "Nätanyş kanal"
    except Exception as e:
        return link.split('/')[-1] if link else "Nätanyş kanal"

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
                'name': await get_channel_name(channel_id=sponsor[1])
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
                'name': addlist[1]
            })

    if get_tgrass_enabled():
        try:
            tgrass_offers = tgrass_get_offers(user_id, username, is_premium)
            if tgrass_offers:
                max_pos = len(all_channels) + 1
                for i, offer in enumerate(tgrass_offers):
                    if not offer.get("subscribed", True):
                        c_name = offer.get('name') or offer.get('title') or f"🌟 Kanal {i+1}"
                        c_link = offer.get('link') or offer.get('url') or ""
                        if c_link:
                            all_channels.append({
                                'id': f"tgrass_{i}",
                                'link': c_link,
                                'position': max_pos + i,
                                'type': 'tgrass',
                                'name': c_name
                            })
        except Exception as e:
            pass

    all_channels.sort(key=lambda x: x['position'])
    return all_channels

async def check_all_subscriptions(user_id, username=None, is_premium=False):
    not_subscribed = []
    
    sponsors = get_sponsors()
    for sponsor in sponsors:
        if not await is_user_subscribed(user_id, sponsor[1]):
            not_subscribed.append({
                'name': await get_channel_name(channel_id=sponsor[1]),
                'link': sponsor[2]
            })
    
    if get_tgrass_enabled():
        try:
            tgrass_not_sub = await check_tgrass_subscription(user_id, username, is_premium)
            for _, link, name in tgrass_not_sub:
                not_subscribed.append({'name': name, 'link': link})
        except Exception as e:
            pass
    
    return len(not_subscribed) == 0, not_subscribed

# ================= USER HANDLERS =================

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
            pass

    all_channels = await get_all_channels(user_id, username, is_premium)

    builder = InlineKeyboardBuilder()
    for channel in all_channels:
        # СИНИЙ цвет каналов (primary style)
        builder.button(
            text=channel['name'],
            url=channel['link'],
            style="primary"
        )

    # ЗЕЛЁНЫЙ цвет кнопки (success style) и иконка
    builder.button(
        text="Agza boldum",
        callback_data="check_sub",
        style="success",
        custom_emoji_id="5039844895779455925"
    )
    builder.adjust(1)

    # Строго указываем parse_mode="HTML"
    await message.answer(START_TEXT, reply_markup=builder.as_markup(), parse_mode=ParseMode.HTML)

@dp.callback_query(F.data == "check_sub")
async def check_sub_callback(call: CallbackQuery):
    user_id = call.from_user.id
    username = call.from_user.username
    is_premium = getattr(call.from_user, 'is_premium', False)

    is_subscribed, not_subscribed = await check_all_subscriptions(user_id, username, is_premium)

    if not is_subscribed:
        builder = InlineKeyboardBuilder()
        for channel in not_subscribed:
            # СИНИЙ цвет непрочитанных каналов
            builder.button(
                text=channel['name'],
                url=channel['link'],
                style="primary"
            )

        # ЗЕЛЁНЫЙ цвет кнопки проверки
        builder.button(
            text="Agza boldum",
            callback_data="check_sub",
            style="success",
            custom_emoji_id="5039844895779455925"
        )
        builder.adjust(1)

        try:
            await call.message.edit_text(
                NOT_SUB_TEXT,
                reply_markup=builder.as_markup(),
                parse_mode=ParseMode.HTML
            )
        except Exception:
            pass
        await call.answer()
    else:
        await call.answer()
        vpn_code = get_setting('vpn_code').strip()
        if not vpn_code:
            vpn_code = "VPN kody entek girizilmändir."

        vpn_message = f'<tg-emoji id="5886397939256925831">🔑</tg-emoji> <b>VPN:</b>\n\n<code>{vpn_code}</code>'

        try:
            await call.message.delete()
        except Exception:
            pass

        await call.message.answer(vpn_message, parse_mode=ParseMode.HTML)

# ================= ADMIN PANEL HANDLERS =================

@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer(
            f'<tg-emoji id="{EMOJI_IDS["warning"]}">⚠️</tg-emoji> Siz admin dälsiňiz!',
            parse_mode=ParseMode.HTML
        )
        return

    builder = InlineKeyboardBuilder()

    builder.button(text="➕ Sponsor goşmak", callback_data="add_sponsor")
    builder.button(text="➖ Sponsor pozmak", callback_data="remove_sponsor")
    builder.button(text="🔑 VPN koduny üýtgetmek", callback_data="edit_code")
    builder.button(text="➕ Addlist goşmak", callback_data="add_addlist")
    builder.button(text="➖ Addlist pozmak", callback_data="remove_addlist")
    builder.button(text="👤 Admin goşmak", callback_data="add_admin")
    builder.button(text="❌ Admin aýyrmak", callback_data="remove_admin")
    builder.button(text="📋 Adminler sanawy", callback_data="list_admins")
    builder.button(text="📢 Bildiriş paýlaşmak", callback_data="broadcast")
    builder.button(text="📊 Statistika", callback_data="stats")
    builder.button(text="🌟 TGrass sazlamalary", callback_data="tgrass_settings")

    builder.adjust(2)

    await message.answer(
        f'<tg-emoji id="{EMOJI_IDS["admin"]}">👑</tg-emoji> <b>Admin Panel</b>',
        reply_markup=builder.as_markup(),
        parse_mode=ParseMode.HTML
    )

@dp.callback_query(F.data == "add_admin")
async def add_admin_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Elýeterlilik ýok!", show_alert=True)
        return

    await call.message.edit_text(
        f'<tg-emoji id="{EMOJI_IDS["add"]}">➕</tg-emoji> <b>Täze Admin goşmak</b>\n\n'
        f"Täze adminiň Telegram ID-syny iberiň (meselem: 123456789)\n"
        f"Ýatyrmak üçin /cancel iberiň.",
        parse_mode=ParseMode.HTML
    )
    await state.set_state(AdminStates.waiting_for_add_admin_id)
    await call.answer()

@dp.message(AdminStates.waiting_for_add_admin_id)
async def process_add_admin_id(message: Message, state: FSMContext):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Operasiýa ýatyrtyldy.")
        return

    try:
        new_admin_id = int(message.text.strip())
        add_admin_db(new_admin_id)
        await message.answer(
            f'<tg-emoji id="{EMOJI_IDS["success"]}">✅</tg-emoji> <b>Admin üstünlikli goşuldy!</b>\n'
            f"ID: <code>{new_admin_id}</code>",
            parse_mode=ParseMode.HTML
        )
    except ValueError:
        await message.answer("❌ Ýalňyş ID! Diňe san giriziň.")
        return

    await state.clear()

@dp.callback_query(F.data == "remove_admin")
async def remove_admin_start(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Elýeterlilik ýok!", show_alert=True)
        return

    admins = get_all_admins()
    builder = InlineKeyboardBuilder()

    for admin_id in admins:
        if admin_id in ADMIN_IDS:
            continue
        builder.button(
            text=f"❌ {admin_id}",
            callback_data=f"del_admin_{admin_id}"
        )

    builder.button(text="◀️ Yza", callback_data="back_to_admin")
    builder.adjust(1)

    await call.message.edit_text(
        f'<tg-emoji id="{EMOJI_IDS["remove"]}">➖</tg-emoji> <b>Aýyrmak üçin admin saýlaň:</b>',
        reply_markup=builder.as_markup(),
        parse_mode=ParseMode.HTML
    )
    await call.answer()

@dp.callback_query(F.data.startswith("del_admin_"))
async def delete_admin(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Elýeterlilik ýok!", show_alert=True)
        return

    admin_to_del = int(call.data.replace("del_admin_", ""))
    remove_admin_db(admin_to_del)

    await call.message.edit_text(
        f'<tg-emoji id="{EMOJI_IDS["success"]}">✅</tg-emoji> Admin aýryldy: <code>{admin_to_del}</code>',
        parse_mode=ParseMode.HTML
    )
    await call.answer()

@dp.callback_query(F.data == "list_admins")
async def list_admins(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Elýeterlilik ýok!", show_alert=True)
        return

    admins = get_all_admins()
    text = f'<tg-emoji id="{EMOJI_IDS["admin"]}">👑</tg-emoji> <b>Adminler sanawy:</b>\n\n'
    for a_id in admins:
        role = " (Baş Admin)" if a_id in ADMIN_IDS else ""
        text += f"• <code>{a_id}</code>{role}\n"

    builder = InlineKeyboardBuilder()
    builder.button(text="◀️ Yza", callback_data="back_to_admin")

    await call.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode=ParseMode.HTML)
    await call.answer()

@dp.callback_query(F.data == "add_sponsor")
async def add_sponsor_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Elýeterlilik ýok!", show_alert=True)
        return
    
    await call.message.edit_text(
        f'<tg-emoji id="{EMOJI_IDS["add"]}">➕</tg-emoji> <b>Sponsor goşmak</b>\n\n'
        f"Kanal ID-syny iberiň (meselem: -1001234567890)\n"
        f"Ýatyrmak üçin /cancel iberiň.",
        parse_mode=ParseMode.HTML
    )
    await state.set_state(AdminStates.waiting_for_sponsor_channel_id)
    await call.answer()

@dp.message(AdminStates.waiting_for_sponsor_channel_id)
async def process_sponsor_channel_id(message: Message, state: FSMContext):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Operasiýa ýatyrtyldy.")
        return
    
    channel_id = message.text.strip()
    await state.update_data(channel_id=channel_id)
    
    await message.answer(
        f'<tg-emoji id="{EMOJI_IDS["link"]}">🔗</tg-emoji> Indi kanalyň çykgydyny (link) iberiň',
        parse_mode=ParseMode.HTML
    )
    await state.set_state(AdminStates.waiting_for_sponsor_link)

@dp.message(AdminStates.waiting_for_sponsor_link)
async def process_sponsor_link(message: Message, state: FSMContext):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Operasiýa ýatyrtyldy.")
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
                f'<tg-emoji id="{EMOJI_IDS["success"]}">✅</tg-emoji> Sponsor üstünlikli goşuldy!\n'
                f"ID: <code>{channel_id}</code>\nLink: {link}",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            await message.answer(f"❌ Ýalňyşlyk: {str(e)}")
    
    await state.clear()

@dp.callback_query(F.data == "remove_sponsor")
async def remove_sponsor_start(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Elýeterlilik ýok!", show_alert=True)
        return
    
    sponsors = get_sponsors()
    if not sponsors:
        await call.message.edit_text("❌ Sponsorlar sanawy boş.")
        await call.answer()
        return
    
    text = f'<tg-emoji id="{EMOJI_IDS["remove"]}">➖</tg-emoji> <b>Pozmak üçin sponsory saýlaň:</b>\n\n'
    builder = InlineKeyboardBuilder()
    
    for sponsor in sponsors:
        name = await get_channel_name(channel_id=sponsor[1])
        builder.button(
            text=f"❌ {name}",
            callback_data=f"del_sponsor_{sponsor[0]}"
        )
    
    builder.button(text="◀️ Yza", callback_data="back_to_admin")
    builder.adjust(1)
    
    await call.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode=ParseMode.HTML)
    await call.answer()

@dp.callback_query(F.data.startswith("del_sponsor_"))
async def delete_sponsor(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Elýeterlilik ýok!", show_alert=True)
        return
    
    sponsor_id = int(call.data.replace("del_sponsor_", ""))
    
    with closing(sqlite3.connect('wwwnahnah.db')) as conn:
        try:
            with conn:
                conn.execute("DELETE FROM sponsors WHERE id = ?", (sponsor_id,))
            await call.message.edit_text(
                f'<tg-emoji id="{EMOJI_IDS["success"]}">✅</tg-emoji> Sponsor pozuldy!',
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            await call.answer(f"Ýalňyşlyk: {str(e)}", show_alert=True)
    
    await call.answer()

@dp.callback_query(F.data == "edit_code")
async def edit_vpn_code(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Elýeterlilik ýok!", show_alert=True)
        return
    
    current_code = get_setting('vpn_code')
    
    await call.message.edit_text(
        f'<tg-emoji id="5886397939256925831">🔑</tg-emoji> <b>VPN koduny üýtgetmek</b>\n\n'
        f"Häzirki kod: <code>{current_code if current_code else 'Bellenmedi'}</code>\n\n"
        f"Täze VPN koduny iberiň ýa-da ýatyrmak üçin /cancel iberiň.",
        parse_mode=ParseMode.HTML
    )
    await state.set_state(AdminStates.waiting_for_vpn_code)
    await call.answer()

@dp.message(AdminStates.waiting_for_vpn_code)
async def process_vpn_code(message: Message, state: FSMContext):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Operasiýa ýatyrtyldy.")
        return
    
    new_code = message.text.strip()
    set_setting('vpn_code', new_code)
    
    await message.answer(
        f'<tg-emoji id="{EMOJI_IDS["success"]}">✅</tg-emoji> VPN kody ýatda saklandy: <code>{new_code}</code>',
        parse_mode=ParseMode.HTML
    )
    await state.clear()

@dp.callback_query(F.data == "add_addlist")
async def add_addlist_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Elýeterlilik ýok!", show_alert=True)
        return
    
    await call.message.edit_text(
        f'<tg-emoji id="{EMOJI_IDS["add"]}">➕</tg-emoji> <b>Addlist goşmak</b>\n\n'
        f"Görkezilmeli adyny iberiň ýa-da ýatyrmak üçin /cancel iberiň.",
        parse_mode=ParseMode.HTML
    )
    await state.set_state(AdminStates.waiting_for_addlist_name)
    await call.answer()

@dp.message(AdminStates.waiting_for_addlist_name)
async def process_addlist_name(message: Message, state: FSMContext):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Operasiýa ýatyrtyldy.")
        return
    
    name = message.text.strip()
    await state.update_data(name=name)
    
    await message.answer(
        f'<tg-emoji id="{EMOJI_IDS["link"]}">🔗</tg-emoji> Indi çykgydy (link) iberiň:',
        parse_mode=ParseMode.HTML
    )
    await state.set_state(AdminStates.waiting_for_addlist_link)

@dp.message(AdminStates.waiting_for_addlist_link)
async def process_addlist_link(message: Message, state: FSMContext):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Operasiýa ýatyrtyldy.")
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
                f'<tg-emoji id="{EMOJI_IDS["success"]}">✅</tg-emoji> Addlist üstünlikli goşuldy!\n'
                f"Ady: {name}\nLink: {link}",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            await message.answer(f"❌ Ýalňyşlyk: {str(e)}")
    
    await state.clear()

@dp.callback_query(F.data == "remove_addlist")
async def remove_addlist_start(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Elýeterlilik ýok!", show_alert=True)
        return
    
    addlists = get_addlists()
    if not addlists:
        await call.message.edit_text("❌ Addlist sanawy boş.")
        await call.answer()
        return
    
    text = f'<tg-emoji id="{EMOJI_IDS["remove"]}">➖</tg-emoji> <b>Pozmak üçin Addlist saýlaň:</b>\n\n'
    builder = InlineKeyboardBuilder()
    
    for addlist in addlists:
        builder.button(
            text=f"❌ {addlist[1]}",
            callback_data=f"del_addlist_{addlist[0]}"
        )
    
    builder.button(text="◀️ Yza", callback_data="back_to_admin")
    builder.adjust(1)
    
    await call.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode=ParseMode.HTML)
    await call.answer()

@dp.callback_query(F.data.startswith("del_addlist_"))
async def delete_addlist(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Elýeterlilik ýok!", show_alert=True)
        return
    
    addlist_id = int(call.data.replace("del_addlist_", ""))
    
    with closing(sqlite3.connect('wwwnahnah.db')) as conn:
        try:
            with conn:
                conn.execute("DELETE FROM addlists WHERE id = ?", (addlist_id,))
            await call.message.edit_text(
                f'<tg-emoji id="{EMOJI_IDS["success"]}">✅</tg-emoji> Addlist pozuldy!',
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            await call.answer(f"Ýalňyşlyk: {str(e)}", show_alert=True)
    
    await call.answer()

@dp.callback_query(F.data == "broadcast")
async def broadcast_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Elýeterlilik ýok!", show_alert=True)
        return
    
    await call.message.edit_text(
        f'<tg-emoji id="{EMOJI_IDS["broadcast"]}">📢</tg-emoji> <b>Bildiriş paýlaşmak</b>\n\n'
        f"Hemme ulanyjylara paýlaşmak işleýän hatyňyzy iberiň.\n"
        f"Ýatyrmak üçin /cancel iberiň.",
        parse_mode=ParseMode.HTML
    )
    await state.set_state(AdminStates.waiting_for_broadcast)
    await call.answer()

@dp.message(AdminStates.waiting_for_broadcast)
async def process_broadcast(message: Message, state: FSMContext):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Operasiýa ýatyrtyldy.")
        return
    
    users = get_all_users()
    success = 0
    failed = 0
    
    await message.answer(f"📤 {len(users)} ulanyja bildiriş ugratmak başlandy...")
    
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
    
    await message.answer(
        f'<tg-emoji id="{EMOJI_IDS["stats"]}">📊</tg-emoji> <b>Bildiriş tamamlandy!</b>\n\n'
        f"✅ Üstünlikli: {success}\n"
        f"❌ Ýalňyşlyk: {failed}",
        parse_mode=ParseMode.HTML
    )
    await state.clear()

@dp.callback_query(F.data == "stats")
async def show_stats(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Elýeterlilik ýok!", show_alert=True)
        return
    
    users = get_all_users()
    sponsors = get_sponsors()
    addlists = get_addlists()
    admins = get_all_admins()
    tgrass_enabled = get_tgrass_enabled()
    
    text = (
        f'<tg-emoji id="{EMOJI_IDS["stats"]}">📊</tg-emoji> <b>Botyň statistikasy</b>\n\n'
        f"👥 Ulanyjylar: {len(users)}\n"
        f"📢 Sponsorlar: {len(sponsors)}\n"
        f"📋 Addlistler: {len(addlists)}\n"
        f"👑 Adminler: {len(admins)}\n"
        f"🌟 TGrass: {'✅ Birikdirilen' if tgrass_enabled else '❌ Öçürilen'}\n"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="◀️ Yza", callback_data="back_to_admin")
    
    await call.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode=ParseMode.HTML)
    await call.answer()

@dp.callback_query(F.data == "tgrass_settings")
async def tgrass_settings(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Elýeterlilik ýok!", show_alert=True)
        return
    
    enabled = get_tgrass_enabled()
    status_text = "✅ Birikdirilen" if enabled else "❌ Öçürilen"
    
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✅ Birikdir" if not enabled else "❌ Öçür",
        callback_data="toggle_tgrass"
    )
    builder.button(
        text="🔄 Kanallary täzele",
        callback_data="refresh_tgrass"
    )
    builder.button(text="◀️ Yza", callback_data="back_to_admin")
    builder.adjust(1)
    
    await call.message.edit_text(
        f'<tg-emoji id="{EMOJI_IDS["tgrass"]}">🌟</tg-emoji> <b>TGrass Sazlamalary</b>\n\n'
        f"Status: {status_text}\n\n"
        f"API: {TGRASS_API_URL}",
        reply_markup=builder.as_markup(),
        parse_mode=ParseMode.HTML
    )
    await call.answer()

@dp.callback_query(F.data == "toggle_tgrass")
async def toggle_tgrass(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Elýeterlilik ýok!", show_alert=True)
        return
    
    current = get_tgrass_enabled()
    set_tgrass_enabled(not current)
    
    new_status = "✅ Birikdirildi" if not current else "❌ Öçürüldi"
    await call.answer(f"TGrass {new_status}!", show_alert=True)
    
    await tgrass_settings(call)

@dp.callback_query(F.data == "refresh_tgrass")
async def refresh_tgrass(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Elýeterlilik ýok!", show_alert=True)
        return
    
    await call.answer("🔄 Kanallar täzelenýär...", show_alert=False)
    
    count, msg = tgrass_fetch_channels()
    
    if msg == "ok":
        await call.message.edit_text(
            f'<tg-emoji id="{EMOJI_IDS["success"]}">✅</tg-emoji> <b>TGrass kanallary täzelendi!</b>\n\n'
            f"📡 Alnan kanal sany: {count}\n\n"
            f"🌟 {count} kanal RAM-e ýatda saklandy.",
            reply_markup=InlineKeyboardBuilder().button(text="◀️ Yza", callback_data="tgrass_settings").as_markup(),
            parse_mode=ParseMode.HTML
        )
    else:
        await call.message.edit_text(
            f'<tg-emoji id="{EMOJI_IDS["warning"]}">❌</tg-emoji> <b>TGrass baglanyşyk hatasy!</b>\n\n'
            f"Hata: <code>{msg}</code>",
            reply_markup=InlineKeyboardBuilder().button(text="◀️ Yza", callback_data="tgrass_settings").as_markup(),
            parse_mode=ParseMode.HTML
        )
    
    await call.answer()

@dp.callback_query(F.data == "back_to_admin")
async def back_to_admin(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Elýeterlilik ýok!", show_alert=True)
        return
    
    builder = InlineKeyboardBuilder()
    
    builder.button(text="➕ Sponsor goşmak", callback_data="add_sponsor")
    builder.button(text="➖ Sponsor pozmak", callback_data="remove_sponsor")
    builder.button(text="🔑 VPN koduny üýtgetmek", callback_data="edit_code")
    builder.button(text="➕ Addlist goşmak", callback_data="add_addlist")
    builder.button(text="➖ Addlist pozmak", callback_data="remove_addlist")
    builder.button(text="👤 Admin goşmak", callback_data="add_admin")
    builder.button(text="❌ Admin aýyrmak", callback_data="remove_admin")
    builder.button(text="📋 Adminler sanawy", callback_data="list_admins")
    builder.button(text="📢 Bildiriş paýlaşmak", callback_data="broadcast")
    builder.button(text="📊 Statistika", callback_data="stats")
    builder.button(text="🌟 TGrass sazlamalary", callback_data="tgrass_settings")
    
    builder.adjust(2)
    
    await call.message.edit_text(
        f'<tg-emoji id="{EMOJI_IDS["admin"]}">👑</tg-emoji> <b>Admin Panel</b>',
        reply_markup=builder.as_markup(),
        parse_mode=ParseMode.HTML
    )
    await call.answer()

# Main runner
async def main():
    logging.info("Bot started")
    print("🤖 Bot işleýär...")
    print(f"👑 Baş Admin ID: {ADMIN_IDS[0]}")
    
    try:
        count, msg = tgrass_fetch_channels()
        if msg == "ok":
            print(f"📡 TGrass: {count} kanal RAM-e ýüklendi")
        else:
            print(f"⚠️ TGrass: {msg}")
    except Exception as e:
        print(f"❌ TGrass init error: {e}")
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot saklandy!")
