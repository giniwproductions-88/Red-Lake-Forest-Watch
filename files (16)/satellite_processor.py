"""
Red Lake Forest Watch - Satellite Data Processing
================================================

This script connects to Google Earth Engine to:
1. Pull Sentinel-2 imagery for Red Lake Reservation
2. Calculate NDVI (vegetation health)
3. Detect forest changes between image dates
4. Generate alerts for significant changes

Prerequisites:
- Google Earth Engine account (free): https://earthengine.google.com/
- Run: earthengine authenticate
- pip install earthengine-api geojson

Usage:
    python satellite_processor.py

"""

import ee
import json
from datetime import datetime, timedelta
from pathlib import Path

# ================================================
# CONFIGURATION
# ================================================

# Red Lake Reservation approximate bounding box
# TODO: Replace with actual boundary from DNR Avenza files
RED_LAKE_BOUNDS = {
    'west': -95.5,
    'south': 47.1,
    'east': -94.0,
    'north': 48.3
}

# Red Lake center point
RED_LAKE_CENTER = [47.88, -94.90]

# Change detection thresholds
NDVI_DECREASE_THRESHOLD = -0.15  # Significant vegetation loss
NDVI_INCREASE_THRESHOLD = 0.10   # Recovery detected
MIN_AREA_ACRES = 2               # Minimum area to report

# Output directory
OUTPUT_DIR = Path('./output')

# Default boundary file
DEFAULT_BOUNDARY = Path('./red_lake_boundary.geojson')


# ================================================
# INITIALIZE EARTH ENGINE
# ================================================

def initialize_ee():
    """Initialize Google Earth Engine connection."""
    try:
        ee.Initialize(project='red-lake-forest-watch')
        print("✓ Connected to Google Earth Engine")
        return True
    except Exception as e:
        print(f"✗ Earth Engine authentication required")
        print(f"  Run: earthengine authenticate")
        print(f"  Error: {e}")
        return False


# ================================================
# BOUNDARY LOADING
# ================================================

def load_reservation_boundary(geojson_path=None):
    """
    Load Red Lake Reservation boundary.
    
    Args:
        geojson_path: Path to GeoJSON file with boundary
                     If None, uses bounding box approximation
    
    Returns:
        ee.Geometry object
    """
    if geojson_path and Path(geojson_path).exists():
        with open(geojson_path) as f:
            geojson = json.load(f)
        return ee.Geometry(geojson['features'][0]['geometry'])
    else:
        # Use bounding box as fallback
        print("⚠ Using bounding box approximation - load actual boundary for accuracy")
        return ee.Geometry.Rectangle([
            RED_LAKE_BOUNDS['west'],
            RED_LAKE_BOUNDS['south'],
            RED_LAKE_BOUNDS['east'],
            RED_LAKE_BOUNDS['north']
        ])


# ================================================
# SENTINEL-2 DATA RETRIEVAL
# ================================================

def get_sentinel2_image(region, start_date, end_date, cloud_max=20):
    """
    Get cloud-free Sentinel-2 composite for a date range.
    
    Args:
        region: ee.Geometry defining area of interest
        start_date: Start date string 'YYYY-MM-DD'
        end_date: End date string 'YYYY-MM-DD'  
        cloud_max: Maximum cloud cover percentage
    
    Returns:
        ee.Image - median composite
    """
    collection = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
        .filterBounds(region)
        .filterDate(start_date, end_date)
        .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', cloud_max))
    )
    
    # Get image count
    count = collection.size().getInfo()
    print(f"  Found {count} Sentinel-2 images for {start_date} to {end_date}")
    
    if count == 0:
        return None
    
    # Return median composite (reduces cloud effects)
    return collection.median().clip(region)


def calculate_ndvi(image):
    """
    Calculate NDVI (Normalized Difference Vegetation Index).
    
    NDVI = (NIR - Red) / (NIR + Red)
    Range: -1 to 1 (higher = more vegetation)
    
    Args:
        image: Sentinel-2 ee.Image
    
    Returns:
        ee.Image with NDVI band
    """
    ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
    return ndvi


def calculate_nbr(image):
    """
    Calculate NBR (Normalized Burn Ratio) for fire/damage detection.
    
    NBR = (NIR - SWIR) / (NIR + SWIR)
    
    Args:
        image: Sentinel-2 ee.Image
    
    Returns:
        ee.Image with NBR band
    """
    nbr = image.normalizedDifference(['B8', 'B12']).rename('NBR')
    return nbr


# ================================================
# CHANGE DETECTION
# ================================================

def detect_changes(region, current_date=None, lookback_days=30):
    """
    Detect forest changes by comparing current imagery to baseline.
    
    Args:
        region: ee.Geometry defining area of interest
        current_date: Date to analyze (default: today)
        lookback_days: Days to look back for comparison
    
    Returns:
        dict with change analysis results
    """
    if current_date is None:
        current_date = datetime.now()
    elif isinstance(current_date, str):
        current_date = datetime.strptime(current_date, '%Y-%m-%d')
    
    # Date ranges
    current_start = (current_date - timedelta(days=15)).strftime('%Y-%m-%d')
    current_end = current_date.strftime('%Y-%m-%d')
    
    baseline_end = (current_date - timedelta(days=lookback_days)).strftime('%Y-%m-%d')
    baseline_start = (current_date - timedelta(days=lookback_days + 15)).strftime('%Y-%m-%d')
    
    print(f"\nAnalyzing changes:")
    print(f"  Baseline: {baseline_start} to {baseline_end}")
    print(f"  Current:  {current_start} to {current_end}")
    
    # Get images
    print("\nFetching baseline imagery...")
    baseline_image = get_sentinel2_image(region, baseline_start, baseline_end)
    
    print("Fetching current imagery...")
    current_image = get_sentinel2_image(region, current_start, current_end)
    
    if baseline_image is None or current_image is None:
        print("✗ Insufficient imagery available")
        return None
    
    # Calculate NDVI for both periods
    baseline_ndvi = calculate_ndvi(baseline_image)
    current_ndvi = calculate_ndvi(current_image)
    
    # Calculate change
    ndvi_change = current_ndvi.subtract(baseline_ndvi).rename('NDVI_change')
    
    # Identify significant decreases (potential damage)
    damage_mask = ndvi_change.lt(NDVI_DECREASE_THRESHOLD)
    
    # Identify recovery areas
    recovery_mask = ndvi_change.gt(NDVI_INCREASE_THRESHOLD)
    
    return {
        'baseline_ndvi': baseline_ndvi,
        'current_ndvi': current_ndvi,
        'ndvi_change': ndvi_change,
        'damage_mask': damage_mask,
        'recovery_mask': recovery_mask,
        'baseline_date': baseline_end,
        'current_date': current_end
    }


def extract_change_areas(change_results, region):
    """
    Extract discrete change areas as potential alerts.
    
    Args:
        change_results: Output from detect_changes()
        region: ee.Geometry
    
    Returns:
        list of alert dictionaries
    """
    alerts = []
    
    # Convert damage mask to vectors
    damage_vectors = change_results['damage_mask'].selfMask().reduceToVectors(
        geometry=region,
        scale=30,  # 30m resolution
        maxPixels=1e8,
        geometryType='polygon'
    )
    
    # Process each damage area
    damage_features = damage_vectors.getInfo()
    
    if damage_features and 'features' in damage_features:
        for i, feature in enumerate(damage_features['features']):
            # Calculate area
            geom = ee.Geometry(feature['geometry'])
            area_sqm = geom.area().getInfo()
            area_acres = area_sqm * 0.000247105
            
            if area_acres >= MIN_AREA_ACRES:
                # Get centroid for alert location
                centroid = geom.centroid().coordinates().getInfo()
                
                alerts.append({
                    'id': f"damage_{i+1}",
                    'type': 'vegetation_change',
                    'severity': 'high' if area_acres > 20 else 'medium',
                    'lat': centroid[1],
                    'lng': centroid[0],
                    'area_acres': round(area_acres, 1),
                    'date': change_results['current_date'],
                    'description': f"Significant vegetation loss detected ({round(area_acres, 1)} acres)"
                })
    
    # Process recovery areas similarly
    recovery_vectors = change_results['recovery_mask'].selfMask().reduceToVectors(
        geometry=region,
        scale=30,
        maxPixels=1e8,
        geometryType='polygon'
    )
    
    recovery_features = recovery_vectors.getInfo()
    
    if recovery_features and 'features' in recovery_features:
        for i, feature in enumerate(recovery_features['features']):
            geom = ee.Geometry(feature['geometry'])
            area_sqm = geom.area().getInfo()
            area_acres = area_sqm * 0.000247105
            
            if area_acres >= MIN_AREA_ACRES:
                centroid = geom.centroid().coordinates().getInfo()
                
                alerts.append({
                    'id': f"recovery_{i+1}",
                    'type': 'recovery',
                    'severity': 'positive',
                    'lat': centroid[1],
                    'lng': centroid[0],
                    'area_acres': round(area_acres, 1),
                    'date': change_results['current_date'],
                    'description': f"Vegetation recovery observed ({round(area_acres, 1)} acres)"
                })
    
    return alerts


# ================================================
# EXPORT FUNCTIONS
# ================================================

def export_alerts_json(alerts, output_path):
    """Export alerts to JSON file for web app consumption."""
    output = {
        'generated': datetime.now().isoformat(),
        'count': len(alerts),
        'alerts': alerts
    }
    
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"✓ Exported {len(alerts)} alerts to {output_path}")


def export_ndvi_tiles(ndvi_image, region, output_name):
    """
    Export NDVI as map tiles for visualization.
    
    Note: For production, you'd use Earth Engine's getMapId() 
    to generate tile URLs for direct use in Leaflet.
    """
    # Get tile URL for Leaflet
    vis_params = {
        'min': -0.2,
        'max': 0.8,
        'palette': ['red', 'yellow', 'green', 'darkgreen']
    }
    
    map_id = ndvi_image.getMapId(vis_params)
    tile_url = map_id['tile_fetcher'].url_format
    
    print(f"✓ NDVI tile URL: {tile_url}")
    return tile_url


# ================================================
# MAIN PROCESSING PIPELINE
# ================================================

def run_analysis(boundary_file=None):
    """
    Run full forest change analysis for Red Lake Reservation.
    
    Args:
        boundary_file: Path to GeoJSON with reservation boundary
    """
    print("=" * 50)
    print("RED LAKE FOREST WATCH - Satellite Analysis")
    print("=" * 50)
    
    # Initialize Earth Engine
    if not initialize_ee():
        return
    
    # Load boundary
    print("\nLoading reservation boundary...")
    region = load_reservation_boundary(boundary_file)
    
    # Run change detection
    print("\nRunning change detection...")
    changes = detect_changes(region)
    
    if changes is None:
        print("Analysis failed - check imagery availability")
        return
    
    # Extract alerts
    print("\nExtracting change areas...")
    alerts = extract_change_areas(changes, region)
    
    print(f"\n✓ Found {len(alerts)} significant changes")
    
    # Create output directory
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    # Export results
    export_alerts_json(alerts, OUTPUT_DIR / 'alerts.json')
    
    # Print summary
    print("\n" + "=" * 50)
    print("ANALYSIS COMPLETE")
    print("=" * 50)
    
    high_priority = [a for a in alerts if a['severity'] == 'high']
    medium_priority = [a for a in alerts if a['severity'] == 'medium']
    recovery = [a for a in alerts if a['severity'] == 'positive']
    
    print(f"  🔴 High priority:   {len(high_priority)}")
    print(f"  🟡 Medium priority: {len(medium_priority)}")
    print(f"  🟢 Recovery areas:  {len(recovery)}")
    
    if alerts:
        print("\nTop alerts:")
        for alert in sorted(alerts, key=lambda x: x['area_acres'], reverse=True)[:5]:
            print(f"  • {alert['type']}: {alert['area_acres']} acres at ({alert['lat']:.4f}, {alert['lng']:.4f})")
    
    return alerts


# ================================================
# SCHEDULED PROCESSING
# ================================================

def schedule_regular_analysis():
    """
    Set up regular analysis runs.
    
    In production, this would be triggered by:
    - Cron job
    - AWS Lambda
    - Google Cloud Functions
    
    Sentinel-2 revisit time is ~5 days, so run every 5-7 days.
    """
    print("For scheduled runs, set up a cron job:")
    print("  0 6 */5 * * python satellite_processor.py")
    print("  (Runs every 5 days at 6 AM)")


# ================================================
# ENTRY POINT
# ================================================

if __name__ == '__main__':
    import sys
    
    # Check for boundary file argument
    boundary_file = sys.argv[1] if len(sys.argv) > 1 else None
    
    if boundary_file:
        print(f"Using boundary file: {boundary_file}")
    else:
        print("No boundary file provided - using bounding box approximation")
        print("Usage: python satellite_processor.py [boundary.geojson]")
    
    # Run analysis
    alerts = run_analysis(boundary_file)
