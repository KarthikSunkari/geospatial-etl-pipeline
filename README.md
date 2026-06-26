# Geospatial ETL Pipeline: Urban Housing Permit & Affordability Aggregator

An end-to-end geospatial data engineering pipeline that ingests raw, unstructured building permit records, processes spatial coordinate data, aligns geographic boundaries, and computes multi-tiered affordability metrics aggregated by 2020 US Census Tracts.

This pipeline was engineered to process tabular historical records from the California Department of Housing and Community Development (HCD) Annual Progress Report (APR) datasets and maps them precisely onto federal geographic boundaries.

## 🚀 Core Engineering Capabilities

* **Spatial Point Vectorization:** Dynamically parses and cleans tabular coordinate vectors (`lat_lng` strings), handling malformed/missing records, and transforms them into standard geometric vector layers using `gpd.points_from_xy`.
* **CRS Synchronization & Geometric Analysis:** Projects regional spatial boundary shapefiles into a unified global coordinate system (`EPSG:4326`). Programmatically computes geometric centroids (`geometry.centroid`) for polygonal tract definitions.
* **Optimized Spatial Indexing (Joins):** Utilizes spatial indexing predicates (`gpd.sjoin` with an `inner`/`within` match) to mathematically locate point-source construction events inside multi-vertex geographical census boundaries.
* **Multi-Dimensional Relational Aggregation:** Executes granular conditional groupings over dynamic time windows to slice building permits into 17 target attributes—segmenting production by housing categories (Single-Family, Multi-Family, Accessory Dwelling Units [ADUs]) and Area Median Income (AMI) affordability tiers.

## 📊 Pipeline Architecture & Data Flow

1. **Extraction:** Loads raw polygon shapefile inputs (`TIGER/Line®`) alongside historical multi-year structural permit registries.
2. **Transformation:** 
   * Normalizes strings, isolates 6-digit federal tract keys, and forces strict coordinate system overrides.
   * Extracts absolute `Latitude` and `Longitude` values to instantiate vector point geometries.
   * Performs an indexed spatial join to bind every permit point directly to its parent census tract boundary.
3. **Aggregation & Load:** Groupings are run across a multi-year iteration stack, auto-filling spatial voids with zero-allocations to preserve statistical continuity, before persisting schema-compliant historical CSV targets.

## 🛠️ Tech Stack & Dependencies

* **Language:** Python
* **Geospatial Processing:** GeoPandas, Shapely (via GEOS)
* **Data Analytics:** Pandas, NumPy
* **Visualization:** Matplotlib
