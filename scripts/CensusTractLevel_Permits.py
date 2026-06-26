"""
San Jose Census Tract Building Permits Analysis
Author: Karthik Sunkari
Description: Aggregates individual building permits to census tracts, broken down by 
             housing type (Single Family, Multi-Family, ADU) and income affordability.
"""

import pandas as pd
import geopandas as gpd
import numpy as np

# ========= CONFIGURATION =========
PERMITS_CSV = '/content/drive/MyDrive/San_Jose_Housing/APR_A2_building_permits_full_cleaned_BR_greater_san_jose.csv'
TRACT_SHP   = '/content/drive/MyDrive/San_Jose_Housing/SanJose_2020_Census_Tract.shp'
OUTPUT_DIR  = '/content/drive/MyDrive/San_Jose_Housing/'
YEARS       = [2018, 2019, 2020, 2021, 2022, 2023, 2024]

# ========= DEFINE HOUSING TYPE CATEGORIES =========
ADU_CATEGORY = 'accessory dwelling unit'

SINGLE_FAMILY_CATEGORIES = [
    'single-family detached unit',
    'single-family attached unit',
    ADU_CATEGORY
]

MULTI_FAMILY_CATEGORIES = [
    '2-, 3-, and 4-plex units per structure',
    '5 or more units per structure'
]

# ========= LOAD TRACT GEOMETRY =========
gdf_tracts = gpd.read_file(TRACT_SHP)
gdf_tracts['Census_Tract_Code'] = gdf_tracts['FIPSCODE'].astype(str).str[-6:]
gdf_tracts['FIPS_Code']         = gdf_tracts['FIPSCODE'].astype(str)
gdf_tracts = gdf_tracts.to_crs('EPSG:4326')
gdf_tracts['Latitude_Centroid']  = gdf_tracts.geometry.centroid.y
gdf_tracts['Longitude_Centroid'] = gdf_tracts.geometry.centroid.x

tract_codes  = gdf_tracts['Census_Tract_Code']
tract_lookup = gdf_tracts.set_index('Census_Tract_Code')[['FIPS_Code', 'Latitude_Centroid', 'Longitude_Centroid']]

# ========= LOAD PERMITS & COORDS =========
permits = pd.read_csv(PERMITS_CSV)
permits['year'] = permits['year'].astype(int)

permits['lat_lng'] = permits['lat_lng'].replace('None', np.nan)
permits_valid = permits[permits['lat_lng'].notna()].copy()

permits_valid[['Latitude', 'Longitude']] = (
    permits_valid['lat_lng'].str.strip('[]').str.split(',', expand=True)
)
permits_valid['Latitude']  = pd.to_numeric(permits_valid['Latitude'],  errors='coerce')
permits_valid['Longitude'] = pd.to_numeric(permits_valid['Longitude'], errors='coerce')
permits_valid = permits_valid[permits_valid['Latitude'].notna() & permits_valid['Longitude'].notna()]

permits_gdf = gpd.GeoDataFrame(
    permits_valid,
    geometry=gpd.points_from_xy(permits_valid['Longitude'], permits_valid['Latitude']),
    crs='EPSG:4326'
)

permits_gdf = gpd.sjoin(
    permits_gdf,
    gdf_tracts[['Census_Tract_Code', 'geometry']],
    how='left',
    predicate='within'
)
permits = permits_gdf

def aggregate_permits_for_year(year, permits, tract_codes):
    df_year = permits[permits['year'] == year].copy()

    # ---- Flag housing types ----
    df_year['is_single_family'] = df_year['unit_cat'].isin(SINGLE_FAMILY_CATEGORIES)
    df_year['is_multi_family']  = df_year['unit_cat'].isin(MULTI_FAMILY_CATEGORIES)
    df_year['is_adu']           = df_year['unit_cat'] == ADU_CATEGORY

    # ---- Total building permits count ----
    no_permits = df_year.groupby('Census_Tract_Code')['no_building_permits'].sum().rename('no_of_building_permits')
    grouped = no_permits.to_frame().reset_index()

    # ---- Affordability fields ----
    affordability_fields = ['bp_vlow_income', 'bp_low_income', 'bp_mod_income', 'bp_above_mod_income']

    # Single-family breakdown (includes ADUs)
    df_sf = df_year[df_year['is_single_family']]
    for field in affordability_fields:
        sf_field = df_sf.groupby('Census_Tract_Code')[field].sum().rename(f'{field}_single_family')
        grouped = grouped.merge(sf_field, on='Census_Tract_Code', how='left')
        grouped[f'{field}_single_family'] = grouped[f'{field}_single_family'].fillna(0)

    # Multi-family breakdown
    df_mf = df_year[df_year['is_multi_family']]
    for field in affordability_fields:
        mf_field = df_mf.groupby('Census_Tract_Code')[field].sum().rename(f'{field}_multi_family')
        grouped = grouped.merge(mf_field, on='Census_Tract_Code', how='left')
        grouped[f'{field}_multi_family'] = grouped[f'{field}_multi_family'].fillna(0)

    # ADU breakdown (subset of single-family)
    df_adu = df_year[df_year['is_adu']]
    for field in affordability_fields:
        adu_field = df_adu.groupby('Census_Tract_Code')[field].sum().rename(f'{field}_ADUs')
        grouped = grouped.merge(adu_field, on='Census_Tract_Code', how='left')
        grouped[f'{field}_ADUs'] = grouped[f'{field}_ADUs'].fillna(0)

    # ---- Ensure all tracts present ----
    grouped = pd.DataFrame({'Census_Tract_Code': tract_codes}).merge(grouped, on='Census_Tract_Code', how='left')

    # Fill NaNs
    for col in grouped.columns:
        if col != 'Census_Tract_Code':
            grouped[col] = grouped[col].fillna(0)

    # ---- Add FIPS and centroids ----
    grouped = grouped.join(tract_lookup, on='Census_Tract_Code')

    # ---- Final 17 columns in order ----
    final_cols = [
        'Census_Tract_Code',
        'FIPS_Code',
        'Latitude_Centroid',
        'Longitude_Centroid',
        'no_of_building_permits',
        'bp_vlow_income_single_family',
        'bp_low_income_single_family',
        'bp_mod_income_single_family',
        'bp_above_mod_income_single_family',
        'bp_vlow_income_multi_family',
        'bp_low_income_multi_family',
        'bp_mod_income_multi_family',
        'bp_above_mod_income_multi_family',
        'bp_vlow_income_ADUs',
        'bp_low_income_ADUs',
        'bp_mod_income_ADUs',
        'bp_above_mod_income_ADUs'
    ]

    grouped = grouped[final_cols]
    return grouped

# ========= RUN & SAVE =========
for year in YEARS:
    out_df = aggregate_permits_for_year(year, permits, tract_codes)
    out_path = f"{OUTPUT_DIR}permits_aggregated_splitted_sanjose_{year}.csv"
    out_df.to_csv(out_path, index=False)
    print(f"✅ Saved: {out_path}")

# ========= GENERATE DATA DICTIONARY =========
print("\n" + "="*80)
print("GENERATING DATA DICTIONARY")
print("="*80)

data_dict = {
    'Column': [
        'Census_Tract_Code',
        'FIPS_Code',
        'Latitude_Centroid',
        'Longitude_Centroid',
        'no_of_building_permits',
        'bp_vlow_income_single_family',
        'bp_low_income_single_family',
        'bp_mod_income_single_family',
        'bp_above_mod_income_single_family',
        'bp_vlow_income_multi_family',
        'bp_low_income_multi_family',
        'bp_mod_income_multi_family',
        'bp_above_mod_income_multi_family',
        'bp_vlow_income_ADUs',
        'bp_low_income_ADUs',
        'bp_mod_income_ADUs',
        'bp_above_mod_income_ADUs'
    ],

    'Description': [
        'Unique 6-digit code identifying the Census tract.',
        'Full federal tract identifier (state + county + tract).',
        'Latitude coordinate of the Census tract geographic center.',
        'Longitude coordinate of the Census tract geographic center.',
        'Total number of building permits issued within the Census tract for the year.',
        'Very low-income housing units (≤50% AMI) permitted in single-family housing (detached, attached, and ADUs).',
        'Low-income housing units (50-80% AMI) permitted in single-family housing (detached, attached, and ADUs).',
        'Moderate-income housing units (80-120% AMI) permitted in single-family housing (detached, attached, and ADUs).',
        'Above moderate-income housing units (>120% AMI) permitted in single-family housing (detached, attached, and ADUs).',
        'Very low-income housing units (≤50% AMI) permitted in multi-family housing (2-4 plex and 5+ units).',
        'Low-income housing units (50-80% AMI) permitted in multi-family housing (2-4 plex and 5+ units).',
        'Moderate-income housing units (80-120% AMI) permitted in multi-family housing (2-4 plex and 5+ units).',
        'Above moderate-income housing units (>120% AMI) permitted in multi-family housing (2-4 plex and 5+ units).',
        'Very low-income housing units (≤50% AMI) permitted in accessory dwelling units (ADUs, granny flats, in-law units).',
        'Low-income housing units (50-80% AMI) permitted in accessory dwelling units (ADUs, granny flats, in-law units).',
        'Moderate-income housing units (80-120% AMI) permitted in accessory dwelling units (ADUs, granny flats, in-law units).',
        'Above moderate-income housing units (>120% AMI) permitted in accessory dwelling units (ADUs, granny flats, in-law units).'
    ],

    'Source': [
        '2020 TIGER/Line® Census shapefile',
        '2020 TIGER/Line® Census shapefile',
        'Calculated from Census tract geometry',
        'Calculated from Census tract geometry',
        'HCD APR Table A2',
        'HCD APR Table A2',
        'HCD APR Table A2',
        'HCD APR Table A2',
        'HCD APR Table A2',
        'HCD APR Table A2',
        'HCD APR Table A2',
        'HCD APR Table A2',
        'HCD APR Table A2',
        'HCD APR Table A2',
        'HCD APR Table A2',
        'HCD APR Table A2',
        'HCD APR Table A2'
    ]
}

df_dict = pd.DataFrame(data_dict)
dict_output_path = f"{OUTPUT_DIR}permits_aggregate_data_dictionary.csv"
df_dict.to_csv(dict_output_path, index=False)
print(f"✅ Data dictionary saved: {dict_output_path}")
print(f"   Total fields documented: {len(df_dict)}")
print("="*80)

# ========= GENERATE DATA DICTIONARY =========
print("\n" + "="*80)
print("GENERATING DATA DICTIONARY")
print("="*80)

data_dict = {
    'Column': [
        'Census_Tract_Code',
        'FIPS_Code',
        'Latitude_Centroid',
        'Longitude_Centroid',
        'no_building_permits_sum',
        'no_building_permits_median',
        'bp_vlow_income_sum',
        'bp_vlow_income_median',
        'bp_low_income_sum',
        'bp_low_income_median',
        'bp_mod_income_sum',
        'bp_mod_income_median',
        'bp_above_mod_income_sum',
        'bp_above_mod_income_median',
        'bp_affordable_sum',
        'bp_affordable_median',
        'unit_cat_single_family_detached_unit_count',
        'unit_cat_single_family_attached_unit_count',
        'unit_cat_accessory_dwelling_unit_count',
        'unit_cat_2_3_4_plex_units_count',
        'unit_cat_5_plus_units_count',
        'units_single_family_count',
        'units_multi_family_count',
        'tenure_owner_count',
        'tenure_renter_count',
        'bp_vlow_income_single_family',
        'bp_vlow_income_multi_family',
        'bp_low_income_single_family',
        'bp_low_income_multi_family',
        'bp_mod_income_single_family',
        'bp_mod_income_multi_family',
        'bp_above_mod_income_single_family',
        'bp_above_mod_income_multi_family',
        'bp_affordable_single_family',
        'bp_affordable_multi_family',
        'jurs_tracking_id_distinct_count'
    ],

    'Description': [
        'Unique 6-digit code identifying the Census tract.',
        'Full federal tract identifier (state + county + tract).',
        'Latitude coordinate of the census tract geographic center.',
        'Longitude coordinate of the census tract geographic center.',
        'Total number of building permits issued within the census tract for the year.',
        'Median number of building permits per development project in the census tract.',
        'Total number of very low-income housing units permitted (households earning ≤50% of Area Median Income).',
        'Median very low-income units per project.',
        'Total number of low-income housing units permitted (households earning 50-80% of Area Median Income).',
        'Median low-income units per project.',
        'Total number of moderate-income housing units permitted (households earning 80-120% of Area Median Income).',
        'Median moderate-income units per project.',
        'Total number of above moderate-income housing units permitted (households earning >120% of Area Median Income).',
        'Median above moderate-income units per project.',
        'Total number of affordable housing units permitted (sum of very low, low, and moderate-income units).',
        'Median affordable units per project.',
        'Number of single-family detached housing units permitted (stand-alone houses on individual lots).',
        'Number of single-family attached housing units permitted (townhomes, row houses).',
        'Number of accessory dwelling units (ADUs) permitted (granny flats, in-law units).',
        'Number of small multi-family units permitted (2-4 units per structure: duplexes, triplexes, fourplexes).',
        'Number of large multi-family units permitted (5+ units per structure: apartment buildings).',
        'Total single-family housing units (sum of detached, attached, and ADUs).',
        'Total multi-family housing units (sum of 2-4 plex and 5+ units).',
        'Number of building permits designated for owner-occupied housing (for-sale units).',
        'Number of building permits designated for renter-occupied housing (rental units).',
        'Very low-income housing units permitted in single-family housing (detached, attached, and ADUs).',
        'Very low-income housing units permitted in multi-family housing (2-4 plex and 5+ units).',
        'Low-income housing units permitted in single-family housing (detached, attached, and ADUs).',
        'Low-income housing units permitted in multi-family housing (2-4 plex and 5+ units).',
        'Moderate-income housing units permitted in single-family housing (detached, attached, and ADUs).',
        'Moderate-income housing units permitted in multi-family housing (2-4 plex and 5+ units).',
        'Above moderate-income housing units permitted in single-family housing (detached, attached, and ADUs).',
        'Above moderate-income housing units permitted in multi-family housing (2-4 plex and 5+ units).',
        'Total affordable housing units permitted in single-family housing (detached, attached, and ADUs).',
        'Total affordable housing units permitted in multi-family housing (2-4 plex and 5+ units).',
        'Number of unique development projects (distinct jurisdiction tracking IDs) in the census tract.'
    ],

    'Source': [
        'Census shapefile',
        'Census shapefile',
        'Calculated from tract centroid',
        'Calculated from tract centroid',
        'APR Table A2',
        'APR Table A2',
        'APR Table A2',
        'APR Table A2',
        'APR Table A2',
        'APR Table A2',
        'APR Table A2',
        'APR Table A2',
        'APR Table A2',
        'APR Table A2',
        'Calculated (no_building_permits - bp_above_mod_income)',
        'Calculated (median of affordable units)',
        'APR Table A2',
        'APR Table A2',
        'APR Table A2',
        'APR Table A2',
        'APR Table A2',
        'Calculated (sum of detached, attached, ADU)',
        'Calculated (sum of 2-4 plex and 5+ units)',
        'APR Table A2',
        'APR Table A2',
        'APR Table A2',
        'APR Table A2',
        'APR Table A2',
        'APR Table A2',
        'APR Table A2',
        'APR Table A2',
        'APR Table A2',
        'APR Table A2',
        'Calculated (sum of vlow, low, mod income for single-family)',
        'Calculated (sum of vlow, low, mod income for multi-family)',
        'APR Table A2'
    ]
}

df_dict = pd.DataFrame(data_dict)
dict_output_path = f"{OUTPUT_DIR}permits_aggregate_data_dictionary.csv"
df_dict.to_csv(dict_output_path, index=False)
print(f"✅ Data dictionary saved: {dict_output_path}")
print(f"   Total fields documented: {len(df_dict)}")
print("="*80)