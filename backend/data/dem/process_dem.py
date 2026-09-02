import math
from pathlib import Path
import numpy as np

# Project Grid Parameters (From developer_assignments.md)
GRID_ROWS = 200
GRID_COLS = 200
CELL_SIZE_M = 10.0
ORIGIN_LAT = 19.0600   # SW corner
ORIGIN_LON = 72.8500   # SW corner

def process_dem_rasters(dem_dir: str):
    dem_path = Path(dem_dir)
    hydro_dem_file = dem_path / "raw" / "Hydro_Conditioned_DEM.tif"
    if not hydro_dem_file.exists():
        hydro_dem_file = dem_path / "raw" / "output_be.tif"

    try:
        import rasterio
        from rasterio.enums import Resampling
        
        with rasterio.open(hydro_dem_file) as src:
            # Resample to exactly 200x200 grid
            data = src.read(
                1,
                out_shape=(GRID_ROWS, GRID_COLS),
                resampling=Resampling.bilinear
            ).astype(np.float32)
            
            # Replace NoData/invalid values if any with minimum valid elevation
            valid_mask = (data > -100) & (data < 1000)
            if not np.all(valid_mask):
                min_valid = np.nanmin(data[valid_mask]) if np.any(valid_mask) else 5.0
                data[~valid_mask] = min_valid
                
            elevation_grid = data
            print(f"Loaded DEM via rasterio. Shape: {elevation_grid.shape}, Min: {elevation_grid.min():.2f}m, Max: {elevation_grid.max():.2f}m")

    except ImportError:
        # Fallback using PIL / pure numpy if rasterio is not installed
        from PIL import Image
        im = Image.open(hydro_dem_file)
        im_resized = im.resize((GRID_COLS, GRID_ROWS), Image.BILINEAR)
        elevation_grid = np.array(im_resized, dtype=np.float32)
        print(f"Loaded DEM via PIL. Shape: {elevation_grid.shape}, Min: {elevation_grid.min():.2f}m, Max: {elevation_grid.max():.2f}m")

    # 1. Save standard 200x200 elevation grid
    elev_out = dem_path / "elevation_grid.npy"
    np.save(elev_out, elevation_grid)
    print(f" -> Saved {elev_out}")

    # 2. Generate Imperviousness grid (Urban core ~0.85, higher slopes ~0.60, water/lowlands ~0.20)
    # Normalize elevation to scale imperviousness realistically
    elev_norm = (elevation_grid - elevation_grid.min()) / (elevation_grid.max() - elevation_grid.min() + 1e-5)
    imperviousness = 0.85 - (0.35 * elev_norm)  # High density built-up in flat lowlands
    imperviousness = np.clip(imperviousness, 0.20, 0.95).astype(np.float32)
    
    imp_out = dem_path / "imperviousness.npy"
    np.save(imp_out, imperviousness)
    print(f" -> Saved {imp_out}")

    # 3. Generate Infiltration grid (mm/hr): base_rate * (1 - imperviousness)
    base_infiltration_rate = 10.0 # mm/hr for typical urban soil
    infiltration = base_infiltration_rate * (1.0 - imperviousness)
    
    inf_out = dem_path / "infiltration.npy"
    np.save(inf_out, infiltration)
    print(f" -> Saved {inf_out}")

if __name__ == "__main__":
    process_dem_rasters("backend/data/dem")
