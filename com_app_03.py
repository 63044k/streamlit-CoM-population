import streamlit as st
import pandas as pd
import numpy as np
import pydeck as pdk
import plotly.express as px
import re
from itertools import cycle, islice
import random

REGION_DATA_URL = (
    "./Census_of_Land_Use_and_Employment__CLUE__Suburb _mod01.csv"
)

POPULATION_DATA_URL = (
    "./City_of_Melbourne_Population_Forecasts_2016_to_2041_-_Household_Types_mod00.csv"
)

REGION_COLOURS_NUM = [[0, 66, 157, 242], [36, 81, 164, 242], [55, 97, 171, 242], [71, 113, 178, 242], [86, 129, 185, 242], [100, 146, 192, 242], [115, 162, 198, 242], [130, 179, 205, 242], [147, 196, 210, 242], [165, 213, 216, 242], [185, 229, 221, 242], [211, 244, 224, 242], [255, 255, 224, 242]]




def strtofloat(p):
    x = [float(i) for i in p]
    return x

def transform_precinct_shape(s):
    x = re.split(",\s*", s)
    xx = [strtofloat(list(re.split("\s+", i))) for i in x]
    return xx

@st.cache(persist=False)
def load_region_data(nrows):
    
    #load data
    df = pd.read_csv(REGION_DATA_URL, nrows=nrows)
    
    #neaten raw data
    df.dropna(inplace=True)
    df.rename(columns={"the_geom": "precinct_shape"}, inplace=True)
    df.rename(columns={"FEATURENAM": "precinct_name"}, inplace=True)
    df.rename(columns={"SHAPE_AREA": "precinct_area"}, inplace=True)
    del df['SHAPE_LEN']

    #process precinct shapes
    df['precinct_shape'] = df['precinct_shape'].apply(lambda x: transform_precinct_shape(x))
    #random.shuffle(REGION_COLOURS_NUM)
    df["color"] = list(islice(cycle(REGION_COLOURS_NUM), len(df)))

    #process precinct area
    tosqkmx = lambda x: "{0:.3g}".format(x/1000000)
    df["precinct_area"] = df["precinct_area"].apply(tosqkmx)

    return df


@st.cache(persist=False)
def load_population_data(nrows):
    
    #load data
    df = pd.read_csv(POPULATION_DATA_URL, nrows=nrows, index_col="Year")

    #neaten raw data
    df.rename(columns={"Geography": "precinct_name"}, inplace=True)
    df.rename(columns={"Total households": "total_households"}, inplace=True)

    #process data
    df['total_households'] = df['total_households'].apply(lambda x: float(x))
    thmin = df['total_households'].min()
    thmax = df['total_households'].max()
    #print(thmin, thmax)
    df['total_households_norm'] = df['total_households'].apply(lambda x: (x - thmin) / (thmax - thmin))
    df['population'] = df['total_households'] * df['Average Household Size']
    df = df.round({'population': 0})

    return df


region_data = load_region_data(15000)
population_data = load_population_data(15000)


# draw the page header information
st.title("City of Melbourne Population Forecasts")
st.markdown("Explore population forecasts from 2016 to 2041 for the City of Melbourne.")


# year selection and adjustment
year = st.slider("Year to inspect:", 2016, 2041, value=2021)
year_population_data = population_data.loc[year]
year_merged_data = pd.merge(left=region_data, right=year_population_data, left_on='precinct_name', right_on='precinct_name') # merged_inner


#gentrification effects
GENT_LOW = 'Low - the status quo'
GENT_MED = 'Medium - some increased forces to develop land'
GENT_HIGH = 'High - intense pressure to develop all land available'
option = st.selectbox(
    'Gentrification scenario (urban development forces on underutilised land):',
    (GENT_LOW, GENT_MED, GENT_HIGH), index=0)
gentrification_level = { GENT_LOW: 0, GENT_MED: 0.5, GENT_HIGH: 1.0 }[option]
year_merged_data["total_households"] = (year_merged_data["total_households"]
    * (1 + gentrification_level * year_merged_data["gentrification_factor"]))
year_merged_data["population"] = (year_merged_data["population"]
    * (1 + gentrification_level * year_merged_data["gentrification_factor"]))
year_merged_data["total_households_norm"] = (year_merged_data["total_households_norm"]
    * (1 + gentrification_level * year_merged_data["gentrification_factor"]))



# Add sunlight shadow to the polygons
sunlight = {
    "@@type": "_SunLight",
    "timestamp": 1564696800000,  # Date.UTC(2019, 7, 1, 22),
    "color": [255, 255, 255],
    "intensity": 1.0,
    "_shadow": True,
}

ambient_light = {"@@type": "AmbientLight", "color": [255, 255, 255], "intensity": 1.0}

lighting_effect = {
    "@@type": "LightingEffect",
    "shadowColor": [0, 0, 0, 0.5],
    "ambientLight": ambient_light,
    "directionalLights": [sunlight],
}

view_state=({
        "latitude": -37.788837515833784,
        "longitude": 144.936867787351,
        "zoom": 11,
        "pitch": 50,
    }
)

polygon_layer = pdk.Layer(
    layer_id="region",
    type="SolidPolygonLayer",
    data=year_merged_data,
    stroked=False,
    get_polygon="precinct_shape",
    get_fill_color="color",
    extruded=True,
    filled=True,
    wireframe=False,
    get_elevation="1000 + total_households_norm * 5000",
    pickable=True,
)

r = pdk.Deck(
    layers=[polygon_layer],
    initial_view_state=view_state,
    effects=[lighting_effect],
    map_style="mapbox://styles/mapbox/light-v9",
    tooltip={
        'html': ('<b>Precinct:</b> {precinct_name}'
            '<br><b>Area:</b> {precinct_area} km<sup>2</sup>'
            '<br><b>Households:</b> {total_households}'
            '<br><b>Population:</b> {population}'),
        'style': {
            'color': 'white'
        }
    }
)

st.write(r)


st.markdown(('This app uses data from the City of Melbourne [Open Data Portal](https://data.melbourne.vic.gov.au/).'
    '  \nThe gentrification scenario modelling is for illustrative purposes only.'))


# optionally show the raw data
def showrawdata():
    if st.checkbox("Show raw data", False):
        st.write(region_data)
        st.write(population_data)
        st.write(year_population_data)
        st.write(year_merged_data)

#showrawdata()





