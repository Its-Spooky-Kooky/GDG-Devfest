"""Fake driver: walks a route and posts to /location, same shape as a real tracker.

Usage:
  python simulate.py --url https://YOUR-SERVICE.run.app/location --token SECRET
  python simulate.py --url http://localhost:8080/location --speedup 4
  python simulate.py --url ... --polyline "<encoded polyline from Routes API>"
"""
import argparse
import math
import time
from urllib.parse import urlparse
import requests

# Default stops around Chennai (approximate). Straight lines between them.
DEFAULT = [
    (13.0067, 80.2570),  # Adyar
    (13.0067, 80.2206),  # Guindy
    (13.0418, 80.2341),  # T. Nagar
    (13.0569, 80.2425),  # Thousand Lights / Greams Rd
    (13.0850, 80.2101)   # Anna Nagar
]


def haversine(a, b):
    R = 6371000
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp, dl = p2 - p1, math.radians(b[1] - a[1])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def decode_polyline(s):
    pts, i, lat, lng = [], 0, 0, 0
    while i < len(s):
        for is_lat in (True, False):
            shift = result = 0
            while True:
                b = ord(s[i]) - 63
                i += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break
            d = ~(result >> 1) if result & 1 else result >> 1
            if is_lat:
                lat += d
            else:
                lng += d
        pts.append((lat / 1e5, lng / 1e5))
    return pts


def densify(points, step_m):
    if not points:
        return []
    out = [points[0]]
    for a, b in zip(points, points[1:]):
        dist = haversine(a, b)
        n = max(1, int(dist // step_m))
        for k in range(1, n + 1):
            t = k / n
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    return out


def fetch_live_route_from_server(location_url):
    """Attempts to fetch current route points from backend /api/route."""
    try:
        parsed = urlparse(location_url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        res = requests.get(f"{base}/api/route", timeout=3)
        if res.status_code == 200:
            data = res.json()
            pts = data.get("points", [])
            if len(pts) >= 2:
                print(f"[simulate] Loaded live route ({len(pts)} stops) from server {base}/api/route")
                return [(float(p[0]), float(p[1])) for p in pts]
    except Exception as e:
        pass
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8080/location")
    ap.add_argument("--token")
    ap.add_argument("--id", default="sim-1")
    ap.add_argument("--speed-kmh", type=float, default=45.0)
    ap.add_argument("--interval", type=float, default=1.5, help="seconds between posts")
    ap.add_argument("--speedup", type=float, default=3.0, help="multiplies distance per tick")
    ap.add_argument("--polyline")
    a = ap.parse_args()

    if a.polyline:
        route = decode_polyline(a.polyline)
    else:
        live_pts = fetch_live_route_from_server(a.url)
        route = live_pts if live_pts else DEFAULT

    step_m = (a.speed_kmh / 3.6) * a.interval * a.speedup
    path = densify(route, step_m)
    params = {"token": a.token} if a.token else {}

    print(f"--- GPS Driver Simulator Started ---")
    print(f"Vehicle: {a.id} | Target URL: {a.url}")
    print(f"Path contains {len(path)} waypoints, ~{step_m:.0f} m/tick at interval {a.interval}s (speedup={a.speedup}x)")
    print("Press Ctrl+C to stop simulation.\n")

    for i, (lat, lon) in enumerate(path):
        body = dict(
            id=a.id,
            lat=lat,
            lon=lon,
            timestamp=int(time.time()),
            speed=a.speed_kmh,
            accuracy=4.5
        )
        try:
            r = requests.post(a.url, json=body, params=params, timeout=10)
            status_text = f"HTTP {r.status_code}"
            print(f"[{i+1}/{len(path)}] Waypoint ({lat:.5f}, {lon:.5f}) -> {status_text}")
        except requests.RequestException as e:
            print(f"[{i+1}/{len(path)}] Post failed: {e}")
        time.sleep(a.interval)

    print("\n[simulate] Route completed! Vehicle has arrived at final destination.")


if __name__ == "__main__":
    main()
