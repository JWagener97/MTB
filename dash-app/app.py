import dash
import dash_bootstrap_components as dbc

APP_TITLE = "Plotly Dash"
app = dash.Dash(
    __name__,
    title=APP_TITLE,
    update_title="Loading...",
    suppress_callback_exceptions=True,
    external_stylesheets=[dbc.themes.FLATLY],
)
