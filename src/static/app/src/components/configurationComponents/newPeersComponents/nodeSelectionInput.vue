<script>
import {fetchGet} from "@/utilities/fetch.js";
import LocaleText from "@/components/text/localeText.vue";

export default {
	name: "nodeSelectionInput",
	components: {LocaleText},
	props: {
		saving: Boolean,
		data: Object
	},
	data() {
		return {
			nodes: [],
			loading: true
		}
	},
	mounted() {
		// Fetch enabled nodes
		fetchGet("/api/nodes/enabled", {}, (res) => {
			this.loading = false;
			if (res.status && res.data) {
				this.nodes = res.data;
			}
		});
	},
	computed: {
		hasNodes() {
			return this.nodes.length > 0;
		}
	}
}
</script>

<template>
	<div class="row">
		<div class="col-sm">
			<div class="form-group">
				<label for="peer_node_selection" class="text-muted mb-1">
					<strong><small><LocaleText t="Node Selection"></LocaleText></small></strong>
				</label>
				<div v-if="loading" class="text-muted">
					<small><LocaleText t="Loading nodes..."></LocaleText></small>
				</div>
				<div v-else-if="!hasNodes" class="text-muted">
					<small><LocaleText t="No nodes configured - peer will be created locally"></LocaleText></small>
				</div>
				<select v-else
				        class="form-select"
				        id="peer_node_selection"
				        v-model="data.node_selection"
				        :disabled="saving"
				>
					<option value="auto">Auto (Load Balanced)</option>
					<option value="">Local (This Server)</option>
					<option v-for="node in nodes" :key="node.id" :value="node.id">
						{{ node.name }} ({{ node.endpoint }})
					</option>
				</select>
				<div class="form-text text-muted">
					<small v-if="data.node_selection === 'auto'">
						<LocaleText t="Automatically select the best available node"></LocaleText>
					</small>
					<small v-else-if="!data.node_selection && hasNodes">
						<LocaleText t="Create peer on this local server"></LocaleText>
					</small>
					<small v-else-if="data.node_selection && hasNodes">
						<LocaleText t="Create peer on selected remote node"></LocaleText>
					</small>
				</div>
			</div>
		</div>
	</div>
</template>

<style scoped>
</style>
