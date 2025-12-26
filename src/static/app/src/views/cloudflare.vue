<template>
  <div class="mt-5">
    <div class="container-fluid">
      <div class="d-flex align-items-center justify-content-between mb-4">
        <h3 class="text-body mb-0">
          <i class="bi bi-cloud-arrow-up me-2"></i>Cloudflare DNS Management
        </h3>
        <button 
          class="btn btn-primary" 
          @click="syncAllDNS" 
          :disabled="syncing"
        >
          <i class="bi bi-arrow-repeat me-2"></i>Sync All DNS
          <span v-if="syncing" class="spinner-border spinner-border-sm ms-2"></span>
        </button>
      </div>

      <!-- Configuration Status -->
      <div class="alert" :class="cloudflareConfigured ? 'alert-success' : 'alert-warning'" role="alert">
        <i class="bi me-2" :class="cloudflareConfigured ? 'bi-check-circle-fill' : 'bi-exclamation-triangle-fill'"></i>
        <span v-if="cloudflareConfigured">
          Cloudflare API is configured and ready
        </span>
        <span v-else>
          Cloudflare API token not configured. Go to <RouterLink to="/settings">Settings</RouterLink> to configure.
        </span>
      </div>

      <!-- Endpoint Groups -->
      <div v-if="loading" class="text-center py-5">
        <div class="spinner-border text-primary" role="status">
          <span class="visually-hidden">Loading...</span>
        </div>
      </div>

      <div v-else-if="endpointGroups.length === 0" class="alert alert-info">
        <i class="bi bi-info-circle me-2"></i>
        No cluster configurations with Cloudflare DNS setup yet. Configure endpoint groups for your multi-node configurations.
      </div>

      <div v-else class="row g-3">
        <div v-for="group in endpointGroups" :key="group.config_name" class="col-12">
          <div class="card h-100">
            <div class="card-header d-flex align-items-center justify-content-between">
              <h5 class="mb-0">
                <samp>{{ group.config_name }}</samp>
              </h5>
              <div class="d-flex gap-2">
                <span 
                  class="badge"
                  :class="getDNSStatusBadge(group.dns_status)"
                >
                  {{ group.dns_status || 'Unknown' }}
                </span>
                <button 
                  class="btn btn-sm btn-outline-primary" 
                  @click="syncSingleDNS(group.config_name)"
                  :disabled="syncing"
                >
                  <i class="bi bi-arrow-repeat me-1"></i>Sync
                </button>
              </div>
            </div>
            <div class="card-body">
              <div class="row">
                <div class="col-md-6">
                  <h6 class="text-muted mb-3">Configuration</h6>
                  <div class="mb-2">
                    <small class="text-muted">Domain:</small>
                    <div><strong>{{ group.domain }}</strong></div>
                  </div>
                  <div class="mb-2">
                    <small class="text-muted">Port:</small>
                    <div>{{ group.port }}</div>
                  </div>
                  <div class="mb-2">
                    <small class="text-muted">DNS Record:</small>
                    <div>{{ group.cloudflare_record_name }}</div>
                  </div>
                  <div class="mb-2">
                    <small class="text-muted">TTL:</small>
                    <div>{{ group.ttl }} seconds</div>
                  </div>
                  <div class="mb-2">
                    <small class="text-muted">Zone ID:</small>
                    <div><code class="small">{{ group.cloudflare_zone_id }}</code></div>
                  </div>
                </div>
                <div class="col-md-6">
                  <h6 class="text-muted mb-3">Active Nodes</h6>
                  <div v-if="group.nodes && group.nodes.length > 0">
                    <div v-for="node in group.nodes" :key="node.id" class="mb-2">
                      <div class="d-flex align-items-center">
                        <span 
                          class="badge me-2"
                          :class="node.is_healthy ? 'bg-success' : 'bg-warning'"
                        >
                          {{ node.is_healthy ? 'Healthy' : 'Unhealthy' }}
                        </span>
                        <span>{{ node.name }}</span>
                      </div>
                      <small class="text-muted">{{ node.endpoint || 'No endpoint' }}</small>
                    </div>
                  </div>
                  <div v-else class="text-muted">
                    <small>No nodes assigned</small>
                  </div>
                </div>
              </div>

              <!-- DNS Records -->
              <div v-if="group.dns_records && group.dns_records.length > 0" class="mt-3">
                <h6 class="text-muted mb-2">Current DNS Records</h6>
                <div class="table-responsive">
                  <table class="table table-sm table-bordered">
                    <thead>
                      <tr>
                        <th>Type</th>
                        <th>Name</th>
                        <th>Content</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="record in group.dns_records" :key="record.id">
                        <td><span class="badge bg-secondary">{{ record.type }}</span></td>
                        <td><code class="small">{{ record.name }}</code></td>
                        <td>{{ record.content }}</td>
                        <td>
                          <span class="badge" :class="record.proxied ? 'bg-warning' : 'bg-success'">
                            {{ record.proxied ? 'Proxied (Warning!)' : 'DNS Only' }}
                          </span>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>

              <!-- Auto-Migration Settings -->
              <div class="mt-3 p-3 bg-light rounded">
                <h6 class="mb-2">Auto-Migration Settings</h6>
                <div class="form-check">
                  <input 
                    class="form-check-input" 
                    type="checkbox" 
                    :checked="group.auto_migrate"
                    disabled
                  >
                  <label class="form-check-label">
                    Automatic peer migration enabled
                  </label>
                </div>
                <div class="form-check">
                  <input 
                    class="form-check-input" 
                    type="checkbox" 
                    :checked="group.publish_only_healthy"
                    disabled
                  >
                  <label class="form-check-label">
                    Publish only healthy nodes to DNS
                  </label>
                </div>
                <small class="text-muted d-block mt-2">
                  Minimum nodes required: {{ group.min_nodes }}
                </small>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- DNS Sync Logs -->
      <div class="card mt-4" v-if="dnsLogs.length > 0">
        <div class="card-header">
          <h5 class="mb-0">
            <i class="bi bi-journal-text me-2"></i>Recent DNS Sync Logs
          </h5>
        </div>
        <div class="card-body">
          <div class="table-responsive">
            <table class="table table-sm table-hover">
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Action</th>
                  <th>Configuration</th>
                  <th>Details</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="log in dnsLogs" :key="log.id">
                  <td><small>{{ formatTimestamp(log.timestamp) }}</small></td>
                  <td><span class="badge bg-info">{{ log.action }}</span></td>
                  <td><samp>{{ log.entity_id }}</samp></td>
                  <td><small>{{ parseLogDetails(log.details) }}</small></td>
                  <td>
                    <i class="bi" :class="log.success ? 'bi-check-circle text-success' : 'bi-x-circle text-danger'"></i>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { fetchGet, fetchPost } from '@/utilities/fetch.js'
import { DashboardConfigurationStore } from '@/stores/DashboardConfigurationStore.js'

export default {
  name: 'CloudflareView',
  setup() {
    const dashboardStore = DashboardConfigurationStore()
    return { dashboardStore }
  },
  data() {
    return {
      endpointGroups: [],
      dnsLogs: [],
      loading: true,
      syncing: false,
      cloudflareConfigured: false
    }
  },
  mounted() {
    this.checkCloudflareConfig()
    this.loadEndpointGroups()
    this.loadDNSLogs()
    
    // Auto-refresh every 30 seconds
    this.refreshInterval = setInterval(() => {
      this.loadEndpointGroups()
      this.loadDNSLogs()
    }, 30000)
  },
  beforeUnmount() {
    if (this.refreshInterval) {
      clearInterval(this.refreshInterval)
    }
  },
  methods: {
    checkCloudflareConfig() {
      this.cloudflareConfigured = this.dashboardStore.Configuration?.Cloudflare?.api_token?.length > 0
    },
    
    async loadEndpointGroups() {
      this.loading = true
      
      // Get all configurations
      await fetchGet('/api/getWireguardConfigurations', {}, async (res) => {
        if (res.status && res.data) {
          const configs = res.data
          const groups = []
          
          // For each config, check if it has an endpoint group
          for (const config of configs) {
            await fetchGet(`/api/configs/${config.Name}/endpoint-group`, {}, async (epRes) => {
              if (epRes.status && epRes.data) {
                const group = epRes.data
                
                // Get nodes for this config
                await fetchGet(`/api/configs/${config.Name}/nodes`, {}, (nodesRes) => {
                  if (nodesRes.status && nodesRes.data) {
                    group.nodes = nodesRes.data
                  }
                })
                
                // Get DNS records (simulated - in real implementation, fetch from Cloudflare)
                group.dns_records = []
                group.dns_status = 'Synced'
                
                groups.push(group)
              }
            })
          }
          
          this.endpointGroups = groups
        }
        this.loading = false
      })
    },
    
    async loadDNSLogs() {
      await fetchGet('/api/audit-logs', {
        action: 'dns_updated',
        limit: 20
      }, (res) => {
        if (res.status && res.data) {
          this.dnsLogs = res.data
        }
      })
    },
    
    async syncSingleDNS(configName) {
      this.syncing = true
      this.dashboardStore.newMessage('Cloudflare', `Syncing DNS for ${configName}...`, 'info')
      
      await fetchPost(`/api/configs/${configName}/sync-dns`, {}, (res) => {
        const msgType = res.status ? 'success' : 'danger'
        this.dashboardStore.newMessage('Cloudflare', res.message, msgType)
        
        if (res.status) {
          this.loadEndpointGroups()
          this.loadDNSLogs()
        }
      })
      
      this.syncing = false
    },
    
    async syncAllDNS() {
      this.syncing = true
      this.dashboardStore.newMessage('Cloudflare', 'Syncing all DNS records...', 'info')
      
      for (const group of this.endpointGroups) {
        await this.syncSingleDNS(group.config_name)
      }
      
      this.syncing = false
      this.dashboardStore.newMessage('Cloudflare', 'All DNS records synced', 'success')
    },
    
    getDNSStatusBadge(status) {
      switch (status) {
        case 'Synced':
          return 'bg-success'
        case 'Updating':
          return 'bg-info'
        case 'Failed':
          return 'bg-danger'
        default:
          return 'bg-secondary'
      }
    },
    
    formatTimestamp(timestamp) {
      if (!timestamp) return 'N/A'
      return new Date(timestamp).toLocaleString()
    },
    
    parseLogDetails(details) {
      if (!details) return 'N/A'
      try {
        const parsed = JSON.parse(details)
        return parsed.message || details
      } catch (e) {
        return details
      }
    }
  }
}
</script>

<style scoped>
.card {
  transition: box-shadow 0.2s;
}

.card:hover {
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}

code {
  background-color: #f8f9fa;
  padding: 2px 6px;
  border-radius: 3px;
}
</style>
