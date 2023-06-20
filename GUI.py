import dash
from dash.dependencies import Output, Input
from dash import dcc
from dash import html
from dash.dependencies import Output, Input
import plotly.graph_objs as go
from plotly.subplots import make_subplots
import paho.mqtt.client as mqtt
from datetime import datetime
import csv
import pandas as pd
import serial
import atexit



# File settings
output_file = "GUI.csv"
# CSV Header 
header = ["Timestamp", "Volt_RMS", "Current_RMS", "Real_Power","PF","RAW_Packet"]



# Predefined list of commands
commands = [
    "v", #Check the voltage reported by the EBM
    "i", #Check the current reported by the EBM
    "y", #Check the volt-amphere reported by the EBM
    "p", #Check the power factor reported by the EBM
    "s", #Check the status of the EBM
]

def read_MTB_status(commands):
    vs = 0
    i = 0
    va = 0
    pf = 0
    s = 0
    for command in commands:
        
        # Append a carriage return (CR) to the command
        command += '\r'

        # Send the command over the serial port
        port.write(command.encode())

        # Read the response from the serial port
        response = port.readline().decode().strip('\r')

        match response[0]:
            case 'v':
                vs = float(response.strip('vs'))
            case 'i':
                i = float(response.strip('i').strip())
            case 'y':
                va = float(response.strip('y').strip())
            case 'p':
                pf = float(response.strip('ps').strip())
            case 's':
                s = float(response.strip('s').strip())
            case _:
                print("Error:",str(response))
    return [vs,i,va,pf,s]






def compare_last_line(csv_file, new_data):
    last_row = ""
    with open(csv_file, "r") as file:
        reader = csv.reader(file)
        for row in reader:
            last_row = row
    return last_row == new_data

#parsing function
def parse(dec_pl):

    print(read_MTB_status(commands))

    Time = dec_pl.split(",")[1]
    Time = (Time.split(":")[-1])
    timestamp = int(Time)
    Time = datetime.fromtimestamp(timestamp / 1000.0)

    V_rms = dec_pl.split(",")[3]
    V_rms = float(V_rms.split(":")[-1])

    I_rms = dec_pl.split(",")[4]
    I_rms = float(I_rms.split(":")[-1])

    if (I_rms == 0):
        I_rms = 0.0000000000000001

    Real_Power = dec_pl.split(",")[6]
    Real_Power = float(Real_Power.split(":")[-1])

    PF =  Real_Power / (V_rms * I_rms)
            
    data = [Time,V_rms,I_rms,Real_Power,PF,dec_pl]

    if V_rms == -1:
        return None
     
    return data


# MQTT broker settings
broker_address = "10.0.0.45"
broker_port = 1883
topic = "us/01973988"

# MQTT broker credentials
username = "sem-rabbitmq"
password = "sem-rabbitmq123"


app = dash.Dash(__name__)
colors = {
    'background': 'black',
    'text': '#7FDBFF'
}
app.layout = html.Div(className="app-body",style={'backgroundColor': colors['background']},
    children = [
        html.Div(style={'width': '49%', 'display': 'inline-block'}, children=[
        dcc.Graph(id='gauge', animate=False),
        dcc.Interval(id='interval',interval=15000,n_intervals = 0),
        dcc.Store(id="clientside-data",data = []),
        ]),

        html.Div(style={'width': '44%', 'display': 'inline-block'}, children=[
        dcc.Graph(id='power_factor', animate=False),
        ]),

        html.Div(style={'width': '5%', 'display': 'inline-block'}, children=[
        dcc.Checklist(['Reset', 'Append', 'Pause'],
                      style={'whiteSpace': 'pre-line',"color": colors['text']})
        ]),

        html.Div(style={'width': '85%', 'display': 'inline-block'}, children=[
        dcc.Graph(id='power', animate=False),
        ]),

        html.Div(style={'width': '15%', 'display': 'inline-block'}, children=[
        html.H3("Last Raw Packet"),
        html.Div(id='my-output', style={'whiteSpace': 'pre-line',"color": colors['text']}), 
        ]),
        
    ]
)

# MQTT client callbacks
def on_connect(client, userdata, flags, rc):
    print("Connected to MQTT broker")
    client.subscribe(topic)

# MQTT client setup
def on_message(client, userdata, msg):
    global Time, Volt
    # Assuming the payload is a single float value
    dec = msg.payload.decode()            
    if dec[2] == 'S':
        if not compare_last_line(output_file, parse(dec)):
            with open(output_file, "a", newline="") as file:
                writer = csv.writer(file)
                writer.writerow(parse(dec))


def on_disconnect(client, userdata, rc):
    print("Disconnected from MQTT broker")

# Create MQTT client instance
client = mqtt.Client()

# Set username and password for MQTT broker authentication
client.username_pw_set(username, password)

# Assign callbacks
client.on_connect = on_connect
client.on_message = on_message
client.on_disconnect = on_disconnect

# Connect to MQTT broker
client.connect(broker_address, broker_port)    

# Start MQTT loop
client.loop_start()



@app.callback(
    Output('clientside-data', 'data'),
    Input('interval', 'n_intervals')
    )
def update_graph_scatter(n):
    df = pd.read_csv("GUI.csv")
    Time = df['Timestamp']
    V_rms = df['Volt_RMS'].to_numpy()
    I_rms = df['Current_RMS'].to_numpy()
    Real_Power = df['Real_Power'].to_numpy()
    PF = df['PF'].to_numpy()
    VA = V_rms * I_rms
    last_entry = df.tail(1)
    plot_data = {'Time':list(Time),'Vrms':list(V_rms),'Irms':list(I_rms),
                 'Real_Power':list(Real_Power),'PF':list(PF),'VA':list(VA) ,'Raw':last_entry['RAW_Packet'] }
    return plot_data


@app.callback(Output(component_id='my-output', component_property='children'),
        [Input('clientside-data', 'data'),]
        )
def update_string(data):
    packet_string = ''.join(data['Raw'])
    packet_string = packet_string.replace(",", "\n")
    return '{}'.format(packet_string)

@app.callback(Output('gauge', 'figure'),
        Input('clientside-data', 'data'),
        )

def update_graph_scatter(data):
    fig = make_subplots(
    rows=2,
    cols=2,                   
    specs=[[{'type': 'indicator'}, {'type': 'indicator'}],
    [{'type': 'indicator'}, {'type': 'indicator'}]],horizontal_spacing = 0.15,
    vertical_spacing = 0.3
    )
    
    fig.add_trace(go.Indicator(
        name = "power_trace",
        value=float(data['Real_Power'][-1]),
            mode="gauge+number",
            title={'text': "Power"},
            number = {'valueformat':'.2f','suffix': 'W'},
            
            gauge={'axis': {'range': [None, 18400]},
            'bar': {'color': "black"},
            'steps': [
                {'range': [0, 13800], 'color': "green"},
                {'range': [13800, 16100], 'color': "orange"},
                {'range': [16100, 18400], 'color': "red"}],}),
            row=1,
            col=1,)
    
    fig.add_trace(go.Indicator(
        name = "pf_trace",
        value=data['PF'][-1],
        mode="gauge+number",
        title={'text': "Power factor, cos(φ)"},
        number = {'valueformat':'.3f'},
        gauge={'axis': {'range': [None, 1.0]},
           'bar': {'color': "black"},
           'steps': [
               {'range': [0.8, 1.0], 'color': "green"},
               {'range': [0.4, 0.8], 'color': "orange"},
               {'range': [0, 0.4], 'color': "red"}],}),
           row=1,
           col=2,)
    
    fig.add_trace(go.Indicator(
        name = "volt_trace",
        value=float(data['Vrms'][-1]),
        mode="gauge+number",
        title={'text': 'Volts'},
        number = {'valueformat':'.2f','suffix': 'V'},
        gauge={'axis': {'range': [207, 253]},
           'bar': {'color': "black"},
           'steps': [
               {'range': [207, 210], 'color': "red"},
               {'range': [210, 220], 'color': "orange"},
               {'range': [220, 240], 'color': "green"},
               {'range': [240, 250], 'color': "orange"},
               {'range': [250, 253], 'color': "red"}],}),
           row=2,
           col=1,)
           
    
    fig.add_trace(go.Indicator(
        name = "current_trace",
        value=float(data['Irms'][-1]),
        mode="gauge+number",
        title={'text': 'Current',},
        number = {'valueformat':'.2f','suffix': 'A'},
        gauge={'axis': {'range': [None, 80]},
        'bar': {'color': "black"},
        'steps': [
            {'range': [0, 60], 'color': "green"},
             {'range': [60, 70], 'color': "orange"},
            {'range': [70, 80], 'color': "red"}],}),
        row=2,
        col=2,)
    fig.update_layout(
        plot_bgcolor=colors['background'],
        paper_bgcolor=colors['background'],
        font_color=colors['text'],
        font=dict(family="Courier New, monospace",size=18)
    )
    
    return fig

@app.callback(Output('power', 'figure'),
        Input('clientside-data', 'data'),
        )

def update_graph_scatter(data):
    fig = go.Figure()
    fig.add_trace(go.Scattergl(
        name = "Real Power(W)",
        x = data['Time'],
        y = data['Real_Power'],
        mode='markers+lines',
        marker=dict(size=10,color='yellow'),
        ))
    fig.add_trace(go.Scattergl(
        name = "Apparent Power(S)",
        x = data['Time'],
        y = data['VA'],
        mode='markers+lines',
        marker=dict(size=10,color='green'),
        ))
    fig.update_layout(
        title="Power",
        title_x=0.5,
        xaxis_title="Time",
        yaxis_title="Power",
        legend_title="Legend Title",
        plot_bgcolor=colors['background'],
        paper_bgcolor=colors['background'],
        font=dict(family="Courier New, monospace",size=18,color=colors['text'])
    )
    return fig


@app.callback(Output('power_factor', 'figure'),
        Input('clientside-data', 'data'),
        )

def update_graph_scatter(data):
    fig = go.Figure()
    fig.add_trace(go.Scattergl(
        name = "Power Factor",
        x = data['Time'],
        y = data['PF'],
        mode='markers+lines',
        marker=dict(size=10,color='yellow'),
        ))
    fig.update_layout(
        title="Power Factor",
        title_x=0.5,
        xaxis_title="Time",
        yaxis_title="Cos(φ)",
        legend_title="Legend Title",
        plot_bgcolor=colors['background'],
        paper_bgcolor=colors['background'],
        font=dict(family="Courier New, monospace",size=18,color=colors['text'])
    )
    return fig

# Function to close the COM port
def close_com_port():
    if port is not None:
        port.close()
        print("COM port closed.")

# Register the close_com_port function to be called on program exit
atexit.register(close_com_port)

if __name__ == '__main__':

    # Configure the serial port
    port = serial.Serial('COM21', baudrate=2400, stopbits=serial.STOPBITS_TWO, timeout=1)

    with open(output_file, "w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(header)

    # Run the Dash app
    app.run_server(debug=False)

    # Close the serial port
    port.close()
