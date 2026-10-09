#!/usr/bin/env python3
import json, os, subprocess, sys

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "keys.json")
GITHUB_USER = "narutop5577"
GITHUB_TOKEN = os.environ.get("DSS_GITHUB_TOKEN", "")
REPO_URL = f"https://{GITHUB_USER}:{GITHUB_TOKEN}@github.com/{GITHUB_USER}/dss-server.git"
TOTAL_SLOTS = 30

class C:
    RESET='\033[0m'; BOLD='\033[1m'
    RED='\033[91m'; GREEN='\033[92m'; YELLOW='\033[93m'
    BLUE='\033[94m'; MAGENTA='\033[95m'; CYAN='\033[96m'

def clear(): os.system('cls' if os.name == 'nt' else 'clear')

def load_db():
    if not os.path.exists(DB_FILE): return {"keys": {}}
    with open(DB_FILE) as f: return json.load(f)

def save_db(db):
    with open(DB_FILE, "w") as f: json.dump(db, f, indent=4)

def slot_name(i): return f"SLOT_{i:02d}"

def is_blank(v):
    return "HWID_HERE" in str(v.get("hwid", ""))

def get_key_for_slot(db, slot_num):
    """Slot number se key dhundo (dono type ke entries me)"""
    for k, v in db["keys"].items():
        if v.get("slot") == slot_num: return k
    # Agar slot field nahi hai
    sn = slot_name(slot_num)
    if sn in db["keys"] and not is_blank(db["keys"][sn]):
        return sn
    return None

def get_blank_slots(db):
    blanks = []
    for i in range(1, TOTAL_SLOTS + 1):
        if get_key_for_slot(db, i) is None:
            blanks.append(i)
    return blanks

def get_filled_slots(db):
    filled = []
    for i in range(1, TOTAL_SLOTS + 1):
        k = get_key_for_slot(db, i)
        if k:
            filled.append((i, k, db["keys"][k]))
    return filled

def git_push(msg):
    try:
        os.chdir(os.path.dirname(DB_FILE))
        subprocess.run(["git","remote","set-url","origin",REPO_URL], capture_output=True)
        subprocess.run(["git","add","-f","keys.json"], capture_output=True)
        subprocess.run(["git","commit","-m",msg], capture_output=True)
        r = subprocess.run(["git","push","origin","main","-f"], capture_output=True, text=True)
        if r.returncode == 0:
            print(f"{C.GREEN}✅ GitHub push ho gaya!{C.RESET}")
            return True
        print(f"{C.RED}❌ Push fail: {r.stderr.strip()}{C.RESET}")
        return False
    except Exception as e:
        print(f"{C.RED}❌ Git error: {e}{C.RESET}")
        return False

# ==================== ADD ====================
def add_key():
    clear()
    print(f"{C.CYAN}{C.BOLD}══════════ ADD KEY ══════════{C.RESET}\n")
    key = input(f"{C.YELLOW}Enter Key: {C.RESET}").strip()
    if not key: print(f"{C.RED}❌ Khali{C.RESET}"); input("Enter..."); return
    hwid = input(f"{C.YELLOW}Enter HWID: {C.RESET}").strip()
    if not hwid: print(f"{C.RED}❌ Khali{C.RESET}"); input("Enter..."); return
    
    db = load_db()
    
    # Agar key already kisi slot me hai
    for k, v in db["keys"].items():
        if k == key:
            print(f"{C.RED}❌ Ye key already exist!{C.RESET}"); input("Enter..."); return
    
    blanks = get_blank_slots(db)
    if not blanks:
        print(f"{C.RED}❌ Koi blank slot nahi!{C.RESET}"); input("Enter..."); return
    
    print(f"\n{C.GREEN}Blank Slots:{C.RESET}")
    for i in blanks: print(f"  [{i}] Slot {i}")
    
    filled = get_filled_slots(db)
    if filled:
        print(f"\n{C.YELLOW}Filled Slots:{C.RESET}")
        for i, k, v in filled:
            print(f"  [{i}] {k[:30]}...")
    
    print()
    try:
        choice = int(input(f"{C.YELLOW}Choose Slot (1-30): {C.RESET}").strip())
    except: 
        print(f"{C.RED}❌ Invalid{C.RESET}"); input("Enter..."); return
    
    if choice < 1 or choice > TOTAL_SLOTS:
        print(f"{C.RED}❌ Out of range{C.RESET}"); input("Enter..."); return
    
    existing = get_key_for_slot(db, choice)
    if existing:
        print(f"{C.RED}❌ Slot {choice} already filled!{C.RESET}"); input("Enter..."); return
    
    # Add key with slot number
    db["keys"][key] = {
        "hwid": hwid,
        "created_at": "2025-01-01T00:00:00",
        "active": True,
        "expiry": 9999999999,
        "slot": choice
    }
    
    # Remove blank SLOT_XX entry
    sn = slot_name(choice)
    if sn in db["keys"]: del db["keys"][sn]
    
    save_db(db)
    
    print(f"\n{C.GREEN}✅ Key added!{C.RESET}")
    print(f"  Key:  {C.CYAN}{key}{C.RESET}")
    print(f"  HWID: {C.CYAN}{hwid}{C.RESET}")
    print(f"  Slot: {C.CYAN}{choice}{C.RESET}")
    print(f"\n{C.YELLOW}📤 GitHub push...{C.RESET}")
    git_push(f"Add key slot {choice}")
    print(f"\n{C.MAGENTA}⚠️  Railway pe REDEPLOY karo!{C.RESET}")
    input("\nEnter...")

# ==================== REMOVE ====================
def remove_key():
    clear()
    print(f"{C.CYAN}{C.BOLD}══════════ REMOVE KEY ══════════{C.RESET}\n")
    db = load_db()
    filled = get_filled_slots(db)
    
    if not filled:
        print(f"{C.RED}❌ Koi key nahi hai{C.RESET}"); input("Enter..."); return
    
    print(f"{C.YELLOW}Active Keys:{C.RESET}\n")
    for i, k, v in filled:
        print(f"  [{i}] {C.CYAN}{k}{C.RESET}")
        print(f"       HWID: {v.get('hwid','')[:30]}...\n")
    
    try:
        choice = int(input(f"{C.YELLOW}Slot to Remove: {C.RESET}").strip())
    except:
        print(f"{C.RED}❌ Invalid{C.RESET}"); input("Enter..."); return
    
    key_to_remove = get_key_for_slot(db, choice)
    if not key_to_remove:
        print(f"{C.RED}❌ Slot {choice} me koi key nahi{C.RESET}"); input("Enter..."); return
    
    confirm = input(f"{C.YELLOW}Remove '{key_to_remove}'? (y/n): {C.RESET}").strip().lower()
    if confirm != 'y':
        print(f"{C.YELLOW}Cancel{C.RESET}"); input("Enter..."); return
    
    # Remove key entry
    del db["keys"][key_to_remove]
    
    # Add blank slot back
    sn = slot_name(choice)
    db["keys"][sn] = {
        "hwid": f"{sn}_HWID_HERE",
        "created_at": "2025-01-01T00:00:00",
        "active": True,
        "expiry": 9999999999
    }
    
    save_db(db)
    
    print(f"\n{C.GREEN}✅ Removed!{C.RESET}")
    print(f"  Slot {choice} ab blank hai")
    print(f"\n{C.YELLOW}📤 GitHub push...{C.RESET}")
    git_push(f"Remove key slot {choice}")
    print(f"\n{C.MAGENTA}⚠️  Railway REDEPLOY ke baad access INVALID!{C.RESET}")
    input("\nEnter...")

# ==================== LIST ====================
def list_keys():
    clear()
    print(f"{C.CYAN}{C.BOLD}══════════ ALL KEYS ══════════{C.RESET}\n")
    db = load_db()
    filled = get_filled_slots(db)
    blanks = get_blank_slots(db)
    print(f"{C.GREEN}Active: {len(filled)}{C.RESET} | {C.YELLOW}Blank: {len(blanks)}{C.RESET}\n")
    
    if filled:
        print(f"{C.CYAN}─── Filled ───{C.RESET}\n")
        for i, k, v in filled:
            print(f"  Slot {i}: {C.GREEN}{k}{C.RESET}")
            print(f"          HWID: {v.get('hwid','')}\n")
    if blanks:
        print(f"{C.YELLOW}─── Blank ───{C.RESET}")
        print(f"  {', '.join(map(str, blanks))}")
    input("\nEnter...")

# ==================== MENU ====================
def main_menu():
    while True:
        clear()
        print(f"{C.CYAN}{C.BOLD}")
        print("╔══════════════════════════════════╗")
        print("║      DSS MART KEY MANAGER        ║")
        print("║         by NARUTO                ║")
        print("╚══════════════════════════════════╝")
        print(f"{C.RESET}")
        db = load_db()
        f = len(get_filled_slots(db)); b = len(get_blank_slots(db))
        print(f"{C.YELLOW}Slots: {f} filled | {b} blank{C.RESET}\n")
        print(f"  {C.GREEN}[1]{C.RESET} Add Key")
        print(f"  {C.RED}[2]{C.RESET} Remove Key")
        print(f"  {C.CYAN}[3]{C.RESET} List Keys")
        print(f"  {C.MAGENTA}[4]{C.RESET} Exit\n")
        ch = input(f"{C.YELLOW}Choose: {C.RESET}").strip()
        if ch == "1": add_key()
        elif ch == "2": remove_key()
        elif ch == "3": list_keys()
        elif ch == "4": print(f"\n{C.GREEN}Bye!{C.RESET}"); sys.exit(0)
        else: print(f"{C.RED}Invalid{C.RESET}"); import time; time.sleep(1)

if __name__ == "__main__":
    try: main_menu()
    except KeyboardInterrupt: print(f"\n\n{C.YELLOW}Exit{C.RESET}"); sys.exit(0)
