<template>
  <div>
    <el-card class="card" v-loading="loading">
      <template #header>系统设置</template>
      <el-form label-width="160px" style="max-width: 520px" @submit.prevent>
        <el-form-item label="疑似下线阈值">
          <el-input-number
            v-if="isAdmin"
            v-model="hours"
            :min="1"
            :max="8760"
            :step="1"
            controls-position="right"
          />
          <span v-else class="value">{{ hours }}</span>
          <span class="unit">小时</span>
        </el-form-item>
        <el-form-item v-if="isAdmin">
          <el-button type="primary" :disabled="!dirty" @click="save">保存</el-button>
        </el-form-item>
        <el-form-item v-if="!isAdmin">
          <span class="hint">仅管理员可修改</span>
        </el-form-item>
      </el-form>
      <div class="desc">
        超过该时长未推送数据的设备将被标记为<span class="value">疑似下线</span>,
        数据不自动删除;重新推送即恢复活跃。
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, inject, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '../api'

const userRole = inject('userRole', ref('viewer'))
const isAdmin = computed(() => userRole.value === 'admin')

const hours = ref(24)
const saved = ref(24)
const loading = ref(false)
const dirty = computed(() => hours.value !== saved.value)

onMounted(async () => {
  loading.value = true
  try {
    const s = await api.getSystemSettings()
    hours.value = s.offline_threshold_hours
    saved.value = s.offline_threshold_hours
  } catch (e) {
    ElMessage.error((e as Error).message)
  } finally {
    loading.value = false
  }
})

async function save() {
  try {
    const s = await api.updateSystemSettings({ offline_threshold_hours: hours.value })
    hours.value = s.offline_threshold_hours
    saved.value = s.offline_threshold_hours
    ElMessage.success('已保存,设备状态按新阈值即时计算')
  } catch (e) {
    ElMessage.error((e as Error).message)
  }
}
</script>

<style scoped>
.card {
  margin-top: 16px;
}
.unit {
  margin-left: 8px;
}
.value {
  font-weight: bold;
}
.hint {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.desc {
  margin-top: 8px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
</style>
