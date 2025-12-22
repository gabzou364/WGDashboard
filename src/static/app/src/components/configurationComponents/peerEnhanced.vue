<script>
import { ref } from 'vue'
import { onClickOutside } from '@vueuse/core'
import "animate.css"
import PeerSettingsDropdown from "@/components/configurationComponents/peerSettingsDropdown.vue";
import LocaleText from "@/components/text/localeText.vue";
import {DashboardConfigurationStore} from "@/stores/DashboardConfigurationStore.js";
import {GetLocale} from "@/utilities/locale.js";
import PeerTagBadge from "@/components/configurationComponents/peerTagBadge.vue";

export default {
	name: "peerEnhanced",
	methods: {GetLocale},
	components: {
		PeerTagBadge, LocaleText, PeerSettingsDropdown
	},
	props: {
		Peer: Object, ConfigurationInfo: Object, order: Number, searchPeersLength: Number
	},
	setup(){
		const target = ref(null);
		const subMenuOpened = ref(false)
		const dashboardStore = DashboardConfigurationStore()
		onClickOutside(target, event => {
			subMenuOpened.value = false;
		});
		return {target, subMenuOpened, dashboardStore}
	},
	computed: {
		getLatestHandshake(){
			if (this.Peer.latest_handshake.includes(",")){
				return this.Peer.latest_handshake.split(",")[0]
			}
			return this.Peer.latest_handshake;
		},
		getDropup(){
			return this.searchPeersLength - this.order <= 3
		},
		// Traffic limit calculations
		hasTrafficLimit(){
			return this.Peer.total_data_limit && this.Peer.total_data_limit > 0
		},
		totalTraffic(){
			return (this.Peer.cumu_receive + this.Peer.cumu_sent + this.Peer.total_receive + this.Peer.total_sent)
		},
		trafficLimitProgress(){
			if (!this.hasTrafficLimit) return 0
			return Math.min(100, (this.totalTraffic / this.Peer.total_data_limit) * 100)
		},
		trafficLimitClass(){
			if (this.trafficLimitProgress >= 90) return 'bg-danger'
			if (this.trafficLimitProgress >= 75) return 'bg-warning'
			return 'bg-success'
		},
		// Expiry calculations
		hasExpiry(){
			return this.Peer.expiry_date && this.Peer.expiry_date !== ''
		},
		daysUntilExpiry(){
			if (!this.hasExpiry) return null
			const now = new Date()
			const expiry = new Date(this.Peer.expiry_date)
			const diffTime = expiry - now
			const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24))
			return diffDays
		},
		expiryClass(){
			if (!this.hasExpiry) return ''
			const days = this.daysUntilExpiry
			if (days < 0) return 'text-danger'
			if (days <= 7) return 'text-warning'
			return 'text-muted'
		},
		expiryText(){
			if (!this.hasExpiry) return ''
			const days = this.daysUntilExpiry
			if (days < 0) return `Expired ${Math.abs(days)} days ago`
			if (days === 0) return 'Expires today'
			if (days === 1) return 'Expires tomorrow'
			return `Expires in ${days} days`
		}
	}
}
</script>

<template>
	<div class="card shadow-sm rounded-3 peerCard"
		 :id="'peer_'+Peer.id"
		:class="{'border-warning': Peer.restricted, 'border-danger': hasExpiry && daysUntilExpiry < 0}">
		<div>
			<div v-if="!Peer.restricted" class="card-header bg-transparent d-flex align-items-center gap-2 border-0">
				<div class="dot ms-0" :class="{active: Peer.status === 'running'}"></div>
				<div
					style="font-size: 0.8rem; color: #28a745"
					class="d-flex align-items-center"
					v-if="dashboardStore.Configuration.Server.dashboard_peer_list_display === 'list' && Peer.status === 'running'">
					<i class="bi bi-box-arrow-in-right me-2"></i>
					<span>
						{{ Peer.endpoint }}
					</span>
				</div>
				
				
				<div style="font-size: 0.8rem" class="ms-auto d-flex gap-2">
					<span class="text-primary">
						<i class="bi bi-arrow-down"></i><strong>
						{{(Peer.cumu_receive + Peer.total_receive).toFixed(4)}}</strong> GB
					</span>
					<span class="text-success">
						<i class="bi bi-arrow-up"></i><strong>
						{{(Peer.cumu_sent + Peer.total_sent).toFixed(4)}}</strong> GB
					</span>
					<span class="text-secondary" v-if="Peer.latest_handshake !== 'No Handshake'">
						<i class="bi bi-arrows-angle-contract"></i>
						{{getLatestHandshake}} ago
					</span>
				</div>
			</div>
			<div v-else class="border-0 card-header bg-transparent text-warning fw-bold" 
			     style="font-size: 0.8rem">
				<i class="bi-lock-fill me-2"></i>
				<LocaleText t="Access Restricted"></LocaleText>
			</div>
		</div>
		<div class="card-body pt-1" style="font-size: 0.9rem">
			<h6 class="d-flex align-items-center gap-2">
				{{Peer.name ? Peer.name : GetLocale('Untitled Peer')}}
				<!-- Expiry badge -->
				<span v-if="hasExpiry" class="badge" :class="expiryClass" style="font-size: 0.7rem;">
					<i class="bi bi-calendar-x me-1"></i>{{ expiryText }}
				</span>
			</h6>
			
			<!-- Traffic Limit Progress Bar -->
			<div v-if="hasTrafficLimit" class="mb-2">
				<div class="d-flex justify-content-between align-items-center mb-1">
					<small class="text-muted">
						<i class="bi bi-speedometer2 me-1"></i>Traffic Usage
					</small>
					<small :class="trafficLimitClass.replace('bg-', 'text-')">
						<strong>{{ totalTraffic.toFixed(2) }}</strong> / {{ Peer.total_data_limit.toFixed(2) }} GB
					</small>
				</div>
				<div class="progress" style="height: 6px;">
					<div 
						class="progress-bar" 
						:class="trafficLimitClass"
						role="progressbar" 
						:style="{width: trafficLimitProgress + '%'}"
						:aria-valuenow="trafficLimitProgress" 
						aria-valuemin="0" 
						aria-valuemax="100"
					></div>
				</div>
			</div>
			
			<div class="d-flex"
			     :class="[dashboardStore.Configuration.Server.dashboard_peer_list_display === 'grid' ? 'gap-1 flex-column' : 'flex-row gap-3']">
				<div :class="{'d-flex gap-2 align-items-center' : dashboardStore.Configuration.Server.dashboard_peer_list_display === 'list'}">
					<small class="text-muted">
						<LocaleText t="Public Key"></LocaleText>
					</small>
					<small class="d-block">
						<samp>{{Peer.id}}</samp>
					</small>
				</div>
				<div :class="{'d-flex gap-2 align-items-center' : dashboardStore.Configuration.Server.dashboard_peer_list_display === 'list'}">
					<small class="text-muted">
						<LocaleText t="Allowed IPs"></LocaleText>
					</small>
					<small class="d-block">
						<samp>{{Peer.allowed_ip}}</samp>
					</small>
				</div>
				<div v-if="Peer.node_id" :class="{'d-flex gap-2 align-items-center' : dashboardStore.Configuration.Server.dashboard_peer_list_display === 'list'}">
					<small class="text-muted">
						<i class="bi bi-hdd-network"></i> <LocaleText t="Node"></LocaleText>
					</small>
					<small class="d-block">
						<span class="badge bg-info text-dark">{{ Peer.node_id }}</span>
					</small>
				</div>
				<div class="d-flex align-items-center gap-1"
					:class="{'ms-auto': dashboardStore.Configuration.Server.dashboard_peer_list_display === 'list'}"
				>
					<PeerTagBadge :BackgroundColor="group.BackgroundColor" :GroupName="group.GroupName" :Icon="'bi-' + group.Icon"
						v-for="group in Object.values(ConfigurationInfo.Info.PeerGroups).filter(x => x.Peers.includes(Peer.id))"
					></PeerTagBadge>
					<div class="ms-auto px-2 rounded-3 subMenuBtn position-relative"
					     :class="{active: this.subMenuOpened}"
					>
						<a role="button" class="text-body"
						   @click="this.subMenuOpened = true">
							<h5 class="mb-0"><i class="bi bi-three-dots"></i></h5>
						</a>
						<Transition name="slide-fade">
							<PeerSettingsDropdown
								:dropup="getDropup"
								@qrcode="this.$emit('qrcode')"
								@configurationFile="this.$emit('configurationFile')"
								@setting="this.$emit('setting')"
								@jobs="this.$emit('jobs')"
								@refresh="this.$emit('refresh')"
								@share="this.$emit('share')"
								@assign="this.$emit('assign')"
								:Peer="Peer"
								:ConfigurationInfo="ConfigurationInfo"
								v-if="this.subMenuOpened"
								ref="target"
							></PeerSettingsDropdown>
						</Transition>
					</div>
				</div>
			</div>
		</div>
		<div class="card-footer" role="button" @click="$emit('details')">
			<small class="d-flex align-items-center">
				<LocaleText t="Details"></LocaleText>
				<i class="bi bi-chevron-right ms-auto"></i>
			</small>
		</div>
	</div>
</template>

<style scoped>
.progress-bar {
	transition: width 0.6s ease;
}

.badge {
	font-weight: 600;
}

.text-danger.badge {
	background-color: #dc3545 !important;
	color: white !important;
}

.text-warning.badge {
	background-color: #ffc107 !important;
	color: #000 !important;
}

.border-danger {
	border-color: #dc3545 !important;
	border-width: 2px !important;
}
</style>
