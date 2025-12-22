"""
Node Model
Represents a WireGuard node in the multi-node architecture
"""
from datetime import datetime


class Node:
    def __init__(self, tableData):
        self.id = tableData.get("id")
        self.name = tableData.get("name")
        self.agent_url = tableData.get("agent_url")
        self.auth_type = tableData.get("auth_type", "hmac")
        self.secret_encrypted = tableData.get("secret_encrypted", "")
        self.wg_interface = tableData.get("wg_interface", "")
        self.endpoint = tableData.get("endpoint", "")
        self.ip_pool_cidr = tableData.get("ip_pool_cidr", "")
        self.enabled = tableData.get("enabled", False)
        self.weight = tableData.get("weight", 100)
        self.max_peers = tableData.get("max_peers", 0)
        self.last_seen = tableData.get("last_seen")
        self.health_json = tableData.get("health_json", "{}")
        self.created_at = tableData.get("created_at")
        self.updated_at = tableData.get("updated_at")

    def toJson(self):
        return {
            "id": self.id,
            "name": self.name,
            "agent_url": self.agent_url,
            "auth_type": self.auth_type,
            "secret_encrypted": self.secret_encrypted,
            "wg_interface": self.wg_interface,
            "endpoint": self.endpoint,
            "ip_pool_cidr": self.ip_pool_cidr,
            "enabled": self.enabled,
            "weight": self.weight,
            "max_peers": self.max_peers,
            "last_seen": self.last_seen.strftime("%Y-%m-%d %H:%M:%S") if self.last_seen else None,
            "health_json": self.health_json,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }

    def __repr__(self):
        return str(self.toJson())
