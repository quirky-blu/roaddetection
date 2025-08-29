from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import json
import os

app = FastAPI(title="GeoJSON Roads with Bounding Box Filter", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load all features from split files at startup
geojson_files = [
    "resources/split/indore_roads_part1.geojson",
    "resources/split/indore_roads_part2.geojson", 
    "resources/split/indore_roads_part3.geojson",
    "resources/split/indore_roads_part4.geojson",
    "resources/split/indore_roads_part5.geojson",  # Fixed: part5 before part6
    "resources/split/indore_roads_part6.geojson"   # Fixed: part6 at end
]

all_features = []

# Load all features at startup
def load_all_features():
    global all_features
    all_features = []
    
    for file_path in geojson_files:
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding='utf-8') as f:
                    data = json.load(f)
                    features = data.get("features", [])
                    all_features.extend(features)
                    print(f"✅ Loaded {len(features)} features from {file_path}")
            except Exception as e:
                print(f"❌ Error loading {file_path}: {e}")
        else:
            print(f"⚠️ Warning: {file_path} not found")
    
    print(f"📊 Total features loaded: {len(all_features)}")

# Load features on startup
load_all_features()

@app.get("/geojson")
def get_geojson(
    north: float = Query(..., description="Northern boundary latitude"),
    south: float = Query(..., description="Southern boundary latitude"), 
    east: float = Query(..., description="Eastern boundary longitude"),
    west: float = Query(..., description="Western boundary longitude")
):
    """Get roads within specified bounding box"""
    
    filtered = []
    
    for feature in all_features:
        try:
            geometry = feature.get("geometry", {})
            coords = geometry.get("coordinates", [])
            geom_type = geometry.get("type", "")
            
            # Handle different geometry types
            lngs = []
            lats = []
            
            if geom_type == "LineString":
                lngs = [c[0] for c in coords]
                lats = [c[1] for c in coords]
            elif geom_type == "MultiLineString":
                for line in coords:
                    lngs.extend([c[0] for c in line])
                    lats.extend([c[1] for c in line])
            elif geom_type == "Polygon":
                # Take exterior ring
                if coords and len(coords) > 0:  # Added safety check
                    lngs = [c[0] for c in coords[0]]
                    lats = [c[1] for c in coords[0]]
                else:
                    continue
            else:
                continue
            
            # Skip if no coordinates found
            if not lngs or not lats:
                continue
            
            # Check if feature intersects with bounding box
            feature_north = max(lats)
            feature_south = min(lats)
            feature_east = max(lngs)
            feature_west = min(lngs)
            
            # Bounding box intersection check
            if (
                feature_south <= north and feature_north >= south and
                feature_west <= east and feature_east >= west
            ):
                filtered.append(feature)
                
        except Exception as e:
            # Skip invalid features
            continue
    
    return JSONResponse({
        "type": "FeatureCollection",
        "features": filtered,
        "metadata": {
            "total_in_bbox": len(filtered),
            "total_searched": len(all_features),  # Added for debugging
            "bbox": {
                "north": north,
                "south": south, 
                "east": east,
                "west": west
            }
        }
    })

@app.get("/geojson/all")
def get_all_geojson():
    """Get all roads without filtering"""
    return JSONResponse({
        "type": "FeatureCollection", 
        "features": all_features,
        "metadata": {
            "total_features": len(all_features)
        }
    })

@app.get("/reload")
def reload_features():
    """Reload all features from files"""
    load_all_features()
    return {
        "status": "reloaded",
        "total_features": len(all_features),
        "files_attempted": len(geojson_files),
        "files_loaded": len([f for f in geojson_files if os.path.exists(f)])
    }

@app.get("/stats")
def get_stats():
    """Get statistics about loaded features"""
    color_counts = {"red": 0, "blue": 0, "yellow": 0, "green": 0, "unknown": 0}
    
    for feature in all_features:
        color = feature.get("properties", {}).get("color", "unknown")
        if color in color_counts:
            color_counts[color] += 1
        else:
            color_counts["unknown"] += 1
    
    return {
        "total_features": len(all_features),
        "color_distribution": color_counts,
        "files_configured": len(geojson_files),
        "files_loaded": len([f for f in geojson_files if os.path.exists(f)])
    }

@app.get("/health")
def health():
    """Health check"""
    files_available = len([f for f in geojson_files if os.path.exists(f)])
    
    return {
        "status": "healthy" if files_available > 0 else "error",
        "features_loaded": len(all_features),
        "files_available": files_available,
        "files_configured": len(geojson_files)
    }

@app.get("/")
def root():
    """Root endpoint with API information"""
    return {
        "message": "GeoJSON Roads API with Bounding Box Filter",
        "version": "1.0.0",
        "endpoints": {
            "/geojson": "Filter roads by bounding box",
            "/geojson/all": "Get all roads",
            "/stats": "Get color statistics",
            "/health": "Health check",
            "/reload": "Reload data files"
        },
        "files_status": {
            "configured": len(geojson_files),
            "available": len([f for f in geojson_files if os.path.exists(f)]),
            "features_loaded": len(all_features)
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
