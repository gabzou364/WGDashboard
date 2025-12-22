<template>
  <div class="dashboard-overview mb-4">
    <!-- Quick Stats Cards -->
    <div class="row g-3 mb-4">
      <div class="col-md-6 col-lg-3">
        <div class="card stat-card border-0 shadow-sm h-100">
          <div class="card-body">
            <div class="d-flex align-items-center">
              <div class="stat-icon bg-primary-subtle text-primary rounded-3 p-3 me-3">
                <i class="bi bi-hdd-network fs-4"></i>
              </div>
              <div>
                <h6 class="text-muted mb-1 small">
                  <LocaleText t="Total Nodes"></LocaleText>
                </h6>
                <h3 class="mb-0">{{ stats.totalNodes }}</h3>
                <small :class="stats.healthyNodes === stats.totalNodes ? 'text-success' : 'text-warning'">
                  {{ stats.healthyNodes }} <LocaleText t="healthy"></LocaleText>
                </small>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="col-md-6 col-lg-3">
        <div class="card stat-card border-0 shadow-sm h-100">
          <div class="card-body">
            <div class="d-flex align-items-center">
              <div class="stat-icon bg-info-subtle text-info rounded-3 p-3 me-3">
                <i class="bi bi-people-fill fs-4"></i>
              </div>
              <div>
                <h6 class="text-muted mb-1 small">
                  <LocaleText t="Total Peers"></LocaleText>
                </h6>
                <h3 class="mb-0">{{ stats.totalPeers }}</h3>
                <small :class="stats.connectedPeers > 0 ? 'text-success' : 'text-muted'">
                  {{ stats.connectedPeers }} <LocaleText t="connected"></LocaleText>
                </small>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="col-md-6 col-lg-3">
        <div class="card stat-card border-0 shadow-sm h-100">
          <div class="card-body">
            <div class="d-flex align-items-center">
              <div class="stat-icon bg-success-subtle text-success rounded-3 p-3 me-3">
                <i class="bi bi-diagram-3-fill fs-4"></i>
              </div>
              <div>
                <h6 class="text-muted mb-1 small">
                  <LocaleText t="Configurations"></LocaleText>
                </h6>
                <h3 class="mb-0">{{ stats.totalConfigurations }}</h3>
                <small :class="stats.activeConfigurations > 0 ? 'text-success' : 'text-muted'">
                  {{ stats.activeConfigurations }} <LocaleText t="active"></LocaleText>
                </small>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="col-md-6 col-lg-3">
        <div class="card stat-card border-0 shadow-sm h-100">
          <div class="card-body">
            <div class="d-flex align-items-center">
              <div class="stat-icon bg-warning-subtle text-warning rounded-3 p-3 me-3">
                <i class="bi bi-arrow-down-up fs-4"></i>
              </div>
              <div>
                <h6 class="text-muted mb-1 small">
                  <LocaleText t="Total Traffic"></LocaleText>
                </h6>
                <h3 class="mb-0">{{ formatBytes(stats.totalTraffic) }}</h3>
                <small class="text-muted">
                  <LocaleText t="all time"></LocaleText>
                </small>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Quick Actions Bar -->
    <div class="card border-0 shadow-sm mb-4">
      <div class="card-body">
        <h6 class="mb-3">
          <i class="bi bi-lightning-fill me-2"></i>
          <LocaleText t="Quick Actions"></LocaleText>
        </h6>
        <div class="d-flex gap-2 flex-wrap">
          <RouterLink to="/nodes" class="btn btn-sm btn-outline-primary">
            <i class="bi bi-hdd-network me-2"></i>
            <LocaleText t="Manage Nodes"></LocaleText>
          </RouterLink>
          <RouterLink to="/new_configuration" class="btn btn-sm btn-outline-success">
            <i class="bi bi-plus-circle me-2"></i>
            <LocaleText t="Add Configuration"></LocaleText>
          </RouterLink>
          <button 
            @click="runHealthCheck" 
            class="btn btn-sm btn-outline-info"
            :disabled="healthCheckRunning"
          >
            <i class="bi bi-heart-pulse me-2"></i>
            <LocaleText t="Node Health Check"></LocaleText>
            <span v-if="healthCheckRunning" class="spinner-border spinner-border-sm ms-2"></span>
          </button>
          <RouterLink 
            v-if="hasCloudflareConfig" 
            to="/cloudflare" 
            class="btn btn-sm btn-outline-warning"
          >
            <i class="bi bi-cloud-arrow-up me-2"></i>
            <LocaleText t="Cloudflare DNS"></LocaleText>
          </RouterLink>
          <RouterLink to="/system_status" class="btn btn-sm btn-outline-secondary">
            <i class="bi bi-graph-up me-2"></i>
            <LocaleText t="System Status"></LocaleText>
          </RouterLink>
        </div>
      </div>
    </div>

    <!-- Cluster Status (if nodes are configured) -->
    <div v-if="clusterInfo.length > 0" class="card border-0 shadow-sm">
      <div class="card-body">
        <h6 class="mb-3">
          <i class="bi bi-diagram-3 me-2"></i>
          <LocaleText t="Cluster Overview"></LocaleText>
        </h6>
        <div class="table-responsive">
          <table class="table table-sm table-hover align-middle mb-0">
            <thead>
              <tr>
                <th><LocaleText t="Configuration"></LocaleText></th>
                <th><LocaleText t="Nodes"></LocaleText></th>
                <th><LocaleText t="Peers"></LocaleText></th>
                <th><LocaleText t="Endpoint"></LocaleText></th>
                <th><LocaleText t="Status"></LocaleText></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="cluster in clusterInfo" :key="cluster.config_name">
                <td>
                  <RouterLink 
                    :to="`/configuration/${cluster.config_name}/peers`"
                    class="text-decoration-none"
                  >
                    <samp>{{ cluster.config_name }}</samp>
                  </RouterLink>
                </td>
                <td>
                  <span class="badge bg-primary-subtle text-primary">
                    {{ cluster.node_count }} nodes
                  </span>
                </td>
                <td>{{ cluster.peer_count }}</td>
                <td>
                  <small class="text-muted">{{ cluster.endpoint || 'N/A' }}</small>
                </td>
                <td>
                  <span 
                    class="badge"
                    :class="cluster.is_healthy ? 'bg-success' : 'bg-warning'"
                  >
                    {{ cluster.is_healthy ? 'Healthy' : 'Degraded' }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, computed } from 'vue'
import { fetchGet } from '@/utilities/fetch.js'
import { DashboardConfigurationStore } from '@/stores/DashboardConfigurationStore.js'
import { WireguardConfigurationsStore } from '@/stores/WireguardConfigurationsStore.js'
import LocaleText from '@/components/text/localeText.vue'

const dashboardStore = DashboardConfigurationStore()
const wireguardStore = WireguardConfigurationsStore()

const stats = ref({
  totalNodes: 0,
  healthyNodes: 0,
  totalPeers: 0,
  connectedPeers: 0,
  totalConfigurations: 0,
  activeConfigurations: 0,
  totalTraffic: 0
})

const clusterInfo = ref([])
const healthCheckRunning = ref(false)
const hasCloudflareConfig = ref(false)
let refreshInterval = null

onMounted(() => {
  loadDashboardData()
  refreshInterval = setInterval(() => {
    loadDashboardData()
  }, 10000) // Refresh every 10 seconds
})

onBeforeUnmount(() => {
  if (refreshInterval) {
    clearInterval(refreshInterval)
  }
})

const loadDashboardData = async () => {
  // Load nodes stats
  await fetchGet('/api/nodes', {}, (res) => {
    if (res.status && res.data) {
      stats.value.totalNodes = res.data.length
      stats.value.healthyNodes = res.data.filter(n => {
        try {
          const health = JSON.parse(n.health_json || '{}')
          return n.enabled && health.status === 'online'
        } catch (e) {
          return false
        }
      }).length
    }
  })

  // Calculate stats from configurations
  if (wireguardStore.Configurations) {
    stats.value.totalConfigurations = wireguardStore.Configurations.length
    stats.value.activeConfigurations = wireguardStore.Configurations.filter(c => c.Status).length
    stats.value.totalPeers = wireguardStore.Configurations.reduce((sum, c) => sum + c.TotalPeers, 0)
    stats.value.connectedPeers = wireguardStore.Configurations.reduce((sum, c) => sum + c.ConnectedPeers, 0)
    stats.value.totalTraffic = wireguardStore.Configurations.reduce((sum, c) => sum + (c.DataUsage?.Total || 0), 0) * 1024 * 1024 * 1024 // Convert GB to bytes
  }

  // Load cluster info (configs with multiple nodes)
  await fetchGet('/api/dashboard/cluster-overview', {}, (res) => {
    if (res.status && res.data) {
      clusterInfo.value = res.data
    }
  })

  // Check if Cloudflare is configured
  hasCloudflareConfig.value = dashboardStore.Configuration?.Cloudflare?.api_token?.length > 0
}

const runHealthCheck = async () => {
  healthCheckRunning.value = true
  
  await fetchGet('/api/nodes', {}, async (res) => {
    if (res.status && res.data) {
      for (const node of res.data) {
        await fetchGet(`/api/nodes/${node.id}/test`, {}, (testRes) => {
          const msgType = testRes.status ? 'success' : 'danger'
          dashboardStore.newMessage('Health Check', `${node.name}: ${testRes.message}`, msgType)
        })
      }
    }
  })
  
  healthCheckRunning.value = false
  loadDashboardData() // Refresh data after health check
}

const formatBytes = (bytes) => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i]
}
</script>

<style scoped>
.stat-card {
  transition: transform 0.2s;
}

.stat-card:hover {
  transform: translateY(-2px);
}

.stat-icon {
  width: 60px;
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.table th {
  font-weight: 600;
  color: #6c757d;
  font-size: 0.875rem;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
</style>
