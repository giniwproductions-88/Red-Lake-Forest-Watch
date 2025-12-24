# Red Lake Forest Watch

Satellite-based forest monitoring for Red Lake Nation.

## Quick Start

### 1. View the App Now
Just open `index.html` in a browser. The map works immediately with demo alerts.

### 2. Deploy to Web (Optional)
Drop the `index.html` file into:
- **Vercel**: Drag folder to vercel.com/new
- **Netlify**: Drag folder to app.netlify.com/drop
- **GitHub Pages**: Push to repo, enable Pages

### 3. Connect Real Satellite Data

#### Get Google Earth Engine Access
1. Go to https://earthengine.google.com/
2. Click "Sign Up" (free for research/nonprofit)
3. Wait for approval (usually same day)
4. Run: `earthengine authenticate`

#### Install Dependencies
```bash
pip install earthengine-api geojson
```

#### Get Red Lake Boundary
Option A: Download from Red Lake DNR (Avenza files)
- https://www.redlakednr.org/gps/
- Convert PDF to GeoJSON using QGIS or geojson.io

Option B: Census TIGER data
- https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html
- Select "American Indian Area Geography"
- Find "Red Lake Reservation"

#### Run Analysis
```bash
python satellite_processor.py boundary.geojson
```

This generates `output/alerts.json` with real change detection alerts.

## File Structure

```
red-lake-forest-watch/
├── index.html              # Web app (works standalone)
├── satellite_processor.py  # Python script for satellite data
├── README.md              # This file
└── output/
    └── alerts.json        # Generated alerts (after running processor)
```

## How It Works

### Satellite Data
- **Source**: Sentinel-2 (European Space Agency)
- **Resolution**: 10 meters
- **Frequency**: Every 5 days
- **Cost**: Free

### Change Detection
1. Pull imagery from two time periods (current vs 30 days ago)
2. Calculate NDVI (vegetation health index)
3. Compare: where did NDVI drop significantly?
4. Flag areas with >15% vegetation loss
5. Generate alerts with coordinates and area estimates

### Alert Types
- 🌪️ **Storm Damage**: Sudden canopy loss
- 🌿 **Vegetation Stress**: Gradual decline (drought, disease, pests)
- 🪓 **Clearing**: Possible unauthorized activity
- 🌱 **Recovery**: Regrowth in previously damaged areas

## Customization

### Change Detection Sensitivity
In `satellite_processor.py`:
```python
NDVI_DECREASE_THRESHOLD = -0.15  # More negative = less sensitive
MIN_AREA_ACRES = 2               # Minimum area to report
```

### Add Real Boundary
In `index.html`, find the TODO comment and load your GeoJSON:
```javascript
fetch('boundary.geojson')
  .then(r => r.json())
  .then(geojson => {
    L.geoJSON(geojson, {
      style: {
        color: '#4d8a5d',
        weight: 2,
        dashArray: '8,4',
        fillOpacity: 0.1
      }
    }).addTo(map);
  });
```

## Next Steps

1. [ ] Get GEE access approved
2. [ ] Download actual Red Lake boundary
3. [ ] Run first real analysis
4. [ ] Show to Red Lake DNR contacts
5. [ ] Set up automated weekly runs
6. [ ] Add email/SMS alerts

## Resources

- **Red Lake DNR**: https://www.redlakednr.org/
- **Google Earth Engine**: https://earthengine.google.com/
- **Sentinel Hub**: https://www.sentinel-hub.com/
- **National Indian Carbon Coalition**: Contact Bryan Van Stippen at bvanstippen@iltf.org

## Contact

Built for Miskwaagamiiwi-zaaga'igan (Red Lake Nation)

---

*Prototype v0.2 - December 2024*
