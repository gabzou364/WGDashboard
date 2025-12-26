<template>
  <div class="mt-5">
    <div class="container-fluid">
      <div class="d-flex align-items-center justify-content-between mb-4">
        <h3 class="text-body mb-0">
          <i class="bi bi-journal-text me-2"></i>System Logs & Diagnostics
        </h3>
        <div class="d-flex gap-2">
          <button 
            class="btn btn-sm btn-outline-secondary" 
            @click="loadLogs"
            :disabled="loading"
          >
            <i class="bi bi-arrow-repeat me-1"></i>Refresh
          </button>
          <button 
            class="btn btn-sm btn-outline-danger" 
            @click="clearFilters"
          >
            <i class="bi bi-x-circle me-1"></i>Clear Filters
          </button>
        </div>
      </div>

      <!-- Filters -->
      <div class="card mb-4">
        <div class="card-body">
          <div class="row g-3">
            <div class="col-md-3">
              <label class="form-label small text-muted">Action Type</label>
              <select v-model="filters.action" class="form-select form-select-sm" @change="loadLogs">
                <option value="">All Actions</option>
                <option value="node_assigned">Node Assigned</option>
                <option value="node_removed">Node Removed</option>
                <option value="peer_migrated">Peer Migrated</option>
                <option value="dns_updated">DNS Updated</option>
                <option value="endpoint_group_updated">Endpoint Group Updated</option>
                <option value="peer_created">Peer Created</option>
                <option value="peer_deleted">Peer Deleted</option>
              </select>
            </div>
            <div class="col-md-3">
              <label class="form-label small text-muted">Entity Type</label>
              <select v-model="filters.entity_type" class="form-select form-select-sm" @change="loadLogs">
                <option value="">All Entities</option>
                <option value="config_node">Config-Node</option>
                <option value="peer">Peer</option>
                <option value="endpoint_group">Endpoint Group</option>
                <option value="dns_record">DNS Record</option>
              </select>
            </div>
            <div class="col-md-3">
              <label class="form-label small text-muted">Entity ID</label>
              <input 
                v-model="filters.entity_id" 
                type="text" 
                class="form-control form-control-sm"
                placeholder="e.g., wg0:node1"
                @input="debouncedLoadLogs"
              />
            </div>
            <div class="col-md-3">
              <label class="form-label small text-muted">Results per page</label>
              <select v-model.number="filters.limit" class="form-select form-select-sm" @change="loadLogs">
                <option :value="50">50</option>
                <option :value="100">100</option>
                <option :value="200">200</option>
                <option :value="500">500</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      <!-- Logs Table -->
      <div v-if="loading" class="text-center py-5">
        <div class="spinner-border text-primary" role="status">
          <span class="visually-hidden">Loading...</span>
        </div>
      </div>

      <div v-else-if="logs.length === 0" class="alert alert-info">
        <i class="bi bi-info-circle me-2"></i>
        No logs found matching the current filters.
      </div>

      <div v-else class="card">
        <div class="card-body p-0">
          <div class="table-responsive">
            <table class="table table-hover mb-0">
              <thead class="table-light">
                <tr>
                  <th style="width: 180px">Timestamp</th>
                  <th style="width: 150px">Action</th>
                  <th style="width: 120px">Entity Type</th>
                  <th>Entity ID</th>
                  <th>Details</th>
                  <th style="width: 100px">User</th>
                </tr>
              </thead>
              <tbody>
                <tr 
                  v-for="log in logs" 
                  :key="log.id"
                  style="cursor: pointer"
                  @click="selectedLog = log"
                  :class="{ 'table-active': selectedLog && selectedLog.id === log.id }"
                >
                  <td>
                    <small>{{ formatTimestamp(log.timestamp) }}</small>
                  </td>
                  <td>
                    <span class="badge" :class="getActionBadgeClass(log.action)">
                      {{ log.action }}
                    </span>
                  </td>
                  <td>
                    <span class="badge bg-secondary">
                      {{ log.entity_type }}
                    </span>
                  </td>
                  <td>
                    <code class="small">{{ log.entity_id || 'N/A' }}</code>
                  </td>
                  <td>
                    <small class="text-muted">{{ truncateDetails(log.details) }}</small>
                  </td>
                  <td>
                    <small>{{ log.user || 'system' }}</small>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
        
        <!-- Pagination -->
        <div class="card-footer d-flex justify-content-between align-items-center">
          <div class="text-muted small">
            Showing {{ logs.length }} entries
          </div>
          <div class="d-flex gap-2">
            <button 
              class="btn btn-sm btn-outline-primary"
              :disabled="filters.offset === 0"
              @click="previousPage"
            >
              <i class="bi bi-chevron-left"></i> Previous
            </button>
            <button 
              class="btn btn-sm btn-outline-primary"
              :disabled="logs.length < filters.limit"
              @click="nextPage"
            >
              Next <i class="bi bi-chevron-right"></i>
            </button>
          </div>
        </div>
      </div>

      <!-- Log Details Modal -->
      <div 
        v-if="selectedLog"
        class="modal fade show d-block" 
        tabindex="-1"
        @click.self="selectedLog = null"
      >
        <div class="modal-dialog modal-lg">
          <div class="modal-content">
            <div class="modal-header">
              <h5 class="modal-title">Log Entry Details</h5>
              <button type="button" class="btn-close" @click="selectedLog = null"></button>
            </div>
            <div class="modal-body">
              <div class="row g-3">
                <div class="col-md-6">
                  <label class="form-label small text-muted">ID</label>
                  <div><code>{{ selectedLog.id }}</code></div>
                </div>
                <div class="col-md-6">
                  <label class="form-label small text-muted">Timestamp</label>
                  <div>{{ formatTimestamp(selectedLog.timestamp) }}</div>
                </div>
                <div class="col-md-6">
                  <label class="form-label small text-muted">Action</label>
                  <div>
                    <span class="badge" :class="getActionBadgeClass(selectedLog.action)">
                      {{ selectedLog.action }}
                    </span>
                  </div>
                </div>
                <div class="col-md-6">
                  <label class="form-label small text-muted">Entity Type</label>
                  <div>
                    <span class="badge bg-secondary">{{ selectedLog.entity_type }}</span>
                  </div>
                </div>
                <div class="col-12">
                  <label class="form-label small text-muted">Entity ID</label>
                  <div><code>{{ selectedLog.entity_id || 'N/A' }}</code></div>
                </div>
                <div class="col-12">
                  <label class="form-label small text-muted">User</label>
                  <div>{{ selectedLog.user || 'system' }}</div>
                </div>
                <div class="col-12">
                  <label class="form-label small text-muted">Details</label>
                  <pre class="bg-light p-3 rounded"><code>{{ formatDetails(selectedLog.details) }}</code></pre>
                </div>
              </div>
            </div>
            <div class="modal-footer">
              <button type="button" class="btn btn-secondary" @click="selectedLog = null">Close</button>
            </div>
          </div>
        </div>
      </div>
      
      <!-- Modal backdrop -->
      <div 
        v-if="selectedLog" 
        class="modal-backdrop fade show"
        @click="selectedLog = null"
      ></div>
    </div>
  </div>
</template>

<script>
import { fetchGet } from '@/utilities/fetch.js'
import { DashboardConfigurationStore } from '@/stores/DashboardConfigurationStore.js'

export default {
  name: 'LogsView',
  setup() {
    const dashboardStore = DashboardConfigurationStore()
    return { dashboardStore }
  },
  data() {
    return {
      logs: [],
      selectedLog: null,
      loading: true,
      filters: {
        action: '',
        entity_type: '',
        entity_id: '',
        limit: 100,
        offset: 0
      },
      debounceTimer: null
    }
  },
  mounted() {
    this.loadLogs()
    
    // Auto-refresh every 30 seconds
    this.refreshInterval = setInterval(() => {
      this.loadLogs()
    }, 30000)
  },
  beforeUnmount() {
    if (this.refreshInterval) {
      clearInterval(this.refreshInterval)
    }
    if (this.debounceTimer) {
      clearTimeout(this.debounceTimer)
    }
  },
  methods: {
    async loadLogs() {
      this.loading = true
      
      const params = {}
      if (this.filters.action) params.action = this.filters.action
      if (this.filters.entity_type) params.entity_type = this.filters.entity_type
      if (this.filters.entity_id) params.entity_id = this.filters.entity_id
      params.limit = this.filters.limit
      params.offset = this.filters.offset
      
      const queryString = new URLSearchParams(params).toString()
      
      await fetchGet(`/api/audit-logs?${queryString}`, {}, (res) => {
        if (res.status && res.data) {
          this.logs = res.data
        } else {
          this.logs = []
        }
        this.loading = false
      })
    },
    
    debouncedLoadLogs() {
      if (this.debounceTimer) {
        clearTimeout(this.debounceTimer)
      }
      this.debounceTimer = setTimeout(() => {
        this.loadLogs()
      }, 500)
    },
    
    clearFilters() {
      this.filters = {
        action: '',
        entity_type: '',
        entity_id: '',
        limit: 100,
        offset: 0
      }
      this.loadLogs()
    },
    
    nextPage() {
      this.filters.offset += this.filters.limit
      this.loadLogs()
    },
    
    previousPage() {
      this.filters.offset = Math.max(0, this.filters.offset - this.filters.limit)
      this.loadLogs()
    },
    
    formatTimestamp(timestamp) {
      if (!timestamp) return 'N/A'
      return new Date(timestamp).toLocaleString()
    },
    
    truncateDetails(details) {
      if (!details) return 'N/A'
      const maxLength = 100
      if (details.length <= maxLength) return details
      return details.substring(0, maxLength) + '...'
    },
    
    formatDetails(details) {
      if (!details) return 'N/A'
      try {
        const parsed = JSON.parse(details)
        return JSON.stringify(parsed, null, 2)
      } catch (e) {
        return details
      }
    },
    
    getActionBadgeClass(action) {
      const badgeMap = {
        'node_assigned': 'bg-success',
        'node_removed': 'bg-danger',
        'peer_migrated': 'bg-warning',
        'dns_updated': 'bg-info',
        'endpoint_group_updated': 'bg-primary',
        'peer_created': 'bg-success',
        'peer_deleted': 'bg-danger'
      }
      return badgeMap[action] || 'bg-secondary'
    }
  }
}
</script>

<style scoped>
.modal.show {
  opacity: 1;
}

code {
  background-color: #f8f9fa;
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 0.875rem;
}

pre {
  max-height: 400px;
  overflow-y: auto;
}

tbody tr {
  transition: background-color 0.15s;
}
</style>
