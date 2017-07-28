import bokeh as bk
import copy

from bokeh.charts import Bar, Scatter, Line, output_file, show, HeatMap, Histogram
from bokeh.charts.attributes import ColorAttr, CatAttr
from bokeh.plotting  import figure, output_notebook
from bokeh.models import (HoverTool, 
                          ColumnDataSource, 
                          LinearColorMapper, 
                          CustomJS,
                          ColorBar)
                          
from bokeh.palettes import Viridis6, Viridis256
from bokeh.models.widgets import Slider
from bokeh.layouts import column, row

import pandas as pd



def simple_county_map(dfm,key='Production',width=600,height=600,palette=Viridis256,
                      state='ca',
                      title='California Production',
                      tools="pan,wheel_zoom,box_zoom,reset,hover,save",
                      datasrc = ''):
    #from bokeh.sampledata.us_counties import data as counties
    palette = palette[::-1]

    #counties = {
    #    code: county for code, county in counties.items() if county["state"] == state
    #}

    county_df  = pd.read_csv(datasrc)

    county_xs = [county["lons"] for county in counties.values()]
    county_ys = [county["lats"] for county in counties.values()]

    county_names = [county['name'] for county in counties.values()]
    #county_rates = [unemployment[county_id] for county_id in counties]
    county_rates = [dfm[dfm['County'] == county['name']][key] for county in counties.values()]
    color_mapper = LinearColorMapper(palette=palette,low=40,high=140)
    color_mapper = LinearColorMapper(palette=palette,low=dfm[key].min(),high=dfm[key].max())

    source = ColumnDataSource(data=dict(
        x=county_xs,
        y=county_ys,
        name=county_names,
        rate=county_rates,
        ))

    p = figure(title=title, tools=tools,
               x_axis_location=None, y_axis_location=None,
               width = width, height = height)
    p.grid.grid_line_color = None

    p.patches('x', 'y', source=source,
              fill_color={'field': 'rate', 'transform': color_mapper},
              fill_alpha=0.7, line_color="white", line_width=0.5)

    hover = p.select_one(HoverTool)
    hover.point_policy = "follow_mouse"
    hover.tooltips = [
        ("County", "@name"),
        ("{}".format(key), "@rate"),

    ]
    color_bar = ColorBar(color_mapper=color_mapper, location=(0, 0), orientation='vertical')
    p.add_layout(color_bar, 'right')
    p.toolbar_location = 'left'
    return p






def process_stats_by_counties(dfm,key='GPCD',groupkey='Year',aggfunc='mean',srcpath=''):
    
    # Initialize dataframe of regions and counties
    
    region_counties_df = pd.read_csv(srcpath)
    region_counties_df = region_counties_df[['Hydrologic Region','County']]

    list_df = []
    for elt in dfm[groupkey].unique():
        temp_df = copy.deepcopy(region_counties_df)
        temp_df[groupkey] = elt
        list_df.append(temp_df)

    # Overwrite initial dataframe
    region_counties_df = pd.concat(list_df)

    grouped_df = dfm.groupby(['Hydrologic Region','County',groupkey])[[key]].agg(aggfunc).reset_index()

    # Adding missing groups if present
    grouped_df = grouped_df.merge(region_counties_df,on=['Hydrologic Region','County',groupkey],how='outer')

    # If counties are missing in some groups fill In Average of hydrologic region
    grouped_df[key] = grouped_df.groupby(['Hydrologic Region',groupkey]).transform(lambda x: x.fillna(x.mean()))
    return grouped_df.groupby(['County',groupkey])[key].agg(aggfunc).reset_index()
    

def add_location_to_dfm(dfm,state="ca"):
    """ Given dataframe with County field adds county boundaries in order to 
    be used in the plotting routine  """
    # Build County boundary DataFrame from bokeh county data
    from bokeh.sampledata.us_counties import data as counties
    counties = {
                code: county for code, county in counties.items() if county["state"] == state
               }
    county_xs = [county["lons"] for county in counties.values()]
    county_ys = [county["lats"] for county in counties.values()]
    county_names = [county['name'] for county in counties.values()]
    
    location_df = pd.DataFrame({'County':county_names,'x':county_xs,'y':county_ys})
    return dfm.merge(location_df,on='County',how='left')


def interactive_county_map(dfm,key='GPCD',slider_key='Year',initial_query='Year == 2014',
                    title='California GPCD',tools = "pan,wheel_zoom,box_zoom,reset,hover,save", 
                    width=600,height=600,zscale='linear'):
    """ Plots interactive map given dataframe with COunty boundary fields as wall as 
    key value and slider_key present in columns"""
    palette = Viridis256
    palette = palette[::-1]

    if zscale == 'log':
        color_mapper = LogColorMapper(palette=palette,low=dfm[key].min(),high=dfm[key].max())
    else:
        color_mapper = LinearColorMapper(palette=palette,low=dfm[key].min(),high=dfm[key].max())

    source = ColumnDataSource(dfm.dropna(), id='src')
    source_flt = ColumnDataSource(dfm.query(initial_query).fillna(-1), id='src_flt')

    p = figure(title=title, tools=tools,x_axis_location=None, y_axis_location=None,
               width = width, height=height)
    p.grid.grid_line_color = None

    p.patches('x', 'y', source=source_flt,
              fill_color={'field': key, 'transform': color_mapper},
              fill_alpha=0.7, line_color="white", line_width=0.5)

    hover = p.select_one(HoverTool)
    hover.point_policy = "follow_mouse"
    hover.tooltips = [
        ("County", "@County"),
        ("{}".format(key), "@{}".format(key)),
        ]



    callback_js_code="""
                     var orig_data = s1.data;
                     var filtered_data = s2.data;
                     var selected = cb_obj["value"];

                     for (var key in orig_data) {{
                         filtered_data[key] = [];
                         for (var i = 0; i < orig_data['County'].length; ++i) {{
                             if (orig_data['{VARNAME}'][i] === selected)  {{
                                 filtered_data[key].push(orig_data[key][i]);
                             }}
                          }}
                     }}
                     s2.trigger("change");
                     """.format(VARNAME = slider_key)

    callback = CustomJS(args=dict(s1=source,s2=source_flt), code=callback_js_code)


    slider = Slider(start=dfm[slider_key].min(), 
                    end=dfm[slider_key].max(), 
                    value=dfm[slider_key].min(), step=1, 
                    title="Select {}".format(slider_key), width=width,
                    callback=callback)


    color_bar = ColorBar(color_mapper=color_mapper, location=(0, 0), orientation='vertical')
    p.add_layout(color_bar, 'right')
    p.toolbar_location = 'left'
    return column(slider,p)
