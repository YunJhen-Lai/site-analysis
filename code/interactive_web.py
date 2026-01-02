import pandas as pd
import numpy as np
import folium
import requests
import json
from math import radians, cos, sin, asin, sqrt

# --- 1. 設定資料路徑 ---
JSON_PATH = r"C:\DCCG_Final_Project\site-analysis\data\merged_data\intercity_routes.json"

# --- 2. 載入景點與人次資料（從 merged_data/tourist_spot.json） ---
SPOTS_PATH = r"C:\DCCG_Final_Project\site-analysis\data\merged_data\tourist_spot.json"
ROAD_PATH = r"C:\DCCG_Final_Project\site-analysis\data\taichung_road.json"

# 解析像「965萬7875人次」這種字串為整數
def parse_visit_count(s):
    s = str(s).replace('人次', '').strip()
    if '萬' in s:
        parts = s.split('萬')
        wan = int(''.join(filter(str.isdigit, parts[0]))) if parts[0] else 0
        rest = int(''.join(filter(str.isdigit, parts[1]))) if len(parts) > 1 and any(ch.isdigit() for ch in parts[1]) else 0
        return wan * 10000 + rest
    # 若沒有萬，直接取數字
    digits = ''.join(filter(str.isdigit, s))
    return int(digits) if digits else 0

# 提前定義 haversine 供後續使用（距離單位：公里）
def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dLat, dLon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dLat / 2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dLon / 2)**2
    return 2 * R * asin(sqrt(a))

# 讀取景點 JSON
spots_data = []
try:
    with open(SPOTS_PATH, 'r', encoding='utf-8') as f:
        spots_json = json.load(f)
        for sp in spots_json:
            name = sp.get('spotname') or sp.get('ScenicSpotName') or sp.get('name')
            pc = sp.get('VisitCount', 0)
            visitors = parse_visit_count(pc)
            pos = sp.get('Position', {})
            lat = pos.get('PositionLat') or pos.get('lat')
            lon = pos.get('PositionLon') or pos.get('lon')
            spots_data.append({
                'name': name,
                'visitors': visitors,
                'lat': float(lat) if lat else None,
                'lon': float(lon) if lon else None,
                'is_line': False
            })
    print(f"載入景點共 {len(spots_data)} 筆資料（自 {SPOTS_PATH}）。")
except Exception as e:
    print(f"讀取景點資料失敗（{e}），嘗試使用備援檔案 site-analysis/data/tourism_spot.json ...")
    alt_path = r"C:\DCCG_Final_Project\site-analysis\data\tourism_spot.json"
    try:
        with open(alt_path, 'r', encoding='utf-8') as f:
            spots_json = json.load(f)
            spots_data = []
            for sp in spots_json:
                name = sp.get('spotname') or sp.get('ScenicSpotName') or sp.get('name')
                pc = sp.get('VisitCount', 0)
                visitors = parse_visit_count(pc)
                pos = sp.get('Position', {})
                lat = pos.get('PositionLat') or pos.get('lat')
                lon = pos.get('PositionLon') or pos.get('lon')
                spots_data.append({
                    'name': name,
                    'visitors': visitors,
                    'lat': float(lat) if lat else None,
                    'lon': float(lon) if lon else None,
                    'is_line': False
                })
        print(f"備援檔案載入成功，共 {len(spots_data)} 筆。")
    except Exception as e2:
        print(f"備援檔案也讀取失敗（{e2}），改用內建清單。")
        spots_data = [
            {"name": "公益路商圈", "visitors": 9657875, "lat": 24.151120, "lon": 120.650820, "is_line": True},
            {"name": "一中商圈", "visitors": 4330135, "lat": 24.148700, "lon": 120.685320, "is_line": False}
        ]

# 標記哪些景點需用整條路來判斷（可擴充）
LINE_SPOTS = {"公益路商圈"}

# 由道路資料找到與景點相關的路段，回傳組合後的座標線條
def parse_linestring(geom):
    geom = geom.replace('LINESTRING(', '').rstrip(')')
    pts = []
    for part in geom.split(','):
        lon_str, lat_str = part.strip().split()
        pts.append((float(lat_str), float(lon_str)))
    return pts

# 讀取道路形狀並為需要的景點找出附近路段
try:
    with open(ROAD_PATH, 'r', encoding='utf-8') as f:
        road_json = json.load(f)
        sections = road_json.get('SectionShapes', [])
        section_coords = [parse_linestring(s.get('Geometry', '')) for s in sections]
except Exception as e:
    print(f"讀取道路資料失敗: {e}")
    section_coords = []

# 尋找與景點相關的路段（以點到頂點距離小於 threshold 的路段視為相關）
for spot in spots_data:
    if spot['name'] in LINE_SPOTS and section_coords:
        threshold_km = 1.0  # 距離容許值，可調整
        matched = []
        for coords in section_coords:
            if any(haversine(spot['lat'], spot['lon'], p[0], p[1]) <= threshold_km for p in coords):
                # append in original point order
                for p in coords:
                    if p not in matched:
                        matched.append(p)
        if matched:
            spot['is_line'] = True
            spot['line_coords'] = matched
            print(f"已為 '{spot['name']}' 找到 {len(matched)} 個路段頂點組成的線段。")
        else:
            print(f"未找到與 '{spot['name']}' 關聯的路段，將以單點作為中心。")

# --- 3. 讀取並清洗資料 ---
print("正在讀取公車路線 JSON 資料...（展開並擷取站點）")
try:
    with open(JSON_PATH, 'r', encoding='utf-8') as f:
        routes_json = json.load(f)

    rows = []
    for r in routes_json:
        # 取得可讀的路線名稱
        route_name = r.get('SubRouteName', {}).get('Zh_tw') or r.get('RouteName', {}).get('Zh_tw') or r.get('RouteUID')
        direction = r.get('Direction')
        stops = r.get('Stops', []) or r.get('Stop', [])
        for s in stops:
            seq = s.get('StopSequence')
            stop_name = s.get('StopName', {}).get('Zh_tw') if isinstance(s.get('StopName'), dict) else s.get('StopName')
            pos = s.get('StopPosition') or {}
            lat = pos.get('PositionLat') or pos.get('positionlat')
            lon = pos.get('PositionLon') or pos.get('positionlon')
            rows.append({
                'RouteDisplay': route_name,
                'Direction': direction,
                'StopSequence': seq,
                'StopName': stop_name,
                'lat': lat,
                'lon': lon
            })

    df_itcroute = pd.DataFrame(rows)

    # 確保為數值格式
    df_itcroute['lat'] = pd.to_numeric(df_itcroute['lat'], errors='coerce')
    df_itcroute['lon'] = pd.to_numeric(df_itcroute['lon'], errors='coerce')
    df_itcroute = df_itcroute.dropna(subset=['lat', 'lon'])

    # 預篩選：只保留台中大致範圍，加速運算
    df_itcroute = df_itcroute[
        (df_itcroute['lat'].between(24.0, 24.5)) & 
        (df_itcroute['lon'].between(120.4, 120.9))
    ]
    print(f"資料讀取成功，共 {len(df_itcroute)} 個站點點位（展開後）。")
except Exception as e:
    print(f"讀取錯誤: {e}")
    exit()

# --- 4. 工具函數 ---
def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dLat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dLat / 2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2)**2
    return 2 * R * asin(sqrt(a))

def dist_to_line(p_lat, p_lon, line_coords):
    return min([haversine(p_lat, p_lon, l[0], l[1]) for l in line_coords])

def get_route_path(coords):
    loc_string = ";".join([f"{lon},{lat}" for lat, lon in coords])
    url = f"http://router.project-osrm.org/route/v1/driving/{loc_string}?overview=full&geometries=geojson"
    try:
        r = requests.get(url, timeout=5)
        res = r.json()
        if res.get('code') == 'Ok':
            route_geometry = res['routes'][0]['geometry']['coordinates']
            return [[lat, lon] for lon, lat in route_geometry]
    except: pass
    return coords

# 人氣比例尺映射（濾掉無效座標與人次的景點）
valid_spots = [s for s in spots_data if s['lat'] is not None and s['lon'] is not None and s['visitors'] > 0]
print(f"景點資料檢查: 總共 {len(spots_data)} 筆，有效 {len(valid_spots)} 筆")
for s in spots_data[:5]:
    print(f"  - {s['name']}: lat={s['lat']}, lon={s['lon']}, visitors={s['visitors']}")

if valid_spots:
    v_min, v_max = min(s['visitors'] for s in valid_spots), max(s['visitors'] for s in valid_spots)
    def remap_radius(v):
        if v_max == v_min:
            return 600  # 若所有人次相同，回傳中間半徑
        return 300 + (v - v_min) * 900 / (v_max - v_min) # 半徑 300m 到 1200m
else:
    print("警告：沒有有效的景點資料！")
    def remap_radius(v):
        return 600  # fallback

# --- 5. 初始化地圖 ---
# 計算景點的中心點
if valid_spots:
    center_lat = sum(s['lat'] for s in valid_spots) / len(valid_spots)
    center_lon = sum(s['lon'] for s in valid_spots) / len(valid_spots)
    m = folium.Map(location=[center_lat, center_lon], zoom_start=12, tiles="Cartodb dark_matter")
    print(f"地圖中心座標: {center_lat}, {center_lon}")
else:
    m = folium.Map(location=[24.16, 120.66], zoom_start=13, tiles="Cartodb dark_matter")
    print("無效景點，使用預設座標")

pink_palette = ['#FFC0CB', '#FFB6C1', '#FF69B4', '#FF1493', '#F48FB1', '#F06292', '#F8BBD0']

# --- 6. 核心繪圖邏輯 ---
for spot in valid_spots:
    print(f"正在處理: {spot['name']} ({spot['visitors']} 人次)...")
    fg = folium.FeatureGroup(name=f"{spot['name']} ({spot['visitors']//10000}萬人)")
    
    # 標示景點核心
    folium.CircleMarker(
        location=[spot['lat'], spot['lon']], radius=10,
        color='yellow', fill=True, fill_opacity=1,
        tooltip=f"<b>{spot['name']}</b>"
    ).add_to(fg)
    
    # 繪製人氣範圍圓 (黃色虛線)
    folium.Circle(
        location=[spot['lat'], spot['lon']], radius=remap_radius(spot['visitors']),
        color='yellow', weight=1.5, fill=True, fill_opacity=0.08, dash_array='8, 8'
    ).add_to(fg)

    # 篩選 1km 直徑 (半徑 0.5km) 內的路線
    def check_near(group):
        for _, row in group.iterrows():
            if spot.get('is_line'):
                line_coords = spot.get('line_coords', [])
                if not line_coords:
                    # 若沒有找到線段資訊，退回到以點為中心判斷
                    d = haversine(spot['lat'], spot['lon'], row['lat'], row['lon'])
                else:
                    d = dist_to_line(row['lat'], row['lon'], line_coords)
            else:
                d = haversine(spot['lat'], spot['lon'], row['lat'], row['lon'])
            if d <= 0.5:
                return True
        return False

    relevant_groups = [g for _, g in df_itcroute.groupby(['RouteDisplay', 'Direction']) if check_near(g)]

    for g in relevant_groups:
        g_sorted = g.sort_values('StopSequence')
        route_name = g_sorted['RouteDisplay'].iloc[0]
        color = pink_palette[hash(str(route_name)) % len(pink_palette)]
        
        stop_coords = list(zip(g_sorted['lat'], g_sorted['lon']))
        if len(stop_coords) >= 2:
            road_path = get_route_path(stop_coords)
            folium.PolyLine(
                locations=road_path, color=color, weight=3, opacity=0.7,
                popup=f"路線: {route_name}"
            ).add_to(fg)
            
            for _, r in g_sorted.iterrows():
                folium.CircleMarker(
                    location=(r['lat'], r['lon']), radius=2.5,
                    color='white', fill=True, fill_color=color, fill_opacity=1,
                    tooltip=r.get('StopName')
                ).add_to(fg)

    fg.add_to(m)

folium.LayerControl(collapsed=False).add_to(m)
m.save('taichung_site_analysis.html')
print("分析完成！請查看 taichung_site_analysis.html")