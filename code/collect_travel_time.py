#!/usr/bin/env python3
"""
Collect bus travel time data from TDX API for all routes in Taichung.

Usage:
  python collect_travel_time.py --app-id <id> --app-key <key>
  python collect_travel_time.py  # Uses TDX_APP_ID, TDX_APP_KEY env vars
"""
import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Dict

import requests
import pandas as pd

# Import the TDXAuth class from auth_TDX
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'data', 'TDX'))
from auth_TDX import TDXAuth


class TaichungBusTravelTimeCollector:
    """Collect and parse bus travel time data from TDX API."""

    BASE_URL = "https://tdx.transportdata.tw/api/basic/v2/Bus/S2STravelTime/City/Taichung"

    def __init__(self, auth: TDXAuth):
        self.auth = auth
        self.data = []

    def fetch_travel_times(self, route_id: str = None) -> List[dict]:
        """
        Fetch travel time data. If route_id is None, fetch all routes.
        If route_id is provided, fetch specific route.
        """
        url = self.BASE_URL if route_id is None else f"{self.BASE_URL}/Route/{route_id}"
        
        try:
            headers = self.auth.get_data_header()
            print(f"Fetching: {url}")
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                # Sometimes wrapped in object; extract if there's data key
                return data.get('data', [data])
            return []
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return []

    def collect_all(self) -> List[dict]:
        """Fetch travel times for all routes."""
        print("Fetching all travel times...")
        self.data = self.fetch_travel_times()
        print(f"Collected {len(self.data)} travel time records")
        return self.data

    def to_json(self, out_path: str):
        """Save raw data as JSON."""
        p = Path(out_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open('w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
        print(f"Wrote JSON: {p}")

    def to_csv(self, out_path: str):
        """Convert to flat CSV with travel time segments."""
        if not self.data:
            print("No data to convert")
            return

        rows = []
        for record in self.data:
            route_id = record.get('RouteID')
            route_name_zh = (record.get('RouteName') or {}).get('Zh_tw')
            route_name_en = (record.get('RouteName') or {}).get('En')
            direction = record.get('Direction')
            operator_code = record.get('OperatorCode')
            
            # Each record may have travel time segments between stops
            segments = record.get('TravelTimes', [])
            if not segments:
                # If no segments, still record the route
                rows.append({
                    'RouteID': route_id,
                    'RouteName_Zh': route_name_zh,
                    'RouteName_En': route_name_en,
                    'Direction': direction,
                    'OperatorCode': operator_code,
                    'FromStopID': None,
                    'ToStopID': None,
                    'TravelTime': None,
                    'Distance': None,
                })
            else:
                for seg in segments:
                    rows.append({
                        'RouteID': route_id,
                        'RouteName_Zh': route_name_zh,
                        'RouteName_En': route_name_en,
                        'Direction': direction,
                        'OperatorCode': operator_code,
                        'FromStopID': seg.get('FromStopID'),
                        'ToStopID': seg.get('ToStopID'),
                        'TravelTime': seg.get('TravelTime'),
                        'Distance': seg.get('Distance'),
                    })

        df = pd.DataFrame(rows)
        p = Path(out_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(p, index=False, encoding='utf-8-sig')
        print(f"Wrote CSV: {p} ({len(df)} rows)")


def main():
    parser = argparse.ArgumentParser(description="Collect bus travel time data from TDX API")
    parser.add_argument('--app-id', help='TDX App ID (or set TDX_APP_ID env var)')
    parser.add_argument('--app-key', help='TDX App Key (or set TDX_APP_KEY env var)')
    parser.add_argument('--out-json', default='data/travel_times.json', help='Output JSON file')
    parser.add_argument('--out-csv', default='data/travel_times.csv', help='Output CSV file')
    parser.add_argument('--format', choices=['json', 'csv', 'both'], default='both', help='Output format')
    args = parser.parse_args()

    # Get credentials from args or env
    app_id = args.app_id or os.getenv('TDX_APP_ID')
    app_key = args.app_key or os.getenv('TDX_APP_KEY')

    if not app_id or not app_key:
        print("Error: Must provide --app-id and --app-key or set TDX_APP_ID and TDX_APP_KEY env vars")
        sys.exit(1)

    try:
        print("Authenticating with TDX...")
        auth = TDXAuth(app_id, app_key)
        auth.authenticate()
        print("✓ Authentication successful")

        collector = TaichungBusTravelTimeCollector(auth)
        collector.collect_all()

        if args.format in ('json', 'both'):
            collector.to_json(args.out_json)
        if args.format in ('csv', 'both'):
            collector.to_csv(args.out_csv)

        print("✓ Collection complete")

    except Exception as e:
        print(f"✗ Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
