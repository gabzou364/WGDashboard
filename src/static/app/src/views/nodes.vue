<template>
  <div class="mt-5">
    <div class="container-fluid">
      <div class="d-flex align-items-center justify-content-between mb-4">
        <h3 class="text-body mb-0">
          <i class="bi bi-hdd-network me-2"></i>Nodes Management
        </h3>
        <button class="btn btn-primary" @click="showCreateModal = true">
          <i class="bi bi-plus-circle me-2"></i>Add Node
        </button>
      </div>

      <!-- Nodes List -->
      <div v-if="loading" class="text-center py-5">
        <div class="spinner-border text-primary" role="status">
          <span class="visually-hidden">Loading...</span>
        </div>
      </div>

      <div v-else-if="nodes.length === 0" class="alert alert-info">
        <i class="bi bi-info-circle me-2"></i>
        No nodes configured yet. Add your first node to enable multi-node management.
      </div>

      <div v-else class="row g-3">
        <div v-for="node in nodes" :key="node.id" class="col-12 col-md-6 col-lg-4">
          <div class="card h-100">
            <div class="card-body">
              <div class="d-flex justify-content-between align-items-start mb-3">
                <h5 class="card-title mb-0">
                  <i class="bi bi-hdd-network me-2"></i>{{ node.name }}
                </h5>
                <span 
                  class="badge"
                  :class="getStatusBadgeClass(node)"
                >
                  {{ getStatusText(node) }}
                </span>
              </div>

              <div class="mb-2">
                <small class="text-muted">Interface:</small>
                <div class="text-break">{{ node.wg_interface }}</div>
              </div>

              <div class="mb-2">
                <small class="text-muted">Agent URL:</small>
                <div class="text-break small">{{ node.agent_url }}</div>
              </div>

              <div class="mb-2">
                <small class="text-muted">Endpoint:</small>
                <div class="text-break">{{ node.endpoint || 'N/A' }}</div>
              </div>

              <div class="mb-2">
                <small class="text-muted">IP Pool:</small>
                <div>{{ node.ip_pool_cidr || 'N/A' }}</div>
              </div>

              <div class="mb-2">
                <small class="text-muted">Last Seen:</small>
                <div>{{ formatLastSeen(node.last_seen) }}</div>
              </div>

              <div class="d-flex gap-2 mt-3">
                <button 
                  class="btn btn-sm btn-outline-primary" 
                  @click="editNode(node)"
                  title="Edit"
                >
                  <i class="bi bi-pencil"></i>
                </button>
                <button 
                  class="btn btn-sm btn-outline-info" 
                  @click="testConnection(node.id)"
                  title="Test Connection"
                >
                  <i class="bi bi-plug"></i>
                </button>
                <button 
                  class="btn btn-sm"
                  :class="node.enabled ? 'btn-outline-warning' : 'btn-outline-success'"
                  @click="toggleNode(node)"
                  :title="node.enabled ? 'Disable' : 'Enable'"
                >
                  <i class="bi" :class="node.enabled ? 'bi-pause' : 'bi-play'"></i>
                </button>
                <button 
                  class="btn btn-sm btn-outline-danger" 
                  @click="confirmDelete(node)"
                  title="Delete"
                >
                  <i class="bi bi-trash"></i>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Create/Edit Modal -->
      <div 
        class="modal fade" 
        :class="{ show: showCreateModal }" 
        :style="{ display: showCreateModal ? 'block' : 'none' }"
        tabindex="-1"
        @click.self="closeModal"
      >
        <div class="modal-dialog modal-lg">
          <div class="modal-content">
            <div class="modal-header">
              <h5 class="modal-title">
                {{ editingNode ? 'Edit Node' : 'Add New Node' }}
              </h5>
              <button type="button" class="btn-close" @click="closeModal"></button>
            </div>
            <div class="modal-body">
              <form @submit.prevent="saveNode">
                <div class="mb-3">
                  <label class="form-label">Node Name *</label>
                  <input 
                    v-model="formData.name" 
                    type="text" 
                    class="form-control" 
                    required
                    placeholder="e.g., Node-EU-1"
                  />
                </div>

                <div class="mb-3">
                  <label class="form-label">Agent URL *</label>
                  <input 
                    v-model="formData.agent_url" 
                    type="url" 
                    class="form-control" 
                    required
                    placeholder="http://node1.example.com:8080"
                  />
                  <small class="text-muted">Full URL to the node agent API</small>
                </div>

                <div class="mb-3">
                  <label class="form-label">WireGuard Interface *</label>
                  <input 
                    v-model="formData.wg_interface" 
                    type="text" 
                    class="form-control" 
                    required
                    placeholder="wg0"
                  />
                </div>

                <div class="mb-3">
                  <label class="form-label">Endpoint</label>
                  <input 
                    v-model="formData.endpoint" 
                    type="text" 
                    class="form-control"
                    placeholder="vpn.example.com:51820"
                  />
                  <small class="text-muted">Public endpoint for clients to connect</small>
                </div>

                <div class="mb-3">
                  <label class="form-label">IP Pool CIDR</label>
                  <input 
                    v-model="formData.ip_pool_cidr" 
                    type="text" 
                    class="form-control"
                    placeholder="10.0.1.0/24"
                  />
                  <small class="text-muted">IP range for peer allocation on this node</small>
                </div>

                <div class="row">
                  <div class="col-md-6 mb-3">
                    <label class="form-label">Weight</label>
                    <input 
                      v-model.number="formData.weight" 
                      type="number" 
                      class="form-control"
                      min="1"
                      max="1000"
                    />
                    <small class="text-muted">Load balancing weight (default: 100)</small>
                  </div>

                  <div class="col-md-6 mb-3">
                    <label class="form-label">Max Peers</label>
                    <input 
                      v-model.number="formData.max_peers" 
                      type="number" 
                      class="form-control"
                      min="0"
                    />
                    <small class="text-muted">0 = unlimited</small>
                  </div>
                </div>

                <div class="mb-3" v-if="!editingNode">
                  <label class="form-label">Shared Secret (optional)</label>
                  <input 
                    v-model="formData.secret" 
                    type="text" 
                    class="form-control"
                    placeholder="Leave empty to auto-generate"
                  />
                  <small class="text-muted">HMAC secret for agent authentication</small>
                </div>

                <div class="mb-3 form-check">
                  <input 
                    v-model="formData.enabled" 
                    type="checkbox" 
                    class="form-check-input" 
                    id="nodeEnabled"
                  />
                  <label class="form-check-label" for="nodeEnabled">
                    Enabled
                  </label>
                </div>
              </form>
            </div>
            <div class="modal-footer">
              <button type="button" class="btn btn-secondary" @click="closeModal">Cancel</button>
              <button type="button" class="btn btn-primary" @click="saveNode">
                {{ editingNode ? 'Update' : 'Create' }}
              </button>
            </div>
          </div>
        </div>
      </div>
      
      <!-- Modal backdrop -->
      <div 
        v-if="showCreateModal" 
        class="modal-backdrop fade show"
        @click="closeModal"
      ></div>
    </div>
  </div>
</template>

<script>
import { fetchGet, fetchPost, fetchPut, fetchDelete } from '@/utilities/fetch.js'
import { DashboardConfigurationStore } from '@/stores/DashboardConfigurationStore.js'

export default {
  name: 'NodesView',
  setup() {
    const dashboardStore = DashboardConfigurationStore()
    return { dashboardStore }
  },
  data() {
    return {
      nodes: [],
      loading: true,
      showCreateModal: false,
      editingNode: null,
      formData: {
        name: '',
        agent_url: '',
        wg_interface: '',
        endpoint: '',
        ip_pool_cidr: '',
        weight: 100,
        max_peers: 0,
        secret: '',
        enabled: true
      }
    }
  },
  mounted() {
    this.loadNodes()
  },
  methods: {
    async loadNodes() {
      this.loading = true
      await fetchGet('/api/nodes', {}, (res) => {
        if (res.status) {
          this.nodes = res.data || []
        } else {
          this.dashboardStore.newMessage('Nodes', res.message || 'Failed to load nodes', 'danger')
        }
        this.loading = false
      })
    },
    
    editNode(node) {
      this.editingNode = node
      this.formData = {
        name: node.name,
        agent_url: node.agent_url,
        wg_interface: node.wg_interface,
        endpoint: node.endpoint || '',
        ip_pool_cidr: node.ip_pool_cidr || '',
        weight: node.weight || 100,
        max_peers: node.max_peers || 0,
        enabled: node.enabled
      }
      this.showCreateModal = true
    },
    
    async saveNode() {
      if (!this.formData.name || !this.formData.agent_url || !this.formData.wg_interface) {
        this.dashboardStore.newMessage('Nodes', 'Please fill all required fields', 'warning')
        return
      }

      const action = this.editingNode 
        ? () => fetchPut(`/api/nodes/${this.editingNode.id}`, this.formData, this.handleSaveResponse)
        : () => fetchPost('/api/nodes', this.formData, this.handleSaveResponse)
      
      await action()
    },
    
    handleSaveResponse(res) {
      if (res.status) {
        this.dashboardStore.newMessage('Nodes', res.message || 'Node saved successfully', 'success')
        this.closeModal()
        this.loadNodes()
      } else {
        this.dashboardStore.newMessage('Nodes', res.message || 'Failed to save node', 'danger')
      }
    },
    
    async toggleNode(node) {
      const newState = !node.enabled
      await fetchPost(`/api/nodes/${node.id}/toggle`, { enabled: newState }, (res) => {
        if (res.status) {
          this.dashboardStore.newMessage('Nodes', res.message, 'success')
          this.loadNodes()
        } else {
          this.dashboardStore.newMessage('Nodes', res.message || 'Failed to toggle node', 'danger')
        }
      })
    },
    
    async testConnection(nodeId) {
      this.dashboardStore.newMessage('Nodes', 'Testing connection...', 'info')
      await fetchPost(`/api/nodes/${nodeId}/test`, {}, (res) => {
        const messageType = res.status ? 'success' : 'danger'
        this.dashboardStore.newMessage('Nodes', res.message, messageType)
      })
    },
    
    confirmDelete(node) {
      if (confirm(`Are you sure you want to delete node "${node.name}"?`)) {
        this.deleteNode(node.id)
      }
    },
    
    async deleteNode(nodeId) {
      await fetchDelete(`/api/nodes/${nodeId}`, {}, (res) => {
        if (res.status) {
          this.dashboardStore.newMessage('Nodes', res.message, 'success')
          this.loadNodes()
        } else {
          this.dashboardStore.newMessage('Nodes', res.message || 'Failed to delete node', 'danger')
        }
      })
    },
    
    closeModal() {
      this.showCreateModal = false
      this.editingNode = null
      this.formData = {
        name: '',
        agent_url: '',
        wg_interface: '',
        endpoint: '',
        ip_pool_cidr: '',
        weight: 100,
        max_peers: 0,
        secret: '',
        enabled: true
      }
    },
    
    getStatusBadgeClass(node) {
      if (!node.enabled) return 'bg-secondary'
      
      try {
        const health = JSON.parse(node.health_json || '{}')
        if (health.status === 'online') return 'bg-success'
        if (health.status === 'offline') return 'bg-danger'
      } catch (e) {
        // Parse error
      }
      
      return 'bg-warning'
    },
    
    getStatusText(node) {
      if (!node.enabled) return 'Disabled'
      
      try {
        const health = JSON.parse(node.health_json || '{}')
        if (health.status === 'online') return 'Online'
        if (health.status === 'offline') return 'Offline'
        if (health.status === 'error') return 'Error'
      } catch (e) {
        // Parse error
      }
      
      return 'Unknown'
    },
    
    formatLastSeen(lastSeen) {
      if (!lastSeen) return 'Never'
      
      try {
        const date = new Date(lastSeen)
        const now = new Date()
        const diffMs = now - date
        const diffMins = Math.floor(diffMs / 60000)
        
        if (diffMins < 1) return 'Just now'
        if (diffMins < 60) return `${diffMins} min ago`
        if (diffMins < 1440) return `${Math.floor(diffMins / 60)} hours ago`
        return date.toLocaleString()
      } catch (e) {
        return lastSeen
      }
    }
  }
}
</script>

<style scoped>
.modal.show {
  opacity: 1;
}

.card {
  transition: transform 0.2s;
}

.card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(0,0,0,0.1);
}
</style>
