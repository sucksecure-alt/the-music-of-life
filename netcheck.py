"""Диагностика: какие узлы достижимы с твоей сети. Запуск: python3 netcheck.py"""
import json, os, socket, time
import urllib.request
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

def probe(cam, t=4):
    url = cam["url"]
    p = urlparse(url)
    host = p.hostname
    port = p.port or (443 if p.scheme == "https" else 80)
    tcp = False
    try:
        s = socket.create_connection((host, port), timeout=t)
        s.close()
        tcp = True
    except Exception:
        pass
    stream = False
    if tcp:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            r = urllib.request.urlopen(req, timeout=t)
            data = r.read(300000)
            stream = b"\xff\xd8" in data
            try: r.close()
            except Exception: pass
        except Exception:
            pass
    return cam["city"], cam["name"], tcp, stream

def main():
    cfg = os.path.join(os.path.dirname(os.path.abspath(__file__)), "camera_sources.json")
    cams = json.load(open(cfg, encoding="utf-8")).get("cameras", [])
    print(f"проверяю {len(cams)} узлов... (vpn: проверь оба режима)\n")
    online = 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(probe, c): c for c in cams}
        for f in as_completed(futs):
            city, name, tcp, stream = f.result()
            mark = "ONLINE" if stream else ("tcp-only" if tcp else "DEAD")
            if stream: online += 1
            print(f"  [{mark:7s}] {city} — {name}")
    print(f"\nитого живых: {online}/{len(cams)}")
    if online == 0:
        print("сеть не пускает ни к одному узлу: переключи vpn (вкл/выкл) и повтори.")

if __name__ == "__main__":
    main()