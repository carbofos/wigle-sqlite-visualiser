#!/usr/bin/env python
# coding: utf-8

"""
WiGLE WiFi Network Visualizer
Reads WiFi network data from SQLite database and creates an interactive map
"""

# SQLite database file name
DB_FILE = 'db/italy_networks.sqlite'


import pandas as pd    # Read data from Wigle Wifi Capture
import folium          # Mapping Library
import sqlite3         # SQLite database connection
import os
import sys
import re
import json
import webbrowser     # For opening browser automatically
import time           # For adding delay before opening browser

# Configuration
HTML_OUTPUT_FILE = 'mapdata.html'


def clean_text_for_js(text):
    """Clean text to be safe for JavaScript strings"""
    if text is None:
        return ""
    
    # Convert to string and clean
    text = str(text)
    
    # Remove or replace problematic characters
    text = text.replace("'", "\\'")
    text = text.replace('"', '\\"')
    text = text.replace('\n', ' ')
    text = text.replace('\r', ' ')
    text = text.replace('\t', ' ')
    
    # Remove any other control characters
    text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)
    
    # Limit length to prevent issues
    if len(text) > 100:
        text = text[:97] + "..."
    
    return text.strip()


def load_data_from_sqlite(db_path):
    """Load WiFi network data from SQLite database"""
    try:
        conn = sqlite3.connect(db_path)
        df = pd.read_sql_query("""
            SELECT 
                bssid as MAC,
                ssid as SSID,
                capabilities as AuthMode,
                lasttime as FirstSeen,
                frequency as Channel,
                bestlevel as RSSI,
                lastlat as CurrentLatitude,
                lastlon as CurrentLongitude,
                0 as AltitudeMeters,
                0 as AccuracyMeters,
                type as Type
            FROM network
            WHERE type = 'W'
        """, conn)
        conn.close()
        return df
    except Exception as e:
        print(f"Error loading data from SQLite: {e}")
        return None


def filter_valid_networks(df):
    """Filter and clean WiFi network data"""
    valid = []
    for rows in df[['MAC', 'SSID', 'AuthMode', 'FirstSeen', 'Channel', 'RSSI', 'CurrentLatitude', 'CurrentLongitude', 'AltitudeMeters', 'AccuracyMeters', 'Type']].values:
        if (rows[10] == 'W'):
            valid.append(rows)
    
    # Clean Set by dropping all NA values
    validframes = pd.DataFrame(valid).dropna()
    validframes.columns = ['MAC', 'SSID', 'AuthMode', 'FirstSeen', 'Channel', 'RSSI', 'CurrentLatitude', 'CurrentLongitude', 'AltitudeMeters', 'AccuracyMeters', 'Type']
    
    return validframes


def save_data_to_json(validframes, json_file='wifi_data.json'):
    """Save WiFi data to JSON file for asynchronous loading"""
    print(f"Saving {len(validframes)} WiFi networks to {json_file}...")
    
    wifi_data = []
    for _, row in validframes.iterrows():
        if ("?" not in str(row['CurrentLatitude'])) and ("?" not in str(row['CurrentLongitude'])):
            wifi_data.append({
                'lat': float(row['CurrentLatitude']),
                'lon': float(row['CurrentLongitude']),
                'ssid': clean_text_for_js(row['SSID']),
                'mac': clean_text_for_js(row['MAC']),
                'rssi': int(row['RSSI']) if pd.notna(row['RSSI']) else 0,
                'channel': int(row['Channel']) if pd.notna(row['Channel']) else 0,
                'auth': clean_text_for_js(row['AuthMode']) if pd.notna(row['AuthMode']) else ''
            })
    
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(wifi_data, f, ensure_ascii=False, indent=2)
    
    print(f"Saved {len(wifi_data)} WiFi networks to {json_file}")
    return len(wifi_data)


def create_lightweight_map(validframes, output_file=HTML_OUTPUT_FILE, json_file='wifi_data.json'):
    """Create lightweight HTML map with asynchronous data loading and marker virtualization"""
    # Compute Average of all the latitudes and longitudes in our dataset to find center and set zoom
    center_lat = validframes.CurrentLatitude.mean()
    center_lon = validframes.CurrentLongitude.mean()
    
    # Create basic map
    mymap = folium.Map(location=[center_lat, center_lon], zoom_start=17)
    
    # Add a simple marker to show the map is working
    folium.Marker(
        location=[center_lat, center_lon],
        tooltip="Map Center",
        popup="WiFi Network Map<br>Loading data...",
        icon=folium.Icon(color='blue', prefix='fa', icon='info')
    ).add_to(mymap)
    
    # Save basic map
    mymap.save(output_file)
    
    # Create enhanced HTML with custom JavaScript for async loading and marker virtualization
    enhanced_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WiFi Network Visualizer</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/leaflet@1.9.3/dist/leaflet.css"/>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@6.2.0/css/all.min.css"/>
    <style>
        #map {{
            height: 100vh;
            width: 100%;
        }}
        .loading {{
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: rgba(255, 255, 255, 0.9);
            padding: 20px;
            border-radius: 10px;
            z-index: 1000;
            text-align: center;
        }}
        .progress {{
            width: 300px;
            height: 20px;
            background: #f0f0f0;
            border-radius: 10px;
            overflow: hidden;
            margin: 10px 0;
        }}
        .progress-bar {{
            height: 100%;
            background: #4CAF50;
            width: 0%;
            transition: width 0.3s;
        }}
        .stats {{
            position: absolute;
            top: 10px;
            right: 10px;
            background: rgba(255, 255, 255, 0.9);
            padding: 10px;
            border-radius: 5px;
            font-size: 12px;
            z-index: 1000;
        }}
    </style>
</head>
<body>
    <div id="map"></div>
    <div class="loading" id="loading">
        <h3>Loading WiFi Networks...</h3>
        <div class="progress">
            <div class="progress-bar" id="progress-bar"></div>
        </div>
        <div id="progress-text">0 / 0 networks loaded</div>
    </div>
    <div class="stats" id="stats">
        <div>Total: <span id="total-count">0</span></div>
        <div>Visible: <span id="visible-count">0</span></div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/leaflet@1.9.3/dist/leaflet.js"></script>
    <script>
        // Global variables
        var map = null;
        var allData = [];
        var visibleMarkers = [];
        var markerCache = new Map();
        var isDataLoaded = false;
        
        // Initialize map
        function initMap() {{
            map = L.map('map').setView([{center_lat}, {center_lon}], 17);
            
            L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                attribution: '© OpenStreetMap contributors'
            }}).addTo(map);
            
            // Add event listeners for map movement
            map.on('moveend', updateVisibleMarkers);
            map.on('zoomend', updateVisibleMarkers);
        }}
        
        // Create marker with caching
        function createMarker(network) {{
            const key = `${{network.lat}},${{network.lon}},${{network.mac}}`;
            
            if (markerCache.has(key)) {{
                return markerCache.get(key);
            }}
            
            const popupContent = `
                <div style="font-family: Arial, sans-serif; font-size: 12px;">
                    <strong>SSID:</strong> ${{network.ssid}}<br>
                    <strong>BSSID:</strong> ${{network.mac}}<br>
                    <strong>RSSI:</strong> ${{network.rssi}} dBm<br>
                    <strong>Channel:</strong> ${{network.channel}}<br>
                    <strong>Auth:</strong> ${{network.auth}}
                </div>
            `;
            
            const marker = L.marker([network.lat, network.lon], {{
                icon: L.divIcon({{
                    className: 'custom-div-icon',
                    html: '<i class="fa fa-wifi" style="color: red; font-size: 16px;"></i>',
                    iconSize: [16, 16],
                    iconAnchor: [8, 8]
                }})
            }})
            .bindTooltip(network.ssid)
            .bindPopup(popupContent);
            
            markerCache.set(key, marker);
            return marker;
        }}
        
        // Update visible markers based on current map bounds
        function updateVisibleMarkers() {{
            if (!isDataLoaded || !map) return;
            
            const bounds = map.getBounds();
            const newVisibleMarkers = [];
            
            // Find markers within current bounds
            for (const network of allData) {{
                if (bounds.contains([network.lat, network.lon])) {{
                    newVisibleMarkers.push(network);
                }}
            }}
            
            // Remove markers that are no longer visible
            for (const marker of visibleMarkers) {{
                if (marker && marker.remove) {{
                    marker.remove();
                }}
            }}
            
            // Add new visible markers
            visibleMarkers = [];
            for (const network of newVisibleMarkers) {{
                const marker = createMarker(network);
                marker.addTo(map);
                visibleMarkers.push(marker);
            }}
            
            // Update stats
            document.getElementById('total-count').textContent = allData.length;
            document.getElementById('visible-count').textContent = visibleMarkers.length;
        }}
        
        // Load data asynchronously
        function loadData() {{
            fetch('{json_file}')
                .then(response => response.json())
                .then(data => {{
                    allData = data;
                    isDataLoaded = true;
                    
                    document.getElementById('total-count').textContent = data.length;
                    document.getElementById('progress-text').textContent = `${{data.length}} networks loaded`;
                    document.getElementById('progress-bar').style.width = '100%';
                    
                    // Hide loading screen
                    setTimeout(() => {{
                        document.getElementById('loading').style.display = 'none';
                    }}, 1000);
                    
                    // Show initial markers
                    updateVisibleMarkers();
                }})
                .catch(error => {{
                    console.error('Error loading data:', error);
                    document.getElementById('loading').innerHTML = '<h3>Error loading data</h3><p>Please check the console for details.</p>';
                }});
        }}
        
        // Initialize everything
        initMap();
        loadData();
    </script>
</body>
</html>
"""
    
    # Save enhanced HTML
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(enhanced_html)
    
    print(f"Lightweight map with marker virtualization saved to {output_file}")
    return output_file


def create_map(validframes, output_file=HTML_OUTPUT_FILE):
    """Create interactive map with WiFi network markers (legacy method)"""
    # Compute Average of all the latitudes and longitudes in our dataset to find center and set zoom
    center_lat = validframes.CurrentLatitude.mean()
    center_lon = validframes.CurrentLongitude.mean()
    
    mymap = folium.Map(location=[center_lat, center_lon], zoom_start=17)
    
    # Add WiFi network markers
    for coord in validframes[['CurrentLatitude','CurrentLongitude', 'SSID', 'Type', 'MAC']].values:
        if ("?" not in str(coord[0])) and ("?" not in str(coord[1])):
            # Clean the text data
            ssid = clean_text_for_js(coord[2])
            mac = clean_text_for_js(coord[4])
            
            # Create safe popup content
            popup_content = f"""
            <div style="font-family: Arial, sans-serif; font-size: 12px;">
                <strong>SSID:</strong> {ssid}<br>
                <strong>BSSID:</strong> {mac}
            </div>
            """
            
            folium.Marker(
                location=[coord[0], coord[1]],
                tooltip=ssid,
                popup=folium.Popup(popup_content, max_width=300),
                icon=folium.Icon(color='red', prefix='fa', icon='wifi')
            ).add_to(mymap)
    
    # Save map to HTML file
    mymap.save(output_file)
    print(f"Map saved to {output_file}")
    
    return mymap


def main():
    """Main function to run the WiFi network visualizer"""
    print("Starting WiFi Network Visualizer...")
    db_path = DB_FILE
    
    print(f"Database path: {db_path}")
    
    # Check if database file exists
    if not os.path.exists(db_path):
        print(f"Error: Database file not found at {db_path}")
        sys.exit(1)
    
    print("Database file found!")
    print("Loading WiFi network data from SQLite database...")
    
    # Load data from SQLite
    df = load_data_from_sqlite(db_path)
    if df is None:
        print("Failed to load data from database")
        sys.exit(1)
    
    print(f"Loaded {len(df)} network records")
    print("Sample data:")
    print(df.sample(5))
    
    # Filter valid networks
    print("\nFiltering valid WiFi networks...")
    validframes = filter_valid_networks(df)
    print(f"Found {len(validframes)} valid WiFi networks")
    print("Sample filtered data:")
    print(validframes.head())
    
    # Save data to JSON for lightweight map
    print("\nCreating lightweight map with JSON data...")
    json_file = 'wifi_data.json'
    num_networks = save_data_to_json(validframes, json_file)
    
    # Create lightweight map
    create_lightweight_map(validframes, HTML_OUTPUT_FILE, json_file)
    
    print(f"\nWiFi Network Visualization completed!")
    print(f"Created {num_networks} WiFi network markers")
    print("Files created:")
    print(f"  - {json_file} (WiFi data)")
    print(f"  - {HTML_OUTPUT_FILE} (Lightweight map)")

if __name__ == "__main__":
    main()

