import dash
import dash_core_components as dcc
import dash_html_components as html
import dash_table
import dash_auth
import dash_cytoscape as cyto
from dash.dependencies import Input, Output, State
import pandas as pd
import plotly.plotly as py
import plotly.graph_objs as go
import plotly.figure_factory as ff
import re
import copy
import os
import ast
import datetime
from dateutil.relativedelta import *

def col_name(short):
    lookup = {
        'pid': 'Project-id',
        'project': 'Project',
        'desc': 'Description',
        'grouping': 'Grouping',
        'scale': 'Resource Requirement (Low/Medium/High)',
        'status': 'Status (Potential/Committed/In progress/Completed/Rejected/Duplicate)',
        'p_theme': 'Primary Library Strategy Theme',
        's_themes': 'Secondary Strategy Theme(s)',
        'all_themes': 'all_themes',
        'teams': 'Library Teams involved',
        'external': 'External Parties involved',
        'start': 'Start Semester',
        'end': 'End Semester'
    }
    if short in lookup:
        return lookup[short]
    else:
        return short

if 'dash-it-all-url' in os.environ:
    url = os.environ['dash-it-all-url']
    df = pd.read_excel(url, 'Projects')
else:
    url = 'lmt_projects.csv'
    df = pd.read_csv(url)

df[col_name('s_themes')] = df[col_name('s_themes')].fillna('')
df["all_themes"] = df[col_name('p_theme')].map(str) + ', ' + df[col_name('s_themes')]
df[col_name('scale')] = df[col_name('scale')].str.strip()
df[col_name('status')] = df[col_name('status')].str.strip()
df[col_name('status')] = df[col_name('status')].str.capitalize()
df[col_name('teams')] = df[col_name('teams')].fillna('')
df[col_name('external')] = df[col_name('external')].fillna('') 
df[col_name('start')] = df[col_name('start')].fillna('')  
df[col_name('end')] = df[col_name('end')].fillna('') 
valid_status = df[col_name('status')].value_counts().axes[0].tolist()
valid_scales = df[col_name('scale')].value_counts().axes[0].tolist()
valid_pthemes = df[col_name('p_theme')].value_counts().axes[0].sort_values().tolist()
scale_colors = {'Low': 'rgb(39, 119, 180)', 
    'Medium': 'rgb(225, 127, 14)', 
    'High': 'rgb(44, 160, 44)' }
# Methods to deal with multi-value columns
def col_groups(col_series):
    val_list = []
    for row in col_series:
        row_list = [x.strip() for x in row.split(',')]
        row_list = [x.capitalize() for x in row_list]
        val_list.append(row_list)
    return val_list

def col_value_counts(col_series, split=False):
    if split == False:
        return col_series.value_counts()
    else:
        val_list = []
        for row in col_series:
            row_list = [x.strip() for x in row.split(',')]
            row_list = [x.capitalize() for x in row_list]
            row_list = filter(None, row_list)
            val_list.extend(row_list)
        return pd.Series(val_list).value_counts()

# Bar chart data
# takes the column of interest, a boolean to indicate whether to break down by scale 
# an array of statuses for filtering, and a boolean to indicate whether the column,
# has multiple comma-separated values which must be handled
# returns an array of 1 or more dicts for bar chart
def column_bar_data(column, scales, statuses=[], teams=[], ptheme='', split=False):
    dfbar = df
    if len(statuses) > 0:
        dfbar = dfbar[dfbar[col_name('status')].isin(statuses)]

    teams = [re.escape(m) for m in teams]
    if len(teams) > 0:
        dfbar  = dfbar[dfbar[col_name('teams')].str.contains('|'.join(teams))]

    if ptheme:
        dfbar = dfbar[dfbar[col_name('p_theme')].isin([ptheme])]

    data = []
    if scales == []:
        scales = valid_scales

    for scale in scales:
        color = scale_colors[scale]
        dfscale = dfbar[dfbar[col_name('scale')] == scale]
        col_vals = col_value_counts(dfscale[column], split)
        if len(col_vals) > 0:
            data.append({'x': col_vals.axes[0], 'y': col_vals.values, 'type': 'bar', 'name': scale, 'marker':{'color': color}}) 
    return data

def bar_return_dict(scale, status, mode, column, title, teams=[], ptheme='', split=False, margin_dict={'b':25}):
    data = column_bar_data(column, scale, status, teams, ptheme, split)
    return {
        'data': data,
        'layout': go.Layout( 
            title=title,
            yaxis={'title': '# of projects'},
            barmode=mode,
            margin=go.layout.Margin(margin_dict),
            xaxis=go.layout.XAxis(categoryorder="category ascending")
        ),
    }

# Graph Data
def graph_data(groups): 
    all_vals = []
    dict1= {}
    for group in groups:
        for val in group:
            if val not in all_vals:
                all_vals.append(val)

            other_vals = [x for x in group if x != val]
            for other_val in other_vals:
                if val in dict1:
                    if other_val in dict1[val]:
                        dict1[val][other_val] += 1
                    else:
                        dict1[val][other_val] = 1
                else:
                    dict1[val] = {other_val: 1}
    edges = []
    for val in all_vals:
        edges.append({'data': {'id': val, 'label': val}})

    done_dict = {}

    for k, v in dict1.items():
        for k1, v1 in dict1[k].items():
            if k1 in done_dict:
                if k not in done_dict[k1]:
                    edges.append({'data': {'source': k, 'target': k1, 'weight': dict1[k][k1]}})
                    if k in done_dict:
                        done_dict[k].append(k1)
                    else:
                        done_dict[k] = [k1]
            else:
                edges.append({'data':{'source': k, 'target': k1, 'weight': dict1[k][k1]}})
                if k in done_dict:
                    done_dict[k].append(k1)
                else:
                    done_dict[k] = [k1]
    return edges

def graph_elements(column, scale, status, ptheme):
    dfgraph = df
    if len(status) > 0:
        dfgraph = dfgraph[dfgraph[col_name('status')].isin(status)]
        
    if len(scale) > 0:
        dfgraph = dfgraph[dfgraph[col_name('scale')].isin(scale)]

    if ptheme:
        dfgraph = dfgraph[dfgraph[col_name('p_theme')].isin([ptheme])]

    #dfgraph = dfgraph[dfgraph[col_name('p_theme')].isin(['T3'])]
    groups = col_groups(dfgraph[column])
    weighted_elements = graph_data(groups)
    return weighted_elements 

def graph_stylesheet(node):
    styles = copy.deepcopy(default_graph_stylesheet)
    styles.append(
        {
            'selector': 'node[id = "{}"]'.format(node['data']['id']),
            'style': {
                'label': 'data(label)',
                'background-color': 'purple',
            }
        }
    )
    for edge in node['edgesData']:
        styles.append({
                "selector": 'edge[id= "{}"]'.format(edge['id']),
                "style": {
                    "line-color": 'blue',
                    'opacity': 0.9,
                    'z-index': 5000
                }
            })
    return styles

# Gantt data
def valid_sem(sem):
    pattern = re.compile("^20\d{2}\/20\d{2}-0[1-3]$")
    if pattern.match(sem):
        return True
    else:
        return False
        
def sem_to_date(sem, start_end):
    assert(valid_sem(sem)), "Error loading gantt chart. {0} is not a valid semester".format(sem)
    
    semester = sem.split('-')[1]
    years = sem.split('-')[0]
    start_year = years.split("/")[0]
    end_year = years.split("/")[1]
    if semester == '01':
        if start_end == 'start':
            return '{0}-09-01'.format(start_year)
        else:
            return '{0}-12-31'.format(start_year)
    elif semester == '02':
        if start_end == 'start':
            return '{0}-01-01'.format(end_year)
        else:
            return '{0}-04-30'.format(end_year)
    else:
        if start_end == 'start':
            return '{0}-05-01'.format(end_year)
        else:
            return '{0}-08-31'.format(end_year)    

def project_progress(status, end_sem_datestr):
    if status == 'Completed':
        return 'Green'
    end_date = datetime.datetime.strptime(end_sem_datestr, "%Y-%m-%d")
    today = datetime.datetime.today()

    if today > end_date:
        return 'Red (late)'
    elif today+relativedelta(months=+1) > end_date:
        return 'Amber (due to finish)'
    else:
        return 'Green'

def gantt_data(scale, status, title, teams=[], ptheme='', color_type='progress'):
    dfgantt = df
    dfgantt[col_name('teams')] = dfgantt[col_name('teams')].str.lower()
    if len(status) > 0:
        relvant_status = ['Completed', 'In progress', 'Committed']
        valid_status = list(set(status) & set(relvant_status))
        dfgantt = dfgantt[dfgantt[col_name('status')].isin(valid_status)]
        
    if len(scale) > 0:
        dfgantt = dfgantt[dfgantt[col_name('scale')].isin(scale)]

    teams = [re.escape(m) for m in teams]
    if len(teams) > 0:
        dfgantt = dfgantt[dfgantt[col_name('teams')].str.contains('|'.join(teams))]
    
    if ptheme:
        dfgantt = dfgantt[dfgantt[col_name('p_theme')].isin([ptheme])]
    
    data = []
    for index, row in dfgantt.iterrows():
        pid = row[col_name('pid')]
        project = row[col_name('project')]
        project = (project[:40] + '....') if len(project) > 40 else project
        row_scale = row[col_name('scale')]
        task = '{0} - {1}'.format(pid, project)
        try:
            start_sem = sem_to_date(row[col_name('start')], 'start')
            end_sem = sem_to_date(row[col_name('end')], 'end')
            project_status = row[col_name('status')]
            progress = project_progress(project_status, end_sem)
            data.append({'Task':task, 'Start':start_sem, 'Finish':end_sem, 'scale': row_scale, 'progress': progress})
        except:
            print('skipping {0} - failed to load valid values'.format(task))

    progress_colors = {
        'Green': 'rgb(44, 160, 44)',
        'Amber (due to finish)': 'rgb(225, 127, 14)',
        'Red (late)': 'rgb(255, 0, 0)',
    }

    if color_type == 'progress':
        index_column = 'progress'
        color_dict = progress_colors
    else:
        index_column = 'scale'
        color_dict = scale_colors

    fig = ff.create_gantt(data, colors=color_dict, index_col=index_column, showgrid_x=True, showgrid_y=True, show_colorbar=True)
    fig['layout'].update(autosize=True, width=1300, height=1500, title=title, xaxis=dict(automargin=True, mirror='allticks', dtick='M4'), margin=dict(b=10, l=350))
    return fig


# Define some re-usable values for HTML components
def options_list(list, lower_val=False):
    options = []
    for val in list:
        value = val
        if lower_val==True:
            value = val.lower()
        options.append({'label': val, 'value': value})
    return options

scale_dropdown_args = {
    'options':options_list(valid_scales), 
    'value':valid_scales,
    'multi': True,
    'searchable':False,
    'placeholder':"Showing all resource requirement levels, click to filter by one or more ...",
}

status_dropdown_args = {
    'options':options_list(valid_status), 
    'value':['Committed', 'In progress', 'Completed'],
    'multi': True,
    'searchable':False,
    'placeholder':"Showing all project statuses, click to filter by one or more ...",
}
            
barmode_dropdown_args={
    'options':[
        {'label': 'Stack Resource Requirements', 'value':'stack'},
        {'label': 'Group Resource Requirements', 'value':'group'}
    ],
    'value':'stack',
    'className':'radio-div',
    'multi': False,
    'searchable':False,
    'clearable': False
}

themes_dropdown_args={
    'options':[
        {'label': 'Primary Themes', 'value':'p_theme'},
        {'label': 'Secondary Themes', 'value':'s_themes'},
        {'label': 'Primary and Secondary Themes', 'value':'all_themes'}
    ],
    'value':'p_theme',
    'multi': False,
    'searchable':False,
    'clearable': False
}

ptheme_options = []
for ptheme in valid_pthemes:
    ptheme_options.append({'label': 'Primary Theme: {0}'.format(ptheme), 'value': ptheme})

ptheme_dropdown_args={
    'options': ptheme_options,
    'multi': False,
    'searchable':False,
    'placeholder':"Filter by a specific Primary Theme ...",
}

graph_layout_dropdown_args = {
    'options': options_list(['random', 'grid', 'circle', 'concentric', 'breadthfirst', 'cose']),
    'value':'circle',
    'multi':False,
    'searchable':False,
    'clearable':False
}

default_graph_stylesheet = [
        {
            'selector': 'node',
            'style': {
                'label': 'data(label)',
                'background-color': 'red',
            }
        },
        {
            'selector': 'edge',
            'style': {
                'width':'data(weight)',
                'line-color': 'green',
            }
        },
    ]

graph_layout_default_args={
    'layout':{'name': 'circle', 'animate': True},
    'elements':[],
    'style':{'width': '100%', 'height': '800px'},
    'zoomingEnabled': False,
    'stylesheet': default_graph_stylesheet
}

all_teams = col_value_counts(df[col_name('teams')], True).axes[0].sort_values()
all_teams = list(filter(None, all_teams))
all_teams_lower = [x.lower() for x in all_teams]
teams_dropdown_args = {
    'options': options_list(all_teams, True), 
    'value': [],
    'multi':True,
    'searchable':False,
    'placeholder':"Filter projects by one or more teams...",
}

# App setup and layout
external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']


app = dash.Dash(__name__, external_stylesheets=external_stylesheets)
server = app.server

if 'dash-it-all-pass' in os.environ:
    pass_pairs = ast.literal_eval(os.environ['dash-it-all-pass'])
    auth = dash_auth.BasicAuth(
        app,
        pass_pairs
    )

app.layout =html.Div(children=[
    html.H1(children='UCC Library Strategy - Planning Dashboard'),

    html.Div(children='''
        The plots below provide an overview of the projects being undertaken in support of the UCC Library Strategy.
    '''),
    html.Div(className="graph-box",
        children=[
            dcc.Graph(id='status-bar'),
            dcc.Dropdown(id='status-bar-barmode', **barmode_dropdown_args),
            dcc.Dropdown(id='status-bar-ptheme', **ptheme_dropdown_args),
            dcc.Dropdown(id='status-bar-teams', **teams_dropdown_args), 
            dcc.Dropdown(id='status-bar-scale', **scale_dropdown_args),
        ]
    ),
    html.Div(className="graph-box",
        children=[
            dcc.Graph(id='pthemes-bar'),
            dcc.Dropdown(id='pthemes-bar-barmode', **barmode_dropdown_args),
            dcc.Dropdown(id='pthemes-bar-themes', **themes_dropdown_args),
            dcc.Dropdown(id='pthemes-bar-teams', **teams_dropdown_args), 
            dcc.Dropdown(id='pthemes-bar-scale', **scale_dropdown_args),
            dcc.Dropdown(id='pthemes-bar-status', **status_dropdown_args),
        ]
    ),
    html.Div(className="graph-box",
        children=[
            html.Div(className="graph-title", children=[html.H3('Intra-project theme relationships'),]),
            cyto.Cytoscape(id='theme-graph', **graph_layout_default_args),
            dcc.Dropdown(id='theme-graph-layout', **graph_layout_dropdown_args),
            dcc.Dropdown(id='theme-graph-ptheme', **ptheme_dropdown_args),
            dcc.Dropdown(id='theme-graph-scale', **scale_dropdown_args),
            dcc.Dropdown(id='theme-graph-status', **status_dropdown_args),
        ]
    ),
    html.Div(className="graph-box",
        children=[
            dcc.Graph(id='grp-bar'),
            dcc.Dropdown(id='grp-bar-barmode', **barmode_dropdown_args),
            dcc.Dropdown(id='grp-bar-ptheme', **ptheme_dropdown_args),
            dcc.Dropdown(id='grp-bar-teams', **teams_dropdown_args), 
            dcc.Dropdown(id='grp-bar-scale', **scale_dropdown_args),
            dcc.Dropdown(id='grp-bar-status', **status_dropdown_args),
        ]
    ),
    html.Div(className="graph-box",
        children=[
            dcc.Graph(id='teams-bar'),
            dcc.Dropdown(id='teams-bar-barmode', **barmode_dropdown_args),
            dcc.Dropdown(id='teams-bar-ptheme', **ptheme_dropdown_args),
            dcc.Dropdown(id='teams-bar-scale', **scale_dropdown_args),
            dcc.Dropdown(id='teams-bar-status', **status_dropdown_args),
        ]
    ),
    html.Div(className="graph-box",
        children=[
            dcc.Graph(id='external-bar'),
            dcc.Dropdown(id='external-bar-barmode', **barmode_dropdown_args),
            dcc.Dropdown(id='external-bar-ptheme', **ptheme_dropdown_args),
            dcc.Dropdown(id='external-bar-scale', **scale_dropdown_args),
            dcc.Dropdown(id='external-bar-status', **status_dropdown_args),
        ]
    ),
    html.Div(className="graph-box",
        children=[
            html.Div(className="graph-title", children=[html.H3('Intra-project Team relationships'),]),
            cyto.Cytoscape(id='teams-graph', **graph_layout_default_args),
            dcc.Dropdown(id='teams-graph-layout', **graph_layout_dropdown_args),
            dcc.Dropdown(id='teams-graph-ptheme', **ptheme_dropdown_args),
            dcc.Dropdown(id='teams-graph-scale', **scale_dropdown_args),
            dcc.Dropdown(id='teams-graph-status', **status_dropdown_args),
        ]
    ),
    html.Div(className="graph-box",
        children=[
            dcc.Graph(id='proj-gantt'),
            dcc.Dropdown(id='proj-gantt-ptheme', **ptheme_dropdown_args),
            dcc.Dropdown(id='proj-gantt-teams', **teams_dropdown_args),
            dcc.Dropdown(id='proj-gantt-scale', **scale_dropdown_args),
            dcc.Dropdown(id='proj-gantt-status', **status_dropdown_args),
        ]
    ),
    #html.Div(className="graph-box",
    #    children=[
    #        dash_table.DataTable(
    #            style_data={'whiteSpace': 'normal'},
    #            css=[{
    #                'selector': '.dash-cell div.dash-cell-value',
    #                'rule': 'display: inline; white-space: inherit; overflow: inherit; text-overflow: inherit;'
    #            }],
    #            id='table',
    #            columns=[{"name": i, "id": i} for i in df.columns],
    #            data=df.to_dict("rows"),
    #        )
    #    ]
    #),    
]) 

# Callbacks and related helper methods
def input_scale(base_id):
    return Input('{0}-scale'.format(base_id), 'value')

def input_status(base_id):
    return Input('{0}-status'.format(base_id), 'value')

def input_barmode(base_id):
    return Input('{0}-barmode'.format(base_id), 'value')

def input_teams(base_id):
    return Input('{0}-teams'.format(base_id), 'value')

def input_ptheme(base_id):
    return Input('{0}-ptheme'.format(base_id), 'value')

def input_theme_type(base_id):
    return Input('{0}-themes'.format(base_id), 'value')

def bar_input_params(base_id, input_list):
    inputs = [] #[input_scale(base_id), input_status(base_id), input_barmode(base_id)]
    if 'scale' in input_list:
        inputs.append(input_scale(base_id))

    if 'status' in input_list:
        inputs.append(input_status(base_id))

    if 'mode' in input_list:
        inputs.append(input_barmode(base_id))

    if 'team' in input_list:
        inputs.append(input_teams(base_id))

    if 'ptheme' in input_list:
        inputs.append(input_ptheme(base_id))

    if 'theme_type' in input_list:
        inputs.append(input_theme_type(base_id)) 
    return inputs

def gantt_input_params(base_id):
    return [input_scale(base_id), input_status(base_id), input_teams(base_id), input_ptheme(base_id)]

def graph_input_params_data(base_id):
    return [input_scale(base_id), input_status(base_id), input_ptheme(base_id)]
    
def graph_input_params_layout(base_id):
    return [Input('{0}-layout'.format(base_id), 'value')]

@app.callback(Output('status-bar', 'figure'), bar_input_params('status-bar', ['scale', 'mode', 'team', 'ptheme']))
def update_status_bar(scale, mode, teams, ptheme):
    return bar_return_dict(scale, [], mode, col_name('status'), 'Project Statuses', teams, ptheme, False, {'b':25})

@app.callback(Output('pthemes-bar', 'figure'), bar_input_params('pthemes-bar', ['scale', 'status', 'mode', 'team', 'theme_type']))
def update_pthemes_bar(scale, status, mode, teams, themes):
    if themes == 'p_theme':
        return bar_return_dict(scale, status, mode, col_name(themes), 'Projects by Primary Themes', teams)
    elif themes == 's_themes':
        return bar_return_dict(scale, status, mode, col_name(themes), 'Projects by Secondary Themes', teams, '', True, {'b':25})
    else: 
        return bar_return_dict(scale, status, mode, col_name(themes), 'Projects by Primary and Secondary Themes', teams, '', True, {'b':25})

# start theme-graph 
@app.callback(Output('theme-graph', 'elements'), graph_input_params_data('theme-graph'))
def update_theme_graph_data(scale, status, ptheme):
    return graph_elements(col_name('all_themes'), scale, status, ptheme)

@app.callback(Output('theme-graph', 'layout'), graph_input_params_layout('theme-graph'))
def update_theme_graph_layout(layout):
    return {'name': layout, 'animate': True}

@app.callback(Output('theme-graph', 'stylesheet'), [Input('theme-graph', 'tapNode')])
def update_theme_graph_stylesheet(node):
    if not node:
        return default_graph_stylesheet  
    return graph_stylesheet(node)
# end theme-graph 

@app.callback(Output('grp-bar', 'figure'), bar_input_params('grp-bar', ['scale', 'status', 'mode', 'team', 'ptheme']))
def update_grp_bar(scale, status, mode, teams, ptheme):
    return bar_return_dict(scale, status, mode, col_name('grouping'), 'Project Groupings', teams, ptheme, False, {'b':140})

@app.callback(Output('teams-bar', 'figure'), bar_input_params('teams-bar', ['scale', 'status', 'mode', 'ptheme']))
def update_teams_bar(scale, status, mode, ptheme):
    return bar_return_dict(scale, status, mode, col_name('teams'), 'Projects by Library Teams', [], ptheme, True, {'b':120})

@app.callback(Output('external-bar', 'figure'), bar_input_params('external-bar', ['scale', 'status', 'mode', 'ptheme']))
def update_external_bar(scale, status, mode, ptheme):
    return bar_return_dict(scale, status, mode, col_name('external'), 'Projects by external entities involved', [], ptheme, True, {'b':120})

# start teams-graph 
@app.callback(Output('teams-graph', 'elements'), graph_input_params_data('teams-graph'))
def update_teams_graph_data(scale, status, ptheme):
    return graph_elements(col_name('teams'), scale, status, ptheme)

@app.callback(Output('teams-graph', 'layout'), graph_input_params_layout('teams-graph'))
def update_teams_graph_layout(layout):
    return {'name': layout, 'animate': True}

@app.callback(Output('teams-graph', 'stylesheet'), [Input('teams-graph', 'tapNode')])
def update_teams_graph_stylesheet(node):
    if not node:
        return default_graph_stylesheet  
    return graph_stylesheet(node)
# end teams-graph    

@app.callback(Output('proj-gantt', 'figure'), gantt_input_params('proj-gantt'))
def update_proj_gantt(scale, status, teams, ptheme):
    return gantt_data(scale, status, "Project Gantt Chart", teams, ptheme)


# Initiate app
if __name__ == '__main__':
    app.run_server(debug=True)
