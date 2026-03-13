<template>
  <div class="progress-overlay">
    <div class="progress-modal">
      <div class="modal-header">
        <h3>任务进度</h3>
        <span :class="'status-tag status-' + task.status">{{ statusLabel }}</span>
      </div>
      <div class="modal-body">
        <div v-if="task.status" class="progress-info">
          <template v-if="isDownloadTask">
            <span class="info-label">阶段（总共三个阶段）:</span>
            <span class="info-value">{{ stageLabel }}</span>
          </template>
          <span class="info-label">进度:</span>
          <span class="info-value">{{ task.progress }}%</span>
        </div>
        <div class="progress-bar-wrapper">
          <div class="progress-bar-fill" :style="{ width: task.progress + '%' }"></div>
        </div>
        <p class="progress-message">{{ task.message }}</p>
        <div v-if="cancelable && !isTerminal" class="modal-footer">
          <button @click="$emit('cancel')" class="btn btn-danger">取消任务</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'TaskProgress',
  props: {
    taskId: {
      type: String,
      required: true
    },
    cancelable: {
      type: Boolean,
      default: false
    }
  },
  data() {
    return {
      task: {
        progress: 0,
        stage: '',
        status: '',
        message: '',
        task_type: ''
      },
      pollInterval: null
    };
  },
  computed: {
    isDownloadTask() {
      return this.task.task_type === 'full' || this.task.task_type === 'incremental';
    },
    isTerminal() {
      return ['success', 'failed', 'cancelled'].includes(this.task.status);
    },
    stageLabel() {
      const stages = {
        download: '下载',
        unzip: '解压',
        analyze: '分析',
        '一、下载': '一、下载',
        '二、解压': '二、解压',
        '三、复制': '三、复制',
        '准备': '准备',
        '完成': '完成'
      };
      return stages[this.task.stage] || this.task.stage;
    },
    statusLabel() {
      const statuses = {
        pending: '等待中',
        running: '运行中',
        success: '成功',
        failed: '失败',
        cancelled: '已取消'
      };
      return statuses[this.task.status] || this.task.status;
    }
  },
  mounted() {
    this.startPolling();
  },
  beforeUnmount() {
    this.stopPolling();
  },
  methods: {
    async fetchTaskStatus() {
      try {
        const response = await fetch(`/api/market-data/tasks/${this.taskId}`, {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`
          }
        });

        if (response.ok) {
          this.task = await response.json();

          if (['success', 'failed', 'cancelled'].includes(this.task.status)) {
            this.stopPolling();
            this.$emit('task-complete', this.task);
          }
        }
      } catch (error) {
        console.error('Failed to fetch task status:', error);
      }
    },
    startPolling() {
      this.fetchTaskStatus();
      this.pollInterval = setInterval(this.fetchTaskStatus, 1000);
    },
    stopPolling() {
      if (this.pollInterval) {
        clearInterval(this.pollInterval);
        this.pollInterval = null;
      }
    }
  }
};
</script>

<style scoped>
.progress-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.progress-modal {
  background: #fff;
  border: 1px solid #e0e0e0;
  border-radius: 0;
  width: 90%;
  max-width: 500px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid #e0e0e0;
  background: #fafafa;
}

.modal-header h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: #000;
}

.modal-body {
  padding: 16px;
}

.status-tag {
  display: inline-block;
  padding: 2px 6px;
  font-size: 11px;
  font-weight: 600;
  border: 1px solid;
  border-radius: 2px;
}

.status-pending,
.status-running {
  background: #e3f2fd;
  color: #1976d2;
  border-color: #1976d2;
}

.status-success {
  background: #e8f5e9;
  color: #2e7d32;
  border-color: #4caf50;
}

.status-failed,
.status-cancelled {
  background: #ffebee;
  color: #c62828;
  border-color: #ef5350;
}


.progress-info {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 8px;
  margin-bottom: 12px;
  font-size: 12px;
}

.info-label {
  color: #666;
}

.info-value {
  color: #000;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.progress-bar-wrapper {
  height: 4px;
  background: #e0e0e0;
  margin-bottom: 12px;
  overflow: hidden;
}

.progress-bar-fill {
  height: 100%;
  background: #1976d2;
  transition: width 0.3s ease;
}

.progress-message {
  margin: 0;
  font-size: 12px;
  color: #666;
}

.modal-footer {
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid #e0e0e0;
  text-align: right;
}

.btn {
  border: 1px solid #d0d0d0;
  background: #fff;
  color: #000;
  padding: 6px 12px;
  border-radius: 2px;
  cursor: pointer;
  font-size: 12px;
  font-weight: 500;
}

.btn-danger {
  background: #d32f2f;
  color: #fff;
  border-color: #d32f2f;
}

.btn-danger:hover {
  background: #c62828;
  border-color: #c62828;
}
</style>
