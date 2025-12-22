"""
Dashboard Configuration
"""
import configparser, secrets, os, pyotp, ipaddress, bcrypt
from sqlalchemy_utils import database_exists, create_database
import sqlalchemy as db
from datetime import datetime
from typing import Any
from flask import current_app
from .ConnectionString import ConnectionString
from .Utilities import (
    GetRemoteEndpoint, ValidateDNSAddress
)
from .DashboardAPIKey import DashboardAPIKey



class DashboardConfig:
    DashboardVersion = 'v4.3.1'
    ConfigurationPath = os.getenv('CONFIGURATION_PATH', '.')
    ConfigurationFilePath = os.path.join(ConfigurationPath, 'wg-dashboard.ini')
    
    def __init__(self):
        if not os.path.exists(DashboardConfig.ConfigurationFilePath):
            open(DashboardConfig.ConfigurationFilePath, "x")
        self.__config = configparser.RawConfigParser(strict=False)
        self.__config.read_file(open(DashboardConfig.ConfigurationFilePath, "r+"))
        self.hiddenAttribute = ["totp_key", "auth_req"]
        self.__default = {
            "Account": {
                "username": "admin",
                "password": "admin",
                "enable_totp": "false",
                "totp_verified": "false",
                "totp_key": pyotp.random_base32()
            },
            "Server": {
                "wg_conf_path": "/etc/wireguard",
                "awg_conf_path": "/etc/amnezia/amneziawg",
                "app_prefix": "",
                "app_ip": "0.0.0.0",
                "app_port": "10086",
                "auth_req": "true",
                "version": DashboardConfig.DashboardVersion,
                "dashboard_refresh_interval": "60000",
                "dashboard_peer_list_display": "grid",
                "dashboard_sort": "status",
                "dashboard_theme": "dark",
                "dashboard_api_key": "false",
                "dashboard_language": "en-US"
            },
            "Peers": {
                "peer_global_DNS": "1.1.1.1",
                "peer_endpoint_allowed_ip": "0.0.0.0/0",
                "peer_display_mode": "grid",
                "remote_endpoint": GetRemoteEndpoint(),
                "peer_MTU": "1420",
                "peer_keep_alive": "21"
            },
            "Other": {
                "welcome_session": "true"
            },
            "Database":{
                "type": "sqlite",
                "host": "",
                "port": "",
                "username": "",
                "password": ""
            },
            "Email":{
                "server": "",
                "port": "",
                "encryption": "",
                "username": "",
                "email_password": "",
                "authentication_required": "true",
                "send_from": "",
                "email_template": ""
            },
            "OIDC": {
                "admin_enable": "false",
                "client_enable": "false"
            },
            "Clients": {
                "enable": "true",
            },
            "WireGuardConfiguration": {
                "autostart": ""
            }
        }

        for section, keys in self.__default.items():
            for key, value in keys.items():
                exist, currentData = self.GetConfig(section, key)
                if not exist:
                    self.SetConfig(section, key, value, True)

        self.engine = db.create_engine(ConnectionString('wgdashboard'))
        self.dbMetadata = db.MetaData()
        self.__createAPIKeyTable()
        self.__createNodeGroupsTable()
        self.__createNodesTable()
        self.__createIPAllocationsTable()
        self.__createConfigNodesTable()
        self.__createEndpointGroupsTable()
        self.__createAuditLogTable()
        self.DashboardAPIKeys = self.__getAPIKeys()
        self.APIAccessed = False
        self.SetConfig("Server", "version", DashboardConfig.DashboardVersion)

    def getConnectionString(self, database) -> str or None:
        sqlitePath = os.path.join(DashboardConfig.ConfigurationPath, "db")
        
        if not os.path.isdir(sqlitePath):
            os.mkdir(sqlitePath)
        
        if self.GetConfig("Database", "type")[1] == "postgresql":
            cn = f'postgresql+psycopg2://{self.GetConfig("Database", "username")[1]}:{self.GetConfig("Database", "password")[1]}@{self.GetConfig("Database", "host")[1]}/{database}'
        elif self.GetConfig("Database", "type")[1] == "mysql":
            cn = f'mysql+mysqldb://{self.GetConfig("Database", "username")[1]}:{self.GetConfig("Database", "password")[1]}@{self.GetConfig("Database", "host")[1]}/{database}'
        else:
            cn = f'sqlite:///{os.path.join(sqlitePath, f"{database}.db")}'
        if not database_exists(cn):
            create_database(cn)
        return cn

    def __createAPIKeyTable(self):
        self.apiKeyTable = db.Table('DashboardAPIKeys', self.dbMetadata,
                                    db.Column("Key", db.String(255), nullable=False, primary_key=True),
                                    db.Column("CreatedAt",
                                              (db.DATETIME if self.GetConfig('Database', 'type')[1] == 'sqlite' else db.TIMESTAMP),
                                              server_default=db.func.now()
                                              ),
                                    db.Column("ExpiredAt",
                                              (db.DATETIME if self.GetConfig('Database', 'type')[1] == 'sqlite' else db.TIMESTAMP)
                                              )
                                    )
        self.dbMetadata.create_all(self.engine)
    
    def __createNodeGroupsTable(self):
        """Create node groups table for organizing nodes (Phase 5)"""
        self.nodeGroupsTable = db.Table('NodeGroups', self.dbMetadata,
                                       db.Column('id', db.String(255), nullable=False, primary_key=True),
                                       db.Column('name', db.String(255), nullable=False, unique=True),
                                       db.Column('description', db.Text, nullable=True),
                                       db.Column('region', db.String(100), nullable=True),
                                       db.Column('priority', db.Integer, server_default='0'),
                                       db.Column('created_at',
                                                (db.DATETIME if self.GetConfig('Database', 'type')[1] == 'sqlite' else db.TIMESTAMP),
                                                server_default=db.func.now()),
                                       db.Column('updated_at',
                                                (db.DATETIME if self.GetConfig('Database', 'type')[1] == 'sqlite' else db.TIMESTAMP),
                                                server_default=db.func.now(),
                                                onupdate=db.func.now())
                                       )
        self.dbMetadata.create_all(self.engine)
    
    def __createNodesTable(self):
        """Create nodes table for multi-node architecture"""
        self.nodesTable = db.Table('Nodes', self.dbMetadata,
                                   db.Column('id', db.String(255), nullable=False, primary_key=True),
                                   db.Column('name', db.String(255), nullable=False),
                                   db.Column('agent_url', db.String(512), nullable=False),
                                   db.Column('auth_type', db.String(50), server_default='hmac'),
                                   db.Column('secret_encrypted', db.Text),
                                   db.Column('wg_interface', db.String(50)),
                                   db.Column('endpoint', db.String(255)),
                                   db.Column('ip_pool_cidr', db.String(50)),
                                   db.Column('enabled', db.Boolean, server_default='1'),
                                   db.Column('weight', db.Integer, server_default='100'),
                                   db.Column('max_peers', db.Integer, server_default='0'),
                                   # Node grouping (Phase 5)
                                   db.Column('group_id', db.String(255), nullable=True),
                                   # Per-node overrides (Phase 4)
                                   db.Column('override_listen_port', db.Integer, nullable=True),
                                   db.Column('override_dns', db.String(255), nullable=True),
                                   db.Column('override_mtu', db.Integer, nullable=True),
                                   db.Column('override_keepalive', db.Integer, nullable=True),
                                   db.Column('override_endpoint_allowed_ip', db.Text, nullable=True),
                                   # Interface-level configuration (Phase 6)
                                   db.Column('private_key_encrypted', db.Text, nullable=True),
                                   db.Column('post_up', db.Text, nullable=True),
                                   db.Column('pre_down', db.Text, nullable=True),
                                   # Panel node identification (Phase 8)
                                   db.Column('is_panel_node', db.Boolean, server_default='0'),
                                   db.Column('last_seen', 
                                            (db.DATETIME if self.GetConfig('Database', 'type')[1] == 'sqlite' else db.TIMESTAMP)),
                                   db.Column('health_json', db.Text),
                                   db.Column('created_at',
                                            (db.DATETIME if self.GetConfig('Database', 'type')[1] == 'sqlite' else db.TIMESTAMP),
                                            server_default=db.func.now()),
                                   db.Column('updated_at',
                                            (db.DATETIME if self.GetConfig('Database', 'type')[1] == 'sqlite' else db.TIMESTAMP),
                                            server_default=db.func.now(),
                                            onupdate=db.func.now())
                                   )
        self.dbMetadata.create_all(self.engine)
    
    def __createIPAllocationsTable(self):
        """Create IP allocations table for per-node IP tracking"""
        self.ipAllocationsTable = db.Table('IPAllocations', self.dbMetadata,
                                          db.Column('id', db.Integer, primary_key=True, autoincrement=True),
                                          db.Column('node_id', db.String(255), nullable=False),
                                          db.Column('peer_id', db.String(255), nullable=False),
                                          db.Column('ip_address', db.String(50), nullable=False),
                                          db.Column('allocated_at',
                                                   (db.DATETIME if self.GetConfig('Database', 'type')[1] == 'sqlite' else db.TIMESTAMP),
                                                   server_default=db.func.now()),
                                          db.UniqueConstraint('node_id', 'ip_address', name='uq_node_ip')
                                          )
        self.dbMetadata.create_all(self.engine)
    
    def __createConfigNodesTable(self):
        """Create config-nodes mapping table for per-config node assignment (Phase 8)"""
        self.configNodesTable = db.Table('ConfigNodes', self.dbMetadata,
                                         db.Column('id', db.Integer, primary_key=True, autoincrement=True),
                                         db.Column('config_name', db.String(255), nullable=False),
                                         db.Column('node_id', db.String(255), nullable=False),
                                         db.Column('is_healthy', db.Boolean, server_default='1'),
                                         db.Column('created_at',
                                                  (db.DATETIME if self.GetConfig('Database', 'type')[1] == 'sqlite' else db.TIMESTAMP),
                                                  server_default=db.func.now()),
                                         db.Column('updated_at',
                                                  (db.DATETIME if self.GetConfig('Database', 'type')[1] == 'sqlite' else db.TIMESTAMP),
                                                  server_default=db.func.now(),
                                                  onupdate=db.func.now()),
                                         db.UniqueConstraint('config_name', 'node_id', name='uq_config_node')
                                         )
        self.dbMetadata.create_all(self.engine)
    
    def __createEndpointGroupsTable(self):
        """Create endpoint groups table for Mode A (Cluster/Single domain) configuration (Phase 8)"""
        self.endpointGroupsTable = db.Table('EndpointGroups', self.dbMetadata,
                                            db.Column('id', db.Integer, primary_key=True, autoincrement=True),
                                            db.Column('config_name', db.String(255), nullable=False, unique=True),
                                            db.Column('domain', db.String(255), nullable=False),
                                            db.Column('port', db.Integer, nullable=False),
                                            db.Column('cloudflare_zone_id', db.String(255), nullable=True),
                                            db.Column('cloudflare_record_name', db.String(255), nullable=True),
                                            db.Column('ttl', db.Integer, server_default='60'),
                                            db.Column('proxied', db.Boolean, server_default='0'),
                                            db.Column('auto_migrate', db.Boolean, server_default='1'),
                                            db.Column('publish_only_healthy', db.Boolean, server_default='1'),
                                            db.Column('min_nodes', db.Integer, server_default='1'),
                                            db.Column('created_at',
                                                     (db.DATETIME if self.GetConfig('Database', 'type')[1] == 'sqlite' else db.TIMESTAMP),
                                                     server_default=db.func.now()),
                                            db.Column('updated_at',
                                                     (db.DATETIME if self.GetConfig('Database', 'type')[1] == 'sqlite' else db.TIMESTAMP),
                                                     server_default=db.func.now(),
                                                     onupdate=db.func.now())
                                            )
        self.dbMetadata.create_all(self.engine)
    
    def __createAuditLogTable(self):
        """Create audit log table for tracking important changes (Phase 8)"""
        self.auditLogTable = db.Table('AuditLog', self.dbMetadata,
                                      db.Column('id', db.Integer, primary_key=True, autoincrement=True),
                                      db.Column('timestamp',
                                               (db.DATETIME if self.GetConfig('Database', 'type')[1] == 'sqlite' else db.TIMESTAMP),
                                               server_default=db.func.now()),
                                      db.Column('action', db.String(100), nullable=False),
                                      db.Column('entity_type', db.String(50), nullable=False),
                                      db.Column('entity_id', db.String(255), nullable=True),
                                      db.Column('details', db.Text, nullable=True),
                                      db.Column('user', db.String(255), nullable=True)
                                      )
        self.dbMetadata.create_all(self.engine)
    
    def __getAPIKeys(self) -> list[DashboardAPIKey]:
        try:
            with self.engine.connect() as conn:
                keys = conn.execute(self.apiKeyTable.select().where(
                    db.or_(self.apiKeyTable.columns.ExpiredAt.is_(None), self.apiKeyTable.columns.ExpiredAt > datetime.now())
                )).fetchall()
                fKeys = []
                for k in keys:
                    fKeys.append(DashboardAPIKey(k[0], k[1].strftime("%Y-%m-%d %H:%M:%S"), (k[2].strftime("%Y-%m-%d %H:%M:%S") if k[2] else None)))
                return fKeys
        except Exception as e:
            current_app.logger.error("API Keys error", e)
        return []

    def createAPIKeys(self, ExpiredAt = None):
        newKey = secrets.token_urlsafe(32)
        with self.engine.begin() as conn:
            conn.execute(
                self.apiKeyTable.insert().values({
                    "Key": newKey,
                    "ExpiredAt": ExpiredAt
                })
            )

        self.DashboardAPIKeys = self.__getAPIKeys()

    def deleteAPIKey(self, key):
        with self.engine.begin() as conn:
            conn.execute(
                self.apiKeyTable.update().values({
                    "ExpiredAt": datetime.now(),
                }).where(self.apiKeyTable.columns.Key == key)
            )

        self.DashboardAPIKeys = self.__getAPIKeys()

    def __configValidation(self, section : str, key: str, value: Any) -> tuple[bool, str]:
        if (type(value) is str and len(value) == 0
                and section not in ['Email', 'WireGuardConfiguration'] and
                (section == 'Peer' and key == 'peer_global_dns')):
            return False, "Field cannot be empty!"
        if section == "Peers" and key == "peer_global_dns" and len(value) > 0:
            return ValidateDNSAddress(value)
        if section == "Peers" and key == "peer_endpoint_allowed_ip":
            value = value.split(",")
            for i in value:
                i = i.strip()
                try:
                    ipaddress.ip_network(i, strict=False)
                except Exception as e:
                    return False, str(e)
        if section == "Server" and key == "wg_conf_path":
            if not os.path.exists(value):
                return False, f"{value} is not a valid path"
        if section == "Account" and key == "password":
            if self.GetConfig("Account", "password")[0]:
                if not self.__checkPassword(
                        value["currentPassword"], self.GetConfig("Account", "password")[1].encode("utf-8")):
                    return False, "Current password does not match."
                if value["newPassword"] != value["repeatNewPassword"]:
                    return False, "New passwords does not match"
        return True, ""

    def generatePassword(self, plainTextPassword: str):
        return bcrypt.hashpw(plainTextPassword.encode("utf-8"), bcrypt.gensalt())

    def __checkPassword(self, plainTextPassword: str, hashedPassword: bytes):
        return bcrypt.checkpw(plainTextPassword.encode("utf-8"), hashedPassword)

    def SetConfig(self, section: str, key: str, value: str | bool | list[str] | dict[str, str], init: bool = False) -> tuple[bool, str] | tuple[bool, None]:
        if key in self.hiddenAttribute and not init:
            return False, None

        if not init:
            valid, msg = self.__configValidation(section, key, value)
            if not valid:
                return False, msg

        if section == "Account" and key == "password":
            if not init:
                value = self.generatePassword(value["newPassword"]).decode("utf-8")
            else:
                value = self.generatePassword(value).decode("utf-8")

        if section == "Email" and key == "email_template":
            value = value.encode('unicode_escape').decode('utf-8')

        if section == "Server" and key == "wg_conf_path":
            if not os.path.exists(value):
                return False, "Path does not exist"

        if section not in self.__config:
            if init:
                self.__config[section] = {}
            else:
                return False, "Section does not exist"

        if ((key not in self.__config[section].keys() and init) or
                (key in self.__config[section].keys())):
            if type(value) is bool:
                if value:
                    self.__config[section][key] = "true"
                else:
                    self.__config[section][key] = "false"
            elif type(value) in [int, float]:
                self.__config[section][key] = str(value)
            elif type(value) is list:
                self.__config[section][key] = "||".join(value).strip("||")
            else:
                self.__config[section][key] = fr"{value}"
            return self.SaveConfig(), ""
        else:
            return False, f"{key} does not exist under {section}"

    def SaveConfig(self) -> bool:
        try:
            with open(DashboardConfig.ConfigurationFilePath, "w+", encoding='utf-8') as configFile:
                self.__config.write(configFile)
            return True
        except Exception as e:
            return False

    def GetConfig(self, section, key) ->tuple[bool, bool] | tuple[bool, str] | tuple[bool, list[str]] | tuple[bool, None]:
        if section not in self.__config:
            return False, None

        if key not in self.__config[section]:
            return False, None

        if section == "Email" and key == "email_template":
            return True, self.__config[section][key].encode('utf-8').decode('unicode_escape')

        if section == "WireGuardConfiguration" and key == "autostart":
            return True, list(filter(lambda x: len(x) > 0, self.__config[section][key].split("||")))

        if self.__config[section][key] in ["1", "yes", "true", "on"]:
            return True, True

        if self.__config[section][key] in ["0", "no", "false", "off"]:
            return True, False


        return True, self.__config[section][key]

    def toJson(self) -> dict[str, dict[Any, Any]]:
        the_dict = {}

        for section in self.__config.sections():
            the_dict[section] = {}
            for key, val in self.__config.items(section):
                if key not in self.hiddenAttribute:
                    the_dict[section][key] = self.GetConfig(section, key)[1]
        return the_dict
