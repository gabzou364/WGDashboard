"""
NodeInterface Model
Represents a WireGuard interface configuration for a node in multi-node architecture
"""
from datetime import datetime


class NodeInterface:
    def __init__(self, tableData):
        self.id = tableData.get("id")
        self.node_id = tableData.get("node_id")
        self.interface_name = tableData.get("interface_name")
        self.endpoint = tableData.get("endpoint")
        self.ip_pool_cidr = tableData.get("ip_pool_cidr")
        self.listen_port = tableData.get("listen_port")
        self.address = tableData.get("address")
        self.private_key_encrypted = tableData.get("private_key_encrypted")
        self.post_up = tableData.get("post_up")
        self.pre_down = tableData.get("pre_down")
        self.mtu = tableData.get("mtu")
        self.dns = tableData.get("dns")
        self.table = tableData.get("table")
        self.enabled = tableData.get("enabled", True)
        self.created_at = tableData.get("created_at")
        self.updated_at = tableData.get("updated_at")

    def toJson(self):
        return {
            "id": self.id,
            "node_id": self.node_id,
            "interface_name": self.interface_name,
            "endpoint": self.endpoint,
            "ip_pool_cidr": self.ip_pool_cidr,
            "listen_port": self.listen_port,
            "address": self.address,
            "private_key_encrypted": self.private_key_encrypted,
            "post_up": self.post_up,
            "pre_down": self.pre_down,
            "mtu": self.mtu,
            "dns": self.dns,
            "table": self.table,
            "enabled": self.enabled,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }

    def __repr__(self):
        return str(self.toJson())
