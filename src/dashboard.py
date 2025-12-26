import logging
import random, shutil, sqlite3, configparser, hashlib, ipaddress, json, os, secrets, subprocess
import time, re, uuid, bcrypt, psutil, pyotp, threading
import traceback
from uuid import uuid4
from zipfile import ZipFile
from datetime import datetime, timedelta

import sqlalchemy
from jinja2 import Template
from flask import Flask, request, render_template, session, send_file
from flask_cors import CORS
from icmplib import ping, traceroute
from flask.json.provider import DefaultJSONProvider
from itertools import islice

from sqlalchemy import RowMapping

from modules.Utilities import (
    RegexMatch, StringToBoolean,
    ValidateIPAddressesWithRange, ValidateDNSAddress,
    GenerateWireguardPublicKey, GenerateWireguardPrivateKey
)
from packaging import version
from modules.Email import EmailSender
from modules.DashboardLogger import DashboardLogger
from modules.PeerJob import PeerJob
from modules.SystemStatus import SystemStatus
from modules.PeerShareLinks import PeerShareLinks
from modules.PeerJobs import PeerJobs
from modules.DashboardConfig import DashboardConfig
from modules.WireguardConfiguration import WireguardConfiguration
from modules.AmneziaWireguardConfiguration import AmneziaWireguardConfiguration

from client import createClientBlueprint

from logging.config import dictConfig

from modules.DashboardClients import DashboardClients
from modules.DashboardPlugins import DashboardPlugins
from modules.DashboardWebHooks import DashboardWebHooks
from modules.NewConfigurationTemplates import NewConfigurationTemplates
from modules.NodesManager import NodesManager
from modules.IPAllocationManager import IPAllocationManager
from modules.NodeSelector import NodeSelector
from modules.DriftDetector import DriftDetector
from modules.ConfigNodesManager import ConfigNodesManager
from modules.NodeInterfacesManager import NodeInterfacesManager
from modules.EndpointGroupsManager import EndpointGroupsManager
from modules.CloudflareDNSManager import CloudflareDNSManager
from modules.PeerMigrationManager import PeerMigrationManager
from modules.AuditLogManager import AuditLogManager

class CustomJsonEncoder(DefaultJSONProvider):
    def __init__(self, app):
        super().__init__(app)

    def default(self, o):
        if callable(getattr(o, "toJson", None)):
            return o.toJson()
        if type(o) is RowMapping:
            return dict(o)
        if type(o) is datetime:
            return o.strftime("%Y-%m-%d %H:%M:%S")
        return super().default(self)



'''
Response Object
'''
def ResponseObject(status=True, message=None, data=None, status_code = 200) -> Flask.response_class:
    response = Flask.make_response(app, {
        "status": status,
        "message": message,
        "data": data
    })
    response.status_code = status_code
    response.content_type = "application/json"
    return response

'''
Flask App
'''
app = Flask("WGDashboard", template_folder=os.path.abspath("./static/dist/WGDashboardAdmin"))

def peerInformationBackgroundThread():
    global WireguardConfigurations
    app.logger.info("Background Thread #1 Started")
    app.logger.info("Background Thread #1 PID:" + str(threading.get_native_id()))
    delay = 6
    time.sleep(10)
    while True:
        with app.app_context():
            try:
                curKeys = list(WireguardConfigurations.keys())
                for name in curKeys:
                    if name in WireguardConfigurations.keys() and WireguardConfigurations.get(name) is not None:
                        c = WireguardConfigurations.get(name)
                        if c.getStatus():
                            c.getPeersLatestHandshake()
                            c.getPeersTransfer()
                            c.getPeersEndpoint()
                            c.getPeers()
                            if delay == 6:
                                if c.configurationInfo.PeerTrafficTracking:
                                    c.logPeersTraffic()
                                if c.configurationInfo.PeerHistoricalEndpointTracking:
                                    c.logPeersHistoryEndpoint()
                            c.getRestrictedPeersList()
            except Exception as e:
                app.logger.error(f"[WGDashboard] Background Thread #1 Error", e)

        if delay == 6:
            delay = 1
        else:
            delay += 1
        time.sleep(10)

def peerJobScheduleBackgroundThread():
    with app.app_context():
        app.logger.info(f"Background Thread #2 Started")
        app.logger.info(f"Background Thread #2 PID:" + str(threading.get_native_id()))
        time.sleep(10)
        while True:
            try:
                AllPeerJobs.runJob()
                time.sleep(180)
            except Exception as e:
                app.logger.error("Background Thread #2 Error", e)

def nodeHealthPollingBackgroundThread():
    """Background thread for polling node health and peer stats"""
    global NodesManager, IPAllocManager, NodeSelector
    with app.app_context():
        app.logger.info(f"Background Thread #3 (Node Health) Started")
        app.logger.info(f"Background Thread #3 PID:" + str(threading.get_native_id()))
        time.sleep(15)  # Initial delay
        while True:
            try:
                enabled_nodes = NodesManager.getEnabledNodes()
                
                for node in enabled_nodes:
                    try:
                        # Get agent client
                        client = NodesManager.getNodeAgentClient(node.id)
                        if not client:
                            continue
                        
                        # Poll health endpoint
                        health_success, health_data = client.get_health()
                        
                        health_info = {}
                        if health_success:
                            health_info['status'] = 'online'
                            health_info['health'] = health_data if isinstance(health_data, dict) else {}
                        else:
                            health_info['status'] = 'offline'
                            health_info['error'] = health_data
                        
                        # Poll WireGuard dump if node is online
                        if health_success and node.wg_interface:
                            dump_success, dump_data = client.get_wg_dump(node.wg_interface)
                            if dump_success:
                                health_info['wg_dump'] = dump_data if isinstance(dump_data, dict) else {}
                        
                        # Update node health in database
                        NodesManager.updateNodeHealth(node.id, health_info)
                        
                    except Exception as e:
                        app.logger.error(f"Error polling node {node.id}: {e}")
                        # Mark node as offline on error
                        NodesManager.updateNodeHealth(node.id, {
                            'status': 'error',
                            'error': str(e)
                        })
                
                time.sleep(60)  # Poll every 60 seconds
            except Exception as e:
                app.logger.error(f"Node Health Polling Thread Error: {e}")
                time.sleep(60)

def gunicornConfig():
    _, app_ip = DashboardConfig.GetConfig("Server", "app_ip")
    _, app_port = DashboardConfig.GetConfig("Server", "app_port")
    return app_ip, app_port

def ProtocolsEnabled() -> list[str]:
    from shutil import which
    protocols = []
    if which('awg') is not None and which('awg-quick') is not None:
        protocols.append("awg")
    if which('wg') is not None and which('wg-quick') is not None:
        protocols.append("wg")
    return protocols

def InitWireguardConfigurationsList(startup: bool = False):
    if os.path.exists(DashboardConfig.GetConfig("Server", "wg_conf_path")[1]):
        confs = os.listdir(DashboardConfig.GetConfig("Server", "wg_conf_path")[1])
        confs.sort()
        for i in confs:
            if RegexMatch("^(.{1,}).(conf)$", i):
                i = i.replace('.conf', '')
                try:
                    if i in WireguardConfigurations.keys():
                        if WireguardConfigurations[i].configurationFileChanged():
                            with app.app_context():
                                WireguardConfigurations[i] = WireguardConfiguration(DashboardConfig, AllPeerJobs, AllPeerShareLinks, DashboardWebHooks, i)
                    else:
                        with app.app_context():
                            WireguardConfigurations[i] = WireguardConfiguration(DashboardConfig, AllPeerJobs, AllPeerShareLinks, DashboardWebHooks, i, startup=startup)
                except WireguardConfiguration.InvalidConfigurationFileException as e:
                    app.logger.error(f"{i} have an invalid configuration file.")

    if "awg" in ProtocolsEnabled():
        confs = os.listdir(DashboardConfig.GetConfig("Server", "awg_conf_path")[1])
        confs.sort()
        for i in confs:
            if RegexMatch("^(.{1,}).(conf)$", i):
                i = i.replace('.conf', '')
                try:
                    if i in WireguardConfigurations.keys():
                        if WireguardConfigurations[i].configurationFileChanged():
                            with app.app_context():
                                WireguardConfigurations[i] = AmneziaWireguardConfiguration(DashboardConfig, AllPeerJobs, AllPeerShareLinks, DashboardWebHooks, i)
                    else:
                        with app.app_context():
                            WireguardConfigurations[i] = AmneziaWireguardConfiguration(DashboardConfig, AllPeerJobs, AllPeerShareLinks, DashboardWebHooks, i, startup=startup)
                except WireguardConfiguration.InvalidConfigurationFileException as e:
                    app.logger.error(f"{i} have an invalid configuration file.")

def startThreads():
    bgThread = threading.Thread(target=peerInformationBackgroundThread, daemon=True)
    bgThread.start()
    scheduleJobThread = threading.Thread(target=peerJobScheduleBackgroundThread, daemon=True)
    scheduleJobThread.start()
    nodeHealthThread = threading.Thread(target=nodeHealthPollingBackgroundThread, daemon=True)
    nodeHealthThread.start()

dictConfig({
    'version': 1,
    'formatters': {'default': {
        'format': '[%(asctime)s] [%(levelname)s] in [%(module)s] %(message)s',
    }},
    'root': {
        'level': 'INFO'
    }
})


WireguardConfigurations: dict[str, WireguardConfiguration] = {}
CONFIGURATION_PATH = os.getenv('CONFIGURATION_PATH', '.')

app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 5206928
app.secret_key = secrets.token_urlsafe(32)
app.json = CustomJsonEncoder(app)
with app.app_context():
    SystemStatus = SystemStatus()
    DashboardConfig = DashboardConfig()
    EmailSender = EmailSender(DashboardConfig)
    AllPeerShareLinks: PeerShareLinks = PeerShareLinks(DashboardConfig, WireguardConfigurations)
    AllPeerJobs: PeerJobs = PeerJobs(DashboardConfig, WireguardConfigurations, AllPeerShareLinks)
    DashboardLogger: DashboardLogger = DashboardLogger()
    DashboardPlugins: DashboardPlugins = DashboardPlugins(app, WireguardConfigurations)
    DashboardWebHooks: DashboardWebHooks = DashboardWebHooks(DashboardConfig)
    NewConfigurationTemplates: NewConfigurationTemplates = NewConfigurationTemplates()
    NodesManager: NodesManager = NodesManager(DashboardConfig)
    IPAllocManager: IPAllocationManager = IPAllocationManager(DashboardConfig)
    NodeSelector: NodeSelector = NodeSelector(NodesManager)
    DriftDetector: DriftDetector = DriftDetector(DashboardConfig)
    ConfigNodesManager: ConfigNodesManager = ConfigNodesManager(DashboardConfig)
    NodeInterfacesManager: NodeInterfacesManager = NodeInterfacesManager(DashboardConfig)
    EndpointGroupsManager: EndpointGroupsManager = EndpointGroupsManager(DashboardConfig)
    CloudflareDNSManager: CloudflareDNSManager = CloudflareDNSManager()
    PeerMigrationManager: PeerMigrationManager = PeerMigrationManager(DashboardConfig, NodesManager, ConfigNodesManager)
    AuditLogManager: AuditLogManager = AuditLogManager(DashboardConfig)
    InitWireguardConfigurationsList(startup=True)
    DashboardClients: DashboardClients = DashboardClients(WireguardConfigurations)
    app.register_blueprint(createClientBlueprint(WireguardConfigurations, DashboardConfig, DashboardClients))

_, APP_PREFIX = DashboardConfig.GetConfig("Server", "app_prefix")
cors = CORS(app, resources={rf"{APP_PREFIX}/api/*": {
    "origins": "*",
    "methods": "DELETE, POST, GET, OPTIONS",
    "allow_headers": ["Content-Type", "wg-dashboard-apikey"]
}})
_, app_ip = DashboardConfig.GetConfig("Server", "app_ip")
_, app_port = DashboardConfig.GetConfig("Server", "app_port")
_, WG_CONF_PATH = DashboardConfig.GetConfig("Server", "wg_conf_path")

'''
API Routes
'''

@app.before_request
def auth_req():
    if request.method.lower() == 'options':
        return ResponseObject(True)        

    DashboardConfig.APIAccessed = False    
    authenticationRequired = DashboardConfig.GetConfig("Server", "auth_req")[1]
    d = request.headers
    if authenticationRequired:
        apiKey = d.get('wg-dashboard-apikey')
        apiKeyEnabled = DashboardConfig.GetConfig("Server", "dashboard_api_key")[1]
        if apiKey is not None and len(apiKey) > 0 and apiKeyEnabled:
            apiKeyExist = len(list(filter(lambda x : x.Key == apiKey, DashboardConfig.DashboardAPIKeys))) == 1
            DashboardLogger.log(str(request.url), str(request.remote_addr), Message=f"API Key Access: {('true' if apiKeyExist else 'false')} - Key: {apiKey}")
            if not apiKeyExist:
                DashboardConfig.APIAccessed = False
                response = Flask.make_response(app, {
                    "status": False,
                    "message": "API Key does not exist",
                    "data": None
                })
                response.content_type = "application/json"
                response.status_code = 401
                return response
            DashboardConfig.APIAccessed = True
        else:
            DashboardConfig.APIAccessed = False
            whiteList = [
                '/static/', 'validateAuthentication', 'authenticate', 'getDashboardConfiguration',
                'getDashboardTheme', 'getDashboardVersion', 'sharePeer/get', 'isTotpEnabled', 'locale',
                '/fileDownload',
                '/client'
            ]
            
            if (("username" not in session or session.get("role") != "admin") 
                    and (f"{(APP_PREFIX if len(APP_PREFIX) > 0 else '')}/" != request.path 
                    and f"{(APP_PREFIX if len(APP_PREFIX) > 0 else '')}" != request.path)
                    and len(list(filter(lambda x : x not in request.path, whiteList))) == len(whiteList)
            ):
                response = Flask.make_response(app, {
                    "status": False,
                    "message": "Unauthorized access.",
                    "data": None
                })
                response.content_type = "application/json"
                response.status_code = 401
                return response

@app.route(f'{APP_PREFIX}/api/handshake', methods=["GET", "OPTIONS"])
def API_Handshake():
    return ResponseObject(True)

@app.get(f'{APP_PREFIX}/api/validateAuthentication')
def API_ValidateAuthentication():
    token = request.cookies.get("authToken")
    if DashboardConfig.GetConfig("Server", "auth_req")[1]:
        if token is None or token == "" or "username" not in session or session["username"] != token:
            return ResponseObject(False, "Invalid authentication.")
    return ResponseObject(True)

@app.get(f'{APP_PREFIX}/api/requireAuthentication')
def API_RequireAuthentication():
    return ResponseObject(data=DashboardConfig.GetConfig("Server", "auth_req")[1])

@app.post(f'{APP_PREFIX}/api/authenticate')
def API_AuthenticateLogin():
    data = request.get_json()
    if not DashboardConfig.GetConfig("Server", "auth_req")[1]:
        return ResponseObject(True, DashboardConfig.GetConfig("Other", "welcome_session")[1])
    
    if DashboardConfig.APIAccessed:
        authToken = hashlib.sha256(f"{request.headers.get('wg-dashboard-apikey')}{datetime.now()}".encode()).hexdigest()
        session['role'] = 'admin'
        session['username'] = authToken
        resp = ResponseObject(True, DashboardConfig.GetConfig("Other", "welcome_session")[1])
        resp.set_cookie("authToken", authToken)
        session.permanent = True
        return resp
    valid = bcrypt.checkpw(data['password'].encode("utf-8"),
                           DashboardConfig.GetConfig("Account", "password")[1].encode("utf-8"))
    totpEnabled = DashboardConfig.GetConfig("Account", "enable_totp")[1]
    totpValid = False
    if totpEnabled:
        totpValid = pyotp.TOTP(DashboardConfig.GetConfig("Account", "totp_key")[1]).now() == data['totp']

    if (valid
            and data['username'] == DashboardConfig.GetConfig("Account", "username")[1]
            and ((totpEnabled and totpValid) or not totpEnabled)
    ):
        authToken = hashlib.sha256(f"{data['username']}{datetime.now()}".encode()).hexdigest()
        session['role'] = 'admin'
        session['username'] = authToken
        resp = ResponseObject(True, DashboardConfig.GetConfig("Other", "welcome_session")[1])
        resp.set_cookie("authToken", authToken)
        session.permanent = True
        DashboardLogger.log(str(request.url), str(request.remote_addr), Message=f"Login success: {data['username']}")
        return resp
    DashboardLogger.log(str(request.url), str(request.remote_addr), Message=f"Login failed: {data['username']}")
    if totpEnabled:
        return ResponseObject(False, "Sorry, your username, password or OTP is incorrect.")
    else:
        return ResponseObject(False, "Sorry, your username or password is incorrect.")

@app.get(f'{APP_PREFIX}/api/signout')
def API_SignOut():
    resp = ResponseObject(True, "")
    resp.delete_cookie("authToken")
    session.clear()
    return resp

@app.get(f'{APP_PREFIX}/api/getWireguardConfigurations')
def API_getWireguardConfigurations():
    InitWireguardConfigurationsList()
    return ResponseObject(data=[wc for wc in WireguardConfigurations.values()])

@app.get(f'{APP_PREFIX}/api/newConfigurationTemplates')
def API_NewConfigurationTemplates():
    return ResponseObject(data=NewConfigurationTemplates.GetTemplates())

@app.get(f'{APP_PREFIX}/api/newConfigurationTemplates/createTemplate')
def API_NewConfigurationTemplates_CreateTemplate():
    return ResponseObject(data=NewConfigurationTemplates.CreateTemplate().model_dump())

@app.post(f'{APP_PREFIX}/api/newConfigurationTemplates/updateTemplate')
def API_NewConfigurationTemplates_UpdateTemplate():
    data = request.get_json()
    template = data.get('Template', None)
    if not template:
        return ResponseObject(False, "Please provide template")
    
    status, msg = NewConfigurationTemplates.UpdateTemplate(template)
    return ResponseObject(status, msg)

@app.post(f'{APP_PREFIX}/api/newConfigurationTemplates/deleteTemplate')
def API_NewConfigurationTemplates_DeleteTemplate():
    data = request.get_json()
    template = data.get('Template', None)
    if not template:
        return ResponseObject(False, "Please provide template")

    status, msg = NewConfigurationTemplates.DeleteTemplate(template)
    return ResponseObject(status, msg)

@app.post(f'{APP_PREFIX}/api/addWireguardConfiguration')
def API_addWireguardConfiguration():
    data = request.get_json()
    requiredKeys = [
        "ConfigurationName", "Address", "ListenPort", "PrivateKey", "Protocol"
    ]
    for i in requiredKeys:
        if i not in data.keys():
            return ResponseObject(False, "Please provide all required parameters.")
    
    if data.get("Protocol") not in ProtocolsEnabled():
        return ResponseObject(False, "Please provide a valid protocol: wg / awg.")

    # Check duplicate names, ports, address
    for i in WireguardConfigurations.values():
        if i.Name == data['ConfigurationName']:
            return ResponseObject(False,
                                  f"Already have a configuration with the name \"{data['ConfigurationName']}\"",
                                  "ConfigurationName")

        if str(i.ListenPort) == str(data["ListenPort"]):
            return ResponseObject(False,
                                  f"Already have a configuration with the port \"{data['ListenPort']}\"",
                                  "ListenPort")

        if i.Address == data["Address"]:
            return ResponseObject(False,
                                  f"Already have a configuration with the address \"{data['Address']}\"",
                                  "Address")

    if "Backup" in data.keys():
        path = {
            "wg": DashboardConfig.GetConfig("Server", "wg_conf_path")[1],
            "awg": DashboardConfig.GetConfig("Server", "awg_conf_path")[1]
        }
     
        if (os.path.exists(os.path.join(path['wg'], 'WGDashboard_Backup', data["Backup"])) and
                os.path.exists(os.path.join(path['wg'], 'WGDashboard_Backup', data["Backup"].replace('.conf', '.sql')))):
            protocol = "wg"
        elif (os.path.exists(os.path.join(path['awg'], 'WGDashboard_Backup', data["Backup"])) and
              os.path.exists(os.path.join(path['awg'], 'WGDashboard_Backup', data["Backup"].replace('.conf', '.sql')))):
            protocol = "awg"
        else:
            return ResponseObject(False, "Backup does not exist")
        
        shutil.copy(
            os.path.join(path[protocol], 'WGDashboard_Backup', data["Backup"]),
            os.path.join(path[protocol], f'{data["ConfigurationName"]}.conf')
        )
        WireguardConfigurations[data['ConfigurationName']] = (
            WireguardConfiguration(DashboardConfig, AllPeerJobs, AllPeerShareLinks, data=data, name=data['ConfigurationName'])) if protocol == 'wg' else (
            AmneziaWireguardConfiguration(DashboardConfig, AllPeerJobs, AllPeerShareLinks, DashboardWebHooks, data=data, name=data['ConfigurationName']))
    else:
        WireguardConfigurations[data['ConfigurationName']] = (
            WireguardConfiguration(DashboardConfig, AllPeerJobs, AllPeerShareLinks, DashboardWebHooks, data=data)) if data.get('Protocol') == 'wg' else (
            AmneziaWireguardConfiguration(DashboardConfig, AllPeerJobs, AllPeerShareLinks, DashboardWebHooks, data=data))
    return ResponseObject()

@app.get(f'{APP_PREFIX}/api/toggleWireguardConfiguration')
def API_toggleWireguardConfiguration():
    configurationName = request.args.get('configurationName')
    if configurationName is None or len(
            configurationName) == 0 or configurationName not in WireguardConfigurations.keys():
        return ResponseObject(False, "Please provide a valid configuration name", status_code=404)
    toggleStatus, msg = WireguardConfigurations[configurationName].toggleConfiguration()
    return ResponseObject(toggleStatus, msg, WireguardConfigurations[configurationName].Status)

@app.post(f'{APP_PREFIX}/api/updateWireguardConfiguration')
def API_updateWireguardConfiguration():
    data = request.get_json()
    requiredKeys = ["Name"]
    for i in requiredKeys:
        if i not in data.keys():
            return ResponseObject(False, "Please provide these following field: " + ", ".join(requiredKeys))
    name = data.get("Name")
    if name not in WireguardConfigurations.keys():
        return ResponseObject(False, "Configuration does not exist", status_code=404)
    
    status, msg = WireguardConfigurations[name].updateConfigurationSettings(data)
    
    return ResponseObject(status, message=msg, data=WireguardConfigurations[name])

@app.post(f'{APP_PREFIX}/api/updateWireguardConfigurationInfo')
def API_updateWireguardConfigurationInfo():
    data = request.get_json()
    name = data.get('Name')
    key = data.get('Key')
    value = data.get('Value')
    if not all([data, key, name]):
        return ResponseObject(status=False, message="Please provide configuration name, key and value")
    if name not in WireguardConfigurations.keys():
        return ResponseObject(False, "Configuration does not exist", status_code=404)
    
    status, msg, key = WireguardConfigurations[name].updateConfigurationInfo(key, value)
    
    return ResponseObject(status=status, message=msg, data=key)

@app.get(f'{APP_PREFIX}/api/getWireguardConfigurationRawFile')
def API_GetWireguardConfigurationRawFile():
    configurationName = request.args.get('configurationName')
    if configurationName is None or len(
            configurationName) == 0 or configurationName not in WireguardConfigurations.keys():
        return ResponseObject(False, "Please provide a valid configuration name", status_code=404)
    
    return ResponseObject(data={
        "path": WireguardConfigurations[configurationName].configPath,
        "content": WireguardConfigurations[configurationName].getRawConfigurationFile()
    })

@app.post(f'{APP_PREFIX}/api/updateWireguardConfigurationRawFile')
def API_UpdateWireguardConfigurationRawFile():
    data = request.get_json()
    configurationName = data.get('configurationName')
    rawConfiguration = data.get('rawConfiguration')
    if configurationName is None or len(
            configurationName) == 0 or configurationName not in WireguardConfigurations.keys():
        return ResponseObject(False, "Please provide a valid configuration name")
    if rawConfiguration is None or len(rawConfiguration) == 0:
        return ResponseObject(False, "Please provide content")
    
    status, err = WireguardConfigurations[configurationName].updateRawConfigurationFile(rawConfiguration)

    return ResponseObject(status=status, message=err)

@app.post(f'{APP_PREFIX}/api/deleteWireguardConfiguration')
def API_deleteWireguardConfiguration():
    data = request.get_json()
    if "ConfigurationName" not in data.keys() or data.get("ConfigurationName") is None or data.get("ConfigurationName") not in WireguardConfigurations.keys():
        return ResponseObject(False, "Please provide the configuration name you want to delete", status_code=404)
    rp =  WireguardConfigurations.pop(data.get("ConfigurationName"))
    
    status = rp.deleteConfiguration()
    if not status:
        WireguardConfigurations[data.get("ConfigurationName")] = rp
    return ResponseObject(status)

@app.post(f'{APP_PREFIX}/api/renameWireguardConfiguration')
def API_renameWireguardConfiguration():
    data = request.get_json()
    keys = ["ConfigurationName", "NewConfigurationName"]
    for k in keys:
        if (k not in data.keys() or data.get(k) is None or len(data.get(k)) == 0 or 
                (k == "ConfigurationName" and data.get(k) not in WireguardConfigurations.keys())): 
            return ResponseObject(False, "Please provide the configuration name you want to rename", status_code=404)
    
    if data.get("NewConfigurationName") in WireguardConfigurations.keys():
        return ResponseObject(False, "Configuration name already exist", status_code=400)
    
    rc = WireguardConfigurations.pop(data.get("ConfigurationName"))
    
    status, message = rc.renameConfiguration(data.get("NewConfigurationName"))
    if status:
        WireguardConfigurations[data.get("NewConfigurationName")] = (WireguardConfiguration(DashboardConfig, AllPeerJobs, AllPeerShareLinks, DashboardWebHooks, data.get("NewConfigurationName")) if rc.Protocol == 'wg' else AmneziaWireguardConfiguration(DashboardConfig, AllPeerJobs, AllPeerShareLinks, DashboardWebHooks, data.get("NewConfigurationName")))
    else:
        WireguardConfigurations[data.get("ConfigurationName")] = rc
    return ResponseObject(status, message)

@app.get(f'{APP_PREFIX}/api/getWireguardConfigurationRealtimeTraffic')
def API_getWireguardConfigurationRealtimeTraffic():
    configurationName = request.args.get('configurationName')
    if configurationName is None or configurationName not in WireguardConfigurations.keys():
        return ResponseObject(False, "Configuration does not exist", status_code=404)
    return ResponseObject(data=WireguardConfigurations[configurationName].getRealtimeTrafficUsage())

@app.get(f'{APP_PREFIX}/api/getPeerTraffic')
def API_getPeerTraffic():
    id = request.args.get('id')
    if id is None:
        return ResponseObject(False, "Missing parameter: id", status_code=400)
    
    # Search for the peer across all configurations
    for configName, config in WireguardConfigurations.items():
        found, peer = config.searchPeer(id)
        if found:
            total_traffic = peer.total_receive + peer.total_sent + peer.cumu_receive + peer.cumu_sent
            return ResponseObject(data={
                "id": peer.id,
                "name": peer.name,
                "total_receive": peer.total_receive,
                "total_sent": peer.total_sent,
                "cumu_receive": peer.cumu_receive,
                "cumu_sent": peer.cumu_sent,
                "total_traffic": total_traffic,
                "configuration": configName
            })
    
    return ResponseObject(False, "Peer not found", status_code=404)

@app.get(f'{APP_PREFIX}/api/getWireguardConfigurationBackup')
def API_getWireguardConfigurationBackup():
    configurationName = request.args.get('configurationName')
    if configurationName is None or configurationName not in WireguardConfigurations.keys():
        return ResponseObject(False, "Configuration does not exist",  status_code=404)
    return ResponseObject(data=WireguardConfigurations[configurationName].getBackups())

@app.get(f'{APP_PREFIX}/api/getAllWireguardConfigurationBackup')
def API_getAllWireguardConfigurationBackup():
    data = {
        "ExistingConfigurations": {},
        "NonExistingConfigurations": {}
    }
    existingConfiguration = WireguardConfigurations.keys()
    for i in existingConfiguration:
        b = WireguardConfigurations[i].getBackups(True)
        if len(b) > 0:
            data['ExistingConfigurations'][i] = WireguardConfigurations[i].getBackups(True)
            
    for protocol in ProtocolsEnabled():
        directory = os.path.join(DashboardConfig.GetConfig("Server", f"{protocol}_conf_path")[1], 'WGDashboard_Backup')
        if os.path.exists(directory):
            files = [(file, os.path.getctime(os.path.join(directory, file)))
                     for file in os.listdir(directory) if os.path.isfile(os.path.join(directory, file))]
            files.sort(key=lambda x: x[1], reverse=True)
        
            for f, ct in files:
                if RegexMatch(r"^(.*)_(.*)\.(conf)$", f):
                    s = re.search(r"^(.*)_(.*)\.(conf)$", f)
                    name = s.group(1)
                    if name not in existingConfiguration:
                        if name not in data['NonExistingConfigurations'].keys():
                            data['NonExistingConfigurations'][name] = []
                        
                        date = s.group(2)
                        d = {
                            "protocol": protocol,
                            "filename": f,
                            "backupDate": date,
                            "content": open(os.path.join(DashboardConfig.GetConfig("Server", f"{protocol}_conf_path")[1], 'WGDashboard_Backup', f), 'r').read()
                        }
                        if f.replace(".conf", ".sql") in list(os.listdir(directory)):
                            d['database'] = True
                            d['databaseContent'] = open(os.path.join(DashboardConfig.GetConfig("Server", f"{protocol}_conf_path")[1], 'WGDashboard_Backup', f.replace(".conf", ".sql")), 'r').read()
                        data['NonExistingConfigurations'][name].append(d)
    return ResponseObject(data=data)

@app.get(f'{APP_PREFIX}/api/createWireguardConfigurationBackup')
def API_createWireguardConfigurationBackup():
    configurationName = request.args.get('configurationName')
    if configurationName is None or configurationName not in WireguardConfigurations.keys():
        return ResponseObject(False, "Configuration does not exist",  status_code=404)
    return ResponseObject(status=WireguardConfigurations[configurationName].backupConfigurationFile()[0], 
                          data=WireguardConfigurations[configurationName].getBackups())

@app.post(f'{APP_PREFIX}/api/deleteWireguardConfigurationBackup')
def API_deleteWireguardConfigurationBackup():
    data = request.get_json()
    if ("ConfigurationName" not in data.keys() or 
            "BackupFileName" not in data.keys() or
            len(data['ConfigurationName']) == 0 or 
            len(data['BackupFileName']) == 0):
        return ResponseObject(False, 
        "Please provide configurationName and backupFileName in body",  status_code=400)
    configurationName = data['ConfigurationName']
    backupFileName = data['BackupFileName']
    if configurationName not in WireguardConfigurations.keys():
        return ResponseObject(False, "Configuration does not exist", status_code=404)
    
    status = WireguardConfigurations[configurationName].deleteBackup(backupFileName)
    return ResponseObject(status=status, message=(None if status else 'Backup file does not exist'), 
                          status_code = (200 if status else 404))

@app.get(f'{APP_PREFIX}/api/downloadWireguardConfigurationBackup')
def API_downloadWireguardConfigurationBackup():
    configurationName = request.args.get('configurationName')
    backupFileName = request.args.get('backupFileName')
    if configurationName is None or configurationName not in WireguardConfigurations.keys():
        return ResponseObject(False, "Configuration does not exist", status_code=404)
    status, zip = WireguardConfigurations[configurationName].downloadBackup(backupFileName)
    return ResponseObject(status, data=zip, status_code=(200 if status else 404))

@app.post(f'{APP_PREFIX}/api/restoreWireguardConfigurationBackup')
def API_restoreWireguardConfigurationBackup():
    data = request.get_json()
    if ("ConfigurationName" not in data.keys() or
            "BackupFileName" not in data.keys() or
            len(data['ConfigurationName']) == 0 or
            len(data['BackupFileName']) == 0):
        return ResponseObject(False,
                              "Please provide ConfigurationName and BackupFileName in body", status_code=400)
    configurationName = data['ConfigurationName']
    backupFileName = data['BackupFileName']
    if configurationName not in WireguardConfigurations.keys():
        return ResponseObject(False, "Configuration does not exist", status_code=404)
    
    status = WireguardConfigurations[configurationName].restoreBackup(backupFileName)
    return ResponseObject(status=status, message=(None if status else 'Restore backup failed'))
    
@app.get(f'{APP_PREFIX}/api/getDashboardConfiguration')
def API_getDashboardConfiguration():
    return ResponseObject(data=DashboardConfig.toJson())

@app.post(f'{APP_PREFIX}/api/updateDashboardConfigurationItem')
def API_updateDashboardConfigurationItem():
    data = request.get_json()
    if "section" not in data.keys() or "key" not in data.keys() or "value" not in data.keys():
        return ResponseObject(False, "Invalid request.")
    valid, msg = DashboardConfig.SetConfig(
        data["section"], data["key"], data['value'])
    if not valid:
        return ResponseObject(False, msg)
    if data['section'] == "Server":
        if data['key'] == 'wg_conf_path':
            WireguardConfigurations.clear()
            WireguardConfigurations.clear()
            InitWireguardConfigurationsList()
    return ResponseObject(True, data=DashboardConfig.GetConfig(data["section"], data["key"])[1])

@app.get(f'{APP_PREFIX}/api/getDashboardAPIKeys')
def API_getDashboardAPIKeys():
    if DashboardConfig.GetConfig('Server', 'dashboard_api_key'):
        return ResponseObject(data=DashboardConfig.DashboardAPIKeys)
    return ResponseObject(False, "WGDashboard API Keys function is disabled")

@app.post(f'{APP_PREFIX}/api/newDashboardAPIKey')
def API_newDashboardAPIKey():
    data = request.get_json()
    if DashboardConfig.GetConfig('Server', 'dashboard_api_key'):
        try:
            if data['NeverExpire']:
                expiredAt = None
            else:
                expiredAt = datetime.strptime(data['ExpiredAt'], '%Y-%m-%d %H:%M:%S')
            DashboardConfig.createAPIKeys(expiredAt)
            return ResponseObject(True, data=DashboardConfig.DashboardAPIKeys)
        except Exception as e:
            return ResponseObject(False, str(e))
    return ResponseObject(False, "Dashboard API Keys function is disbaled")

@app.post(f'{APP_PREFIX}/api/deleteDashboardAPIKey')
def API_deleteDashboardAPIKey():
    data = request.get_json()
    if DashboardConfig.GetConfig('Server', 'dashboard_api_key'):
        if len(data['Key']) > 0 and len(list(filter(lambda x : x.Key == data['Key'], DashboardConfig.DashboardAPIKeys))) > 0:
            DashboardConfig.deleteAPIKey(data['Key'])
            return ResponseObject(True, data=DashboardConfig.DashboardAPIKeys)
        else:
            return ResponseObject(False, "API Key does not exist", status_code=404)
    return ResponseObject(False, "Dashboard API Keys function is disbaled")
    
@app.post(f'{APP_PREFIX}/api/updatePeerSettings/<configName>')
def API_updatePeerSettings(configName):
    data = request.get_json()
    id = data['id']
    if len(id) > 0 and configName in WireguardConfigurations.keys():
        name = data['name']
        private_key = data['private_key']
        dns_addresses = data['DNS']
        allowed_ip = data['allowed_ip']
        endpoint_allowed_ip = data['endpoint_allowed_ip']
        preshared_key = data['preshared_key']
        mtu = data['mtu']
        keepalive = data['keepalive']
        wireguardConfig = WireguardConfigurations[configName]
        foundPeer, peer = wireguardConfig.searchPeer(id)
        if foundPeer:
            if wireguardConfig.Protocol == 'wg':
                status, msg = peer.updatePeer(name, private_key, preshared_key, dns_addresses,
                                       allowed_ip, endpoint_allowed_ip, mtu, keepalive)
            else:
                status, msg = peer.updatePeer(name, private_key, preshared_key, dns_addresses,
                    allowed_ip, endpoint_allowed_ip, mtu, keepalive, "off")
            wireguardConfig.getPeers()
            DashboardWebHooks.RunWebHook('peer_updated', {
                "configuration": wireguardConfig.Name,
                "peers": [id]
            })
            return ResponseObject(status, msg)
            
    return ResponseObject(False, "Peer does not exist")

@app.post(f'{APP_PREFIX}/api/resetPeerData/<configName>')
def API_resetPeerData(configName):
    data = request.get_json()
    id = data['id']
    type = data['type']
    if len(id) == 0 or configName not in WireguardConfigurations.keys():
        return ResponseObject(False, "Configuration/Peer does not exist")
    wgc = WireguardConfigurations.get(configName)
    foundPeer, peer = wgc.searchPeer(id)
    if not foundPeer:
        return ResponseObject(False, "Configuration/Peer does not exist")
    
    resetStatus = peer.resetDataUsage(type)
    if resetStatus:
        wgc.restrictPeers([id])
        wgc.allowAccessPeers([id])
    
    return ResponseObject(status=resetStatus)

@app.post(f'{APP_PREFIX}/api/deletePeers/<configName>')
def API_deletePeers(configName: str) -> ResponseObject:
    data = request.get_json()
    peers = data['peers']
    if configName in WireguardConfigurations.keys():
        if len(peers) == 0:
            return ResponseObject(False, "Please specify one or more peers", status_code=400)
        configuration = WireguardConfigurations.get(configName)
        
        # Check each peer for node_id and delete via agent if needed
        for peer_id in peers:
            found, peer = configuration.searchPeer(peer_id)
            if found and peer.node_id:
                # Peer is on a remote node - delete via agent
                try:
                    client = NodesManager.getNodeAgentClient(peer.node_id)
                    if client and peer.iface:
                        success, response = client.delete_peer(peer.iface, peer_id)
                        if not success:
                            app.logger.error(f"Failed to delete peer {peer_id} from node: {response}")
                            return ResponseObject(False, f"Failed to delete peer from node: {response}")
                    
                    # Deallocate IP
                    IPAllocManager.deallocateIP(peer.node_id, peer_id)
                    
                    # Remove from database
                    with configuration.engine.begin() as conn:
                        conn.execute(
                            configuration.peersTable.delete().where(
                                configuration.peersTable.c.id == peer_id
                            )
                        )
                    
                    # Delete jobs and share links
                    for job in peer.jobs:
                        AllPeerJobs.deleteJob(job)
                    for shareLink in peer.ShareLink:
                        AllPeerShareLinks.updateLinkExpireDate(shareLink.ShareID, datetime.now())
                        
                except Exception as e:
                    app.logger.error(f"Error deleting peer {peer_id} from node: {e}")
                    return ResponseObject(False, f"Error deleting peer from node: {str(e)}")
        
        # For local peers, use existing delete logic
        local_peers = []
        for peer_id in peers:
            found, peer = configuration.searchPeer(peer_id)
            if found and not peer.node_id:
                local_peers.append(peer_id)
        
        if local_peers:
            status, msg = configuration.deletePeers(local_peers, AllPeerJobs, AllPeerShareLinks)
            if not status:
                return ResponseObject(status, msg)
        
        # Delete Assignment
        for p in peers:
            assignments = DashboardClients.DashboardClientsPeerAssignment.GetAssignedClients(configName, p)
            for c in assignments:
                DashboardClients.DashboardClientsPeerAssignment.UnassignClients(c.AssignmentID)
        
        # Refresh peers
        configuration.getPeers()
        
        return ResponseObject(True, f"Deleted {len(peers)} peer(s) successfully")

    return ResponseObject(False, "Configuration does not exist", status_code=404)

@app.post(f'{APP_PREFIX}/api/restrictPeers/<configName>')
def API_restrictPeers(configName: str) -> ResponseObject:
    data = request.get_json()
    peers = data['peers']
    if configName in WireguardConfigurations.keys():
        if len(peers) == 0:
            return ResponseObject(False, "Please specify one or more peers")
        configuration = WireguardConfigurations.get(configName)
        status, msg = configuration.restrictPeers(peers)
        return ResponseObject(status, msg)
    return ResponseObject(False, "Configuration does not exist", status_code=404)

@app.post(f'{APP_PREFIX}/api/sharePeer/create')
def API_sharePeer_create():
    data: dict[str, str] = request.get_json()
    Configuration = data.get('Configuration')
    Peer = data.get('Peer')
    ExpireDate = data.get('ExpireDate')
    if Configuration is None or Peer is None:
        return ResponseObject(False, "Please specify configuration and peers")
    activeLink = AllPeerShareLinks.getLink(Configuration, Peer)
    if len(activeLink) > 0:
        return ResponseObject(True, 
                              "This peer is already sharing. Please view data for shared link.",
                                data=activeLink[0]
        )
    status, message = AllPeerShareLinks.addLink(Configuration, Peer, datetime.strptime(ExpireDate, "%Y-%m-%d %H:%M:%S"))
    if not status:
        return ResponseObject(status, message)
    return ResponseObject(data=AllPeerShareLinks.getLinkByID(message))

@app.post(f'{APP_PREFIX}/api/sharePeer/update')
def API_sharePeer_update():
    data: dict[str, str] = request.get_json()
    ShareID: str = data.get("ShareID")
    ExpireDate: str = data.get("ExpireDate")
    
    if not all([ShareID, ExpireDate]):
        return ResponseObject(False, "Please specify ShareID")
    
    if len(AllPeerShareLinks.getLinkByID(ShareID)) == 0:
        return ResponseObject(False, "ShareID does not exist")
    
    status, message = AllPeerShareLinks.updateLinkExpireDate(ShareID, datetime.strptime(ExpireDate, "%Y-%m-%d %H:%M:%S"))
    if not status:
        return ResponseObject(status, message)
    return ResponseObject(data=AllPeerShareLinks.getLinkByID(ShareID))

@app.get(f'{APP_PREFIX}/api/sharePeer/get')
def API_sharePeer_get():
    data = request.args
    ShareID = data.get("ShareID")
    if ShareID is None or len(ShareID) == 0:
        return ResponseObject(False, "Please provide ShareID")
    link = AllPeerShareLinks.getLinkByID(ShareID)
    if len(link) == 0:
        return ResponseObject(False, "This link is either expired to invalid")
    l = link[0]
    if l.Configuration not in WireguardConfigurations.keys():
        return ResponseObject(False, "The peer you're looking for does not exist")
    c = WireguardConfigurations.get(l.Configuration)
    fp, p = c.searchPeer(l.Peer)
    if not fp:
        return ResponseObject(False, "The peer you're looking for does not exist")
    
    return ResponseObject(data=p.downloadPeer())
    
@app.post(f'{APP_PREFIX}/api/allowAccessPeers/<configName>')
def API_allowAccessPeers(configName: str) -> ResponseObject:
    data = request.get_json()
    peers = data['peers']
    if configName in WireguardConfigurations.keys():
        if len(peers) == 0:
            return ResponseObject(False, "Please specify one or more peers")
        configuration = WireguardConfigurations.get(configName)
        status, msg = configuration.allowAccessPeers(peers)
        return ResponseObject(status, msg)
    return ResponseObject(False, "Configuration does not exist")

@app.post(f'{APP_PREFIX}/api/addPeers/<configName>')
def API_addPeers(configName):
    if configName in WireguardConfigurations.keys():
        data: dict = request.get_json()
        try:
            # Multi-node support: node selection
            node_selection: str = data.get('node_selection', None)  # "auto", specific node_id, or None for local
            selected_node = None
            selected_node_id = None
            
            # If node selection is provided, select a node
            if node_selection:
                success, node, message = NodeSelector.selectNode(node_selection)
                if not success and node is None:
                    # No nodes available, fallback to legacy local mode
                    app.logger.info(f"Node selection fallback to local: {message}")
                    node_selection = None
                elif not success:
                    # Selection failed with error
                    return ResponseObject(False, message)
                else:
                    # Node selected successfully
                    selected_node = node
                    selected_node_id = node.id
                    app.logger.info(f"Selected node {node.name} for peer creation")

            bulkAdd: bool = data.get("bulkAdd", False)
            bulkAddAmount: int = data.get('bulkAddAmount', 0)
            preshared_key_bulkAdd: bool = data.get('preshared_key_bulkAdd', False)

            public_key: str = data.get('public_key', "")
            allowed_ips: list[str] = data.get('allowed_ips', [])
            allowed_ips_validation: bool = data.get('allowed_ips_validation', True)
            
            endpoint_allowed_ip: str = data.get('endpoint_allowed_ip', DashboardConfig.GetConfig("Peers", "peer_endpoint_allowed_ip")[1])
            dns_addresses: str = data.get('DNS', DashboardConfig.GetConfig("Peers", "peer_global_DNS")[1])
            
            
            mtu: int = data.get('mtu', None)
            keep_alive: int = data.get('keepalive', None)
            preshared_key: str = data.get('preshared_key', "")            
    
            if type(mtu) is not int or mtu < 0 or mtu > 1460:
                default: str = DashboardConfig.GetConfig("Peers", "peer_mtu")[1]
                if default.isnumeric():
                    try:
                        mtu = int(default)
                    except Exception as e:
                        mtu = 0
                else:
                    mtu = 0
            if type(keep_alive) is not int or keep_alive < 0:
                default = DashboardConfig.GetConfig("Peers", "peer_keep_alive")[1]
                if default.isnumeric():
                    try:
                        keep_alive = int(default)
                    except Exception as e:
                        keep_alive = 0
                else:
                    keep_alive = 0
            
            config = WireguardConfigurations.get(configName)
            if not config.getStatus():
                config.toggleConfiguration()
            ipStatus, availableIps = config.getAvailableIP(-1)
            ipCountStatus, numberOfAvailableIPs = config.getNumberOfAvailableIP()
            defaultIPSubnet = list(availableIps.keys())[0]
            if bulkAdd:
                if type(preshared_key_bulkAdd) is not bool:
                    preshared_key_bulkAdd = False
                if type(bulkAddAmount) is not int or bulkAddAmount < 1:
                    return ResponseObject(False, "Please specify amount of peers you want to add")
                if not ipStatus:
                    return ResponseObject(False, "No more available IP can assign")
                if len(availableIps.keys()) == 0:
                    return ResponseObject(False, "This configuration does not have any IP address available")
                if bulkAddAmount > sum(list(numberOfAvailableIPs.values())):
                    return ResponseObject(False,
                            f"The maximum number of peers can add is {sum(list(numberOfAvailableIPs.values()))}")
                keyPairs = []
                addedCount = 0
                for subnet in availableIps.keys():
                    for ip in availableIps[subnet]:
                        newPrivateKey = GenerateWireguardPrivateKey()[1]
                        addedCount += 1
                        keyPairs.append({
                            "private_key": newPrivateKey,
                            "id": GenerateWireguardPublicKey(newPrivateKey)[1],
                            "preshared_key": (GenerateWireguardPrivateKey()[1] if preshared_key_bulkAdd else ""),
                            "allowed_ip": ip,
                            "name": f"BulkPeer_{(addedCount + 1)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                            "DNS": dns_addresses,
                            "endpoint_allowed_ip": endpoint_allowed_ip,
                            "mtu": mtu,
                            "keepalive": keep_alive,
                            "advanced_security": "off"
                        })
                        if addedCount == bulkAddAmount:
                            break
                    if addedCount == bulkAddAmount:
                        break
                if len(keyPairs) == 0 or (bulkAdd and len(keyPairs) != bulkAddAmount):
                    return ResponseObject(False, "Generating key pairs by bulk failed")
                status, addedPeers, message = config.addPeers(keyPairs)
                return ResponseObject(status=status, message=message, data=addedPeers)
    
            else:
                if config.searchPeer(public_key)[0] is True:
                    return ResponseObject(False, f"This peer already exist")
                name = data.get("name", "")
                private_key = data.get("private_key", "")

                if len(public_key) == 0:
                    if len(private_key) == 0:
                        private_key = GenerateWireguardPrivateKey()[1]
                        public_key = GenerateWireguardPublicKey(private_key)[1]
                    else:
                        public_key = GenerateWireguardPublicKey(private_key)[1]
                else:
                    if len(private_key) > 0:
                        genPub = GenerateWireguardPublicKey(private_key)[1]
                        # Check if provided pubkey match provided private key
                        if public_key != genPub:
                            return ResponseObject(False, "Provided Public Key does not match provided Private Key")
                
                # IP allocation logic - different for node vs local
                if selected_node:
                    # Allocate IP from node's pool using IPAM
                    if len(allowed_ips) == 0:
                        success, ip_or_error = IPAllocManager.allocateIP(selected_node_id, public_key)
                        if not success:
                            return ResponseObject(False, f"Failed to allocate IP: {ip_or_error}")
                        allowed_ips = [ip_or_error]
                    else:
                        # User provided IP - validate it's in node's pool
                        # For now, still allocate to track it
                        success, _ = IPAllocManager.allocateIP(selected_node_id, public_key)
                        if not success:
                            app.logger.warning(f"Failed to track user-provided IP in IPAM")
                else:
                    # Legacy local mode - use existing logic
                    if len(allowed_ips) == 0:
                        if ipStatus:
                            for subnet in availableIps.keys():
                                for ip in availableIps[subnet]:
                                    allowed_ips = [ip]
                                    break
                                break  
                        else:
                            return ResponseObject(False, "No more available IP can assign") 

                    if allowed_ips_validation:
                        for i in allowed_ips:
                            found = False
                            for subnet in availableIps.keys():
                                network = ipaddress.ip_network(subnet, False)
                                ap = ipaddress.ip_network(i)
                                if network.version == ap.version and ap.subnet_of(network):
                                    found = True
                        
                            if not found:
                                return ResponseObject(False, f"This IP is not available: {i}")

                # For remote nodes, create peer via agent
                if selected_node:
                    # Create peer via node agent
                    try:
                        # Select appropriate interface for this node
                        # Priority:
                        # 1. Interface specified by user (if added to API in future)
                        # 2. Interface with available IPs in its pool
                        # 3. First enabled interface
                        # 4. Fallback to legacy wg_interface field
                        
                        selected_interface = None
                        interface_name = None
                        interface_endpoint = None
                        
                        # Get enabled interfaces for this node
                        node_interfaces = NodeInterfacesManager.getEnabledInterfacesByNodeId(selected_node_id)
                        
                        if node_interfaces:
                            # For now, select the first enabled interface
                            # TODO: Implement smarter selection based on IP pool availability
                            selected_interface = node_interfaces[0]
                            interface_name = selected_interface.interface_name
                            interface_endpoint = selected_interface.endpoint or selected_node.endpoint
                        else:
                            # Fallback to legacy wg_interface field
                            interface_name = selected_node.wg_interface
                            interface_endpoint = selected_node.endpoint
                        
                        if not interface_name:
                            # Rollback IP allocation
                            IPAllocManager.deallocateIP(selected_node_id, public_key)
                            return ResponseObject(False, "Node has no interface configured")
                        
                        client = NodesManager.getNodeAgentClient(selected_node_id)
                        if not client:
                            # Rollback IP allocation
                            IPAllocManager.deallocateIP(selected_node_id, public_key)
                            return ResponseObject(False, "Failed to get agent client for node")
                        
                        # Prepare peer data for agent
                        peer_data = {
                            "public_key": public_key,
                            "preshared_key": preshared_key if preshared_key else None,
                            "allowed_ips": allowed_ips,
                            "persistent_keepalive": keep_alive if keep_alive > 0 else 0
                        }
                        
                        # Call agent to add peer
                        success, response = client.add_peer(interface_name, peer_data)
                        
                        if not success:
                            # Rollback IP allocation
                            IPAllocManager.deallocateIP(selected_node_id, public_key)
                            return ResponseObject(False, f"Failed to add peer to node: {response}")
                        
                        # Store peer in database with node_id and iface
                        peer_record = {
                            "id": public_key,
                            "private_key": private_key,
                            "DNS": dns_addresses,
                            "endpoint_allowed_ip": endpoint_allowed_ip,
                            "name": name,
                            "total_receive": 0,
                            "total_sent": 0,
                            "total_data": 0,
                            "endpoint": "N/A",
                            "status": "stopped",
                            "latest_handshake": "N/A",
                            "allowed_ip": ','.join(allowed_ips),
                            "cumu_receive": 0,
                            "cumu_sent": 0,
                            "cumu_data": 0,
                            "mtu": mtu,
                            "keepalive": keep_alive,
                            "remote_endpoint": interface_endpoint or selected_node.endpoint,
                            "preshared_key": preshared_key,
                            "node_id": selected_node_id,
                            "iface": interface_name
                        }
                        
                        with config.engine.begin() as conn:
                            conn.execute(
                                config.peersTable.insert().values(peer_record)
                            )
                        
                        # Refresh peers list
                        config.getPeers()
                        peerFound, addedPeer = config.searchPeer(public_key)
                        
                        if peerFound:
                            return ResponseObject(status=True, message="Peer created on node successfully", data=[addedPeer])
                        else:
                            return ResponseObject(status=True, message="Peer created on node", data=[])
                            
                    except Exception as e:
                        # Rollback IP allocation
                        IPAllocManager.deallocateIP(selected_node_id, public_key)
                        app.logger.error(f"Error creating peer on node: {e}")
                        return ResponseObject(False, f"Error creating peer on node: {str(e)}")
                
                # Local peer creation (existing logic)
                status, addedPeers, message = config.addPeers([
                    {
                        "name": name,
                        "id": public_key,
                        "private_key": private_key,
                        "allowed_ip": ','.join(allowed_ips),
                        "preshared_key": preshared_key,
                        "endpoint_allowed_ip": endpoint_allowed_ip,
                        "DNS": dns_addresses,
                        "mtu": mtu,
                        "keepalive": keep_alive,
                        "advanced_security": "off"
                    }]
                )
                return ResponseObject(status=status, message=message, data=addedPeers)
        except Exception as e:
            app.logger.error("Add peers failed", e)
            return ResponseObject(False,
                                  f"Add peers failed. Reason: {message}")

    return ResponseObject(False, "Configuration does not exist")

@app.get(f"{APP_PREFIX}/api/downloadPeer/<configName>")
def API_downloadPeer(configName):
    data = request.args
    if configName not in WireguardConfigurations.keys():
        return ResponseObject(False, "Configuration does not exist")
    configuration = WireguardConfigurations[configName]
    peerFound, peer = configuration.searchPeer(data['id'])
    if len(data['id']) == 0 or not peerFound:
        return ResponseObject(False, "Peer does not exist")
    return ResponseObject(data=peer.downloadPeer())

@app.get(f"{APP_PREFIX}/api/downloadAllPeers/<configName>")
def API_downloadAllPeers(configName):
    if configName not in WireguardConfigurations.keys():
        return ResponseObject(False, "Configuration does not exist")
    configuration = WireguardConfigurations[configName]
    peerData = []
    untitledPeer = 0
    for i in configuration.Peers:
        file = i.downloadPeer()
        if file["fileName"] == "UntitledPeer":
            file["fileName"] = str(untitledPeer) + "_" + file["fileName"]
            untitledPeer += 1
        peerData.append(file)
    return ResponseObject(data=peerData)

@app.get(f"{APP_PREFIX}/api/getAvailableIPs/<configName>")
def API_getAvailableIPs(configName):
    if configName not in WireguardConfigurations.keys():
        return ResponseObject(False, "Configuration does not exist")
    status, ips = WireguardConfigurations.get(configName).getAvailableIP()
    return ResponseObject(status=status, data=ips)

@app.get(f"{APP_PREFIX}/api/getNumberOfAvailableIPs/<configName>")
def API_getNumberOfAvailableIPs(configName):
    if configName not in WireguardConfigurations.keys():
        return ResponseObject(False, "Configuration does not exist")
    status, ips = WireguardConfigurations.get(configName).getNumberOfAvailableIP()
    return ResponseObject(status=status, data=ips)

@app.get(f'{APP_PREFIX}/api/getWireguardConfigurationInfo')
def API_getConfigurationInfo():
    configurationName = request.args.get("configurationName")
    if not configurationName or configurationName not in WireguardConfigurations.keys():
        return ResponseObject(False, "Please provide configuration name")
    return ResponseObject(data={
        "configurationInfo": WireguardConfigurations[configurationName],
        "configurationPeers": WireguardConfigurations[configurationName].getPeersList(),
        "configurationRestrictedPeers": WireguardConfigurations[configurationName].getRestrictedPeersList()
    })

@app.get(f'{APP_PREFIX}/api/getPeerHistoricalEndpoints')
def API_GetPeerHistoricalEndpoints():
    configurationName = request.args.get("configurationName")
    id = request.args.get('id')
    if not configurationName or not id:
        return ResponseObject(False, "Please provide configurationName and id")
    fp, p = WireguardConfigurations.get(configurationName).searchPeer(id)
    if fp:
        result = p.getEndpoints()
        geo = {}
        try:
            r = requests.post(f"http://ip-api.com/batch?fields=city,country,lat,lon,query",
                              data=json.dumps([x['endpoint'] for x in result]))
            d = r.json()
            
                
        except Exception as e:
            return ResponseObject(data=result, message="Failed to request IP address geolocation. " + str(e))
        
        return ResponseObject(data={
            "endpoints": p.getEndpoints(),
            "geolocation": d
        })
    return ResponseObject(False, "Peer does not exist")

@app.get(f'{APP_PREFIX}/api/getPeerSessions')
def API_GetPeerSessions():
    configurationName = request.args.get("configurationName")
    id = request.args.get('id')
    try:
        startDate = request.args.get('startDate', None)
        endDate = request.args.get('endDate', None)
        
        if startDate is None:
            endDate = None
        else:
            startDate = datetime.strptime(startDate, "%Y-%m-%d")
            if endDate:
                endDate = datetime.strptime(endDate, "%Y-%m-%d")
                if startDate > endDate:
                    return ResponseObject(False, "startDate must be smaller than endDate")
    except Exception as e:
        return ResponseObject(False, "Dates are invalid")
    if not configurationName or not id:
        return ResponseObject(False, "Please provide configurationName and id")
    fp, p = WireguardConfigurations.get(configurationName).searchPeer(id)
    if fp:
        return ResponseObject(data=p.getSessions(startDate, endDate))
    return ResponseObject(False, "Peer does not exist")

@app.get(f'{APP_PREFIX}/api/getPeerTraffics')
def API_GetPeerTraffics():
    configurationName = request.args.get("configurationName")
    id = request.args.get('id')
    try:
        interval = request.args.get('interval', 30)
        startDate = request.args.get('startDate', None)
        endDate = request.args.get('endDate', None)
        if type(interval) is str:
            if not interval.isdigit():
                return ResponseObject(False, "Interval must be integers in minutes")
            interval = int(interval)
        if startDate is None:
            endDate = None
        else:
            startDate = datetime.strptime(startDate, "%Y-%m-%d")
            if endDate:
                endDate = datetime.strptime(endDate, "%Y-%m-%d")
                if startDate > endDate:
                    return ResponseObject(False, "startDate must be smaller than endDate")
    except Exception as e:
        return ResponseObject(False, "Dates are invalid" + e)
    if not configurationName or not id:
        return ResponseObject(False, "Please provide configurationName and id")
    fp, p = WireguardConfigurations.get(configurationName).searchPeer(id)
    if fp:
        return ResponseObject(data=p.getTraffics(interval, startDate, endDate))
    return ResponseObject(False, "Peer does not exist")

@app.get(f'{APP_PREFIX}/api/getPeerTrackingTableCounts')
def API_GetPeerTrackingTableCounts():
    configurationName = request.args.get("configurationName")
    if configurationName not in WireguardConfigurations.keys():
        return ResponseObject(False, "Configuration does not exist")
    c = WireguardConfigurations.get(configurationName)
    return ResponseObject(data={
        "TrafficTrackingTableSize": c.getTransferTableSize(),
        "HistoricalTrackingTableSize": c.getHistoricalEndpointTableSize()
    })

@app.get(f'{APP_PREFIX}/api/downloadPeerTrackingTable')
def API_DownloadPeerTackingTable():
    configurationName = request.args.get("configurationName")
    table = request.args.get('table')
    if configurationName not in WireguardConfigurations.keys():
        return ResponseObject(False, "Configuration does not exist")
    if table not in ['TrafficTrackingTable', 'HistoricalTrackingTable']:
        return ResponseObject(False, "Table does not exist")
    c = WireguardConfigurations.get(configurationName)
    return ResponseObject(
        data=c.downloadTransferTable() if table == 'TrafficTrackingTable' 
        else c.downloadHistoricalEndpointTable())

@app.post(f'{APP_PREFIX}/api/deletePeerTrackingTable')
def API_DeletePeerTrackingTable():
    data = request.get_json()
    configurationName = data.get('configurationName')
    table = data.get('table')
    if not configurationName or configurationName not in WireguardConfigurations.keys():
        return ResponseObject(False, "Configuration does not exist")
    if not table or table not in ['TrafficTrackingTable', 'HistoricalTrackingTable']:
        return ResponseObject(False, "Table does not exist")
    c = WireguardConfigurations.get(configurationName)
    return ResponseObject(
        status=c.deleteTransferTable() if table == 'TrafficTrackingTable'
        else c.deleteHistoryEndpointTable())

@app.get(f'{APP_PREFIX}/api/getDashboardTheme')
def API_getDashboardTheme():
    return ResponseObject(data=DashboardConfig.GetConfig("Server", "dashboard_theme")[1])

@app.get(f'{APP_PREFIX}/api/getDashboardVersion')
def API_getDashboardVersion():
    return ResponseObject(data=DashboardConfig.GetConfig("Server", "version")[1])

@app.post(f'{APP_PREFIX}/api/savePeerScheduleJob')
def API_savePeerScheduleJob():
    data = request.json
    if "Job" not in data.keys():
        return ResponseObject(False, "Please specify job")
    job: dict = data['Job']
    if "Peer" not in job.keys() or "Configuration" not in job.keys():
        return ResponseObject(False, "Please specify peer and configuration")
    configuration = WireguardConfigurations.get(job['Configuration'])
    if configuration is None:
        return ResponseObject(False, "Configuration does not exist")
    f, fp = configuration.searchPeer(job['Peer'])
    if not f:
        return ResponseObject(False, "Peer does not exist")
    
    
    s, p = AllPeerJobs.saveJob(PeerJob(
        job['JobID'], job['Configuration'], job['Peer'], job['Field'], job['Operator'], job['Value'],
        job['CreationDate'], job['ExpireDate'], job['Action']))
    if s:
        return ResponseObject(s, data=p)
    return ResponseObject(s, message=p)

@app.post(f'{APP_PREFIX}/api/deletePeerScheduleJob')
def API_deletePeerScheduleJob():
    data = request.json
    if "Job" not in data.keys():
        return ResponseObject(False, "Please specify job")
    job: dict = data['Job']
    if "Peer" not in job.keys() or "Configuration" not in job.keys():
        return ResponseObject(False, "Please specify peer and configuration")
    configuration = WireguardConfigurations.get(job['Configuration'])
    if configuration is None:
        return ResponseObject(False, "Configuration does not exist")
    # f, fp = configuration.searchPeer(job['Peer'])
    # if not f:
    #     return ResponseObject(False, "Peer does not exist")

    s, p = AllPeerJobs.deleteJob(PeerJob(
        job['JobID'], job['Configuration'], job['Peer'], job['Field'], job['Operator'], job['Value'],
        job['CreationDate'], job['ExpireDate'], job['Action']))
    if s:
        return ResponseObject(s)
    return ResponseObject(s, message=p)

@app.get(f'{APP_PREFIX}/api/getPeerScheduleJobLogs/<configName>')
def API_getPeerScheduleJobLogs(configName):
    if configName not in WireguardConfigurations.keys():
        return ResponseObject(False, "Configuration does not exist")
    data = request.args.get("requestAll")
    requestAll = False
    if data is not None and data == "true":
        requestAll = True
    return ResponseObject(data=AllPeerJobs.getPeerJobLogs(configName))

'''
File Download
'''
@app.get(f'{APP_PREFIX}/fileDownload')
def API_download():
    file = request.args.get('file')
    if file is None or len(file) == 0:
        return ResponseObject(False, "Please specify a file")
    if os.path.exists(os.path.join('download', file)):
        return send_file(os.path.join('download', file), as_attachment=True)
    else:
        return ResponseObject(False, "File does not exist")


'''
Tools
'''

@app.get(f'{APP_PREFIX}/api/ping/getAllPeersIpAddress')
def API_ping_getAllPeersIpAddress():
    ips = {}
    for c in WireguardConfigurations.values():
        cips = {}
        for p in c.Peers:
            allowed_ip = p.allowed_ip.replace(" ", "").split(",")
            parsed = []
            for x in allowed_ip:
                try:
                    ip = ipaddress.ip_network(x, strict=False)
                except ValueError as e:
                    app.logger.error(f"Failed to parse IP address of {p.id} - {c.Name}")
                host = list(ip.hosts())
                if len(host) == 1:
                    parsed.append(str(host[0]))
            endpoint = p.endpoint.replace(" ", "").replace("(none)", "")
            if len(p.name) > 0:
                cips[f"{p.name} - {p.id}"] = {
                    "allowed_ips": parsed,
                    "endpoint": endpoint
                }
            else:
                cips[f"{p.id}"] = {
                    "allowed_ips": parsed,
                    "endpoint": endpoint
                }
        ips[c.Name] = cips
    return ResponseObject(data=ips)

import requests

@app.get(f'{APP_PREFIX}/api/ping/execute')
def API_ping_execute():
    if "ipAddress" in request.args.keys() and "count" in request.args.keys():
        ip = request.args['ipAddress']
        count = request.args['count']
        try:
            if ip is not None and len(ip) > 0 and count is not None and count.isnumeric():
                result = ping(ip, count=int(count), source=None)
                data = {
                    "address": result.address,
                    "is_alive": result.is_alive,
                    "min_rtt": result.min_rtt,
                    "avg_rtt": result.avg_rtt,
                    "max_rtt": result.max_rtt,
                    "package_sent": result.packets_sent,
                    "package_received": result.packets_received,
                    "package_loss": result.packet_loss,
                    "geo": None
                }
                try:
                    r = requests.get(f"http://ip-api.com/json/{result.address}?field=city")
                    data['geo'] = r.json()
                except Exception as e:
                    pass
                return ResponseObject(data=data)
            return ResponseObject(False, "Please specify an IP Address (v4/v6)")
        except Exception as exp:
            return ResponseObject(False, exp)
    return ResponseObject(False, "Please provide ipAddress and count")


@app.get(f'{APP_PREFIX}/api/traceroute/execute')
def API_traceroute_execute():
    if "ipAddress" in request.args.keys() and len(request.args.get("ipAddress")) > 0:
        ipAddress = request.args.get('ipAddress')
        try:
            tracerouteResult = traceroute(ipAddress, timeout=1, max_hops=64)
            result = []
            for hop in tracerouteResult:
                if len(result) > 1:
                    skipped = False
                    for i in range(result[-1]["hop"] + 1, hop.distance):
                        result.append(
                            {
                                "hop": i,
                                "ip": "*",
                                "avg_rtt": "*",
                                "min_rtt": "*",
                                "max_rtt": "*"
                            }
                        )
                        skip = True
                    if skipped: continue
                result.append(
                    {
                        "hop": hop.distance,
                        "ip": hop.address,
                        "avg_rtt": hop.avg_rtt,
                        "min_rtt": hop.min_rtt,
                        "max_rtt": hop.max_rtt
                    })
            try:
                r = requests.post(f"http://ip-api.com/batch?fields=city,country,lat,lon,query",
                                  data=json.dumps([x['ip'] for x in result]))
                d = r.json()
                for i in range(len(result)):
                    result[i]['geo'] = d[i]  
            except Exception as e:
                return ResponseObject(data=result, message="Failed to request IP address geolocation")
            return ResponseObject(data=result)
        except Exception as exp:
            return ResponseObject(False, exp)
    else:
        return ResponseObject(False, "Please provide ipAddress")

@app.get(f'{APP_PREFIX}/api/getDashboardUpdate')
def API_getDashboardUpdate():
    import urllib.request as req
    try:
        r = req.urlopen("https://api.github.com/repos/WGDashboard/WGDashboard/releases/latest", timeout=5).read()
        data = dict(json.loads(r))
        tagName = data.get('tag_name')
        htmlUrl = data.get('html_url')
        if tagName is not None and htmlUrl is not None:
            if version.parse(tagName) > version.parse(DashboardConfig.DashboardVersion):
                return ResponseObject(message=f"{tagName} is now available for update!", data=htmlUrl)
            else:
                return ResponseObject(message="You're on the latest version")
        return ResponseObject(False)
    except Exception as e:
        return ResponseObject(False, f"Request to GitHub API failed.")

'''
Sign Up
'''

@app.get(f'{APP_PREFIX}/api/isTotpEnabled')
def API_isTotpEnabled():
    return (
        ResponseObject(data=DashboardConfig.GetConfig("Account", "enable_totp")[1] and DashboardConfig.GetConfig("Account", "totp_verified")[1]))


@app.get(f'{APP_PREFIX}/api/Welcome_GetTotpLink')
def API_Welcome_GetTotpLink():
    if not DashboardConfig.GetConfig("Account", "totp_verified")[1]:
        DashboardConfig.SetConfig("Account", "totp_key", pyotp.random_base32(), True)
        return ResponseObject(
            data=pyotp.totp.TOTP(DashboardConfig.GetConfig("Account", "totp_key")[1]).provisioning_uri(
                issuer_name="WGDashboard"))
    return ResponseObject(False)


@app.post(f'{APP_PREFIX}/api/Welcome_VerifyTotpLink')
def API_Welcome_VerifyTotpLink():
    data = request.get_json()
    totp = pyotp.TOTP(DashboardConfig.GetConfig("Account", "totp_key")[1]).now()
    if totp == data['totp']:
        DashboardConfig.SetConfig("Account", "totp_verified", "true")
        DashboardConfig.SetConfig("Account", "enable_totp", "true")
    return ResponseObject(totp == data['totp'])

@app.post(f'{APP_PREFIX}/api/Welcome_Finish')
def API_Welcome_Finish():
    data = request.get_json()
    if DashboardConfig.GetConfig("Other", "welcome_session")[1]:
        if data["username"] == "":
            return ResponseObject(False, "Username cannot be blank.")

        if data["newPassword"] == "" or len(data["newPassword"]) < 8:
            return ResponseObject(False, "Password must be at least 8 characters")

        updateUsername, updateUsernameErr = DashboardConfig.SetConfig("Account", "username", data["username"])
        updatePassword, updatePasswordErr = DashboardConfig.SetConfig("Account", "password",
                                                                      {
                                                                          "newPassword": data["newPassword"],
                                                                          "repeatNewPassword": data["repeatNewPassword"],
                                                                          "currentPassword": "admin"
                                                                      })
        if not updateUsername or not updatePassword:
            return ResponseObject(False, f"{updateUsernameErr},{updatePasswordErr}".strip(","))

        DashboardConfig.SetConfig("Other", "welcome_session", False)
    return ResponseObject()

class Locale:
    def __init__(self):
        self.localePath = './static/locales/'
        self.activeLanguages = {}
        with open(os.path.join(f"{self.localePath}supported_locales.json"), "r") as f:
            self.activeLanguages = sorted(json.loads(''.join(f.readlines())), key=lambda x : x['lang_name'])
        
    def getLanguage(self) -> dict | None:
        currentLanguage = DashboardConfig.GetConfig("Server", "dashboard_language")[1]
        if currentLanguage == "en":
            return None
        if os.path.exists(os.path.join(f"{self.localePath}{currentLanguage}.json")):
            with open(os.path.join(f"{self.localePath}{currentLanguage}.json"), "r") as f:
                return dict(json.loads(''.join(f.readlines())))
        else:
            return None
    
    def updateLanguage(self, lang_id):
        if not os.path.exists(os.path.join(f"{self.localePath}{lang_id}.json")):
            DashboardConfig.SetConfig("Server", "dashboard_language", "en-US")
        else:
            DashboardConfig.SetConfig("Server", "dashboard_language", lang_id)
        
Locale = Locale()

@app.get(f'{APP_PREFIX}/api/locale')
def API_Locale_CurrentLang():    
    return ResponseObject(data=Locale.getLanguage())

@app.get(f'{APP_PREFIX}/api/locale/available')
def API_Locale_Available():
    return ResponseObject(data=Locale.activeLanguages)
        
@app.post(f'{APP_PREFIX}/api/locale/update')
def API_Locale_Update():
    data = request.get_json()
    if 'lang_id' not in data.keys():
        return ResponseObject(False, "Please specify a lang_id")
    Locale.updateLanguage(data['lang_id'])
    return ResponseObject(data=Locale.getLanguage())

@app.get(f'{APP_PREFIX}/api/email/ready')
def API_Email_Ready():
    return ResponseObject(EmailSender.ready())

@app.post(f'{APP_PREFIX}/api/email/send')
def API_Email_Send():
    data = request.get_json()
    if "Receiver" not in data.keys() or "Subject" not in data.keys():
        return ResponseObject(False, "Please at least specify receiver and subject")
    body = data.get('Body', '')
    subject = data.get('Subject','')
    download = None
    if ("ConfigurationName" in data.keys() 
            and "Peer" in data.keys()):
        if data.get('ConfigurationName') in WireguardConfigurations.keys():
            configuration = WireguardConfigurations.get(data.get('ConfigurationName'))
            attachmentName = ""
            if configuration is not None:
                fp, p = configuration.searchPeer(data.get('Peer'))
                if fp:
                    template = Template(body)
                    download = p.downloadPeer()
                    body = template.render(peer=p.toJson(), configurationFile=download)
                    subject = Template(data.get('Subject', '')).render(peer=p.toJson(), configurationFile=download)
                    if data.get('IncludeAttachment', False):
                        u = str(uuid4())
                        attachmentName = f'{u}.conf'
                        with open(os.path.join('./attachments', attachmentName,), 'w+') as f:
                            f.write(download['file'])   
                        
    
    s, m = EmailSender.send(data.get('Receiver'), subject, body,  
                            data.get('IncludeAttachment', False), (attachmentName if download else ''))
    return ResponseObject(s, m)

@app.post(f'{APP_PREFIX}/api/email/preview')
def API_Email_PreviewBody():
    data = request.get_json()
    subject = data.get('Subject', '')
    body = data.get('Body', '')
    
    if ("ConfigurationName" not in data.keys() 
            or "Peer" not in data.keys() or data.get('ConfigurationName') not in WireguardConfigurations.keys()):
        return ResponseObject(False, "Please specify configuration and peer")
    
    configuration = WireguardConfigurations.get(data.get('ConfigurationName'))
    fp, p = configuration.searchPeer(data.get('Peer'))
    if not fp:
        return ResponseObject(False, "Peer does not exist")

    try:
        template = Template(body)
        download = p.downloadPeer()
        return ResponseObject(data={
            "Body": Template(body).render(peer=p.toJson(), configurationFile=download),
            "Subject": Template(subject).render(peer=p.toJson(), configurationFile=download)
        })
    except Exception as e:
        return ResponseObject(False, message=str(e))

@app.get(f'{APP_PREFIX}/api/systemStatus')
def API_SystemStatus():
    return ResponseObject(data=SystemStatus)

@app.get(f'{APP_PREFIX}/api/protocolsEnabled')
def API_ProtocolsEnabled():
    return ResponseObject(data=ProtocolsEnabled())

'''
OIDC Controller
'''
@app.get(f'{APP_PREFIX}/api/oidc/toggle')
def API_OIDC_Toggle():
    data = request.args
    if not data.get('mode'):
        return ResponseObject(False, "Please provide mode")
    mode = data.get('mode')
    if mode == 'Client':
        DashboardConfig.SetConfig("OIDC", "client_enable", 
                                  not DashboardConfig.GetConfig("OIDC", "client_enable")[1])
    elif mode == 'Admin':
        DashboardConfig.SetConfig("OIDC", "admin_enable",
                                  not DashboardConfig.GetConfig("OIDC", "admin_enable")[1])
    else:
        return ResponseObject(False, "Mode does not exist")
    return ResponseObject()

@app.get(f'{APP_PREFIX}/api/oidc/status')
def API_OIDC_Status():
    data = request.args
    if not data.get('mode'):
        return ResponseObject(False, "Please provide mode")
    mode = data.get('mode')
    if mode == 'Client':
        return ResponseObject(data=DashboardConfig.GetConfig("OIDC", "client_enable")[1])
    elif mode == 'Admin':
        return ResponseObject(data=DashboardConfig.GetConfig("OIDC", "admin_enable")[1])
    return ResponseObject(False, "Mode does not exist")

'''
Client Controller
'''

@app.get(f'{APP_PREFIX}/api/clients/toggleStatus')
def API_Clients_ToggleStatus():
    DashboardConfig.SetConfig("Clients", "enable",
                              not DashboardConfig.GetConfig("Clients", "enable")[1])
    return ResponseObject(data=DashboardConfig.GetConfig("Clients", "enable")[1])


@app.get(f'{APP_PREFIX}/api/clients/allClients')
def API_Clients_AllClients():
    return ResponseObject(data=DashboardClients.GetAllClients())

@app.get(f'{APP_PREFIX}/api/clients/allClientsRaw')
def API_Clients_AllClientsRaw():
    return ResponseObject(data=DashboardClients.GetAllClientsRaw())

@app.post(f'{APP_PREFIX}/api/clients/assignClient')
def API_Clients_AssignClient():
    data = request.get_json()
    configurationName = data.get('ConfigurationName')
    id = data.get('Peer')
    client = data.get('ClientID')
    if not all([configurationName, id, client]):
        return ResponseObject(False, "Please provide all required fields")
    if not DashboardClients.GetClient(client):
        return ResponseObject(False, "Client does not exist")
    
    status, data = DashboardClients.AssignClient(configurationName, id, client)
    if not status:
        return ResponseObject(status, message="Client already assiged to this peer")
    
    return ResponseObject(data=data)

@app.post(f'{APP_PREFIX}/api/clients/unassignClient')
def API_Clients_UnassignClient():
    data = request.get_json()
    assignmentID = data.get('AssignmentID')
    if not assignmentID:
        return ResponseObject(False, "Please provide AssignmentID")
    return ResponseObject(status=DashboardClients.UnassignClient(assignmentID))

@app.get(f'{APP_PREFIX}/api/clients/assignedClients')
def API_Clients_AssignedClients():
    data = request.args
    configurationName = data.get('ConfigurationName')
    peerID = data.get('Peer')
    if not all([configurationName, id]):
        return ResponseObject(False, "Please provide all required fields")
    return ResponseObject(
        data=DashboardClients.GetAssignedPeerClients(configurationName, peerID))

@app.get(f'{APP_PREFIX}/api/clients/allConfigurationsPeers')
def API_Clients_AllConfigurationsPeers():
    c = {}
    for (key, val) in WireguardConfigurations.items():
        c[key] = list(map(lambda x : {
            "id": x.id,
            "name": x.name
        }, val.Peers))
    
    return ResponseObject(
        data=c
    )

@app.get(f'{APP_PREFIX}/api/clients/assignedPeers')
def API_Clients_AssignedPeers():
    data = request.args
    clientId = data.get("ClientID")
    if not clientId:
        return ResponseObject(False, "Please provide ClientID")
    if not DashboardClients.GetClient(clientId):
        return ResponseObject(False, "Client does not exist")
    d = DashboardClients.GetClientAssignedPeersGrouped(clientId)
    if d is None:
        return ResponseObject(False, "Client does not exist")
    return ResponseObject(data=d)

@app.post(f'{APP_PREFIX}/api/clients/generatePasswordResetLink')
def API_Clients_GeneratePasswordResetLink():
    data = request.get_json()
    clientId = data.get("ClientID")
    if not clientId:
        return ResponseObject(False, "Please provide ClientID")
    if not DashboardClients.GetClient(clientId):
        return ResponseObject(False, "Client does not exist")
    
    token = DashboardClients.GenerateClientPasswordResetToken(clientId)
    if token:
        return ResponseObject(data=token)
    return ResponseObject(False, "Failed to generate link")

@app.post(f'{APP_PREFIX}/api/clients/updateProfileName')
def API_Clients_UpdateProfile():
    data = request.get_json()
    clientId = data.get("ClientID")
    if not clientId:
        return ResponseObject(False, "Please provide ClientID")
    if not DashboardClients.GetClient(clientId):
        return ResponseObject(False, "Client does not exist")
    
    value = data.get('Name')
    return ResponseObject(status=DashboardClients.UpdateClientProfile(clientId, value))

@app.post(f'{APP_PREFIX}/api/clients/deleteClient')
def API_Clients_DeleteClient():
    data = request.get_json()
    clientId = data.get("ClientID")
    if not clientId:
        return ResponseObject(False, "Please provide ClientID")
    if not DashboardClients.GetClient(clientId):
        return ResponseObject(False, "Client does not exist")
    return ResponseObject(status=DashboardClients.DeleteClient(clientId))   

@app.get(f'{APP_PREFIX}/api/webHooks/getWebHooks')
def API_WebHooks_GetWebHooks():
    return ResponseObject(data=DashboardWebHooks.GetWebHooks())

@app.get(f'{APP_PREFIX}/api/webHooks/createWebHook')
def API_WebHooks_createWebHook():
    return ResponseObject(data=DashboardWebHooks.CreateWebHook().model_dump(
        exclude={'CreationDate'}
    ))

@app.post(f'{APP_PREFIX}/api/webHooks/updateWebHook')
def API_WebHooks_UpdateWebHook():
    data = request.get_json()
    status, msg = DashboardWebHooks.UpdateWebHook(data)
    return ResponseObject(status, msg)

@app.post(f'{APP_PREFIX}/api/webHooks/deleteWebHook')
def API_WebHooks_DeleteWebHook():
    data = request.get_json()
    status, msg = DashboardWebHooks.DeleteWebHook(data)
    return ResponseObject(status, msg)

@app.get(f'{APP_PREFIX}/api/webHooks/getWebHookSessions')
def API_WebHooks_GetWebHookSessions():
    webhookID = request.args.get('WebHookID')
    if not webhookID:
        return ResponseObject(False, "Please provide WebHookID")
    
    webHook = DashboardWebHooks.SearchWebHookByID(webhookID)
    if not webHook:
        return ResponseObject(False, "Webhook does not exist")
    
    return ResponseObject(data=DashboardWebHooks.GetWebHookSessions(webHook))
    

'''
Dashboard Overview API Routes
'''

@app.get(f'{APP_PREFIX}/api/dashboard/cluster-overview')
def API_GetClusterOverview():
    """Get cluster overview information for dashboard"""
    try:
        cluster_data = []
        
        # Get all configurations
        for config_name in WireguardConfigurations.keys():
            config = WireguardConfigurations.get(config_name)
            if not config:
                continue
            
            # Get nodes assigned to this config
            config_nodes = ConfigNodesManager.getNodesForConfig(config_name)
            
            # Only include configs with nodes assigned (cluster configs)
            if len(config_nodes) > 0:
                # Get endpoint group info
                endpoint_group = EndpointGroupsManager.getEndpointGroup(config_name)
                endpoint = endpoint_group.domain + ":" + str(endpoint_group.port) if endpoint_group else None
                
                # Check cluster health
                healthy_nodes = [cn for cn in config_nodes if cn.is_healthy]
                is_healthy = len(healthy_nodes) > 0
                
                # Get peer count for this config
                peer_count = len(config.getPeers())
                
                cluster_data.append({
                    'config_name': config_name,
                    'node_count': len(config_nodes),
                    'peer_count': peer_count,
                    'endpoint': endpoint,
                    'is_healthy': is_healthy,
                    'healthy_node_count': len(healthy_nodes)
                })
        
        return ResponseObject(data=cluster_data)
    except Exception as e:
        app.logger.error(f"Error getting cluster overview: {e}")
        return ResponseObject(False, "Failed to get cluster overview", data=[])

'''
Nodes Management API Routes
'''

@app.get(f'{APP_PREFIX}/api/nodes')
def API_GetNodes():
    """Get all nodes"""
    try:
        nodes = NodesManager.getAllNodes()
        include_interfaces = request.args.get('include_interfaces', 'false').lower() == 'true'
        
        nodes_data = []
        for node in nodes:
            node_data = node.toJson()
            if include_interfaces:
                interfaces = NodeInterfacesManager.getInterfacesByNodeId(node.id)
                node_data['interfaces'] = [iface.toJson() for iface in interfaces]
            nodes_data.append(node_data)
        
        return ResponseObject(data=nodes_data)
    except Exception as e:
        app.logger.error(f"Error getting nodes: {e}")
        return ResponseObject(False, "Failed to get nodes")

@app.get(f'{APP_PREFIX}/api/nodes/enabled')
def API_GetEnabledNodes():
    """Get only enabled nodes for peer creation UI"""
    try:
        nodes = NodesManager.getEnabledNodes()
        include_interfaces = request.args.get('include_interfaces', 'true').lower() == 'true'
        
        nodes_data = []
        for node in nodes:
            node_data = node.toJson()
            if include_interfaces:
                # For enabled nodes, include only enabled interfaces
                interfaces = NodeInterfacesManager.getEnabledInterfacesByNodeId(node.id)
                node_data['interfaces'] = [iface.toJson() for iface in interfaces]
            nodes_data.append(node_data)
        
        return ResponseObject(data=nodes_data)
    except Exception as e:
        app.logger.error(f"Error getting enabled nodes: {e}")
        return ResponseObject(False, "Failed to get enabled nodes")

@app.get(f'{APP_PREFIX}/api/nodes/<node_id>')
def API_GetNode(node_id):
    """Get node by ID"""
    try:
        node = NodesManager.getNodeById(node_id)
        if node:
            node_data = node.toJson()
            # Always include interfaces when getting a specific node
            interfaces = NodeInterfacesManager.getInterfacesByNodeId(node.id)
            node_data['interfaces'] = [iface.toJson() for iface in interfaces]
            return ResponseObject(data=node_data)
        return ResponseObject(False, "Node not found")
    except Exception as e:
        app.logger.error(f"Error getting node: {e}")
        return ResponseObject(False, "Failed to get node")

@app.post(f'{APP_PREFIX}/api/nodes')
def API_CreateNode():
    """Create a new node"""
    try:
        data = request.get_json()
        required_fields = ['name', 'agent_url']
        
        if not all(field in data for field in required_fields):
            return ResponseObject(False, "Missing required fields: name, agent_url")
        
        success, result = NodesManager.createNode(
            name=data['name'],
            agent_url=data['agent_url'],
            wg_interface=data.get('wg_interface', ''),  # Keep for backward compatibility
            endpoint=data.get('endpoint', ''),
            ip_pool_cidr=data.get('ip_pool_cidr', ''),
            secret=data.get('secret'),
            auth_type=data.get('auth_type', 'hmac'),
            weight=data.get('weight', 100),
            max_peers=data.get('max_peers', 0),
            enabled=data.get('enabled', True)
        )
        
        if not success:
            return ResponseObject(False, result)
        
        node = result
        
        # Create interfaces if provided
        # Priority 1: interfaces array (new approach)
        if 'interfaces' in data and isinstance(data['interfaces'], list):
            for iface_data in data['interfaces']:
                if 'interface_name' not in iface_data:
                    continue
                    
                NodeInterfacesManager.createInterface(
                    node_id=node.id,
                    interface_name=iface_data['interface_name'],
                    endpoint=iface_data.get('endpoint'),
                    ip_pool_cidr=iface_data.get('ip_pool_cidr'),
                    listen_port=iface_data.get('listen_port'),
                    address=iface_data.get('address'),
                    private_key_encrypted=iface_data.get('private_key_encrypted'),
                    post_up=iface_data.get('post_up'),
                    pre_down=iface_data.get('pre_down'),
                    mtu=iface_data.get('mtu'),
                    dns=iface_data.get('dns'),
                    table=iface_data.get('table'),
                    enabled=iface_data.get('enabled', True)
                )
        # Priority 2: Legacy wg_interface field (backward compatibility)
        elif data.get('wg_interface'):
            NodeInterfacesManager.createInterface(
                node_id=node.id,
                interface_name=data['wg_interface'],
                endpoint=data.get('endpoint'),
                ip_pool_cidr=data.get('ip_pool_cidr'),
                listen_port=data.get('override_listen_port'),
                private_key_encrypted=data.get('private_key_encrypted'),
                post_up=data.get('post_up'),
                pre_down=data.get('pre_down'),
                mtu=data.get('override_mtu'),
                dns=data.get('override_dns'),
                enabled=True
            )
        
        # Get created interfaces to include in response
        interfaces = NodeInterfacesManager.getInterfacesByNodeId(node.id)
        response_data = node.toJson()
        response_data['interfaces'] = [iface.toJson() for iface in interfaces]
        
        return ResponseObject(True, "Node created successfully", data=response_data)
    except Exception as e:
        app.logger.error(f"Error creating node: {e}")
        return ResponseObject(False, "Failed to create node")

@app.put(f'{APP_PREFIX}/api/nodes/<node_id>')
def API_UpdateNode(node_id):
    """Update node"""
    try:
        data = request.get_json()
        success, result = NodesManager.updateNode(node_id, data)
        
        if success:
            return ResponseObject(True, "Node updated successfully", data=result.toJson())
        return ResponseObject(False, result)
    except Exception as e:
        app.logger.error(f"Error updating node: {e}")
        return ResponseObject(False, "Failed to update node")

@app.post(f'{APP_PREFIX}/api/nodes/<node_id>/toggle')
def API_ToggleNode(node_id):
    """Enable/disable node"""
    try:
        data = request.get_json()
        enabled = data.get('enabled', True)
        success, result = NodesManager.toggleNodeEnabled(node_id, enabled)
        
        if success:
            status = "enabled" if enabled else "disabled"
            return ResponseObject(True, f"Node {status} successfully", data=result.toJson())
        return ResponseObject(False, result)
    except Exception as e:
        app.logger.error(f"Error toggling node: {e}")
        return ResponseObject(False, "Failed to toggle node")

@app.post(f'{APP_PREFIX}/api/nodes/<node_id>/test')
def API_TestNodeConnection(node_id):
    """Test connection to node"""
    try:
        success, message = NodesManager.testNodeConnection(node_id)
        return ResponseObject(success, message)
    except Exception as e:
        app.logger.error(f"Error testing node connection: {e}")
        return ResponseObject(False, "Failed to test connection")

@app.delete(f'{APP_PREFIX}/api/nodes/<node_id>')
def API_DeleteNode(node_id):
    """Delete node"""
    try:
        success, message = NodesManager.deleteNode(node_id)
        return ResponseObject(success, message)
    except Exception as e:
        app.logger.error(f"Error deleting node: {e}")
        return ResponseObject(False, "Failed to delete node")


# Node Interface Management API Endpoints

@app.get(f'{APP_PREFIX}/api/nodes/<node_id>/interfaces')
def API_GetNodeInterfaces(node_id):
    """Get all interfaces for a node"""
    try:
        interfaces = NodeInterfacesManager.getInterfacesByNodeId(node_id)
        return ResponseObject(True, "Interfaces retrieved successfully", 
                            data=[iface.toJson() for iface in interfaces])
    except Exception as e:
        app.logger.error(f"Error getting node interfaces: {e}")
        return ResponseObject(False, "Failed to get node interfaces")

@app.post(f'{APP_PREFIX}/api/nodes/<node_id>/interfaces')
def API_CreateNodeInterface(node_id):
    """Create a new interface for a node"""
    try:
        data = request.get_json()
        required_fields = ['interface_name']
        
        if not all(field in data for field in required_fields):
            return ResponseObject(False, "Missing required field: interface_name")
        
        success, result = NodeInterfacesManager.createInterface(
            node_id=node_id,
            interface_name=data['interface_name'],
            endpoint=data.get('endpoint'),
            ip_pool_cidr=data.get('ip_pool_cidr'),
            listen_port=data.get('listen_port'),
            address=data.get('address'),
            private_key_encrypted=data.get('private_key_encrypted'),
            post_up=data.get('post_up'),
            pre_down=data.get('pre_down'),
            mtu=data.get('mtu'),
            dns=data.get('dns'),
            table=data.get('table'),
            enabled=data.get('enabled', True)
        )
        
        if success:
            return ResponseObject(True, "Interface created successfully", data=result.toJson())
        return ResponseObject(False, result)
    except Exception as e:
        app.logger.error(f"Error creating node interface: {e}")
        return ResponseObject(False, "Failed to create node interface")

@app.get(f'{APP_PREFIX}/api/nodes/<node_id>/interfaces/<interface_id>')
def API_GetNodeInterface(node_id, interface_id):
    """Get a specific interface"""
    try:
        interface = NodeInterfacesManager.getInterfaceById(interface_id)
        if interface and interface.node_id == node_id:
            return ResponseObject(True, "Interface retrieved successfully", data=interface.toJson())
        return ResponseObject(False, "Interface not found")
    except Exception as e:
        app.logger.error(f"Error getting node interface: {e}")
        return ResponseObject(False, "Failed to get node interface")

@app.put(f'{APP_PREFIX}/api/nodes/<node_id>/interfaces/<interface_id>')
def API_UpdateNodeInterface(node_id, interface_id):
    """Update an interface"""
    try:
        # Verify the interface belongs to the node
        interface = NodeInterfacesManager.getInterfaceById(interface_id)
        if not interface or interface.node_id != node_id:
            return ResponseObject(False, "Interface not found")
        
        data = request.get_json()
        success, result = NodeInterfacesManager.updateInterface(interface_id, data)
        
        if success:
            return ResponseObject(True, "Interface updated successfully", data=result.toJson())
        return ResponseObject(False, result)
    except Exception as e:
        app.logger.error(f"Error updating node interface: {e}")
        return ResponseObject(False, "Failed to update node interface")

@app.delete(f'{APP_PREFIX}/api/nodes/<node_id>/interfaces/<interface_id>')
def API_DeleteNodeInterface(node_id, interface_id):
    """Delete an interface"""
    try:
        # Verify the interface belongs to the node
        interface = NodeInterfacesManager.getInterfaceById(interface_id)
        if not interface or interface.node_id != node_id:
            return ResponseObject(False, "Interface not found")
        
        success, message = NodeInterfacesManager.deleteInterface(interface_id)
        return ResponseObject(success, message)
    except Exception as e:
        app.logger.error(f"Error deleting node interface: {e}")
        return ResponseObject(False, "Failed to delete node interface")

@app.post(f'{APP_PREFIX}/api/nodes/<node_id>/interfaces/<interface_id>/toggle')
def API_ToggleNodeInterface(node_id, interface_id):
    """Toggle interface enabled status"""
    try:
        # Verify the interface belongs to the node
        interface = NodeInterfacesManager.getInterfaceById(interface_id)
        if not interface or interface.node_id != node_id:
            return ResponseObject(False, "Interface not found")
        
        data = request.get_json()
        enabled = data.get('enabled', not interface.enabled)
        success, result = NodeInterfacesManager.toggleInterfaceEnabled(interface_id, enabled)
        
        if success:
            return ResponseObject(True, "Interface toggled successfully", data=result.toJson())
        return ResponseObject(False, result)
    except Exception as e:
        app.logger.error(f"Error toggling node interface: {e}")
        return ResponseObject(False, "Failed to toggle node interface")


@app.get(f'{APP_PREFIX}/api/drift/nodes/<node_id>')
def API_GetNodeDrift(node_id):
    """Get drift report for a specific node"""
    try:
        node = NodesManager.getNodeById(node_id)
        if not node:
            return ResponseObject(False, "Node not found")
        
        # Get agent client
        client = NodesManager.getNodeAgentClient(node_id)
        if not client:
            return ResponseObject(False, "Failed to create agent client")
        
        # Get WireGuard dump from agent
        success, wg_data = client.get_wg_dump(node.wg_interface)
        
        if not success:
            return ResponseObject(False, f"Failed to get WireGuard dump: {wg_data}")
        
        # Detect drift
        drift_report = DriftDetector.detectDrift(node_id, wg_data)
        
        return ResponseObject(True, "Drift detection completed", data=drift_report)
        
    except Exception as e:
        app.logger.error(f"Error detecting drift for node {node_id}: {e}")
        return ResponseObject(False, "Failed to detect drift")


@app.get(f'{APP_PREFIX}/api/drift/nodes')
def API_GetAllNodesDrift():
    """Get drift report for all enabled nodes"""
    try:
        drift_reports = DriftDetector.detectDriftForAllNodes(NodesManager)
        
        # Calculate summary
        total_drift_count = sum(1 for report in drift_reports.values() if report.get('has_drift', False))
        total_issues = sum(report.get('summary', {}).get('total_issues', 0) for report in drift_reports.values())
        
        return ResponseObject(True, "Drift detection completed for all nodes", data={
            "nodes": drift_reports,
            "summary": {
                "total_nodes": len(drift_reports),
                "nodes_with_drift": total_drift_count,
                "total_issues": total_issues
            }
        })
        
    except Exception as e:
        app.logger.error(f"Error detecting drift for all nodes: {e}")
        return ResponseObject(False, "Failed to detect drift for all nodes")


@app.post(f'{APP_PREFIX}/api/drift/nodes/<node_id>/reconcile')
def API_ReconcileNodeDrift(node_id):
    """Reconcile drift for a specific node by applying panel configuration"""
    try:
        node = NodesManager.getNodeById(node_id)
        if not node:
            return ResponseObject(False, "Node not found")
        
        data = request.get_json()
        
        # Get what to reconcile from request body
        reconcile_missing = data.get('reconcile_missing', True)
        reconcile_mismatched = data.get('reconcile_mismatched', True)
        remove_unknown = data.get('remove_unknown', False)
        
        # Get agent client
        client = NodesManager.getNodeAgentClient(node_id)
        if not client:
            return ResponseObject(False, "Failed to create agent client")
        
        # First, detect current drift
        success, wg_data = client.get_wg_dump(node.wg_interface)
        if not success:
            return ResponseObject(False, f"Failed to get WireGuard dump: {wg_data}")
        
        drift_report = DriftDetector.detectDrift(node_id, wg_data)
        
        if not drift_report.get('has_drift', False):
            return ResponseObject(True, "No drift detected, nothing to reconcile")
        
        reconcile_results = {
            "added": [],
            "updated": [],
            "removed": [],
            "errors": []
        }
        
        # Reconcile missing peers (add them to node)
        if reconcile_missing:
            for missing_peer in drift_report.get('missing_peers', []):
                try:
                    # Get full peer data from DB
                    peer_public_key = missing_peer['public_key']
                    peer_data = {
                        'public_key': peer_public_key,
                        'allowed_ips': missing_peer.get('allowed_ips', []),
                        'persistent_keepalive': 0  # Default, would need to fetch from DB
                    }
                    
                    success, result = client.add_peer(node.wg_interface, peer_data)
                    if success:
                        reconcile_results['added'].append(peer_public_key)
                    else:
                        reconcile_results['errors'].append({
                            'peer': peer_public_key,
                            'action': 'add',
                            'error': result
                        })
                except Exception as e:
                    reconcile_results['errors'].append({
                        'peer': missing_peer['public_key'],
                        'action': 'add',
                        'error': str(e)
                    })
        
        # Reconcile mismatched peers (update them on node)
        if reconcile_mismatched:
            for mismatched_peer in drift_report.get('mismatched_peers', []):
                try:
                    peer_public_key = mismatched_peer['public_key']
                    
                    # Build update data from mismatches
                    update_data = {}
                    for mismatch in mismatched_peer.get('mismatches', []):
                        if mismatch['field'] == 'allowed_ips':
                            update_data['allowed_ips'] = mismatch['expected']
                        elif mismatch['field'] == 'persistent_keepalive':
                            update_data['persistent_keepalive'] = mismatch['expected']
                    
                    if update_data:
                        success, result = client.update_peer(node.wg_interface, peer_public_key, update_data)
                        if success:
                            reconcile_results['updated'].append(peer_public_key)
                        else:
                            reconcile_results['errors'].append({
                                'peer': peer_public_key,
                                'action': 'update',
                                'error': result
                            })
                except Exception as e:
                    reconcile_results['errors'].append({
                        'peer': mismatched_peer['public_key'],
                        'action': 'update',
                        'error': str(e)
                    })
        
        # Remove unknown peers (remove them from node)
        if remove_unknown:
            for unknown_peer in drift_report.get('unknown_peers', []):
                try:
                    peer_public_key = unknown_peer['public_key']
                    success, result = client.delete_peer(node.wg_interface, peer_public_key)
                    if success:
                        reconcile_results['removed'].append(peer_public_key)
                    else:
                        reconcile_results['errors'].append({
                            'peer': peer_public_key,
                            'action': 'remove',
                            'error': result
                        })
                except Exception as e:
                    reconcile_results['errors'].append({
                        'peer': unknown_peer['public_key'],
                        'action': 'remove',
                        'error': str(e)
                    })
        
        # Build response message
        message_parts = []
        if reconcile_results['added']:
            message_parts.append(f"Added {len(reconcile_results['added'])} peers")
        if reconcile_results['updated']:
            message_parts.append(f"Updated {len(reconcile_results['updated'])} peers")
        if reconcile_results['removed']:
            message_parts.append(f"Removed {len(reconcile_results['removed'])} peers")
        if reconcile_results['errors']:
            message_parts.append(f"{len(reconcile_results['errors'])} errors")
        
        message = ", ".join(message_parts) if message_parts else "No actions taken"
        
        return ResponseObject(True, message, data=reconcile_results)
        
    except Exception as e:
        app.logger.error(f"Error reconciling drift for node {node_id}: {e}")
        return ResponseObject(False, f"Failed to reconcile drift: {str(e)}")


# Interface-Level Configuration Management (Phase 6)
@app.get(f'{APP_PREFIX}/api/nodes/<node_id>/interface')
def API_GetNodeInterface(node_id):
    """Get node interface configuration"""
    try:
        success, result = NodesManager.getNodeInterfaceConfig(node_id)
        if success:
            return ResponseObject(True, "Interface configuration retrieved", data=result)
        else:
            return ResponseObject(False, result)
    except Exception as e:
        app.logger.error(f"Error getting node interface: {e}")
        return ResponseObject(False, "Failed to get node interface configuration")


@app.put(f'{APP_PREFIX}/api/nodes/<node_id>/interface')
def API_UpdateNodeInterface(node_id):
    """Update node interface configuration in panel database"""
    try:
        data = request.get_json()
        
        # Extract interface-level fields
        update_data = {}
        interface_fields = ['private_key_encrypted', 'override_listen_port', 
                          'post_up', 'pre_down', 'override_dns', 'override_mtu']
        
        for field in interface_fields:
            if field in data:
                update_data[field] = data[field]
        
        if not update_data:
            return ResponseObject(False, "No interface fields to update")
        
        success, result = NodesManager.updateNode(node_id, update_data)
        if success:
            return ResponseObject(True, "Node interface configuration updated", data=result.toJson() if hasattr(result, 'toJson') else result)
        else:
            return ResponseObject(False, result)
            
    except Exception as e:
        app.logger.error(f"Error updating node interface: {e}")
        return ResponseObject(False, "Failed to update node interface configuration")


@app.post(f'{APP_PREFIX}/api/nodes/<node_id>/interface/sync')
def API_SyncNodeInterface(node_id):
    """Manually sync interface configuration to node agent"""
    try:
        success, message = NodesManager.syncNodeInterfaceConfig(node_id)
        return ResponseObject(success, message)
    except Exception as e:
        app.logger.error(f"Error syncing node interface: {e}")
        return ResponseObject(False, "Failed to sync node interface configuration")


@app.post(f'{APP_PREFIX}/api/nodes/<node_id>/interface/enable')
def API_EnableNodeInterface(node_id):
    """Enable (bring up) node interface"""
    try:
        success, message = NodesManager.enableNodeInterface(node_id)
        return ResponseObject(success, message)
    except Exception as e:
        app.logger.error(f"Error enabling node interface: {e}")
        return ResponseObject(False, "Failed to enable node interface")


@app.post(f'{APP_PREFIX}/api/nodes/<node_id>/interface/disable')
def API_DisableNodeInterface(node_id):
    """Disable (bring down) node interface"""
    try:
        success, message = NodesManager.disableNodeInterface(node_id)
        return ResponseObject(success, message)
    except Exception as e:
        app.logger.error(f"Error disabling node interface: {e}")
        return ResponseObject(False, "Failed to disable node interface")


'''
Phase 8: Config-Node Assignment & Endpoint Group APIs
'''

@app.post(f'{APP_PREFIX}/api/configs/<config_name>/nodes')
def API_AssignNodeToConfig(config_name):
    """Assign a node to a configuration"""
    try:
        data = request.get_json()
        node_id = data.get('node_id')
        
        if not node_id:
            return ResponseObject(False, "node_id is required", status_code=400)
        
        # Verify config exists
        if config_name not in WireguardConfigurations.keys():
            return ResponseObject(False, "Configuration not found", status_code=404)
        
        # Verify node exists
        node = NodesManager.getNodeById(node_id)
        if not node:
            return ResponseObject(False, "Node not found", status_code=404)
        
        success, message = ConfigNodesManager.assignNodeToConfig(config_name, node_id)
        
        if success:
            # Log audit entry
            AuditLogManager.log(
                "node_assigned",
                "config_node",
                f"{config_name}:{node_id}",
                json.dumps({"config": config_name, "node": node_id}),
                session.get("username")
            )
        
        return ResponseObject(success, message)
    except Exception as e:
        app.logger.error(f"Error assigning node to config: {e}")
        return ResponseObject(False, "Failed to assign node to config", status_code=500)


@app.delete(f'{APP_PREFIX}/api/configs/<config_name>/nodes/<node_id>')
def API_RemoveNodeFromConfig(config_name, node_id):
    """Remove a node from a configuration"""
    try:
        # Verify config exists
        if config_name not in WireguardConfigurations.keys():
            return ResponseObject(False, "Configuration not found", status_code=404)
        
        # Get node
        node = NodesManager.getNodeById(node_id)
        if not node:
            return ResponseObject(False, "Node not found", status_code=404)
        
        # Create backup of interface config before removal
        from modules.NodeAgent import AgentClient
        agent = AgentClient(node.agent_url, node.secret_encrypted)
        backup_success, backup_data = agent.get_interface_config(node.wg_interface)
        
        if backup_success:
            # Store backup (simplified - could be stored in DB or filesystem)
            backup_info = {
                "config_name": config_name,
                "node_id": node_id,
                "timestamp": datetime.now().isoformat(),
                "config": backup_data
            }
            app.logger.info(f"Created backup for {config_name} on node {node_id}")
        
        # Migrate peers from this node
        migrated, migrate_msg, peer_count = PeerMigrationManager.migrate_peers_from_node(
            config_name, node_id
        )
        
        if not migrated and peer_count > 0:
            return ResponseObject(False, f"Failed to migrate peers: {migrate_msg}", status_code=500)
        
        # Remove node assignment
        success, message = ConfigNodesManager.removeNodeFromConfig(config_name, node_id)
        
        if success:
            # Delete interface on node
            delete_success, _ = agent.delete_interface(node.wg_interface)
            
            # Log audit entry
            AuditLogManager.log(
                "node_removed",
                "config_node",
                f"{config_name}:{node_id}",
                json.dumps({
                    "config": config_name,
                    "node": node_id,
                    "peers_migrated": peer_count,
                    "interface_deleted": delete_success
                }),
                session.get("username")
            )
            
            # Update DNS if endpoint group exists
            endpoint_group = EndpointGroupsManager.getEndpointGroup(config_name)
            if endpoint_group and endpoint_group.cloudflare_zone_id:
                _update_dns_for_config(config_name)
        
        return ResponseObject(success, message, {"peers_migrated": peer_count})
    except Exception as e:
        app.logger.error(f"Error removing node from config: {e}")
        return ResponseObject(False, "Failed to remove node from config", status_code=500)


@app.get(f'{APP_PREFIX}/api/configs/<config_name>/nodes')
def API_GetNodesForConfig(config_name):
    """Get all nodes assigned to a configuration"""
    try:
        # Verify config exists
        if config_name not in WireguardConfigurations.keys():
            return ResponseObject(False, "Configuration not found", status_code=404)
        
        config_nodes = ConfigNodesManager.getNodesForConfig(config_name)
        
        # Enrich with node details
        result = []
        for cn in config_nodes:
            node = NodesManager.getNodeById(cn.node_id)
            if node:
                node_data = node.toJson()
                node_data['config_node_id'] = cn.id
                node_data['is_healthy'] = cn.is_healthy
                result.append(node_data)
        
        return ResponseObject(True, "Nodes retrieved successfully", result)
    except Exception as e:
        app.logger.error(f"Error getting nodes for config: {e}")
        return ResponseObject(False, "Failed to get nodes for config", status_code=500)


@app.post(f'{APP_PREFIX}/api/configs/<config_name>/endpoint-group')
def API_CreateOrUpdateEndpointGroup(config_name):
    """Create or update endpoint group (Mode A / Cluster configuration)"""
    try:
        data = request.get_json()
        
        # Verify config exists
        if config_name not in WireguardConfigurations.keys():
            return ResponseObject(False, "Configuration not found", status_code=404)
        
        # Validate required fields
        required = ['domain', 'port']
        for field in required:
            if field not in data:
                return ResponseObject(False, f"{field} is required", status_code=400)
        
        # Ensure proxied is false
        data['proxied'] = False
        
        success, message = EndpointGroupsManager.createOrUpdateEndpointGroup(config_name, data)
        
        if success:
            # Update DNS if Cloudflare configured
            if data.get('cloudflare_zone_id'):
                _update_dns_for_config(config_name)
            
            # Log audit entry
            AuditLogManager.log(
                "endpoint_group_updated",
                "endpoint_group",
                config_name,
                json.dumps(data),
                session.get("username")
            )
        
        return ResponseObject(success, message)
    except Exception as e:
        app.logger.error(f"Error creating/updating endpoint group: {e}")
        return ResponseObject(False, "Failed to create/update endpoint group", status_code=500)


@app.get(f'{APP_PREFIX}/api/configs/<config_name>/endpoint-group')
def API_GetEndpointGroup(config_name):
    """Get endpoint group for a configuration"""
    try:
        # Verify config exists
        if config_name not in WireguardConfigurations.keys():
            return ResponseObject(False, "Configuration not found", status_code=404)
        
        endpoint_group = EndpointGroupsManager.getEndpointGroup(config_name)
        
        if endpoint_group:
            return ResponseObject(True, "Endpoint group retrieved successfully", endpoint_group.toJson())
        else:
            return ResponseObject(False, "Endpoint group not found", status_code=404)
    except Exception as e:
        app.logger.error(f"Error getting endpoint group: {e}")
        return ResponseObject(False, "Failed to get endpoint group", status_code=500)


@app.post(f'{APP_PREFIX}/api/configs/<config_name>/sync-dns')
def API_SyncDNS(config_name):
    """Manually trigger DNS sync for a configuration"""
    try:
        # Get endpoint group
        endpoint_group = EndpointGroupsManager.getEndpointGroup(config_name)
        if not endpoint_group:
            return ResponseObject(False, "No endpoint group configured for this configuration")
        
        # Get Cloudflare API token
        cloudflare_token = DashboardConfig.GetConfig("Cloudflare", "api_token")[1]
        if not cloudflare_token:
            return ResponseObject(False, "Cloudflare API token not configured")
        
        # Get nodes for this config
        config_nodes = ConfigNodesManager.getNodesForConfig(config_name)
        if not config_nodes:
            return ResponseObject(False, "No nodes assigned to this configuration")
        
        # Filter to healthy nodes if configured
        nodes_to_publish = config_nodes
        if endpoint_group.publish_only_healthy:
            nodes_to_publish = ConfigNodesManager.getHealthyNodesForConfig(config_name)
        
        if len(nodes_to_publish) < endpoint_group.min_nodes:
            return ResponseObject(False, f"Not enough healthy nodes (min: {endpoint_group.min_nodes})")
        
        # Extract IPs from node endpoints
        node_ips = []
        for cn in nodes_to_publish:
            node = NodesManager.getNodeById(cn.node_id)
            if node and node.endpoint:
                # Parse endpoint to get IP (format: ip:port or domain:port)
                endpoint_parts = node.endpoint.split(':')
                if endpoint_parts:
                    node_ips.append(endpoint_parts[0])
        
        if not node_ips:
            return ResponseObject(False, "No valid node IPs found")
        
        # Sync DNS
        CloudflareDNSManager.setAPIToken(cloudflare_token)
        success, message = CloudflareDNSManager.sync_node_ips_to_dns(
            endpoint_group.cloudflare_zone_id,
            endpoint_group.cloudflare_record_name,
            node_ips,
            endpoint_group.ttl
        )
        
        if success:
            # Log audit entry
            AuditLogManager.log(
                action="dns_updated",
                entity_type="endpoint_group",
                entity_id=config_name,
                details=json.dumps({"ips": node_ips, "record": endpoint_group.cloudflare_record_name}),
                user=session.get("username", "system")
            )
            return ResponseObject(True, "DNS records synchronized successfully")
        else:
            return ResponseObject(False, f"DNS sync failed: {message}")
            
    except Exception as e:
        app.logger.error(f"Error syncing DNS: {e}")
        traceback.print_exc()
        return ResponseObject(False, f"Failed to sync DNS: {str(e)}")


@app.get(f'{APP_PREFIX}/api/audit-logs')
def API_GetAuditLogs():
    """Query audit logs"""
    try:
        entity_type = request.args.get('entity_type')
        entity_id = request.args.get('entity_id')
        action = request.args.get('action')
        limit = int(request.args.get('limit', 100))
        offset = int(request.args.get('offset', 0))
        
        logs = AuditLogManager.get_logs(entity_type, entity_id, action, limit, offset)
        
        return ResponseObject(True, "Audit logs retrieved successfully", 
                            [log.toJson() for log in logs])
    except Exception as e:
        app.logger.error(f"Error getting audit logs: {e}")
        return ResponseObject(False, "Failed to get audit logs", status_code=500)


def _update_dns_for_config(config_name: str):
    """Helper function to update DNS records for a config's endpoint group"""
    try:
        endpoint_group = EndpointGroupsManager.getEndpointGroup(config_name)
        if not endpoint_group or not endpoint_group.cloudflare_zone_id:
            return
        
        # Get Cloudflare API token from config
        _, cf_token = DashboardConfig.GetConfig("Cloudflare", "api_token")
        if not cf_token:
            app.logger.warning("Cloudflare API token not configured")
            return
        
        CloudflareDNSManager.set_api_token(cf_token)
        
        # Get healthy nodes for this config
        if endpoint_group.publish_only_healthy:
            config_nodes = ConfigNodesManager.getHealthyNodesForConfig(config_name)
        else:
            config_nodes = ConfigNodesManager.getNodesForConfig(config_name)
        
        # Get node IPs
        node_ips = []
        for cn in config_nodes:
            node = NodesManager.getNodeById(cn.node_id)
            if node and node.enabled:
                # Extract IP from endpoint (format: ip:port or domain:port)
                endpoint = node.endpoint
                if endpoint and ':' in endpoint:
                    ip_part = endpoint.rsplit(':', 1)[0]
                    # Simple validation - if it looks like an IP, add it
                    try:
                        import ipaddress
                        ipaddress.ip_address(ip_part)
                        node_ips.append(ip_part)
                    except ValueError:
                        # Not an IP, skip
                        pass
        
        # Sync DNS records
        if node_ips:
            success, message = CloudflareDNSManager.sync_node_ips_to_dns(
                endpoint_group.cloudflare_zone_id,
                endpoint_group.cloudflare_record_name or endpoint_group.domain,
                node_ips,
                endpoint_group.ttl
            )
            
            if success:
                # Log audit entry
                AuditLogManager.log(
                    "dns_updated",
                    "dns_record",
                    config_name,
                    json.dumps({"domain": endpoint_group.domain, "ips": node_ips}),
                    "system"
                )
                app.logger.info(f"Updated DNS for {config_name}: {len(node_ips)} IPs")
            else:
                app.logger.error(f"Failed to update DNS for {config_name}: {message}")
    except Exception as e:
        app.logger.error(f"Error updating DNS for config: {e}")


'''
Index Page
'''

@app.get(f'{APP_PREFIX}/')
def index():
    return render_template('index.html')

if __name__ == "__main__":
    startThreads()
    DashboardPlugins.startThreads()
    app.run(host=app_ip, debug=False, port=app_port)