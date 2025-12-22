"""
IP Allocation Manager
Handles per-node IP address allocation with CIDR-aware logic
"""
import ipaddress
import sqlalchemy as db
from typing import Optional, Tuple, List
from flask import current_app


class IPAllocationManager:
    """Manager for allocating IP addresses from node pools"""
    
    def __init__(self, DashboardConfig):
        self.DashboardConfig = DashboardConfig
        self.engine = DashboardConfig.engine
        self.ipAllocationsTable = DashboardConfig.ipAllocationsTable
        self.nodesTable = DashboardConfig.nodesTable
    
    def allocateIP(self, node_id: str, peer_id: str, max_retries: int = 3) -> Tuple[bool, str]:
        """
        Allocate a free IP address from node's pool for a peer
        
        Args:
            node_id: Node ID to allocate from
            peer_id: Peer ID (public key) to allocate for
            max_retries: Maximum number of retries on conflict
            
        Returns:
            Tuple of (success: bool, ip_address or error_message)
        """
        try:
            # Get node's IP pool CIDR
            with self.engine.connect() as conn:
                result = conn.execute(
                    self.nodesTable.select().where(self.nodesTable.c.id == node_id)
                ).mappings().fetchone()
                
                if not result:
                    return False, "Node not found"
                
                ip_pool_cidr = result.get('ip_pool_cidr')
                if not ip_pool_cidr:
                    return False, "Node does not have an IP pool configured"
            
            # Parse CIDR
            try:
                network = ipaddress.ip_network(ip_pool_cidr, strict=False)
            except Exception as e:
                return False, f"Invalid IP pool CIDR: {e}"
            
            # Get already allocated IPs for this node
            allocated_ips = self._getAllocatedIPs(node_id)
            
            # Try to allocate an IP with retries
            for attempt in range(max_retries):
                # Find next available IP
                available_ip = self._findAvailableIP(network, allocated_ips)
                if not available_ip:
                    return False, "No available IPs in node's pool"
                
                # Try to allocate (handle race conditions with retry)
                success = self._insertAllocation(node_id, peer_id, available_ip)
                if success:
                    return True, available_ip
                
                # If failed (likely due to conflict), refresh allocated IPs and retry
                allocated_ips = self._getAllocatedIPs(node_id)
            
            return False, "Failed to allocate IP after retries (possible conflict)"
            
        except Exception as e:
            current_app.logger.error(f"Error allocating IP: {e}")
            return False, str(e)
    
    def _getAllocatedIPs(self, node_id: str) -> set:
        """Get set of already allocated IPs for a node"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(
                    db.select(self.ipAllocationsTable.c.ip_address)
                    .where(self.ipAllocationsTable.c.node_id == node_id)
                ).fetchall()
                return {row[0] for row in result}
        except Exception as e:
            current_app.logger.error(f"Error getting allocated IPs: {e}")
            return set()
    
    def _findAvailableIP(self, network: ipaddress.IPv4Network, allocated_ips: set) -> Optional[str]:
        """
        Find next available IP in network
        
        Reserves first usable address (.1 for most subnets) for server/gateway
        Note: network.hosts() already excludes network and broadcast addresses
        """
        hosts = list(network.hosts())
        if not hosts:
            return None
        
        # Reserve first usable host for server/gateway (typically .1)
        # Start from second host address
        for host in hosts[1:]:
            ip_str = f"{host}/{network.prefixlen}"
            if ip_str not in allocated_ips:
                return ip_str
        
        return None
    
    def _insertAllocation(self, node_id: str, peer_id: str, ip_address: str) -> bool:
        """
        Insert allocation record
        
        Returns:
            bool: True if successful, False if conflict
        """
        try:
            with self.engine.begin() as conn:
                conn.execute(
                    self.ipAllocationsTable.insert().values({
                        'node_id': node_id,
                        'peer_id': peer_id,
                        'ip_address': ip_address
                    })
                )
            return True
        except db.exc.IntegrityError:
            # Unique constraint violation (node_id, ip_address already exists)
            return False
        except Exception as e:
            current_app.logger.error(f"Error inserting allocation: {e}")
            return False
    
    def deallocateIP(self, node_id: str, peer_id: str) -> Tuple[bool, str]:
        """
        Deallocate IP address for a peer
        
        Args:
            node_id: Node ID
            peer_id: Peer ID (public key)
            
        Returns:
            Tuple of (success: bool, message)
        """
        try:
            with self.engine.begin() as conn:
                conn.execute(
                    self.ipAllocationsTable.delete().where(
                        db.and_(
                            self.ipAllocationsTable.c.node_id == node_id,
                            self.ipAllocationsTable.c.peer_id == peer_id
                        )
                    )
                )
            return True, "IP deallocated successfully"
        except Exception as e:
            current_app.logger.error(f"Error deallocating IP: {e}")
            return False, str(e)
    
    def getAllocatedIP(self, node_id: str, peer_id: str) -> Optional[str]:
        """
        Get allocated IP for a peer on a node
        
        Returns:
            IP address string or None
        """
        try:
            with self.engine.connect() as conn:
                result = conn.execute(
                    self.ipAllocationsTable.select().where(
                        db.and_(
                            self.ipAllocationsTable.c.node_id == node_id,
                            self.ipAllocationsTable.c.peer_id == peer_id
                        )
                    )
                ).mappings().fetchone()
                
                if result:
                    return result['ip_address']
                return None
        except Exception as e:
            current_app.logger.error(f"Error getting allocated IP: {e}")
            return None
    
    def getNodeStats(self, node_id: str) -> dict:
        """
        Get allocation statistics for a node
        
        Returns:
            Dict with total_ips, allocated_ips, available_ips
        """
        try:
            # Get node's IP pool
            with self.engine.connect() as conn:
                result = conn.execute(
                    self.nodesTable.select().where(self.nodesTable.c.id == node_id)
                ).mappings().fetchone()
                
                if not result or not result.get('ip_pool_cidr'):
                    return {'total_ips': 0, 'allocated_ips': 0, 'available_ips': 0}
                
                network = ipaddress.ip_network(result['ip_pool_cidr'], strict=False)
                # Subtract 2 for network/broadcast, and 1 for gateway
                total_ips = network.num_addresses - 3 if network.num_addresses > 3 else 0
                
                # Get allocated count
                allocated_count = conn.execute(
                    db.select(db.func.count())
                    .select_from(self.ipAllocationsTable)
                    .where(self.ipAllocationsTable.c.node_id == node_id)
                ).scalar()
                
                return {
                    'total_ips': total_ips,
                    'allocated_ips': allocated_count,
                    'available_ips': max(0, total_ips - allocated_count)
                }
        except Exception as e:
            current_app.logger.error(f"Error getting node stats: {e}")
            return {'total_ips': 0, 'allocated_ips': 0, 'available_ips': 0}
