from flask import Flask, render_template, request, redirect, url_for, session
from pydantic import BaseModel, field_validator
from datetime import datetime, timedelta, timezone
# import uuid
from azure.identity import ManagedIdentityCredential, DefaultAzureCredential
from azure.monitor.query import LogsQueryClient, LogsQueryStatus
from applicationinsights.flask.ext import AppInsights
import logging
import os

app = Flask(__name__)
app.secret_key = "computehealth"

# Set up Application Insights for the web app
app.config['APPINSIGHTS_INSTRUMENTATIONKEY'] = 'e813553d-3352-4bd7-bb2d-843b95d0b2c3'
appinsights = AppInsights(app)
app.logger.setLevel(logging.DEBUG)

# This makes datetime, timedelta, and timezone available in all templates
@app.context_processor
def inject_datetime():
    return dict(datetime=datetime, timedelta=timedelta, timezone=timezone)


@app.route("/", methods = ["POST", "GET"])
def get_params():
    ## set default values
    if "workspaceId" not in session:
        session["workspaceId"] = "f38e815f-79eb-4d78-8a05-2dff4e55453f" 
    if "startTime" not in session:
        session["startTime"] = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S")
    if "endTime" not in session:
        session["endTime"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    if request.method == "POST":
        session["workspaceId"] = request.form["workspaceId"]
        session["startTime"] = request.form["startTime"]
        session["endTime"] = request.form["endTime"]
        return redirect(url_for("get_chart"))
    else:
        return render_template("landing.html", workspaceId=session["workspaceId"], startTime=session["startTime"], endTime=session["endTime"])

@app.route("/charts", methods = ["POST","GET"])
def get_chart():
    if request.method == "POST":
        session["workspaceId"] = request.form["workspaceId"]
        session["startTime"] = request.form["startTime"]
        session["endTime"] = request.form["endTime"]
    app.logger.debug('Create Log Analytics client')
    ## authenticate
    credential = DefaultAzureCredential() # after pushing to the Azure cloud, this function will use the MSI instead. Please remember to assign the masterreader's role to the MSI. 
    #credential = ManagedIdentityCredential(client_id = "1133145e-4000-4719-957b-5abd09c56c48") # use a user-assigned managed identity
    logs_query_client = LogsQueryClient(credential)

    # Data to be passed to the template
    p = Params(workspaceid=session["workspaceId"], metricname="UserErrorExcludedABTaskFailureRate", starttime_str=session["startTime"], endtime_str=session["endTime"])
    labels, data = GetMetric(p, logs_query_client)

    p = Params(workspaceid=session["workspaceId"], metricname="ABTaskCancelRate", starttime_str=session["startTime"], endtime_str=session["endTime"])
    labels_jobcount, data_jobcount = GetMetric(p, logs_query_client)

    p = Params(workspaceid=session["workspaceId"], metricname="ABTaskE2ETime", starttime_str=session["startTime"], endtime_str=session["endTime"])
    labels_token, data_token = GetMetric(p, logs_query_client)

    p = Params(workspaceid=session["workspaceId"], metricname="DebugInfo_FailedAndCancelledABTasks", starttime_str=session["startTime"], endtime_str=session["endTime"])
    jobs = GetDebugInfo(p, logs_query_client)
    
    appinsights.flush() # force flushing application insights handler

    return render_template("index.html", request = request\
                , labels = labels, data = data, jobs = jobs\
                    , labels_jobcount = labels_jobcount, data_jobcount = data_jobcount\
                    , labels_token = labels_token, data_token = data_token\
                        , workspaceId = session["workspaceId"], startTime = session["startTime"], endTime = session["endTime"])

if __name__ == '__main__':  
   app.run()

class Params(BaseModel):
    workspaceid: str
    metricname: str
    starttime_str: str
    endtime_str: str

    # @field_validator("workspaceid") 
    # def validate_workspaceid(cls, value):
    #     try:
    #         uuid.UUID(value, version=4)
    #     except ValueError:
    #         raise ValueError(f"{value} is not a valid GUID")
    #     return value

    @field_validator("starttime_str")
    def validate_starttime(cls, value):
        try:
            datetime.strptime(value, "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            raise ValueError(f"{value} does not match format '%Y-%m-%dT%H:%M:%S'")
        return value
    
    @field_validator("endtime_str")
    def validate_endtime(cls, value):
        try:
            datetime.strptime(value, "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            raise ValueError(f"{value} does not match format '%Y-%m-%dT%H:%M:%S'")
        return value
    
    @field_validator("metricname")
    def validate_metricname(cls, value):
        try:
            value in ("ABTaskE2ETime", "UserErrorExcludedABTaskFailureRate", "ABTaskCancelRate", "DebugInfo_FailedAndCancelledABTasks")
        except ValueError:
            raise ValueError(f"The metric {value} has not been defined yet.") 
        return value

def GetQuery(metricname: str) -> str:
    
    ## debugging file not found error
    current_dir = os.getcwd()
    files = os.listdir(current_dir)
    metricsfiles = os.listdir(f"{current_dir}/metrics")
    app.logger.debug(f"Files in the current directory: {', '.join(files)}")
    app.logger.debug(f"Files in the metrics folder: {', '.join(metricsfiles)}")

    with open(f"./metrics/{metricname}.txt", "r") as file:
        query = file.read()
    return query
    
def GetMetric(p: Params, logs_query_client):
    
    app.logger.debug('Initialize variables used in the query')
    ## convert params
    starttime = datetime.strptime(p.starttime_str, "%Y-%m-%dT%H:%M:%S")
    endtime = datetime.strptime(p.endtime_str, "%Y-%m-%dT%H:%M:%S")
    query = GetQuery(p.metricname)
    query = query.format(starttime_str = p.starttime_str, endtime_str = p.endtime_str, workspaceid = p.workspaceid)

    app.logger.debug('Fetch data from the TML')
    response = logs_query_client.query_workspace(
        workspace_id="42be50a4-118c-4aca-81ae-a59709b406e0", 
        query=query,
        timespan=(starttime, endtime)
        )
    if response.status == LogsQueryStatus.SUCCESS:
        data = response.tables
    else:
        # LogsQueryPartialResult
        data = response.partial_data
    
    values = [] 
    days = []

    app.logger.debug('Reformat the output')
    table = data[0] # because batch query is not used here
    value_idx = table.columns.index(p.metricname) # assume that the query always return a column called metricname (need to be more flexible)
    day_idx = table.columns.index("Day") # assume that the query always return a column called "Day"
    for row in table.rows:
        value = row[value_idx] # float type
        day = row[day_idx] # datetime type
        values.append(value)
        days.append(day)
    return days, values

def GetDebugInfo(p: Params, logs_query_client):
    starttime = datetime.strptime(p.starttime_str, "%Y-%m-%dT%H:%M:%S")
    endtime = datetime.strptime(p.endtime_str, "%Y-%m-%dT%H:%M:%S")
    query = GetQuery(p.metricname)
    query = query.format(starttime_str = p.starttime_str, endtime_str = p.endtime_str, workspaceid = p.workspaceid)

    app.logger.debug('Fetch data from the TML')
    response = logs_query_client.query_workspace(
        workspace_id="42be50a4-118c-4aca-81ae-a59709b406e0", 
        query=query,
        timespan=(starttime, endtime)
        )
    if response.status == LogsQueryStatus.SUCCESS:
        data = response.tables
    else:
        # LogsQueryPartialResult
        data = response.partial_data

    debuginfo = []
    for table in data:
        cols = table.columns
        for row in table.rows:
            debuginfo.append(dict(zip(cols, row)))

    return debuginfo