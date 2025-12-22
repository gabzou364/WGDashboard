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
	name: "peer",
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
		// Phase 7: Computed properties for traffic and expiry
		hasTrafficLimit() {
			return this.Peer.traffic_limit && this.Peer.traffic_limit > 0;
		},
		trafficUsagePercent() {
			if (!this.hasTrafficLimit) return 0;
			const totalTrafficGB = this.Peer.cumu_receive + this.Peer.cumu_sent + 
			                       this.Peer.total_receive + this.Peer.total_sent; // Already in GB
			const totalTrafficBytes = totalTrafficGB * 1073741824; // Convert GB to bytes
			return Math.min(100, (totalTrafficBytes / this.Peer.traffic_limit) * 100);
		},
		trafficLimitExceeded() {
			return this.hasTrafficLimit && this.trafficUsagePercent >= 100;
		},
		trafficLimitWarning() {
			const threshold = this.Peer.traffic_warn_threshold || 80;
			return this.hasTrafficLimit && this.trafficUsagePercent >= threshold && this.trafficUsagePercent < 100;
		},
		hasExpiry() {
			return this.Peer.expiry_date !== null && this.Peer.expiry_date !== undefined;
		},
		isExpired() {
			if (!this.hasExpiry) return false;
			const now = new Date();
			const expiry = new Date(this.Peer.expiry_date);
			return now >= expiry;
		},
		daysUntilExpiry() {
			if (!this.hasExpiry) return -1;
			const now = new Date();
			const expiry = new Date(this.Peer.expiry_date);
			const diffTime = expiry - now;
			const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
			return Math.max(0, diffDays);
		},
		expiryWarning() {
			return this.hasExpiry && !this.isExpired && this.daysUntilExpiry <= 7;
		}
	}
}
</script>

<template>
	<div class="card shadow-sm rounded-3 peerCard"
		 :id="'peer_'+Peer.id"
		:class="{'border-warning': Peer.restricted}">
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
			<h6>
				{{Peer.name ? Peer.name : GetLocale('Untitled Peer')}}
			</h6>
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
		<!-- Phase 7: Traffic & Expiry Indicators -->
		<div v-if="hasTrafficLimit || hasExpiry" class="card-body pt-0 pb-2">
			<!-- Traffic Limit Indicator -->
			<div v-if="hasTrafficLimit" class="mb-2">
				<div class="d-flex align-items-center mb-1">
					<small class="text-muted">
						<i class="bi bi-speedometer2 me-1"></i>
						<LocaleText t="Traffic Usage"></LocaleText>
					</small>
					<small class="ms-auto" 
					       :class="{
					           'text-danger fw-bold': trafficLimitExceeded,
					           'text-warning fw-bold': trafficLimitWarning,
					           'text-muted': !trafficLimitExceeded && !trafficLimitWarning
					       }">
						{{ trafficUsagePercent.toFixed(1) }}%
						<i v-if="trafficLimitExceeded" class="bi bi-exclamation-circle-fill"></i>
						<i v-else-if="trafficLimitWarning" class="bi bi-exclamation-triangle-fill"></i>
					</small>
				</div>
				<div class="progress" style="height: 6px;">
					<div class="progress-bar" 
					     :class="{
					         'bg-danger': trafficLimitExceeded,
					         'bg-warning': trafficLimitWarning,
					         'bg-primary': !trafficLimitExceeded && !trafficLimitWarning
					     }"
					     :style="{width: trafficUsagePercent + '%'}"></div>
				</div>
			</div>
			<!-- Expiry Date Indicator -->
			<div v-if="hasExpiry" class="d-flex align-items-center">
				<small class="text-muted">
					<i class="bi bi-calendar-event me-1"></i>
					<LocaleText t="Expiry"></LocaleText>
				</small>
				<small class="ms-auto"
				       :class="{
				           'text-danger fw-bold': isExpired,
				           'text-warning fw-bold': expiryWarning,
				           'text-muted': !isExpired && !expiryWarning
				       }">
					<span v-if="isExpired">
						<i class="bi bi-x-circle-fill"></i>
						<LocaleText t="Expired"></LocaleText>
					</span>
					<span v-else-if="daysUntilExpiry === 0">
						<i class="bi bi-clock-fill"></i>
						<LocaleText t="Expires today"></LocaleText>
					</span>
					<span v-else>
						<i class="bi bi-clock-fill" v-if="expiryWarning"></i>
						{{ daysUntilExpiry }} {{ daysUntilExpiry === 1 ? 'day' : 'days' }}
					</span>
				</small>
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



.subMenuBtn.active{
	background-color: #ffffff20;
}

.peerCard{
	transition: box-shadow 0.1s cubic-bezier(0.82, 0.58, 0.17, 0.9);
}

.peerCard:hover{
	box-shadow: var(--bs-box-shadow) !important;
}
</style>