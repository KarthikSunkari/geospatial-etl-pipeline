# Geospatial ETL Pipeline: Urban Housing & Economic Spatial Aggregator

**Author:** Karthik Sunkari

## 📌 Overview
An end-to-end geospatial data engineering pipeline that ingests raw, unstructured building permit records, processes spatial coordinate data, aligns geographic boundaries, and computes multi-tiered affordability metrics aggregated by 2020 US Census Tracts.

This pipeline was engineered to process tabular historical records from the California Department of Housing and Community Development (HCD) Annual Progress Report (APR) datasets and map them precisely onto federal geographic boundaries.

## 🌍 Core Geospatial Capabilities

* **Geometric Point Vectorization:** Dynamically parses and cleans tabular coordinate vectors (`lat_lng` strings), handling malformed/missing records, and transforms them into standard geometric vector layers using `gpd.points_from_xy`.
* **CRS Synchronization & Geometric Analysis:** Projects regional spatial boundary shapefiles into a unified global coordinate system (`EPSG:4326`). Programmatically computes geometric centroids (`geometry.centroid`) for polygonal tract definitions.
* **Optimized Spatial Indexing (Joins):** Utilizes spatial indexing predicates (`gpd.sjoin` with an `inner`/`within` match) to mathematically locate point-source construction events inside multi-vertex geographical census boundaries.
* **Multi-Dimensional Relational Aggregation:** Executes granular conditional groupings over dynamic time windows to slice building permits into 17 target attributes—segmenting production by housing categories and Area Median Income (AMI) affordability tiers.

## 🗂️ Repository Architecture

```
geospatial-etl-pipeline/
├── docs/                                  # Data dictionaries and external spatial/economic reference reports
├── notebooks/                             # Jupyter notebooks detailing spatial methodology and visual plots
├── scripts/                               # Executable Python scripts for the automated geospatial pipeline
└── README.md
```
## 📊 Pipeline Architecture & Data Flow

The ETL scripts orchestrate a three-stage spatial data flow:

1. **Extraction & Geocoding:** Loads unstructured tabular building permit data alongside 2020 US Census Tract shapefiles.
2. **Spatial Transformation:** Cleans coordinate features, instantiates geometries, and binds every independent localized permit point directly to its encompassing Census Tract polygon via intersection logic.
3. **Multi-Dimensional Aggregation:** Groups the spatially joined dataset by tract geometry and categorizes construction density by **Typology** (Single-Family, Multi-Family (2+ units), and Accessory Dwelling Units (ADUs)) and **Economic Tiers** (Very Low, Low, Moderate, and Above Moderate based on regional Area Median Income (AMI) indexes).

## 🛠️ Tech Stack & Dependencies

* **Language:** Python 3.x
* **Geospatial Engine:** GeoPandas, Shapely (GEOS)
* **Data Processing:** Pandas, NumPy
* **Visualization:** Matplotlib