<template>
  <div class="mt-5">
    <div class="container-fluid">
      <div class="d-flex align-items-center justify-content-between mb-4">
        <h3 class="text-body mb-0">
          <i class="bi bi-graph-up me-2"></i>Traffic Monitoring
        </h3>
        <div class="d-flex gap-2">
          <select v-model="selectedConfig" class="form-select form-select-sm" @change="loadTrafficData">
            <option value="">All Configurations</option>
            <option v-for="config in configurations" :key="config.Name" :value="config.Name">
              {{ config.Name }}
            </option>
          </select>
          <button 
            class="btn btn-sm btn-outline-secondary" 
            @click="loadTrafficData"
            :disabled="loading"
          >
            <i class="bi bi-arrow-repeat me-1"></i>Refresh
          </button>
        </div>
      </div>

      <!-- Summary Cards -->
      <div class="row g-3 mb-4">
        <div class="col-md-3">
          <div class="card border-0 shadow-sm">
            <div class="card-body">
              <div class="d-flex align-items-center">
                <div class="stat-icon bg-primary-subtle text-primary rounded-3 p-2 me-3">
                  <i class="bi bi-arrow-down-up fs-5"></i>
                </div>
                <div>
                  <small class="text-muted d-block">Total Traffic</small>
                  <h5 class="mb-0">{{ formatBytes(totalTraffic) }}</h5>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div class="col-md-3">
          <div class="card border-0 shadow-sm">
            <div class="card-body">
              <div class="d-flex align-items-center">
                <div class="stat-icon bg-success-subtle text-success rounded-3 p-2 me-3">
                  <i class="bi bi-arrow-up fs-5"></i>
                </div>
                <div>
                  <small class="text-muted d-block">Total Upload</small>
                  <h5 class="mb-0">{{ formatBytes(totalUpload) }}</h5>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div class="col-md-3">
          <div class="card border-0 shadow-sm">
            <div class="card-body">
              <div class="d-flex align-items-center">
                <div class="stat-icon bg-info-subtle text-info rounded-3 p-2 me-3">
                  <i class="bi bi-arrow-down fs-5"></i>
                </div>
                <div>
                  <small class="text-muted d-block">Total Download</small>
                  <h5 class="mb-0">{{ formatBytes(totalDownload) }}</h5>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div class="col-md-3">
          <div class="card border-0 shadow-sm">
            <div class="card-body">
              <div class="d-flex align-items-center">
                <div class="stat-icon bg-warning-subtle text-warning rounded-3 p-2 me-3">
                  <i class="bi bi-people fs-5"></i>
                </div>
                <div>
                  <small class="text-muted d-block">Active Peers</small>
                  <h5 class="mb-0">{{ activePeers }}</h5>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Top Peers by Traffic -->
      <div class="card mb-4">
        <div class="card-header bg-transparent">
          <h5 class="mb-0">
            <i class="bi bi-bar-chart-fill me-2"></i>Top Peers by Traffic
          </h5>
        </div>
        <div class="card-body">
          <div v-if="loading" class="text-center py-5">
            <div class="spinner-border text-primary" role="status">
              <span class="visually-hidden">Loading...</span>
            </div>
          </div>
          
          <div v-else-if="topPeers.length === 0" class="text-muted text-center py-5">
            No traffic data available
          </div>
          
          <div v-else class="table-responsive">
            <table class="table table-hover align-middle mb-0">
              <thead class="table-light">
                <tr>
                  <th style="width: 50px">#</th>
                  <th>Peer Name</th>
                  <th>Configuration</th>
                  <th>Total Traffic</th>
                  <th>Upload</th>
                  <th>Download</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(peer, index) in topPeers" :key="peer.id">
                  <td>{{ index + 1 }}</td>
                  <td>
                    <strong>{{ peer.name || 'Untitled Peer' }}</strong>
                    <br>
                    <small class="text-muted">
                      <samp>{{ peer.id.substring(0, 20) }}...</samp>
                    </small>
                  </td>
                  <td>
                    <RouterLink 
                      :to="`/configuration/${peer.config}/peers`"
                      class="text-decoration-none"
                    >
                      <samp>{{ peer.config }}</samp>
                    </RouterLink>
                  </td>
                  <td>
                    <strong>{{ formatBytes(peer.total) }}</strong>
                    <div class="progress mt-1" style="height: 4px;">
                      <div 
                        class="progress-bar bg-primary" 
                        :style="{width: (peer.total / topPeers[0].total * 100) + '%'}"
                      ></div>
                    </div>
                  </td>
                  <td class="text-success">
                    <i class="bi bi-arrow-up me-1"></i>
                    {{ formatBytes(peer.upload) }}
                  </td>
                  <td class="text-info">
                    <i class="bi bi-arrow-down me-1"></i>
                    {{ formatBytes(peer.download) }}
                  </td>
                  <td>
                    <span 
                      class="badge"
                      :class="peer.status === 'running' ? 'bg-success' : 'bg-secondary'"
                    >
                      {{ peer.status === 'running' ? 'Active' : 'Inactive' }}
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- Configuration Breakdown -->
      <div class="card" v-if="!selectedConfig">
        <div class="card-header bg-transparent">
          <h5 class="mb-0">
            <i class="bi bi-pie-chart-fill me-2"></i>Traffic by Configuration
          </h5>
        </div>
        <div class="card-body">
          <div class="row g-3">
            <div v-for="config in configTraffic" :key="config.name" class="col-md-6 col-lg-4">
              <div class="card h-100 border">
                <div class="card-body">
                  <h6 class="card-title">
                    <RouterLink 
                      :to="`/configuration/${config.name}/peers`"
                      class="text-decoration-none"
                    >
                      <samp>{{ config.name }}</samp>
                    </RouterLink>
                  </h6>
                  <div class="mb-2">
                    <small class="text-muted">Total Traffic</small>
                    <h5 class="mb-0">{{ formatBytes(config.total) }}</h5>
                  </div>
                  <div class="row g-2">
                    <div class="col-6">
                      <small class="text-muted d-block">Upload</small>
                      <small class="text-success">
                        <i class="bi bi-arrow-up me-1"></i>
                        <strong>{{ formatBytes(config.upload) }}</strong>
                      </small>
                    </div>
                    <div class="col-6">
                      <small class="text-muted d-block">Download</small>
                      <small class="text-info">
                        <i class="bi bi-arrow-down me-1"></i>
                        <strong>{{ formatBytes(config.download) }}</strong>
                      </small>
                    </div>
                  </div>
                  <hr>
                  <div class="d-flex justify-content-between align-items-center">
                    <small class="text-muted">
                      <i class="bi bi-people me-1"></i>
                      {{ config.peers }} peers
                    </small>
                    <small class="text-muted">
                      <span 
                        class="badge"
                        :class="config.status ? 'bg-success' : 'bg-secondary'"
                      >
                        {{ config.status ? 'Active' : 'Inactive' }}
                      </span>
                    </small>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { fetchGet } from '@/utilities/fetch.js'
import { WireguardConfigurationsStore } from '@/stores/WireguardConfigurationsStore.js'

export default {
  name: 'TrafficMonitoringView',
  setup() {
    const wireguardStore = WireguardConfigurationsStore()
    return { wireguardStore }
  },
  data() {
    return {
      loading: true,
      selectedConfig: '',
      topPeers: [],
      configTraffic: [],
      refreshInterval: null
    }
  },
  computed: {
    configurations() {
      return this.wireguardStore.Configurations || []
    },
    totalTraffic() {
      return this.configTraffic.reduce((sum, c) => sum + c.total, 0)
    },
    totalUpload() {
      return this.configTraffic.reduce((sum, c) => sum + c.upload, 0)
    },
    totalDownload() {
      return this.configTraffic.reduce((sum, c) => sum + c.download, 0)
    },
    activePeers() {
      return this.topPeers.filter(p => p.status === 'running').length
    }
  },
  mounted() {
    this.loadTrafficData()
    
    // Auto-refresh every 10 seconds
    this.refreshInterval = setInterval(() => {
      this.loadTrafficData()
    }, 10000)
  },
  beforeUnmount() {
    if (this.refreshInterval) {
      clearInterval(this.refreshInterval)
    }
  },
  methods: {
    async loadTrafficData() {
      this.loading = true
      
      // Get configurations if not loaded
      if (!this.wireguardStore.Configurations) {
        await this.wireguardStore.getConfigurations()
      }
      
      const configs = this.selectedConfig 
        ? this.configurations.filter(c => c.Name === this.selectedConfig)
        : this.configurations
      
      const allPeers = []
      const configStats = []
      
      // Process each configuration
      for (const config of configs) {
        await fetchGet('/api/getWireguardConfigurationInfo', {
          configurationName: config.Name
        }, (res) => {
          if (res.status && res.data) {
            const peers = res.data.configurationPeers || []
            
            // Calculate config totals
            let configTotal = 0
            let configUpload = 0
            let configDownload = 0
            
            peers.forEach(peer => {
              const upload = (peer.cumu_sent || 0) + (peer.total_sent || 0)
              const download = (peer.cumu_receive || 0) + (peer.total_receive || 0)
              const total = upload + download
              
              configTotal += total
              configUpload += upload
              configDownload += download
              
              allPeers.push({
                id: peer.id,
                name: peer.name,
                config: config.Name,
                total: total * 1024 * 1024 * 1024, // Convert GB to bytes
                upload: upload * 1024 * 1024 * 1024,
                download: download * 1024 * 1024 * 1024,
                status: peer.status
              })
            })
            
            configStats.push({
              name: config.Name,
              total: configTotal * 1024 * 1024 * 1024,
              upload: configUpload * 1024 * 1024 * 1024,
              download: configDownload * 1024 * 1024 * 1024,
              peers: peers.length,
              status: config.Status
            })
          }
        })
      }
      
      // Sort peers by total traffic
      allPeers.sort((a, b) => b.total - a.total)
      this.topPeers = allPeers.slice(0, 20)
      
      // Sort configs by total traffic
      configStats.sort((a, b) => b.total - a.total)
      this.configTraffic = configStats
      
      this.loading = false
    },
    
    formatBytes(bytes) {
      if (bytes === 0) return '0 B'
      const k = 1024
      const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
      const i = Math.floor(Math.log(bytes) / Math.log(k))
      return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i]
    }
  }
}
</script>

<style scoped>
.stat-icon {
  width: 50px;
  height: 50px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.card {
  transition: box-shadow 0.2s;
}

.card:hover {
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}

.progress-bar {
  transition: width 0.6s ease;
}

thead th {
  font-size: 0.875rem;
  text-transform: uppercase;
  font-weight: 600;
  color: #6c757d;
}
</style>
