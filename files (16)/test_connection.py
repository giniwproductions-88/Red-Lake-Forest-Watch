"""
Test script to verify Earth Engine connection and pull first data
Run: python test_connection.py
"""

import ee
import json
from datetime import datetime, timedelta

def test_connection():
    print("=" * 50)
    print("RED LAKE FOREST WATCH - Connection Test")
    print("=" * 50)
    
    # Initialize Earth Engine
    print("\n1. Testing Earth Engine connection...")
    try:
        ee.Initialize(project='red-lake-forest-watch')
        print("   ✓ Connected to Earth Engine")
    except Exception as e:
        print(f"   ✗ Connection failed: {e}")
        print("\n   Try running: python -c \"import ee; ee.Authenticate()\"")
        return False
    
    # Test Sentinel-2 access
    print("\n2. Testing Sentinel-2 data access...")
    try:
        # Red Lake area bounding box
        red_lake = ee.Geometry.Rectangle([-95.35, 47.58, -94.38, 48.17])
        
        # Get recent imagery
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        
        collection = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
            .filterBounds(red_lake)
            .filterDate(start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 30)))
        
        count = collection.size().getInfo()
        print(f"   ✓ Found {count} Sentinel-2 images in last 30 days")
        
        if count > 0:
            # Get the most recent image date
            latest = collection.sort('system:time_start', False).first()
            date = datetime.fromtimestamp(latest.get('system:time_start').getInfo() / 1000)
            print(f"   ✓ Most recent image: {date.strftime('%Y-%m-%d')}")
    except Exception as e:
        print(f"   ✗ Sentinel-2 access failed: {e}")
        return False
    
    # Test boundary file
    print("\n3. Testing boundary file...")
    try:
        with open('red_lake_boundary.geojson', 'r') as f:
            boundary = json.load(f)
        feature_count = len(boundary['features'])
        print(f"   ✓ Loaded boundary file with {feature_count} features")
    except FileNotFoundError:
        print("   ⚠ Boundary file not found (red_lake_boundary.geojson)")
        print("   The app will work but won't show the reservation boundary")
    except Exception as e:
        print(f"   ✗ Error loading boundary: {e}")
    
    # Test NDVI calculation
    print("\n4. Testing NDVI calculation...")
    try:
        if count > 0:
            image = collection.median()
            ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
            
            # Get mean NDVI for the area
            mean_ndvi = ndvi.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=red_lake,
                scale=100,
                maxPixels=1e9
            ).getInfo()
            
            print(f"   ✓ Mean NDVI for Red Lake area: {mean_ndvi['NDVI']:.3f}")
            
            if mean_ndvi['NDVI'] > 0.3:
                print("   ✓ Healthy vegetation detected (NDVI > 0.3)")
            else:
                print("   ⚠ Low vegetation signal - may be winter/snow cover")
    except Exception as e:
        print(f"   ✗ NDVI calculation failed: {e}")
        return False
    
    print("\n" + "=" * 50)
    print("ALL TESTS PASSED - Ready to run full analysis")
    print("=" * 50)
    print("\nNext steps:")
    print("  1. Open index.html in a browser to see the app")
    print("  2. Run: python satellite_processor.py")
    print("     to generate real forest change alerts")
    
    return True

if __name__ == '__main__':
    test_connection()
