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
        # Node grouping (Phase 5)
        self.group_id = tableData.get("group_id")
        # Per-node overrides (Phase 4)
        self.override_listen_port = tableData.get("override_listen_port")
        self.override_dns = tableData.get("override_dns")
        self.override_mtu = tableData.get("override_mtu")
        self.override_keepalive = tableData.get("override_keepalive")
        self.override_endpoint_allowed_ip = tableData.get("override_endpoint_allowed_ip")
        # Interface-level configuration (Phase 6)
        self.private_key_encrypted = tableData.get("private_key_encrypted")
        self.post_up = tableData.get("post_up")
        self.pre_down = tableData.get("pre_down")
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
            "group_id": self.group_id,
            "override_listen_port": self.override_listen_port,
            "override_dns": self.override_dns,
            "override_mtu": self.override_mtu,
            "override_keepalive": self.override_keepalive,
            "override_endpoint_allowed_ip": self.override_endpoint_allowed_ip,
            "private_key_encrypted": self.private_key_encrypted,
            "post_up": self.post_up,
            "pre_down": self.pre_down,
            "last_seen": self.last_seen.strftime("%Y-%m-%d %H:%M:%S") if self.last_seen else None,
            "health_json": self.health_json,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }

    def __repr__(self):
        return str(self.toJson())
