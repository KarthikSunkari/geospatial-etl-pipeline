"""
San Jose Census Tract Building Cost Analysis
Author: Karthik Sunkari
Description: Aggregates tax assessor data to census tracts and estimates development costs
             using CCCI and CPI indexes.
"""

# Install required packages
!pip install -q dbfread pandas

# Import libraries
import os
import zipfile
import pandas as pd
import numpy as np
from pathlib import Path
from dbfread import DBF
import glob
import warnings
warnings.filterwarnings('ignore')

# Mount Google Drive
from google.colab import drive
drive.mount('/content/drive', force_remount=False)

print("Setup complete.")

# ============================================
# CHECK IF TAX DATA IS LOADED
# ============================================
try:
    print(f"Tax data already loaded: {len(tax_df):,} records")
except NameError:
    print("Tax data not found. Loading now...")

    # ============================================
    # RELOAD TAX ASSESSOR DATA
    # ============================================
    import pandas as pd
    import zipfile
    import os
    import glob

    tax_assessor_zip = '/content/drive/MyDrive/San_Jose_Housing/tax-assessor-unl_01k8sgbp1h5y10h2gcg594tgr6.zip'
    tax_assessor_extract_dir = '/content/tax_assessor_data'

    os.makedirs(tax_assessor_extract_dir, exist_ok=True)

    with zipfile.ZipFile(tax_assessor_zip, 'r') as zip_ref:
        zip_ref.extractall(tax_assessor_extract_dir)

    # Load ALL tax assessor CSV files
    csv_gz_files = sorted(glob.glob(os.path.join(tax_assessor_extract_dir, '*.csv.gz')))
    csv_files = sorted(glob.glob(os.path.join(tax_assessor_extract_dir, '*.csv')))

    tax_dfs = []

    for csv_gz in csv_gz_files:
        try:
            df = pd.read_csv(csv_gz, compression='gzip')
            tax_dfs.append(df)
            print(f"  ✓ Loaded: {os.path.basename(csv_gz)} ({len(df):,} records)")
        except Exception as e:
            print(f"  ✗ Warning: {os.path.basename(csv_gz)} - {e}")

    for csv_file in csv_files:
        try:
            df = pd.read_csv(csv_file)
            tax_dfs.append(df)
            print(f"  ✓ Loaded: {os.path.basename(csv_file)} ({len(df):,} records)")
        except Exception as e:
            print(f"  ✗ Warning: {os.path.basename(csv_file)} - {e}")

    # Concatenate all tax assessor data
    tax_df = pd.concat(tax_dfs, ignore_index=True)
    print(f"\n✓ Combined Tax Assessor Data: {len(tax_df):,} total records")

import pandas as pd
import geopandas as gpd
from shapely.geometry import Point

# ============================================
# LOAD CENSUS TRACT SHAPEFILE
# ============================================
SHAPEFILE_PATH = "/content/drive/MyDrive/San_Jose_Housing/SanJose_2020_Census_Tract.shp"
tracts_gdf = gpd.read_file(SHAPEFILE_PATH)

print("=" * 70)
print("CENSUS TRACT SHAPEFILE")
print("=" * 70)
print(f"Total Census Tracts: {len(tracts_gdf)}")
print(f"CRS: {tracts_gdf.crs}")

# Extract tract identifiers (matching your existing pattern)
tracts_gdf['FIPS_Code'] = tracts_gdf['FIPSCODE'].astype(str).str.strip()
tracts_gdf['Census_Tract_Code'] = tracts_gdf['FIPS_Code'].str[-6:]

print(f"\n✅ Sample mappings:")
print(f"   FIPS: {tracts_gdf['FIPS_Code'].iloc[0]}")
print(f"   Census_Tract_Code: {tracts_gdf['Census_Tract_Code'].iloc[0]}")

# Set tract identifier columns
tract_id_col = 'Census_Tract_Code'
fips_col = 'FIPS_Code'

print(f"\nUsing tract ID column: {tract_id_col}")
print(f"Using FIPS column: {fips_col}")

# Ensure CRS is set
if tracts_gdf.crs is None:
    print("⚠️ No CRS found, setting to WGS84")
    tracts_gdf = tracts_gdf.set_crs('EPSG:4326')

# ============================================
# PREPARE TAX ASSESSOR DATA FOR SPATIAL JOIN
# ============================================
print("\n" + "=" * 70)
print("PREPARING TAX ASSESSOR DATA")
print("=" * 70)

# Filter for valid coordinates
tax_spatial = tax_df[
    (tax_df['LATITUDE'].notna()) &
    (tax_df['LONGITUDE'].notna()) &
    (tax_df['LATITUDE'] != 0) &
    (tax_df['LONGITUDE'] != 0)
].copy()

print(f"Records with valid coordinates: {len(tax_spatial):,}")
print(f"Sample coordinates:")
print(tax_spatial[['LATITUDE', 'LONGITUDE']].head(3))

# Create geometry column
tax_spatial['geometry'] = tax_spatial.apply(
    lambda row: Point(row['LONGITUDE'], row['LATITUDE']),
    axis=1
)

# Convert to GeoDataFrame (WGS84 - EPSG:4326)
tax_gdf = gpd.GeoDataFrame(tax_spatial, geometry='geometry', crs='EPSG:4326')
print(f"Tax assessor GeoDataFrame CRS: {tax_gdf.crs}")

# ============================================
# SPATIAL JOIN
# ============================================
print("\n" + "=" * 70)
print("PERFORMING SPATIAL JOIN")
print("=" * 70)

# Keep essential columns from tracts
tract_cols_to_keep = ['geometry', 'Census_Tract_Code', 'FIPS_Code']
tracts_subset = tracts_gdf[tract_cols_to_keep].copy()

print(f"Tracts GeoDataFrame CRS: {tracts_subset.crs}")

# Ensure matching CRS
if tax_gdf.crs != tracts_subset.crs:
    print(f"⚠️ CRS mismatch! Converting tracts to {tax_gdf.crs}")
    tracts_subset = tracts_subset.to_crs(tax_gdf.crs)

# Spatial join
print(f"\nPerforming spatial join...")
tax_with_tracts = gpd.sjoin(
    tax_gdf,
    tracts_subset,
    how='left',
    predicate='within'
)

matched = tax_with_tracts['Census_Tract_Code'].notna().sum()
print(f"✓ Spatial join complete: {len(tax_with_tracts):,} records")
print(f"✓ Properties matched to tracts: {matched:,}/{len(tax_with_tracts):,}")

if matched == 0:
    print("\n⚠️ Spatial join failed! Trying nearest neighbor...")
    tax_with_tracts = gpd.sjoin_nearest(
        tax_gdf,
        tracts_subset,
        how='left',
        max_distance=0.01
    )
    matched = tax_with_tracts['Census_Tract_Code'].notna().sum()
    print(f"Properties matched (nearest): {matched:,}/{len(tax_with_tracts):,}")

print(f"\nSample tract codes from tax data:")
print(tax_with_tracts['Census_Tract_Code'].dropna().head(10).tolist())

# ============================================
# PREPARE FOR YEARLY AGGREGATION
# ============================================
print("\n" + "=" * 70)
print("PREPARING YEARLY AGGREGATIONS")
print("=" * 70)

# Extract year from sale date
if 'DEEDLASTSALEDATE' in tax_with_tracts.columns:
    tax_with_tracts['DEEDLASTSALEDATE'] = pd.to_datetime(
        tax_with_tracts['DEEDLASTSALEDATE'], errors='coerce'
    )
    tax_with_tracts['Sale_Year'] = tax_with_tracts['DEEDLASTSALEDATE'].dt.year

# Use tax year as fallback
if 'Sale_Year' not in tax_with_tracts.columns or tax_with_tracts['Sale_Year'].isna().all():
    if 'TAXMARKETVALUEYEAR' in tax_with_tracts.columns:
        tax_with_tracts['Sale_Year'] = tax_with_tracts['TAXMARKETVALUEYEAR']
    elif 'TAXYEARASSESSED' in tax_with_tracts.columns:
        tax_with_tracts['Sale_Year'] = tax_with_tracts['TAXYEARASSESSED']

print(f"\nYear distribution (top 10):")
print(tax_with_tracts['Sale_Year'].value_counts().sort_index().head(10))

# Clean numeric columns - replace zeros and negatives with NA
for col in ['TAXMARKETVALUELAND', 'TAXASSESSEDVALUELAND', 'AREALOTSF',
            'AREALOTACRES', 'AREABUILDING', 'STORIESCOUNT', 'UNITSCOUNT']:
    if col in tax_with_tracts.columns:
        tax_with_tracts.loc[tax_with_tracts[col] <= 0, col] = pd.NA

print(f"Year range in data: {tax_with_tracts['Sale_Year'].min()} to {tax_with_tracts['Sale_Year'].max()}")

# ============================================
# AGGREGATE FOR EACH YEAR (2018-2024)
# ============================================
print("\n" + "=" * 70)
print("AGGREGATING BY YEAR - COST ANALYSIS")
print("=" * 70)

years = range(2018, 2025)  # 2018 to 2024

for year in years:
    print(f"\n--- Processing Year: {year} ---")

    # Filter for current year and valid tracts
    year_data = tax_with_tracts[
        (tax_with_tracts['Sale_Year'] == year) &
        (tax_with_tracts['Census_Tract_Code'].notna())
    ].copy()

    if len(year_data) == 0:
        print(f"  ⚠ No data for {year}")
        continue

    print(f"  Records for {year}: {len(year_data):,}")
    print(f"  Unique tracts: {year_data['Census_Tract_Code'].nunique()}")

    # Build aggregation dictionary dynamically
    agg_dict = {
        # Count
        'Property_Count': ('PARCELNUMBERRAW', 'count'),

        # Land values (COST METRICS)
        'Median_Land_Market_Value': ('TAXMARKETVALUELAND', lambda x: x.median(skipna=True)),
        'Median_Land_Assessed_Value': ('TAXASSESSEDVALUELAND', lambda x: x.median(skipna=True)),

        # Areas
        'Median_Land_Area_SqFt': ('AREALOTSF', lambda x: x.median(skipna=True)),
        'Median_Land_Area_Acres': ('AREALOTACRES', lambda x: x.median(skipna=True)),
        'Median_Building_Area_SqFt': ('AREABUILDING', lambda x: x.median(skipna=True)),

        # Building characteristics
        'Median_Stories_Count': ('STORIESCOUNT', lambda x: x.median(skipna=True)),
    }

    # Add units count if available
    if 'UNITSCOUNT' in year_data.columns:
        agg_dict['Median_Units_Count'] = ('UNITSCOUNT', lambda x: x.median(skipna=True))

    # Aggregate by census tract (include both tract code and FIPS)
    aggregation = year_data.groupby(['Census_Tract_Code', 'FIPS_Code'], as_index=False).agg(**agg_dict)

    # Add year and jurisdiction
    aggregation['Year'] = year
    aggregation['Jurisdiction'] = 'San Jose'

    # Reorder columns to put identifiers first
    id_cols = ['Census_Tract_Code', 'FIPS_Code', 'Year', 'Jurisdiction']
    other_cols = [col for col in aggregation.columns if col not in id_cols]
    aggregation = aggregation[id_cols + other_cols]

    # Save to CSV
    output_path = f'/content/drive/MyDrive/San_Jose_Housing/census_tract_cost_analysis_{year}.csv'
    aggregation.to_csv(output_path, index=False)

    print(f"  ✓ Census Tracts in {year}: {len(aggregation)}")
    print(f"  ✓ Saved to: {output_path}")

    # Display sample for first year
    if year == 2018:
        print(f"\n  Sample data for {year}:")
        print(aggregation.head(3))
        print(f"\n  Columns: {list(aggregation.columns)}")

# ============================================
# CREATE COMBINED FILE (ALL YEARS)
# ============================================
print("\n" + "=" * 70)
print("CREATING COMBINED FILE")
print("=" * 70)

all_years_data = []
for year in years:
    file_path = f'/content/drive/MyDrive/San_Jose_Housing/census_tract_cost_analysis_{year}.csv'
    try:
        df = pd.read_csv(file_path)
        all_years_data.append(df)
        print(f"  ✓ Loaded {year}: {len(df)} tracts")
    except:
        print(f"  ✗ No file for {year}")

if all_years_data:
    combined_df = pd.concat(all_years_data, ignore_index=True)
    combined_output = '/content/drive/MyDrive/San_Jose_Housing/census_tract_cost_analysis_2018_2024_combined.csv'
    combined_df.to_csv(combined_output, index=False)
    print(f"\n✓ Combined file saved: {combined_output}")
    print(f"  Total records: {len(combined_df):,}")
    print(f"  Years: {sorted(combined_df['Year'].unique())}")
    print(f"  Unique tracts: {combined_df['Census_Tract_Code'].nunique()}")

# ============================================
# SUMMARY
# ============================================
print("\n" + "=" * 70)
print("COST ANALYSIS AGGREGATION COMPLETE")
print("=" * 70)
print("\nIndividual year files:")
for year in years:
    print(f"  - census_tract_cost_analysis_{year}.csv")
print(f"\nCombined file:")
print(f"  - census_tract_cost_analysis_2018_2024_combined.csv")
print(f"\n✓ Total shapefile tracts: {len(tracts_gdf)}")
print(f"✓ Properties spatially joined: {matched:,}")

# ============================================
# DIAGNOSE LAND VALUE DATA
# ============================================
print("\n" + "=" * 70)
print("DIAGNOSING LAND MARKET VALUE DATA")
print("=" * 70)

# Check if column exists
if 'TAXMARKETVALUELAND' in tax_df.columns:
    print("✓ TAXMARKETVALUELAND column exists")

    # Check basic stats
    print(f"\nTotal records: {len(tax_df):,}")
    print(f"Non-null values: {tax_df['TAXMARKETVALUELAND'].notna().sum():,}")
    print(f"Values > 0: {(tax_df['TAXMARKETVALUELAND'] > 0).sum():,}")
    print(f"Values = 0: {(tax_df['TAXMARKETVALUELAND'] == 0).sum():,}")
    print(f"Null values: {tax_df['TAXMARKETVALUELAND'].isna().sum():,}")

    # Show distribution
    print("\nValue distribution:")
    print(tax_df['TAXMARKETVALUELAND'].describe())

    # Show sample non-zero values
    non_zero = tax_df[tax_df['TAXMARKETVALUELAND'] > 0]['TAXMARKETVALUELAND']
    if len(non_zero) > 0:
        print(f"\nSample non-zero values:")
        print(non_zero.head(20).tolist())

    # Check related columns
    print("\n\nChecking related land value columns:")
    for col in ['TAXMARKETVALUELAND', 'TAXASSESSEDVALUELAND', 'TAXMARKETVALUETOTAL',
                'TAXASSESSEDVALUETOTAL', 'TAXMARKETVALUEIMPROVEMENTS']:
        if col in tax_df.columns:
            non_zero_count = (tax_df[col] > 0).sum()
            print(f"  {col}: {non_zero_count:,} non-zero values")
else:
    print("✗ TAXMARKETVALUELAND column NOT FOUND")
    print("\nAvailable columns with 'LAND' or 'VALUE':")
    land_cols = [col for col in tax_df.columns if 'LAND' in col or 'VALUE' in col]
    for col in land_cols:
        print(f"  - {col}")

import pandas as pd

# ============================================
# CONSTRUCTION COST INDEXES (2018-2024) - OFFICIAL VERIFIED VALUES
# ============================================

cost_index_data = {
    'Year': [2018, 2019, 2020, 2021, 2022, 2023, 2024],
    # Official CCCI from California DGS (December values)
    'CCCI': [6684, 6924, 7120, 8072, 8823, 9654, 9876],
    # Official Bay Area CPI-U from BLS (San Francisco-Oakland-Hayward, December values)
    'Bay_Area_CPI': [289.90, 297.01, 302.95, 315.80, 331.22, 339.92, 348.00]
}

df_indexes = pd.DataFrame(cost_index_data)

# Calculate index factors (relative to 2019 base year)
base_year = 2019
base_ccci = 6924
base_cpi = 297.01

df_indexes['CCCI_Factor'] = (df_indexes['CCCI'] / base_ccci).round(4)
df_indexes['CPI_Factor'] = (df_indexes['Bay_Area_CPI'] / base_cpi).round(4)

# RAND 2019 base costs
HARD_COST_BASE_2019 = 292  # $/sq ft
SOFT_COST_BASE_2019 = 100  # $/sq ft

# Calculate indexed costs per sq ft
df_indexes['Hard_Cost_Per_SqFt'] = (HARD_COST_BASE_2019 * df_indexes['CCCI_Factor']).round(2)
df_indexes['Soft_Cost_Per_SqFt'] = (SOFT_COST_BASE_2019 * df_indexes['CPI_Factor']).round(2)

print("=" * 80)
print("VERIFIED CONSTRUCTION COST INDEXES (2018-2024)")
print("=" * 80)
print("\nOfficial Sources:")
print("  - CCCI: California DGS (December values)")
print("  - CPI-U: BLS San Francisco-Oakland-Hayward (December values)")
print("\nBase: RAND 2019 - Hard: $292/sq ft, Soft: $100/sq ft\n")
print(df_indexes[['Year', 'CCCI', 'Bay_Area_CPI', 'CCCI_Factor', 'CPI_Factor',
                   'Hard_Cost_Per_SqFt', 'Soft_Cost_Per_SqFt']].to_string(index=False))

# ============================================
# PROCESS EACH YEAR FILE
# ============================================
print("\n" + "=" * 80)
print("PROCESSING INDIVIDUAL YEAR FILES")
print("=" * 80)

years = range(2018, 2025)
base_path = '/content/drive/MyDrive/San_Jose_Housing/census_tract_cost_analysis_{year}.csv'

for year in years:
    print(f"\n--- Processing Year: {year} ---")

    file_path = base_path.replace('{year}', str(year))

    try:
        # Load the year file
        df_year = pd.read_csv(file_path)
        print(f"  ✓ Loaded: {len(df_year)} tracts")

        # Remove empty Median_Land_Market_Value column
        if 'Median_Land_Market_Value' in df_year.columns:
            df_year = df_year.drop(columns=['Median_Land_Market_Value'])
            print(f"  ✓ Removed empty Median_Land_Market_Value column")

        # Get cost indexes for this year
        year_costs = df_indexes[df_indexes['Year'] == year].iloc[0]

        # Add per sq ft costs
        df_year['Hard_Cost_Per_SqFt'] = year_costs['Hard_Cost_Per_SqFt']
        df_year['Soft_Cost_Per_SqFt'] = year_costs['Soft_Cost_Per_SqFt']

        # Calculate total costs based on median building area
        df_year['Land_Cost'] = df_year['Median_Land_Assessed_Value'].fillna(0).round(2)

        df_year['Hard_Cost'] = (
            df_year['Median_Building_Area_SqFt'] * df_year['Hard_Cost_Per_SqFt']
        ).round(2)

        df_year['Soft_Cost'] = (
            df_year['Median_Building_Area_SqFt'] * df_year['Soft_Cost_Per_SqFt']
        ).round(2)

        # Total Development Cost = Land + Hard + Soft
        df_year['Total_Development_Cost'] = (
            df_year['Land_Cost'] + df_year['Hard_Cost'] + df_year['Soft_Cost']
        ).round(2)

        # Reorder columns - Land, Hard, Soft side by side
        id_cols = ['Census_Tract_Code', 'FIPS_Code', 'Year', 'Jurisdiction']

        property_cols = [c for c in ['Property_Count', 'Median_Building_Area_SqFt',
                                       'Median_Land_Area_SqFt', 'Median_Land_Area_Acres',
                                       'Median_Stories_Count', 'Median_Units_Count']
                         if c in df_year.columns]

        # COST COLUMNS SIDE BY SIDE: Per SqFt, then Total Costs
        cost_per_sqft_cols = ['Hard_Cost_Per_SqFt', 'Soft_Cost_Per_SqFt']

        cost_total_cols = ['Land_Cost', 'Hard_Cost', 'Soft_Cost', 'Total_Development_Cost']

        # Other land value columns (keep assessed values)
        other_land_cols = [c for c in ['Median_Land_Assessed_Value', 'Median_Total_Assessed_Value']
                           if c in df_year.columns]

        # Build ordered column list
        ordered_cols = (id_cols + property_cols + cost_per_sqft_cols +
                        cost_total_cols + other_land_cols)

        # Add any remaining columns
        remaining = [c for c in df_year.columns if c not in ordered_cols]
        ordered_cols.extend(remaining)

        df_year = df_year[ordered_cols]

        # Save back to same file
        df_year.to_csv(file_path, index=False)
        print(f"  ✓ Updated and saved: {file_path}")
        print(f"  ✓ Total columns: {len(df_year.columns)}")

        # Show cost breakdown summary
        non_null_costs = df_year[df_year['Total_Development_Cost'].notna()]
        if len(non_null_costs) > 0:
            print(f"\n  Cost Summary for {year}:")
            print(f"    Hard Cost/SqFt: ${year_costs['Hard_Cost_Per_SqFt']:.2f}")
            print(f"    Soft Cost/SqFt: ${year_costs['Soft_Cost_Per_SqFt']:.2f}")
            print(f"    Median Land Cost: ${non_null_costs['Land_Cost'].median():,.0f}")
            print(f"    Median Hard Cost: ${non_null_costs['Hard_Cost'].median():,.0f}")
            print(f"    Median Soft Cost: ${non_null_costs['Soft_Cost'].median():,.0f}")
            print(f"    Median Total Development Cost: ${non_null_costs['Total_Development_Cost'].median():,.0f}")

        # Show sample for 2023
        if year == 2023:
            print(f"\n  Sample breakdown for {year} (first 2 tracts):")
            sample_cols = ['Census_Tract_Code', 'Median_Building_Area_SqFt',
                          'Land_Cost', 'Hard_Cost', 'Soft_Cost', 'Total_Development_Cost']
            print(df_year[sample_cols].head(2).to_string(index=False))

    except FileNotFoundError:
        print(f"  ✗ File not found: {file_path}")
    except Exception as e:
        print(f"  ✗ Error processing {year}: {e}")

# ============================================
# SUMMARY
# ============================================
print("\n" + "=" * 80)
print("COMPLETE!")
print("=" * 80)
print("\n✅ All individual year files updated with VERIFIED INDEXES:")
print("\n   Official Sources:")
print("   - CCCI: California DGS")
print("   - CPI-U: BLS San Francisco-Oakland-Hayward")
print("\n   REMOVED:")
print("   ✗ Median_Land_Market_Value (empty column)")
print("\n   ADDED Cost Structure (side by side):")
print("   ✓ Land_Cost (from Median_Land_Assessed_Value)")
print("   ✓ Hard_Cost (construction - CCCI indexed)")
print("   ✓ Soft_Cost (regulatory/fees - CPI indexed)")
print("   ✓ Total_Development_Cost (Land + Hard + Soft)")
print("\n   Also includes:")
print("   ✓ Hard_Cost_Per_SqFt")
print("   ✓ Soft_Cost_Per_SqFt")
print("\n✅ Files location:")
print("   /content/drive/MyDrive/San_Jose_Housing/census_tract_cost_analysis_YYYY.csv")
print("=" * 80)