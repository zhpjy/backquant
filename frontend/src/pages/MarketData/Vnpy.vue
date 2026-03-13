<template>
  <div class="vnpy-container">
    <div class="content-layout">
      <div class="main-panel">
        <div class="panel-header">
          <h3>期货数据管理</h3>
          <div class="header-actions">
            <button
              @click="refreshStats"
              class="btn btn-secondary btn-mini"
              :disabled="refreshing"
            >
              {{ refreshing ? '刷新中...' : '刷新统计' }}
            </button>
            <button
              @click="showConfirm = true"
              class="btn btn-primary btn-mini"
              :disabled="importing"
            >
              {{ importing ? '导入中...' : '期货数据导入' }}
            </button>
          </div>
        </div>
        <div class="panel-body">
          <div v-if="loading" class="loading-state">
            <p>加载中...</p>
          </div>

          <div v-else-if="error" class="error-state">
            <div class="inline-error">{{ error }}</div>
            <button @click="loadStats" class="btn btn-secondary">重试</button>
          </div>

          <div v-else-if="stats.total_rows === 0" class="empty-state">
            <p>暂无期货数据，请点击"期货数据导入"按钮导入数据</p>
          </div>

          <div v-else>
            <div class="stats-grid">
              <div class="stat-item">
                <div class="stat-label">总数据量</div>
                <div class="stat-value">{{ formatNumber(stats.total_rows) }}</div>
              </div>
              <div class="stat-item">
                <div class="stat-label">期货合约数</div>
                <div class="stat-value">{{ formatNumber(stats.contract_count) }}</div>
              </div>
              <div class="stat-item">
                <div class="stat-label">交易所数量</div>
                <div class="stat-value">{{ stats.exchange_count }}</div>
              </div>
              <div class="stat-item">
                <div class="stat-label">时间跨度</div>
                <div class="stat-value">{{ formatDateRange(stats.min_date, stats.max_date) }}</div>
              </div>
              <div class="stat-item">
                <div class="stat-label">统计更新时间</div>
                <div class="stat-value">{{ formatDate(stats.updated_at) }}</div>
              </div>
            </div>

            <div class="data-section">
              <div class="exchange-table-wrapper">
                <h4 class="section-title">按交易所统计</h4>
                <table class="data-table">
                  <thead>
                    <tr>
                      <th style="width: 60px; text-align: center">#</th>
                      <th>交易所</th>
                      <th style="text-align: center">合约数</th>
                      <th style="text-align: center">数据行数</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(item, index) in stats.by_exchange" :key="item.exchange">
                      <td class="row-number">{{ index + 1 }}</td>
                      <td>{{ item.exchange }}</td>
                      <td class="text-center mono">{{ formatNumber(item.contracts) }}</td>
                      <td class="text-center mono">{{ formatNumber(item.rows) }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <div class="chart-wrapper">
                <h4 class="section-title">数据量分布</h4>
                <div class="chart-container">
                  <canvas ref="chartCanvas"></canvas>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-if="logs.length > 0" class="main-panel">
        <div class="panel-header">
          <h3>最近导入日志</h3>
          <button @click="logs = []" class="btn btn-secondary btn-mini">清除</button>
        </div>
        <div class="panel-body">
          <div class="log-container">
            <div v-for="(log, i) in logs" :key="i" class="log-line">{{ log }}</div>
          </div>
        </div>
      </div>
    </div>

    <ConfirmDialog
      v-if="showConfirm"
      message="将会把 futures.h5 数据导入 MariaDB 数据库（backquant.dbbardata），数据量约百万级，导入过程可能需要几分钟。确认继续？"
      @confirm="doImport"
      @cancel="showConfirm = false"
    />

    <TaskProgress
      v-if="currentTaskId"
      :task-id="currentTaskId"
      :cancelable="true"
      @task-complete="handleTaskComplete"
      @cancel="cancelTask"
    />
  </div>
</template>

<script>
import ConfirmDialog from '@/components/MarketData/ConfirmDialog.vue';
import TaskProgress from '@/components/MarketData/TaskProgress.vue';

export default {
  name: 'MarketDataVnpy',
  components: {
    ConfirmDialog,
    TaskProgress
  },
  data() {
    return {
      loading: false,
      error: null,
      stats: {
        total_rows: 0,
        contract_count: 0,
        exchange_count: 0,
        min_date: null,
        max_date: null,
        by_exchange: []
      },
      showConfirm: false,
      importing: false,
      refreshing: false,
      currentTaskId: null,
      logs: []
    };
  },
  mounted() {
    this.loadStats();
    this.checkRunningTask();
  },
  watch: {
    'stats.by_exchange': {
      handler(val) {
        if (val && val.length > 0) {
          this.$nextTick(() => {
            this.renderChart();
          });
        }
      }
    }
  },
  methods: {
    async checkRunningTask() {
      try {
        const response = await fetch('/api/market-data/vnpy/running-task', {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`
          }
        });
        if (response.ok) {
          const task = await response.json();
          if (task && task.task_id) {
            this.currentTaskId = task.task_id;
            this.importing = true;
            this.pollLogs(task.task_id);
          }
        }
      } catch (e) {
        // ignore
      }
    },
    async cancelTask() {
      if (!this.currentTaskId) return;
      try {
        const response = await fetch(`/api/market-data/vnpy/cancel/${this.currentTaskId}`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`
          }
        });
        if (response.ok) {
          this.currentTaskId = null;
          this.importing = false;
          if (this._logPoll) {
            clearInterval(this._logPoll);
            this._logPoll = null;
          }
        } else {
          const data = await response.json();
          alert(data.error || '取消失败');
        }
      } catch (e) {
        alert('网络错误');
      }
    },
    async loadStats() {
      this.loading = true;
      this.error = null;
      try {
        const response = await fetch('/api/market-data/vnpy/stats', {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`
          }
        });
        if (response.ok) {
          this.stats = await response.json();
        } else {
          const data = await response.json();
          this.error = data.error || '加载统计数据失败';
        }
      } catch (err) {
        this.error = '网络错误，请重试';
      } finally {
        this.loading = false;
      }
    },
    async refreshStats() {
      this.refreshing = true;
      try {
        const response = await fetch('/api/market-data/vnpy/refresh-stats', {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`
          }
        });
        if (response.ok) {
          await this.loadStats();
        } else {
          const data = await response.json();
          alert(data.error || '刷新失败');
        }
      } catch (err) {
        alert('网络错误，请重试');
      } finally {
        this.refreshing = false;
      }
    },
    async doImport() {
      this.showConfirm = false;
      this.importing = true;
      try {
        const response = await fetch('/api/market-data/vnpy/import', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${localStorage.getItem('token')}`
          }
        });
        if (response.ok) {
          const result = await response.json();
          this.currentTaskId = result.task_id;
          this.pollLogs(result.task_id);
        } else if (response.status === 409) {
          alert('已有任务正在运行，请等待完成');
        } else {
          const data = await response.json();
          alert(data.error || '触发导入失败');
        }
      } catch (err) {
        alert('网络错误，请重试');
      } finally {
        this.importing = false;
      }
    },
    async pollLogs(taskId) {
      this._logPoll = setInterval(async () => {
        try {
          const response = await fetch(`/api/market-data/tasks/${taskId}/logs?limit=200`, {
            headers: {
              'Authorization': `Bearer ${localStorage.getItem('token')}`
            }
          });
          if (response.ok) {
            const data = await response.json();
            this.logs = (data.logs || []).map(l => `[${l.level}] ${l.message}`).reverse();
          }
        } catch (e) {
          // ignore
        }
      }, 2000);
    },
    handleTaskComplete(task) {
      this.currentTaskId = null;
      if (this._logPoll) {
        clearInterval(this._logPoll);
        this._logPoll = null;
      }
      if (task.status === 'success') {
        this.loadStats();
      }
    },
    renderChart() {
      const canvas = this.$refs.chartCanvas;
      if (!canvas || !this.stats.by_exchange || this.stats.by_exchange.length === 0) return;

      const dpr = window.devicePixelRatio || 1;
      const displayWidth = 450;
      const displayHeight = 300;

      canvas.width = displayWidth * dpr;
      canvas.height = displayHeight * dpr;
      canvas.style.width = displayWidth + 'px';
      canvas.style.height = displayHeight + 'px';

      const ctx = canvas.getContext('2d');
      ctx.scale(dpr, dpr);

      const colors = ['#1976d2', '#388e3c', '#f57c00', '#7b1fa2', '#d32f2f', '#00838f'];
      const data = this.stats.by_exchange.map((item, i) => ({
        label: item.exchange,
        value: item.rows,
        color: colors[i % colors.length]
      }));

      this.drawPieChart(ctx, data, displayWidth, displayHeight);
    },
    drawPieChart(ctx, data, width, height) {
      const total = data.reduce((sum, d) => sum + d.value, 0);
      if (total === 0) return;

      const centerX = width * 0.4;
      const centerY = height / 2;
      const radius = Math.min(centerX, centerY) - 20;

      let startAngle = -Math.PI / 2;

      data.forEach((item) => {
        const sliceAngle = (item.value / total) * 2 * Math.PI;

        // Draw slice
        ctx.beginPath();
        ctx.moveTo(centerX, centerY);
        ctx.arc(centerX, centerY, radius, startAngle, startAngle + sliceAngle);
        ctx.closePath();
        ctx.fillStyle = item.color;
        ctx.fill();
        ctx.strokeStyle = '#fff';
        ctx.lineWidth = 2;
        ctx.stroke();

        // Percentage label inside slice
        if (sliceAngle > 0.2) {
          const midAngle = startAngle + sliceAngle / 2;
          const labelR = radius * 0.6;
          const lx = centerX + Math.cos(midAngle) * labelR;
          const ly = centerY + Math.sin(midAngle) * labelR;
          const pct = ((item.value / total) * 100).toFixed(1);
          ctx.fillStyle = '#fff';
          ctx.font = 'bold 11px ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace';
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.fillText(pct + '%', lx, ly);
        }

        startAngle += sliceAngle;
      });

      // Legend on right side
      const legendX = width * 0.72;
      const legendStartY = (height - data.length * 24) / 2;
      ctx.font = '12px sans-serif';
      ctx.textAlign = 'left';
      ctx.textBaseline = 'middle';
      data.forEach((item, i) => {
        const y = legendStartY + i * 24;
        ctx.fillStyle = item.color;
        ctx.fillRect(legendX, y - 5, 12, 12);
        ctx.fillStyle = '#333';
        const label = item.value >= 10000
          ? item.label + ' ' + (item.value / 10000).toFixed(1) + '万'
          : item.label + ' ' + item.value.toLocaleString();
        ctx.fillText(label, legendX + 18, y + 1);
      });
    },
    formatNumber(num) {
      if (!num && num !== 0) return '0';
      return Number(num).toLocaleString('zh-CN');
    },
    formatDateRange(minDate, maxDate) {
      if (!minDate || !maxDate) return '-';
      const min = minDate.substring(0, 10);
      const max = maxDate.substring(0, 10);
      return `${min} ~ ${max}`;
    },
    formatDate(dateStr) {
      if (!dateStr) return '-';
      const date = new Date(dateStr.endsWith('Z') ? dateStr : dateStr + 'Z');
      const y = date.getFullYear();
      const m = String(date.getMonth() + 1).padStart(2, '0');
      const d = String(date.getDate()).padStart(2, '0');
      const h = String(date.getHours()).padStart(2, '0');
      const mi = String(date.getMinutes()).padStart(2, '0');
      const s = String(date.getSeconds()).padStart(2, '0');
      return `${y}-${m}-${d} ${h}:${mi}:${s}`;
    }
  },
  beforeUnmount() {
    if (this._logPoll) {
      clearInterval(this._logPoll);
    }
  }
};
</script>

<style scoped>
.vnpy-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.loading-state,
.error-state,
.empty-state {
  padding: 40px;
  text-align: center;
}

.loading-state p,
.empty-state p {
  margin: 0 0 16px 0;
  color: #666;
  font-size: 12px;
}

.inline-error {
  background: #ffebee;
  border: 1px solid #ef5350;
  color: #c62828;
  padding: 8px 12px;
  border-radius: 2px;
  margin-bottom: 12px;
  font-size: 12px;
}

.content-layout {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.main-panel {
  background: #fff;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid #e0e0e0;
  background: #fafafa;
}

.panel-header h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: #000;
}

.header-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.panel-body {
  padding: 16px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 12px;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid #e0e0e0;
}

.stat-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stat-label {
  font-size: 11px;
  color: #666;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.stat-value {
  font-size: 14px;
  color: #000;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-weight: 500;
}

.data-section {
  display: flex;
  gap: 16px;
  align-items: stretch;
  flex-wrap: wrap;
}

.section-title {
  margin: 0 0 12px 0;
  font-size: 13px;
  font-weight: 600;
  color: #000;
}

.exchange-table-wrapper {
  flex: 1 1 400px;
  min-width: 350px;
  max-width: 600px;
  padding: 16px;
  background: #fff;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
}

.chart-wrapper {
  flex: 1 1 450px;
  min-width: 400px;
  padding: 16px;
  background: #fff;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
}

.chart-container {
  display: flex;
  align-items: center;
  justify-content: center;
}

.chart-container canvas {
  display: block;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  background: #fff;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  overflow: hidden;
}

.data-table thead th {
  background: #fafafa;
  padding: 8px 12px;
  border-bottom: 1px solid #e0e0e0;
  font-size: 12px;
  font-weight: 600;
  color: #000;
  text-align: left;
}

.data-table tbody td {
  padding: 8px 12px;
  border-bottom: 1px solid #e0e0e0;
  font-size: 12px;
  color: #000;
}

.data-table tbody tr:last-child td {
  border-bottom: none;
}

.row-number {
  color: #999;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  text-align: center;
}

.text-center {
  text-align: center;
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.log-container {
  max-height: 300px;
  overflow-y: auto;
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 12px;
  border-radius: 4px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 11px;
  line-height: 1.6;
}

.log-line {
  white-space: pre-wrap;
  word-break: break-all;
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
  transition: all 0.15s ease;
}

.btn:hover:not(:disabled) {
  border-color: #999;
  background: #f5f5f5;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-primary {
  background: #1976d2;
  color: #fff;
  border-color: #1976d2;
}

.btn-primary:hover:not(:disabled) {
  background: #1565c0;
  border-color: #1565c0;
}

.btn-danger {
  background: #d32f2f;
  color: #fff;
  border-color: #d32f2f;
}

.btn-danger:hover:not(:disabled) {
  background: #c62828;
  border-color: #c62828;
}

.btn-secondary {
  background: #fff;
}

.btn-mini {
  padding: 4px 8px;
  font-size: 12px;
}
</style>
