# -*- coding: utf-8 -*-
# ═══════════════════════════════════════════════════════════
#  پنل ساخت پک ایموجی پرمیوم — معماری دو بات
#
#  PANEL_BOT_TOKEN → بات دوم (فقط رابط پنل؛ از BotFather یه بات جدید بساز)
#  MAIN_BOT_TOKEN  → توکن بات اصلی (پک مالِ او می‌شه و ایموجی پرمیوم می‌فرسته)
# ═══════════════════════════════════════════════════════════
import re, json, requests

PANEL_BOT_TOKEN = "8981709760:AAH08wkY9XwdJcQcTHoFX9ByBmWe50srROo"
MAIN_BOT_TOKEN  = "8266974282:AAEQt54_iNNDtn7Epa13uopIbwpGzLPgvxA"
ADMIN_IDS = {7845464086}

PANEL_API     = f"https://api.telegram.org/bot{PANEL_BOT_TOKEN}"
MAIN_API      = f"https://api.telegram.org/bot{MAIN_BOT_TOKEN}"
MAIN_FILE_API = f"https://api.telegram.org/file/bot{MAIN_BOT_TOKEN}"

me = requests.get(f"{MAIN_API}/getMe", timeout=30).json()["result"]
BOT_ID, BOT_USERNAME = me["id"], me["username"]

EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF"
    "\U0001F1E6-\U0001F1FF\u2B00-\u2BFF\uFE0F\u200D]+"
)

states = {}

# ─────────────────── توابع پایه ───────────────────
def main_api(method, payload=None, files=None):
    """عملیات استیکر/پک — همیشه با هویت بات اصلی"""
    try:
        return requests.post(f"{MAIN_API}/{method}", data=payload, files=files, timeout=180).json()
    except Exception as e:
        return {"ok": False, "description": str(e)}

def panel_send(chat_id, text, kb=None, parse="Markdown"):
    p = {"chat_id": chat_id, "text": text, "parse_mode": parse}
    if kb:
        p["reply_markup"] = json.dumps(kb)
    return requests.post(f"{PANEL_API}/sendMessage", json=p, timeout=60).json()

def panel_edit(chat_id, msg_id, text, parse="Markdown"):
    return requests.post(f"{PANEL_API}/editMessageText", json={
        "chat_id": chat_id, "message_id": msg_id,
        "text": text, "parse_mode": parse,
    }, timeout=60).json()

def main_send(chat_id, text, parse="HTML"):
    """پیام تست پرمیوم باید با بات اصلی ارسال بشه"""
    try:
        return requests.post(f"{MAIN_API}/sendMessage", json={
            "chat_id": chat_id, "text": text, "parse_mode": parse,
        }, timeout=60).json()
    except Exception:
        return {"ok": False}

PANEL_KB = {"inline_keyboard": [[{"text": "🎨 ساخت پک ایموجی", "callback_data": "mkpack"}]]}

def panel_text():
    return (f"🛠 **پنل مدیریت ایموجی**\n"
            f"پک‌ها با هویت @{BOT_USERNAME} ساخته می‌شن ✅\n\n"
            "🔗 لینک پک موجود → کپی کامل با هویت بات اصلی\n"
            "🔢 آیدی عددی → کپی فقط همون ایموجی‌ها")

# ─────────────────── منطق ساخت/کپی پک ───────────────────
def sanitize(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", name.strip()) or "Pack"

def extract_pack_name(text: str) -> str:
    m = re.search(r"(?:addemoji|addstickers)/([A-Za-z0-9_]+)", text)
    return m.group(1) if m else text.strip()

def detect_format(s: dict) -> str:
    if s.get("is_animated"):
        return "animated"
    if s.get("is_video"):
        return "video"
    return "static"

def download_sticker(file_id: str) -> bytes:
    res = main_api("getFile", {"file_id": file_id})
    if not res.get("ok"):
        raise RuntimeError(f"getFile: {res.get('description')}")
    return requests.get(f"{MAIN_FILE_API}/{res['result']['file_path']}", timeout=180).content

def looks_like_ids(text: str) -> bool:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    return bool(lines) and all(re.fullmatch(r"\d{5,}(\s*=\s*.+)?", l) for l in lines)

def _norm_emoji(e) -> list:
    if isinstance(e, str):
        found = EMOJI_RE.findall(e)
        return found or ["😀"]
    return e or ["😀"]

def _file_meta(it, key):
    if it["format"] == "video":
        return key, ("e.webm", it["data"], "video/webm")
    if it["format"] == "animated":
        return key, ("e.tgs", it["data"], "application/x-tgz")
    ext = "webp" if it["data"][:4] == b"RIFF" else "png"
    return key, (f"e.{ext}", it["data"], f"image/{ext}")

def fetch_source_items(source_text: str):
    text = source_text.strip()

    if looks_like_ids(text):
        ids, emoji_map = [], {}
        for line in text.splitlines():
            line = line.strip()
            if "=" in line:
                eid, emo = line.split("=", 1)
                eid = eid.strip()
                ids.append(eid)
                emoji_map[eid] = _norm_emoji(emo)
            else:
                ids.append(line)
        res = main_api("getCustomEmojiStickers", {"custom_emoji_ids": json.dumps(ids)})
        if not res.get("ok"):
            raise RuntimeError(f"getCustomEmojiStickers: {res.get('description')}")
        items = [{
            "data":   download_sticker(s["file_id"]),
            "emoji":  emoji_map.get(s.get("custom_emoji_id"), _norm_emoji(s.get("emoji"))),
            "format": detect_format(s),
        } for s in res["result"]]
        if not items:
            raise RuntimeError("هیچ ایموجی‌ای پیدا نشد؛ آیدی‌ها رو چک کن")
        return items[:120], "Emoji Pack"

    name = extract_pack_name(text)
    res = main_api("getStickerSet", {"name": name})
    if not res.get("ok"):
        raise RuntimeError(f"پک «{name}» پیدا نشد: {res.get('description')}")
    pack = res["result"]
    items = [{
        "data":   download_sticker(s["file_id"]),
        "emoji":  _norm_emoji(s.get("emoji")),
        "format": detect_format(s),
    } for s in pack["stickers"]]
    return items[:120], pack.get("title") or name

def build_pack(short_name: str, title: str, items) -> str:
    name = f"{sanitize(short_name)}_by_{BOT_USERNAME}"

    stickers, files = [], {}
    for i, it in enumerate(items[:50]):
        k = f"f{i}"
        stickers.append({"sticker": f"attach://{k}",
                         "emoji_list": it["emoji"],
                         "format": it["format"]})
        k, f = _file_meta(it, k)
        files[k] = f
    res = main_api("createNewStickerSet", {
        "user_id": str(BOT_ID),          # ⬅️ پک مال بات اصلی می‌شه
        "name": name,
        "title": (title or "My Emojis")[:64],
        "sticker_type": "custom_emoji",
        "stickers": json.dumps(stickers),
    }, files=files)
    if not res.get("ok"):
        raise RuntimeError(f"ساخت پک: {res.get('description')}")

    for it in items[50:]:
        k, f = _file_meta(it, "s")
        res = main_api("addStickerToSet", {
            "user_id": str(BOT_ID),
            "name": name,
            "sticker": json.dumps({"sticker": "attach://s",
                                   "emoji_list": it["emoji"],
                                   "format": it["format"]}),
        }, files={"s": f})
        if not res.get("ok"):
            raise RuntimeError(f"افزودن ایموجی: {res.get('description')}")
    return name

def pack_report(name: str):
    res = main_api("getStickerSet", {"name": name})
    if not res.get("ok"):
        raise RuntimeError("خواندن پک جدید ناموفق بود")
    rows = [("".join(s.get("emoji") or ["😀"]), s["custom_emoji_id"])
            for s in res["result"]["stickers"] if s.get("custom_emoji_id")]
    return res["result"].get("title", name), rows

# ─────────────────── پیام‌های فلو ───────────────────
MSG_NAME = ("🎨 **ساخت پک ایموجی**\n\n"
            "۱. یه **اسم انگلیسی** برای پک بفرست (حروف/عدد/آندرلاین، بدون فاصله)\n"
            "مثال: `MyEmojis`\n\nلغو: /cancel")

MSG_SOURCE = ("۲. حالا **سورس** رو بفرست؛ یکی از دو حالت:\n\n"
              "🔗 **کپی کل پک:** لینکش رو بفرست:\n"
              "`t.me/addemoji/PackName`\n\n"
              "🔢 **آیدی دستی:** هر خط یه آیدی (ایموجی اختیاری):\n"
              "`5368324170671202286 = 😎`")

# ─────────────────── اجرای فلوی ساخت ───────────────────
def run_build(chat_id, msg_id, short, source):
    try:
        panel_edit(chat_id, msg_id, "⏳ در حال دانلود فایل‌ها از مبدا...")
        items, title = fetch_source_items(source)

        panel_edit(chat_id, msg_id, f"⏳ {len(items)} ایموجی گرفتم؛ دارم پک رو می‌سازم...")
        full = build_pack(short, title, items)

        panel_edit(chat_id, msg_id, "⏳ در حال خروجی گرفتن آیدی‌ها...")
        pt, rows = pack_report(full)
    except Exception as e:
        panel_edit(chat_id, msg_id, f"❌ خطا: `{e}`\n\nاز دکمه پنل دوباره تلاش کن.")
        return

    lines = [f"✅ پک **{pt}** ساخته شد!", f"نام پک: `{full}`", ""]
    sample = []
    for emo, eid in rows:
        lines.append(f"{emo} → `{eid}`")
        sample.append(f'<tg-emoji emoji-id="{eid}">{emo}</tg-emoji>')

    text = "\n".join(lines)
    if len(text) > 4000:
        f = {"report.txt": (f"{short}_ids.txt", text.encode("utf-8"))}
        requests.post(f"{PANEL_API}/sendDocument",
                      data={"chat_id": chat_id, "caption": f"📁 آیدی‌های پک {pt}"},
                      files=f, timeout=120)
    else:
        panel_send(chat_id, text)

    # پیام تست پرمیوم — با بات اصلی ارسال می‌شه (اونیه که صاحب پکه)
    sent = False
    for i in range(0, len(sample), 30):
        r = main_send(chat_id, "\n".join(sample[i:i + 30]))
        sent = sent or r.get("ok")
    if not sent:
        panel_send(chat_id, "ℹ️ برای دیدن پیام تست پرمیوم، اول به بات اصلی یه /start بده و دوباره بساز.")

    panel_send(chat_id, panel_text(), PANEL_KB)

# ─────────────────── هندل آپدیت‌ها ───────────────────
def handle_update(u):
    if "callback_query" in u:
        cq = u["callback_query"]
        uid = cq["from"]["id"]
        requests.post(f"{PANEL_API}/answerCallbackQuery",
                      json={"callback_query_id": cq["id"]}, timeout=30)
        if uid in ADMIN_IDS and cq.get("data") == "mkpack":
            states[uid] = {"step": "name"}
            panel_send(cq["message"]["chat"]["id"], MSG_NAME)
        return

    msg = u.get("message")
    if not msg or "text" not in msg:
        return
    uid, chat, text = msg["from"]["id"], msg["chat"]["id"], msg["text"].strip()

    if uid not in ADMIN_IDS:
        return

    if text in ("/start", "/panel", "/menu"):
        states.pop(uid, None)
        panel_send(chat, panel_text(), PANEL_KB)
        return
    if text == "/cancel":
        if states.pop(uid, None):
            panel_send(chat, "لغو شد ✅")
        return

    st = states.get(uid)
    if not st:
        panel_send(chat, panel_text(), PANEL_KB)
        return

    if st["step"] == "name":
        name = text
        if not re.fullmatch(r"[A-Za-z0-9_]{2,40}", name):
            panel_send(chat, "❌ اسم نامعتبره! فقط حروف انگلیسی، عدد و `_` — دوباره بفرست:")
            return
        st["short"], st["step"] = name, "source"
        panel_send(chat, MSG_SOURCE)
        return

    if st["step"] == "source":
        if not (re.search(r"addemoji|addstickers", text) or looks_like_ids(text)):
            panel_send(chat, "❌ فرمت درست نیست!\nیا لینک `t.me/addemoji/...` بفرست یا لیست آیدی‌ها.")
            return
        short = st["short"]
        states.pop(uid, None)
        prog = panel_send(chat, "⏳ شروع می‌کنم...")
        run_build(chat, prog["result"]["message_id"], short, text)

# ─────────────────── حلقه اصلی ───────────────────
if __name__ == "__main__":
    print(f"✅ پنل ایموجی روشن شد — پک‌ساز: @{BOT_USERNAME}")
    offset = 0
    while True:
        try:
            res = requests.get(f"{PANEL_API}/getUpdates", params={
                "offset": offset,
                "timeout": 50,
                "allowed_updates": json.dumps(["message", "callback_query"]),
            }, timeout=70).json()
            for u in res.get("result", []):
                offset = u["update_id"] + 1
                try:
                    handle_update(u)
                except Exception as e:
                    print("خطا در پردازش:", e)
        except Exception as e:
            print("خطای شبکه:", e)
