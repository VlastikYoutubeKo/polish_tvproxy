import requests
import re
import sys
import base64
import json
import os
from datetime import datetime
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from flask import Flask, Response, request, stream_with_context
from werkzeug.middleware.proxy_fix import ProxyFix

# --- NASTAVENÍ ---
HOST_ADDRESS = "0.0.0.0"
PORT = 8080
CHANNELS_JSON_URL = "https://telewizjada.cc/kanal/channels.json"
BASE_SITE_URL = "https://telewizjada.cc/"
FALLBACK_EMBED_URL_TEMPLATE = "https://tvdarmowa.cc/embed/{slug}/" # Šablona pro automatickou zálohu
CACHE_FILE = "working_sources_cache.json"

# --- PŘEKLADY (cs, en, pl) ---
TRANSLATIONS = {
    'cs': { 'page_title': "📺 Telka Proxy - Seznam kanálů", 'header_title': "Telka Proxy", 'header_subtitle': "Streamování televizních kanálů přes proxy server", 'search_placeholder': "Vyhledat kanál...", 'export_button': "Export M3U", 'stats_title': "Dostupné kanály", 'meta_sources': "zdrojů", 'error_loading': "Chyba: Nepodařilo se načíst seznam kanálů.", 'no_results': "Žádné kanály neodpovídají vašemu vyhledávání." },
    'en': { 'page_title': "📺 Telka Proxy - Channel List", 'header_title': "Telka Proxy", 'header_subtitle': "Streaming TV channels through a proxy server", 'search_placeholder': "Search for a channel...", 'export_button': "Export M3U", 'stats_title': "Available Channels", 'meta_sources': "sources", 'error_loading': "Error: Failed to load the channel list.", 'no_results': "No channels match your search." },
    'pl': { 'page_title': "📺 Telka Proxy - Lista kanałów", 'header_title': "Telka Proxy", 'header_subtitle': "Przesyłanie strumieniowe kanałów telewizyjnych przez serwer proxy", 'search_placeholder': "Wyszukaj kanał...", 'export_button': "Eksport M3U", 'stats_title': "Dostępne kanały", 'meta_sources': "źródeł", 'error_loading': "Błąd: Nie udało się załadować listy kanałów.", 'no_results': "Brak kanałów pasujących do wyszukiwania." }
}

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

WORKING_SOURCE_CACHE = {}
CACHED_CHANNELS = None

# Všechny pomocné funkce (load_cache, atd.) zůstávají stejné...
def load_cache():
    global WORKING_SOURCE_CACHE
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                WORKING_SOURCE_CACHE = json.load(f)
            print(f"✅ Načtena cache z {CACHE_FILE} - {len(WORKING_SOURCE_CACHE)} záznamů")
    except (json.JSONDecodeError, IOError): WORKING_SOURCE_CACHE = {}

def save_cache():
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(WORKING_SOURCE_CACHE, f, ensure_ascii=False, indent=2)
        print(f"💾 Cache uložena do {CACHE_FILE}")
    except IOError: pass

def update_cache(channel_id, source_index, channel_name):
    WORKING_SOURCE_CACHE[str(channel_id)] = { "source_index": source_index, "last_used": datetime.now().isoformat(), "channel_name": channel_name }
    save_cache()

def fetch_channels():
    global CACHED_CHANNELS
    print("Stahuji seznam dostupných kanálů...")
    try:
        resp = requests.get(CHANNELS_JSON_URL, timeout=10)
        resp.raise_for_status()
        CACHED_CHANNELS = resp.json()
        print(f"✅ Načteno {len(CACHED_CHANNELS)} kanálů.")
        return True
    except (requests.exceptions.RequestException, requests.exceptions.JSONDecodeError) as e:
        print(f"❌ Chyba při stahování nebo zpracování seznamu kanálů: {e}", file=sys.stderr)
        return False

def find_stream_url(page_url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0', 'Referer': BASE_SITE_URL}
        resp = requests.get(page_url, headers=headers, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        scripts = soup.find_all('script')
        for script in scripts:
            if script.string and ('new Clappr.Player' in script.string or 'player.source' in script.string):
                match = re.search(r'source\s*:\s*"(.*?)"', script.string)
                if match: return match.group(1)
        return None
    except requests.exceptions.RequestException:
        return None

def validate_stream(stream_url, referer_url):
    try:
        headers = {"User-Agent": "Mozilla/5.0", "Referer": referer_url}
        playlist_resp = requests.get(stream_url, headers=headers, timeout=5)
        playlist_resp.raise_for_status()
        first_segment_url = None
        for line in playlist_resp.text.splitlines():
            line = line.strip()
            if line and not line.startswith('#'):
                first_segment_url = urljoin(stream_url, line)
                break
        if not first_segment_url: return False
        segment_resp = requests.head(first_segment_url, headers=headers, timeout=5)
        segment_resp.raise_for_status()
        return True
    except requests.exceptions.RequestException:
        return False

def get_locale():
    return request.accept_languages.best_match(['cs', 'pl', 'en']) or 'en'

@app.route("/")
def index():
    if not CACHED_CHANNELS: fetch_channels()
    lang = get_locale()
    t = TRANSLATIONS.get(lang, TRANSLATIONS['en'])
    html = f"""
    <!DOCTYPE html><html lang="{lang}"><head><meta charset="UTF-8"><title>{t['page_title']}</title><link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet"><style>*{'{'}margin:0;padding:0;box-sizing:border-box{'}'}body{'{'}font-family:'Segoe UI',sans-serif;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);min-height:100vh;color:#333{'}'}.container{'{'}max-width:1200px;margin:0 auto;padding:20px{'}'}.header{'{'}text-align:center;margin-bottom:40px;color:white{'}'}.header h1{'{'}font-size:3rem;text-shadow:2px 2px 4px rgba(0,0,0,0.3){'}'}.header p{'{'}font-size:1.2rem;opacity:0.9{'}'}.controls{'{'}display:flex;justify-content:space-between;align-items:center;margin-bottom:30px;flex-wrap:wrap;gap:15px{'}'}.search-box{'{'}flex:1;min-width:300px{'}'}.search-input{'{'}width:100%;padding:12px 20px;padding-left:45px;border:none;border-radius:25px;font-size:16px;background:rgba(255,255,255,0.95);box-shadow:0 8px 32px rgba(0,0,0,0.1){'}'}.search-input:focus{'{'}outline:none;box-shadow:0 8px 32px rgba(0,0,0,0.2);transform:translateY(-2px){'}'}.search-icon{'{'}position:absolute;left:15px;top:50%;transform:translateY(-50%);color:#666{'}'}.search-container{'{'}position:relative{'}'}.export-btn{'{'}background:linear-gradient(45deg,#ff6b6b,#ee5a24);color:white;border:none;padding:12px 25px;border-radius:25px;font-size:16px;font-weight:600;cursor:pointer;text-decoration:none;display:inline-flex;align-items:center;gap:8px;box-shadow:0 8px 32px rgba(0,0,0,0.1){'}'}.export-btn:hover{'{'}transform:translateY(-2px);box-shadow:0 12px 40px rgba(0,0,0,0.2){'}'}.channels-grid{'{'}display:grid;grid-template-columns:repeat(auto-fill,minmax(350px,1fr));gap:20px{'}'}.channel-card{'{'}background:rgba(255,255,255,0.95);backdrop-filter:blur(10px);border-radius:20px;overflow:hidden;box-shadow:0 8px 32px rgba(0,0,0,0.1);border:1px solid rgba(255,255,255,0.2){'}'}.channel-card:hover{'{'}transform:translateY(-5px);box-shadow:0 20px 40px rgba(0,0,0,0.2){'}'}.channel-link{'{'}display:flex;align-items:center;padding:20px;text-decoration:none;color:#333{'}'}.channel-logo{'{'}width:60px;height:45px;object-fit:contain;background:#2c3e50;border-radius:10px;padding:5px;margin-right:20px{'}'}.channel-name{'{'}font-size:1.1rem;font-weight:600;color:#2c3e50{'}'}.channel-meta{'{'}font-size:0.9rem;color:#7f8c8d{'}'}.play-icon{'{'}color:#667eea;font-size:1.5rem;margin-left:auto{'}'}.stats{'{'}text-align:center;margin:30px 0;color:white{'}'}.error-message{'{'}text-align:center;padding:40px;background:rgba(255,255,255,0.95);border-radius:20px;color:#e74c3c{'}'}.no-results{'{'}text-align:center;padding:40px;color:white;opacity:0.8{'}'}</style></head>
    <body><div class="container"><div class="header"><h1><i class="fas fa-tv"></i> {t['header_title']}</h1><p>{t['header_subtitle']}</p></div><div class="controls"><div class="search-box"><div class="search-container"><i class="fas fa-search search-icon"></i><input type="text" class="search-input" id="searchInput" placeholder="{t['search_placeholder']}"></div></div><a href="/export.m3u" class="export-btn"><i class="fas fa-download"></i> {t['export_button']}</a></div>
    """
    if not CACHED_CHANNELS: html += f'<div class="error-message"><i class="fas fa-exclamation-triangle"></i> {t["error_loading"]}</div>'
    else:
        sources_known_count = sum(1 for ch in CACHED_CHANNELS if ch.get('sources'))
        html += f"""<div class="stats"><h3>{t['stats_title']}</h3><div>{sources_known_count} / {len(CACHED_CHANNELS)}</div></div><div class="channels-grid" id="channelsGrid">"""
        for i, channel in enumerate(CACHED_CHANNELS):
            link, logo_url, channel_name, sources_count = f'/play/{i}', urljoin(BASE_SITE_URL, channel.get('logo','')), channel.get("name"), len(channel.get('sources',[]))
            html += f"""<div class="channel-card" data-name="{channel_name.lower()}"><a href="{link}" target="_blank" class="channel-link"><img class="channel-logo" src="{logo_url}" alt="Logo" onerror="this.style.display='none'"><div class="channel-info"><div class="channel-name">{channel_name}</div><div class="channel-meta">{sources_count} {t['meta_sources']}</div></div><i class="fas fa-play play-icon"></i></a></div>"""
        html += f"""</div><div class="no-results" id="noResults" style="display:none;"><p>{t['no_results']}</p></div>"""
    html += """</div><script>document.getElementById('searchInput').addEventListener('input',function(e){'{'}const t=e.target.value.toLowerCase(),c=document.querySelectorAll('.channel-card');let n=0;c.forEach(e=>{'{'}e.dataset.name.includes(t)?(e.style.display='block',n++):e.style.display='none'{'}'}),document.getElementById('noResults').style.display=0===n&&""!==t?"block":"none"{'}'})</script></body></html>"""
    return html

@app.route("/export.m3u")
def export_m3u():
    if not CACHED_CHANNELS: fetch_channels()
    if not CACHED_CHANNELS: return "Chyba: Nepodařilo se načíst seznam kanálů.", 500
    server_url = f"{request.scheme}://{request.host}"
    m3u_content = "#EXTM3U\n"
    for i, channel in enumerate(CACHED_CHANNELS):
        channel_name, logo_url, category = channel.get("name"), urljoin(BASE_SITE_URL, channel.get('logo','')), channel.get('category','Různé')
        m3u_content += f'#EXTINF:-1 tvg-name="{channel_name}" tvg-logo="{logo_url}" group-title="{category}",{channel_name}\n'
        m3u_content += f'{server_url}/play/{i}\n\n'
    response = Response(m3u_content, mimetype='audio/x-mpegurl')
    response.headers['Content-Disposition'] = 'attachment; filename="telka_proxy_playlist.m3u"'
    print(f"📁 Vygenerován M3U playlist s {len(CACHED_CHANNELS)} kanály pro doménu {request.host}")
    return response

@app.route("/play/<int:channel_id>")
def play_channel(channel_id):
    if not CACHED_CHANNELS or channel_id >= len(CACHED_CHANNELS): return "Chyba: Kanál nenalezen.", 404
    channel = CACHED_CHANNELS[channel_id]
    channel_name = channel.get('name', 'Neznámý kanál')
    sources_to_try = list(channel.get('sources', []))

    # --- NOVÁ AUTOMATICKÁ LOGIKA ---
    # Pokud v JSONu nejsou žádné zdroje, zkusíme je vygenerovat z loga
    if not sources_to_try:
        print(f"  -> Pro kanál '{channel_name}' nebyly v JSON nalezeny žádné zdroje. Zkouším automatickou zálohu.")
        logo_path = channel.get('logo')
        if logo_path and logo_path.endswith('.png'):
            try:
                # Získáme slug z cesty k logu (např. /logo/eskatvextra.png -> eskatvextra)
                slug = logo_path.split('/')[-1].replace('.png', '')
                fallback_url = FALLBACK_EMBED_URL_TEMPLATE.format(slug=slug)
                fallback_source = {'name': 'Automatická záloha (tvdarmowa.cc)', 'url': fallback_url}
                sources_to_try.append(fallback_source)
                print(f"    - Vygenerován záložní zdroj: {fallback_url}")
            except Exception:
                print(f"    - Logo path '{logo_path}' má nečekaný formát, nelze vygenerovat zálohu.")
    
    if not sources_to_try: return f"Chyba: Kanál '{channel_name}' nemá definované žádné zdroje a nelze vytvořit zálohu.", 500

    print(f"\nProhledávám zdroje pro kanál '{channel_name}'...")
    upstream_m3u8_url, working_embed_url = None, None
    cache_key = str(channel_id)
    if cache_key in WORKING_SOURCE_CACHE:
        cache_entry = WORKING_SOURCE_CACHE[cache_key]
        cached_index = cache_entry["source_index"]
        if cached_index < len(sources_to_try):
            source = sources_to_try[cached_index]
            source_name = source.get('name', f'Zdroj #{cached_index + 1}')
            print(f"  -> Zkouším prioritně zdroj z cache: '{source_name}'...")
            embed_page_url = urljoin(BASE_SITE_URL, source['url'])
            found_url = find_stream_url(embed_page_url)
            if found_url and validate_stream(found_url, embed_page_url):
                print("    ✅ Zdroj z cache je stále platný!")
                upstream_m3u8_url, working_embed_url = found_url, embed_page_url
                update_cache(channel_id, cached_index, channel['name'])
            else:
                print("    ❌ Zdroj z cache selhal. Prohledávám všechny zdroje.")
                if cache_key in WORKING_SOURCE_CACHE: del WORKING_SOURCE_CACHE[cache_key]
    
    if not upstream_m3u8_url:
        for i, source in enumerate(sources_to_try):
            source_name = source.get('name', f'Zdroj #{i+1}')
            print(f"  -> Zkouším zdroj: {source_name}...")
            embed_page_url = urljoin(BASE_SITE_URL, source['url'])
            found_url = find_stream_url(embed_page_url)
            if found_url:
                print(f"    - Nalezen potenciální stream. Ověřuji funkčnost...")
                if validate_stream(found_url, embed_page_url):
                    print(f"    ✅ Stream je platný! Používám tento zdroj.")
                    upstream_m3u8_url, working_embed_url = found_url, embed_page_url
                    update_cache(channel_id, i, channel['name'])
                    break
                else:
                    print(f"    ❌ Stream se nepodařilo ověřit.")
            print(f"    -> Tento zdroj selhal.")

    if not upstream_m3u8_url: return f"Chyba: Pro kanál '{channel_name}' se nepodařilo najít funkční stream.", 500
    resp = requests.get(upstream_m3u8_url, headers={"Referer": working_embed_url})
    encoded_referer = base64.urlsafe_b64encode(working_embed_url.encode()).decode()
    rewritten_content = []
    for line in resp.text.splitlines():
        line = line.strip()
        if line and not line.startswith('#'):
            full_segment_url = urljoin(upstream_m3u8_url, line)
            encoded_segment_url = base64.urlsafe_b64encode(full_segment_url.encode()).decode()
            rewritten_content.append(f"/stream/{encoded_segment_url}/{encoded_referer}")
        else:
            rewritten_content.append(line)
    return Response("\n".join(rewritten_content), mimetype='application/vnd.apple.mpegurl')

@app.route("/stream/<encoded_segment_url>/<encoded_referer>")
def stream_segment(encoded_segment_url, encoded_referer):
    try:
        segment_url = base64.urlsafe_b64decode(encoded_segment_url).decode()
        referer_url = base64.urlsafe_b64decode(encoded_referer).decode()
        headers = {"Referer": referer_url,"User-Agent": "Mozilla/5.0"}
        req = requests.get(segment_url, headers=headers, stream=True, timeout=5)
        return Response(stream_with_context(req.iter_content(chunk_size=8192)), content_type=req.headers.get('content-type'))
    except Exception as e:
        print(f"\n❌ Chyba při streamování segmentu: {e}", file=sys.stderr)
        return Response(status=500)

if __name__ == '__main__':
    load_cache()
    fetch_channels()
    print("\n" + "="*50)
    print("=== Webový server pro streamy je spuštěn! ===")
    print(f"Otevři v prohlížeči adresu: http://{HOST_ADDRESS}:{PORT}")
    print("="*50 + "\n")
    try:
        app.run(host=HOST_ADDRESS, port=PORT)
    except KeyboardInterrupt:
        print(f"\n🔄 Server ukončen.")
        save_cache()