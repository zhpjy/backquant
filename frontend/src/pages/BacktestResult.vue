<template>
  <div class="result-page">
    <header class="summary-bar">
      <div class="summary-left">
        <div class="title-row">
          <h2>回测结果</h2>
          <span class="mono run-chip">{{ runId }}</span>
          <span class="status" :class="statusClass">{{ jobStatusText }}</span>
        </div>
        <div class="summary-meta">
          <span v-if="runSummary.strategyId" class="meta-item">
            策略：<button class="link-btn mono" type="button" @click="goEditStrategy">{{ runSummary.strategyId }}</button>
          </span>
          <span v-if="runSummary.params" class="meta-item">
            区间：{{ runSummary.params.start_date }} ~ {{ runSummary.params.end_date }}
          </span>
          <span v-if="runSummary.params" class="meta-item">
            资金：{{ formatCash(runSummary.params.cash) }}
          </span>
          <span v-if="runSummary.params" class="meta-item">
            频率：{{ runSummary.params.frequency }}
          </span>
          <span v-if="jobError" class="meta-item error">
            错误：{{ jobError }}
          </span>
        </div>
      </div>

      <div class="summary-right">
        <button class="btn btn-secondary" type="button" :disabled="!runSummary.strategyId" @click="goEditStrategy">返回策略</button>
        <button class="btn btn-secondary" type="button" :disabled="!runSummary.strategyId" @click="goHistory">
          历史回测
        </button>
        <button class="btn btn-secondary" type="button" :disabled="loadingJob" @click="fetchJobOnce(false)">
          {{ loadingJob ? '刷新中...' : '刷新状态' }}
        </button>
        <button class="btn btn-secondary" type="button" :disabled="loadingResult || jobStatus !== 'FINISHED'" @click="fetchResultOnce(false)">
          {{ loadingResult ? '拉取中...' : '拉取结果' }}
        </button>
      </div>
    </header>

    <section class="layout">
      <aside class="left-nav">
        <button
          v-for="item in navItems"
          :key="item.key"
          class="nav-item"
          :class="{ active: activeTab === item.key }"
          type="button"
          @click="setActiveTab(item.key)"
        >
          {{ item.label }}
          <span v-if="item.badge" class="badge">{{ item.badge }}</span>
        </button>
      </aside>

      <main class="content">
        <section v-show="activeTab === 'overview'" class="panel">
          <div class="panel-header">
            <h3>收益概览</h3>
          </div>
          <div class="panel-body">
            <div v-if="jobStatus !== 'FINISHED'" class="inline-hint">
              <div class="hint-title">
                回测进行中（{{ jobProgressStage }}）
                <span class="progress-percent">{{ jobProgressPercent }}%</span>
              </div>
              <div class="progress">
                <div class="bar" :style="{ width: jobProgressPercent + '%' }" />
              </div>
            </div>

            <div class="cards">
              <div v-for="card in summaryCards" :key="card.key" class="card">
                <div class="card-label">{{ card.label }}</div>
                <div class="card-value">
                  {{ formatMetricValue(card.value, card.percent) }}
                </div>
              </div>
            </div>

            <div class="chart-card">
              <div class="chart-header">
                <div class="chart-title">净值曲线</div>
                <div class="chart-meta">
                  <span v-if="hasBenchmarkSeries" class="meta-chip">含基准</span>
                  <span v-else class="meta-chip muted">无基准数据</span>
                </div>
              </div>
              <div class="chart-body">
                <div v-if="!hasEquityData" class="empty">
                  {{ jobStatus === 'FINISHED' ? '无净值数据（请检查后端 result.equity 返回）' : '等待结果生成...' }}
                </div>
                <canvas v-show="hasEquityData" ref="equityChart" class="chart-canvas" />
              </div>
            </div>
          </div>
        </section>

        <section v-show="activeTab === 'trades'" class="panel">
          <div class="panel-header">
            <h3>交易详情</h3>
            <div class="panel-actions">
              <span class="meta">{{ trades.length }} 笔</span>
              <button class="btn btn-mini btn-secondary" type="button" @click="toggleTradeFieldMode">
                {{ showAllTradeFields ? '收起字段' : '展开全部字段' }}
              </button>
            </div>
          </div>
          <div class="panel-body">
            <div v-if="!trades.length" class="empty">
              {{ jobStatus === 'FINISHED' ? '暂无交易数据' : '回测未完成' }}
            </div>

            <div v-else class="table-scroll">
              <table class="table">
                <thead>
                  <tr>
                    <th v-for="key in displayTradeColumns" :key="key">{{ formatTradeColumnLabel(key) }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(row, idx) in pagedTrades" :key="idx">
                    <td v-for="key in displayTradeColumns" :key="key">
                      {{ formatCellValue(row[key]) }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div v-if="trades.length" class="pager">
              <button class="btn btn-secondary" :disabled="tradePage <= 1" @click="tradePage -= 1">上一页</button>
              <div class="pager-meta">第 {{ tradePage }} / {{ totalTradePages }} 页</div>
              <button class="btn btn-secondary" :disabled="tradePage >= totalTradePages" @click="tradePage += 1">下一页</button>
            </div>
          </div>
        </section>

        <section v-show="activeTab === 'logs'" class="panel">
          <div class="panel-header">
            <h3>日志</h3>
            <div class="panel-actions">
              <button class="btn btn-mini btn-secondary" type="button" :disabled="loadingLog" @click="fetchLogOnce(false)">
                {{ loadingLog ? '拉取中...' : '拉取日志' }}
              </button>
              <button class="btn btn-mini btn-secondary" type="button" @click="logText = ''">清空</button>
            </div>
          </div>
          <div class="panel-body">
            <div v-if="jobStatus !== 'FINISHED'" class="inline-hint">
              <div class="hint-title">实时刷新</div>
              <div class="hint-sub">
                当前会在任务状态轮询时（2s）尝试刷新日志。若后端日志接口较重，可考虑提供增量日志接口。
              </div>
            </div>
            <pre class="log">{{ logText || '暂无日志' }}</pre>
          </div>
        </section>

        <section v-show="activeTab === 'performance'" class="panel">
          <div class="panel-header">
            <h3>性能分析</h3>
            <div class="panel-actions">
              <span class="meta">{{ performanceRows.length }} 项</span>
            </div>
          </div>
          <div class="panel-body">
            <div v-if="performanceRows.length" class="kv-grid performance-grid">
              <div v-for="item in performanceRows" :key="item.key" class="kv">
                <div class="k">{{ item.label }}</div>
                <div class="v">{{ formatMetricValue(item.value, item.percent) }}</div>
              </div>
            </div>
            <div v-else class="empty">暂无性能指标</div>
          </div>
        </section>

        <section v-show="activeTab === 'code'" class="panel">
          <div class="panel-header">
            <h3>策略代码</h3>
            <div class="panel-actions">
              <button class="btn btn-mini btn-secondary" type="button" :disabled="loadingStrategyCode || !runSummary.strategyId" @click="fetchStrategyCode(false)">
                {{ loadingStrategyCode ? '加载中...' : '加载代码' }}
              </button>
            </div>
          </div>
          <div class="panel-body">
            <div v-if="!runSummary.strategyId" class="empty">
              未知策略 ID：请从策略编辑页启动回测，或后端在 job 信息中返回 strategy_id。
            </div>
            <PythonCodeEditor v-else :model-value="strategyCode || '# 暂无代码\n'" :min-height="520" read-only />
          </div>
        </section>
      </main>
    </section>

    <transition name="toast">
      <div v-if="showToast" class="toast" :class="toastType">
        <span>{{ toastMessage }}</span>
      </div>
    </transition>
  </div>
</template>

<script>
import Chart from 'chart.js/auto';
import PythonCodeEditor from '@/components/PythonCodeEditor.vue';
import { getJob, getResult, getLog, getStrategy } from '@/api/backtest';
import {
  getBacktestRunState,
  setBacktestRunActiveTab,
  upsertBacktestRunSummary,
  upsertBacktestRunCache
} from '@/stores/backtestRunStore';
import { normalizeCodePayload } from '@/utils/strategyNormalize';

function toNumberOrNull(value) {
  if (value === null || value === undefined || value === '') {
    return null;
  }
  const num = Number(value);
  return Number.isFinite(num) ? num : null;
}

function getValueByPath(obj, path) {
  if (!obj || typeof obj !== 'object') {
    return undefined;
  }
  const parts = String(path || '').split('.');
  let cur = obj;
  for (let i = 0; i < parts.length; i += 1) {
    const key = parts[i];
    if (!cur || typeof cur !== 'object') {
      return undefined;
    }
    cur = cur[key];
  }
  return cur;
}

function pickFirstAvailable(sources, keys) {
  for (let i = 0; i < sources.length; i += 1) {
    const source = sources[i];
    if (!source || typeof source !== 'object') {
      continue;
    }
    for (let k = 0; k < keys.length; k += 1) {
      const key = keys[k];
      if (key.includes('.')) {
        const nested = getValueByPath(source, key);
        if (nested !== undefined && nested !== null && nested !== '') {
          return nested;
        }
      } else if (source[key] !== undefined && source[key] !== null && source[key] !== '') {
        return source[key];
      }
    }
  }
  return undefined;
}

function normalizeLogPayload(payload) {
  if (!payload) {
    return '';
  }
  if (typeof payload === 'string') {
    return payload;
  }
  if (payload.data !== undefined && payload.data !== null) {
    return normalizeLogPayload(payload.data);
  }
  if (typeof payload.log === 'string') {
    return payload.log;
  }
  if (typeof payload.text === 'string') {
    return payload.text;
  }
  return JSON.stringify(payload, null, 2);
}

const SUMMARY_KEY_LABEL_MAP = {
  total_returns: '总收益',
  total_return: '总收益',
  annualized_returns: '年化收益',
  annualized_return: '年化收益',
  annual_return: '年化收益',
  benchmark_returns: '基准收益',
  benchmark_return: '基准收益',
  excess_returns: '超额收益',
  excess_return: '超额收益',
  alpha_returns: '超额收益',
  max_drawdown: '最大回撤',
  maximum_drawdown: '最大回撤',
  volatility: '波动率',
  annualized_volatility: '年化波动率',
  annual_volatility: '年化波动率',
  sharpe: '夏普比率',
  sharpe_ratio: '夏普比率',
  sortino: '索提诺比率',
  sortino_ratio: '索提诺比率',
  calmar: '卡玛比率',
  calmar_ratio: '卡玛比率',
  information_ratio: '信息比率',
  ir: '信息比率',
  alpha: '阿尔法',
  beta: '贝塔',
  win_rate: '胜率',
  winning_rate: '胜率',
  profit_factor: '盈亏比',
  turnover: '换手率',
  turnover_rate: '换手率',
  trade_count: '交易次数',
  trades_count: '交易次数',
  trades: '交易次数'
};

const METRIC_TOKEN_LABEL_MAP = {
  annualized: '年化',
  annual: '年化',
  benchmark: '基准',
  excess: '超额',
  total: '总',
  cumulative: '累计',
  return: '收益',
  returns: '收益',
  drawdown: '回撤',
  max: '最大',
  maximum: '最大',
  volatility: '波动率',
  sharpe: '夏普',
  sortino: '索提诺',
  calmar: '卡玛',
  information: '信息',
  ratio: '比率',
  alpha: '阿尔法',
  beta: '贝塔',
  win: '胜',
  winning: '胜',
  rate: '率',
  turnover: '换手率',
  trade: '交易',
  trades: '交易',
  count: '次数',
  profit: '盈利',
  loss: '亏损',
  factor: '因子'
};

function formatMetricKeyLabelZh(key) {
  const raw = String(key || '').trim();
  if (!raw) {
    return '指标';
  }
  const normalized = raw.replace(/([a-z0-9])([A-Z])/g, '$1_$2').toLowerCase();
  if (SUMMARY_KEY_LABEL_MAP[normalized]) {
    return SUMMARY_KEY_LABEL_MAP[normalized];
  }
  const parts = normalized.split('_').filter(Boolean);
  if (!parts.length) {
    return `指标（${raw}）`;
  }
  const translated = parts.map((part) => METRIC_TOKEN_LABEL_MAP[part] || null);
  if (translated.every(Boolean)) {
    return translated.join('');
  }
  return `指标（${raw}）`;
}

const PERFORMANCE_METRIC_DEFS = [
  { key: 'total_returns', label: '总收益', paths: ['total_returns', 'total_return', 'returns', 'cumulative_returns', 'cum_returns'], percent: true },
  { key: 'annualized_returns', label: '年化收益', paths: ['annualized_returns', 'annualized_return', 'annual_return'], percent: true },
  { key: 'benchmark_returns', label: '基准收益', paths: ['benchmark_returns', 'benchmark_return'], percent: true },
  { key: 'excess_returns', label: '超额收益', paths: ['excess_returns', 'excess_return', 'alpha_returns'], percent: true },
  { key: 'max_drawdown', label: '最大回撤', paths: ['max_drawdown', 'maximum_drawdown'], percent: true },
  { key: 'volatility', label: '波动率', paths: ['volatility', 'annualized_volatility', 'annual_volatility'], percent: true },
  { key: 'sharpe', label: '夏普比率', paths: ['sharpe', 'sharpe_ratio'], percent: false },
  { key: 'sortino', label: '索提诺比率', paths: ['sortino', 'sortino_ratio'], percent: false },
  { key: 'calmar', label: '卡玛比率', paths: ['calmar', 'calmar_ratio'], percent: false },
  { key: 'information_ratio', label: '信息比率', paths: ['information_ratio', 'ir'], percent: false },
  { key: 'alpha', label: '阿尔法', paths: ['alpha'], percent: true },
  { key: 'beta', label: '贝塔', paths: ['beta'], percent: false },
  { key: 'win_rate', label: '胜率', paths: ['win_rate', 'winning_rate'], percent: true },
  { key: 'profit_factor', label: '盈亏比', paths: ['profit_factor'], percent: false },
  { key: 'turnover', label: '换手率', paths: ['turnover', 'turnover_rate'], percent: true },
  { key: 'trade_count', label: '交易次数', paths: ['trade_count', 'trades_count', 'trades'], percent: false }
];

export default {
  name: 'BacktestResult',
  components: {
    PythonCodeEditor
  },
  data() {
    return {
      runId: '',
      runSummary: {
        strategyId: '',
        params: null,
        ui: { activeTab: 'overview' }
      },
      activeTab: 'overview',
      jobStatus: 'QUEUED',
      jobError: '',
      jobProgress: {
        percentage: 0,
        stage: 'queued',
      },
      loadingJob: false,
      loadingResult: false,
      loadingLog: false,
      resultData: null,
      logText: '',
      pollTimer: null,
      pollingRequesting: false,
      chart: null,
      showAllTradeFields: false,
      tradePage: 1,
      tradePageSize: 12,
      strategyCode: '',
      loadingStrategyCode: false,
      showToast: false,
      toastType: 'success',
      toastMessage: '',
      toastTimer: null
    };
  },
  computed: {
    navItems() {
      return [
        { key: 'overview', label: '收益概览' },
        { key: 'trades', label: '交易详情' },
        { key: 'logs', label: '日志' },
        { key: 'performance', label: '性能分析' },
        { key: 'code', label: '策略代码' }
      ];
    },
    statusClass() {
      const status = (this.jobStatus || 'QUEUED').toLowerCase();
      return `status-${status}`;
    },
    jobStatusText() {
      const status = (this.jobStatus || 'QUEUED').toUpperCase();
      if (status === 'RUNNING') return 'RUNNING';
      if (status === 'FINISHED') return 'FINISHED';
      if (status === 'FAILED') return 'FAILED';
      if (status === 'CANCELLED') return 'CANCELLED';
      return 'QUEUED';
    },
    jobProgressPercent() {
      // Use actual progress data if available (from sys_progress module)
      if (this.jobProgress && typeof this.jobProgress.percentage === 'number') {
        return Math.min(Math.max(this.jobProgress.percentage, 0), 100);
      }
      // Fallback to status-based estimation
      const status = (this.jobStatus || 'QUEUED').toUpperCase();
      if (status === 'RUNNING') return 50;
      if (status === 'FINISHED') return 100;
      if (status === 'FAILED' || status === 'CANCELLED') return 100;
      return 24;
    },
    jobProgressStage() {
      const stage = this.jobProgress && this.jobProgress.stage ? this.jobProgress.stage : 'unknown';
      const stageLabels = {
        'queued': '排队中',
        'backtesting': '回测中',
        'analyzing': '分析中',
        'finished': '已完成',
        'failed': '失败',
        'cancelled': '已取消',
        'unknown': '处理中',
      };
      return stageLabels[stage] || stageLabels.unknown;
    },
    summaryPayload() {
      const result = this.resultData || {};
      if (result.summary && typeof result.summary === 'object') return result.summary;
      if (result.result && result.result.summary && typeof result.result.summary === 'object') return result.result.summary;
      if (result.data && result.data.summary && typeof result.data.summary === 'object') return result.data.summary;
      return {};
    },
    summaryMetricSources() {
      return [this.summaryPayload, this.resultData || {}];
    },
    equityData() {
      const result = this.resultData || {};
      const eq = result.equity || getValueByPath(result, 'result.equity') || getValueByPath(result, 'data.equity') || {};
      return eq && typeof eq === 'object' ? eq : {};
    },
    equityDates() {
      return Array.isArray(this.equityData.dates) ? this.equityData.dates : [];
    },
    equityAlignedLength() {
      const nav = Array.isArray(this.equityData.nav) ? this.equityData.nav : [];
      return Math.min(this.equityDates.length, nav.length);
    },
    equityDateSeries() {
      return this.equityDates.slice(0, this.equityAlignedLength);
    },
    equityNavSeries() {
      const nav = Array.isArray(this.equityData.nav) ? this.equityData.nav : [];
      return nav.slice(0, this.equityAlignedLength).map((v) => toNumberOrNull(v));
    },
    benchmarkNavSeries() {
      const eq = this.equityData || {};
      const pairSources = [
        { dates: eq.benchmark_dates || eq.dates, values: eq.benchmark_nav },
        { dates: eq.benchmark_dates || eq.dates, values: eq.benchmark },
        { dates: eq.benchmark_dates || eq.dates, values: eq.benchmark_navs },
        { dates: getValueByPath(this.resultData, 'benchmark_equity.dates'), values: getValueByPath(this.resultData, 'benchmark_equity.nav') }
      ];

      for (let i = 0; i < pairSources.length; i += 1) {
        const source = pairSources[i];
        const values = Array.isArray(source.values) ? source.values : [];
        const dates = Array.isArray(source.dates) ? source.dates : this.equityDateSeries;
        if (!values.length) continue;

        const size = Math.min(dates.length, values.length, this.equityDateSeries.length || dates.length);
        const aligned = values.slice(0, size).map((v) => toNumberOrNull(v));
        if (aligned.some((v) => v !== null)) {
          return aligned;
        }
      }
      return [];
    },
    hasBenchmarkSeries() {
      return this.benchmarkNavSeries.some((v) => v !== null);
    },
    hasEquityData() {
      return this.equityDateSeries.length > 0 && this.equityNavSeries.some((v) => v !== null);
    },
    totalReturnsMetric() {
      const fromSummary = toNumberOrNull(pickFirstAvailable(this.summaryMetricSources, [
        'total_returns',
        'total_return',
        'returns',
        'cumulative_returns',
        'cum_returns'
      ]));
      if (fromSummary !== null) return fromSummary;

      if (this.equityNavSeries.length >= 2) {
        const first = this.equityNavSeries[0];
        const last = this.equityNavSeries[this.equityNavSeries.length - 1];
        if (first !== null && last !== null && first !== 0) {
          return (last - first) / first;
        }
      }
      return null;
    },
    annualizedReturnsMetric() {
      const fromSummary = toNumberOrNull(pickFirstAvailable(this.summaryMetricSources, [
        'annualized_returns',
        'annualized_return',
        'annual_return'
      ]));
      if (fromSummary !== null) return fromSummary;

      if (this.totalReturnsMetric === null || this.equityDateSeries.length < 2) return null;
      const start = new Date(this.equityDateSeries[0]).getTime();
      const end = new Date(this.equityDateSeries[this.equityDateSeries.length - 1]).getTime();
      if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start) return null;
      const years = (end - start) / (365 * 24 * 3600 * 1000);
      if (years <= 0) return null;
      return Math.pow(1 + this.totalReturnsMetric, 1 / years) - 1;
    },
    sharpeMetric() {
      return toNumberOrNull(pickFirstAvailable(this.summaryMetricSources, ['sharpe', 'sharpe_ratio']));
    },
    maxDrawdownMetric() {
      const fromSummary = toNumberOrNull(pickFirstAvailable(this.summaryMetricSources, ['max_drawdown', 'maximum_drawdown']));
      if (fromSummary !== null) return fromSummary;
      if (!this.equityNavSeries.length) return null;
      let peak = null;
      let maxDd = null;
      for (let i = 0; i < this.equityNavSeries.length; i += 1) {
        const nav = this.equityNavSeries[i];
        if (nav === null) continue;
        if (peak === null || nav > peak) peak = nav;
        if (peak && peak > 0) {
          const dd = (nav - peak) / peak;
          if (maxDd === null || dd < maxDd) maxDd = dd;
        }
      }
      return maxDd;
    },
    summaryCards() {
      return [
        { key: 'total_returns', label: '总收益', value: this.totalReturnsMetric, percent: true },
        { key: 'annualized_returns', label: '年化收益', value: this.annualizedReturnsMetric, percent: true },
        { key: 'sharpe', label: '夏普比率', value: this.sharpeMetric, percent: false },
        { key: 'max_drawdown', label: '最大回撤', value: this.maxDrawdownMetric, percent: true }
      ];
    },
    performanceRows() {
      const rows = [];
      const consumedKeys = new Set();
      PERFORMANCE_METRIC_DEFS.forEach((def) => {
        def.paths.forEach((path) => consumedKeys.add(path));
        const value = pickFirstAvailable(this.summaryMetricSources, def.paths);
        if (value === undefined || value === null || value === '') {
          return;
        }
        rows.push({
          key: def.key,
          label: def.label,
          value,
          percent: def.percent
        });
      });

      const summary = this.summaryPayload || {};
      Object.keys(summary).forEach((key) => {
        if (consumedKeys.has(key)) {
          return;
        }
        const value = summary[key];
        if (value === undefined || value === null || value === '') {
          return;
        }
        if (Array.isArray(value) || (typeof value === 'object' && value !== null)) {
          return;
        }
        rows.push({
          key: `summary_${key}`,
          label: this.formatSummaryKeyLabel(key),
          value,
          percent: this.isPercentMetricKey(key)
        });
      });

      return rows;
    },
    tradesRaw() {
      const result = this.resultData;
      if (!result) return [];
      if (Array.isArray(result.trades)) return result.trades;
      if (result.trades && Array.isArray(result.trades.items)) return result.trades.items;
      if (result.trades && Array.isArray(result.trades.records)) return result.trades.records;
      return [];
    },
    tradeColumnCandidates() {
      const result = this.resultData;
      if (!result) return [];
      const candidate = [];
      const pushColumns = (list) => {
        if (!Array.isArray(list)) return;
        list.forEach((item) => {
          if (typeof item === 'string' && item && !candidate.includes(item)) {
            candidate.push(item);
          }
        });
      };
      pushColumns(result.trade_columns);
      pushColumns(result.trade_keys);
      if (result.trades && typeof result.trades === 'object') {
        pushColumns(result.trades.columns);
        pushColumns(result.trades.keys);
      }
      return candidate;
    },
    trades() {
      const rows = this.tradesRaw;
      if (!rows.length) return [];
      const first = rows.find((row) => row !== null && row !== undefined);
      if (!first) return [];

      if (!Array.isArray(first)) {
        return rows
          .filter((row) => row && typeof row === 'object' && !Array.isArray(row))
          .map((row) => ({ ...row }));
      }

      const columnKeys = this.tradeColumnCandidates.length === first.length
        ? this.tradeColumnCandidates
        : first.map((_, index) => `col_${index + 1}`);

      return rows.map((row) => {
        if (!Array.isArray(row)) {
          if (row && typeof row === 'object') return { ...row };
          return { value: row };
        }
        const mapped = {};
        columnKeys.forEach((key, index) => {
          mapped[key] = row[index];
        });
        return mapped;
      });
    },
    allTradeColumns() {
      if (!this.trades.length) return [];
      const collected = new Set();
      this.trades.slice(0, 80).forEach((row) => {
        if (row && typeof row === 'object') {
          Object.keys(row).forEach((key) => collected.add(key));
        }
      });
      const rowKeys = Array.from(collected);
      if (!rowKeys.length) return [];
      const ordered = this.tradeColumnCandidates.filter((k) => collected.has(k));
      if (ordered.length) {
        const remain = rowKeys.filter((k) => !ordered.includes(k));
        return [...ordered, ...remain];
      }
      return rowKeys;
    },
    displayTradeColumns() {
      if (this.showAllTradeFields) return this.allTradeColumns;
      return this.allTradeColumns.slice(0, Math.min(10, this.allTradeColumns.length));
    },
    totalTradePages() {
      if (!this.trades.length) return 1;
      return Math.max(1, Math.ceil(this.trades.length / this.tradePageSize));
    },
    pagedTrades() {
      const start = (this.tradePage - 1) * this.tradePageSize;
      return this.trades.slice(start, start + this.tradePageSize);
    }
  },
  watch: {
    '$route.params.runId': {
      immediate: true,
      handler(value) {
        this.runId = String(value || '').trim();
        const run = getBacktestRunState(this.runId);
        this.runSummary = run || this.runSummary;
        this.activeTab = (run && run.ui && run.ui.activeTab) || 'overview';
        if (run && run.cache) {
          this.jobStatus = run.cache.jobStatus || this.jobStatus;
          this.jobError = run.cache.jobError || this.jobError;
          this.resultData = run.cache.resultData || this.resultData;
          this.logText = run.cache.logText || this.logText;
        }
        this.resetForNewRun();
      }
    },
    resultData() {
      this.tradePage = 1;
      this.showAllTradeFields = false;
      this.$nextTick(() => {
        this.renderEquityChart();
      });
    },
    activeTab(tab) {
      setBacktestRunActiveTab(this.runId, tab);
      if (tab === 'logs' && !this.logText) {
        this.fetchLogOnce(true);
      }
      if (tab === 'code' && !this.strategyCode) {
        this.fetchStrategyCode(true);
      }
    }
  },
  methods: {
    showMessage(message, type = 'success') {
      this.toastType = type;
      this.toastMessage = message;
      this.showToast = true;
      if (this.toastTimer) {
        clearTimeout(this.toastTimer);
      }
      this.toastTimer = setTimeout(() => {
        this.showToast = false;
      }, 2200);
    },
    getErrorMessage(error, fallback) {
      if (error && error.response && error.response.data) {
        const data = error.response.data;
        if (typeof data === 'string') return data;
        return data.message || data.error || fallback;
      }
      return (error && error.message) || fallback;
    },
    formatMetricValue(value, isPercent = false) {
      const num = toNumberOrNull(value);
      if (num !== null) {
        if (isPercent) {
          const absNum = Math.abs(num);
          const percentVal = absNum <= 2 ? num * 100 : num;
          return `${percentVal.toFixed(2)}%`;
        }
        return num.toFixed(4).replace(/\\.?0+$/, '');
      }
      if (value === null || value === undefined || value === '') return 'N/A';
      return String(value);
    },
    formatCash(value) {
      const num = Number(value);
      if (!Number.isFinite(num)) return String(value || '-');
      return num.toLocaleString('zh-CN');
    },
    formatSummaryKeyLabel(key) {
      return formatMetricKeyLabelZh(key);
    },
    isPercentMetricKey(key) {
      const val = String(key || '').toLowerCase();
      return (
        val.includes('return') ||
        val.includes('drawdown') ||
        val.includes('volatility') ||
        val.includes('turnover') ||
        val.endsWith('_rate') ||
        val.includes('ratio_pct')
      );
    },
    formatTradeColumnLabel(key) {
      const map = {
        id: '编号',
        trade_id: '成交编号',
        order_id: '委托编号',
        datetime: '时间',
        time: '时间',
        traded_at: '成交时间',
        created_at: '创建时间',
        updated_at: '更新时间',
        date: '日期',
        symbol_id: '标的',
        symbol: '标的',
        instrument: '标的',
        security: '标的',
        ticker: '标的',
        code: '代码',
        order_book_id: '标的',
        side: '方向',
        position_effect: '开平方向',
        order_type: '委托类型',
        status: '状态',
        price: '价格',
        avg_price: '均价',
        close_price: '收盘价',
        quantity: '数量',
        filled: '已成交',
        filled_quantity: '成交数量',
        position_qty: '持仓数量',
        amount: '金额',
        value: '市值',
        fee: '费用',
        commission: '手续费',
        tax: '印花税',
        slippage: '滑点',
        pnl: '盈亏'
      };
      if (map[key]) return map[key];
      const colMatch = /^col_(\d+)$/.exec(String(key || ''));
      if (colMatch) return `字段${colMatch[1]}`;

      const normalized = String(key || '').toLowerCase();
      if (normalized.includes('time') || normalized.includes('date')) return '时间';
      if (normalized.includes('symbol') || normalized.includes('order_book') || normalized.includes('ticker')) return '标的';
      if (normalized.includes('price')) return '价格';
      if (normalized.includes('qty') || normalized.includes('quantity')) return '数量';
      if (normalized.includes('amount') || normalized.includes('cash') || normalized.includes('value')) return '金额';
      if (normalized.includes('pnl') || normalized.includes('profit') || normalized.includes('loss')) return '盈亏';
      if (normalized.includes('fee') || normalized.includes('commission')) return '费用';

      return `字段(${key})`;
    },
    formatCellValue(value) {
      const num = toNumberOrNull(value);
      if (num !== null) {
        return num.toLocaleString('zh-CN', { maximumFractionDigits: 6 });
      }
      if (value === null || value === undefined || value === '') return 'N/A';
      if (typeof value === 'object') return JSON.stringify(value);
      return String(value);
    },
    toggleTradeFieldMode() {
      this.showAllTradeFields = !this.showAllTradeFields;
      this.tradePage = 1;
    },
    setActiveTab(tab) {
      this.activeTab = String(tab || 'overview');
    },
    goStrategies() {
      this.$router.push({ name: 'strategies' });
    },
    goHistory() {
      this.$router.push({
        name: 'backtest-history',
        query: {
          strategy_id: this.runSummary.strategyId || '',
          job_id: this.runId || ''
        }
      });
    },
    goEditStrategy() {
      if (!this.runSummary.strategyId) {
        return;
      }
      this.$router.push({ name: 'strategy-edit', params: { id: String(this.runSummary.strategyId) } });
    },
    resetForNewRun() {
      this.stopPolling();
      // 若 store 中已有缓存（例如从编辑页跳转过来），优先沿用，避免 UI 闪烁/重复请求
      const run = getBacktestRunState(this.runId);
      const cache = (run && run.cache) || {};

      this.jobStatus = cache.jobStatus || 'QUEUED';
      this.jobError = cache.jobError || '';
      this.resultData = cache.resultData || null;
      this.logText = cache.logText || '';
      this.strategyCode = '';
      this.fetchJobOnce(true);
    },
    async fetchJobOnce(silent = true) {
      if (!this.runId || this.loadingJob) {
        return;
      }
      this.loadingJob = true;
      try {
        const data = await getJob(this.runId);
        const status = ((data && data.status) || this.jobStatus || 'QUEUED').toUpperCase();
        this.jobStatus = status;
        this.jobError = (data && (data.error || data.message)) || '';
        upsertBacktestRunCache(this.runId, { jobStatus: this.jobStatus, jobError: this.jobError });

        // 如果后端在 job 中返回策略信息，尽量补齐 summary
        const strategyId = data && (data.strategy_id || data.strategyId);
        if (strategyId) {
          upsertBacktestRunSummary(this.runId, { strategyId: String(strategyId) });
          this.runSummary = getBacktestRunState(this.runId) || this.runSummary;
        }

        if (status === 'FAILED') {
          this.stopPolling();
          if (!silent) {
            this.showMessage(this.jobError ? `回测失败：${this.jobError}` : '回测失败', 'error');
          }
          return;
        }

        if (status === 'FINISHED') {
          this.stopPolling();
          await this.fetchResultOnce(true);
        } else if (status === 'RUNNING' || status === 'QUEUED') {
          this.startPolling();
        }

        if (this.activeTab === 'logs' && (status === 'RUNNING' || status === 'QUEUED')) {
          this.fetchLogOnce(true);
        }
      } catch (error) {
        if (!silent) {
          this.showMessage(this.getErrorMessage(error, '任务状态查询失败'), 'error');
        }
      } finally {
        this.loadingJob = false;
      }
    },
    async fetchProgressOnce() {
      if (!this.runId || this.jobStatus === 'FINISHED' || this.jobStatus === 'FAILED' || this.jobStatus === 'CANCELLED') {
        return;
      }
      try {
        const response = await this.$http.get(`/api/backtest/jobs/${this.runId}/progress`);
        const data = response.data || {};
        if (data.progress && typeof data.progress === 'object') {
          this.jobProgress = {
            percentage: typeof data.progress.percentage === 'number' ? data.progress.percentage : 0,
            stage: typeof data.progress.stage === 'string' ? data.progress.stage : 'unknown',
          };
        }
      } catch (error) {
        // Progress fetch failure is non-critical, silently continue
      }
    },
    startPolling() {
      if (this.pollTimer) return;
      this.pollTimer = setInterval(() => {
        this.fetchJobOnce(true);
        this.fetchProgressOnce();
      }, 1000);
    },
    stopPolling() {
      if (this.pollTimer) {
        clearInterval(this.pollTimer);
        this.pollTimer = null;
      }
    },
    async fetchResultOnce(silent = true) {
      if (!this.runId || this.loadingResult) {
        return;
      }
      this.loadingResult = true;
      try {
        const data = await getResult(this.runId);
        this.resultData = data || null;
        upsertBacktestRunCache(this.runId, { resultData: this.resultData });
        if (!silent) {
          this.showMessage('结果已更新');
        }
      } catch (error) {
        // 运行中若后端返回 409，说明暂不支持实时拉取完整结果
        // TODO(BE): 若希望支持“实时曲线/实时回测指标”，建议新增：
        // - GET /api/backtest/jobs/:jobId/result/partial（可分页/增量）
        // - 或 GET /api/backtest/jobs/:jobId/metrics /equity?cursor=...
        const status = error && error.response && error.response.status;
        if (status === 409) {
          this.jobStatus = 'RUNNING';
          if (!silent) {
            this.showMessage('任务运行中：后端暂不支持实时拉取完整结果（409）', 'error');
          }
          return;
        }
        if (!silent) {
          this.showMessage(this.getErrorMessage(error, '获取回测结果失败'), 'error');
        }
      } finally {
        this.loadingResult = false;
      }
    },
    async fetchLogOnce(silent = true) {
      if (!this.runId || this.loadingLog) {
        return;
      }
      this.loadingLog = true;
      try {
        const data = await getLog(this.runId);
        this.logText = normalizeLogPayload(data) || this.logText || '';
        upsertBacktestRunCache(this.runId, { logText: this.logText });
      } catch (error) {
        if (!silent) {
          this.showMessage(this.getErrorMessage(error, '获取日志失败'), 'error');
        }
      } finally {
        this.loadingLog = false;
      }
    },
    async fetchStrategyCode(silent = true) {
      const id = this.runSummary.strategyId;
      if (!id || this.loadingStrategyCode) {
        return;
      }
      this.loadingStrategyCode = true;
      try {
        const data = await getStrategy(id);
        this.strategyCode = normalizeCodePayload(data) || '';
      } catch (error) {
        if (!silent) {
          this.showMessage(this.getErrorMessage(error, '加载策略代码失败'), 'error');
        }
      } finally {
        this.loadingStrategyCode = false;
      }
    },
    renderEquityChart() {
      if (!this.$refs.equityChart) {
        return;
      }

      if (!this.hasEquityData) {
        if (this.chart) {
          this.chart.destroy();
          this.chart = null;
        }
        return;
      }

      const canvasEl = this.$refs.equityChart;
      const ctx = canvasEl.getContext('2d');
      if (!ctx) return;

      if (this.chart) {
        this.chart.destroy();
        this.chart = null;
      }

      const datasets = [
        {
          label: '策略净值',
          data: this.equityNavSeries,
          borderColor: '#409EFF',
          backgroundColor: 'rgba(64, 158, 255, 0.08)',
          borderWidth: 2,
          pointRadius: 0,
          pointHoverRadius: 3,
          tension: 0.25,
          spanGaps: true
        }
      ];

      if (this.hasBenchmarkSeries) {
        datasets.push({
          label: '基准净值',
          data: this.benchmarkNavSeries,
          borderColor: '#f59e0b',
          backgroundColor: 'rgba(245, 158, 11, 0.08)',
          borderWidth: 2,
          pointRadius: 0,
          pointHoverRadius: 3,
          borderDash: [6, 4],
          tension: 0.25,
          spanGaps: true
        });
      }

      this.chart = new Chart(ctx, {
        type: 'line',
        data: {
          labels: this.equityDateSeries,
          datasets
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          animation: false,
          interaction: {
            mode: 'index',
            intersect: false
          },
          plugins: {
            legend: {
              display: true,
              labels: {
                color: '#0f172a'
              }
            }
          },
          scales: {
            x: {
              type: 'category',
              ticks: {
                autoSkip: true,
                maxTicksLimit: 8,
                padding: 6,
                color: '#334155'
              },
              grid: {
                color: 'rgba(226, 232, 240, 0.9)'
              }
            },
            y: {
              ticks: {
                color: '#334155',
                padding: 8
              },
              grid: {
                color: 'rgba(226, 232, 240, 0.9)'
              }
            }
          }
        }
      });
    }
  },
  mounted() {
    window.addEventListener('resize', this.renderEquityChart);
  },
  beforeUnmount() {
    this.stopPolling();
    if (this.toastTimer) {
      clearTimeout(this.toastTimer);
      this.toastTimer = null;
    }
    if (this.chart) {
      this.chart.destroy();
      this.chart = null;
    }
    window.removeEventListener('resize', this.renderEquityChart);
  }
};
</script>

<style scoped>
.result-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.summary-bar {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  justify-content: space-between;
  padding: 20px 24px;
  border-radius: 2px;
  background: linear-gradient(135deg, #ffffff 0%, #f7fbff 100%);
  box-shadow: 0 4px 20px rgba(15, 23, 42, 0.08), 0 1px 3px rgba(15, 23, 42, 0.04);
  border: 1px solid rgba(223, 231, 242, 0.6);
  transition: box-shadow 0.3s ease;
}

.summary-bar:hover {
  box-shadow: 0 6px 24px rgba(15, 23, 42, 0.1), 0 2px 6px rgba(15, 23, 42, 0.06);
}

.title-row {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}

.title-row h2 {
  margin: 0;
  font-size: 22px;
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', monospace;
}

.run-chip {
  background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
  color: #fff;
  padding: 3px 10px;
  border-radius: 2px;
  font-size: 12px;
  font-weight: 800;
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.3);
}

.status {
  padding: 3px 12px;
  border-radius: 2px;
  font-size: 12px;
  font-weight: 900;
  border: 1.5px solid #d1d5db;
  background: #fff;
  color: #0f172a;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.08);
}

.status-running {
  border-color: rgba(59, 130, 246, 0.3);
  background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
  color: #1e40af;
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.15);
}

.status-finished {
  border-color: rgba(34, 197, 94, 0.3);
  background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%);
  color: #166534;
  box-shadow: 0 2px 8px rgba(34, 197, 94, 0.15);
}

.status-failed,
.status-cancelled {
  border-color: rgba(239, 68, 68, 0.3);
  background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%);
  color: #991b1b;
  box-shadow: 0 2px 8px rgba(239, 68, 68, 0.15);
}

.summary-meta {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  color: #5f6f86;
  font-size: 12px;
}

.meta-item.error {
  color: #b91c1c;
  font-weight: 800;
}

.summary-right {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
}

.layout {
  display: grid;
  grid-template-columns: 220px 1fr;
  gap: 12px;
  align-items: start;
}

.left-nav {
  background: #fff;
  border: 1px solid #eef2f7;
  border-radius: 2px;
  box-shadow: 0 4px 20px rgba(15, 23, 42, 0.08), 0 1px 3px rgba(15, 23, 42, 0.04);
  padding: 12px;
  position: sticky;
  top: 76px;
  transition: box-shadow 0.3s ease;
}

.left-nav:hover {
  box-shadow: 0 6px 24px rgba(15, 23, 42, 0.1), 0 2px 6px rgba(15, 23, 42, 0.06);
}

.nav-item {
  width: 100%;
  text-align: left;
  border: 1px solid transparent;
  background: transparent;
  padding: 11px 12px;
  border-radius: 2px;
  cursor: pointer;
  font-weight: 700;
  color: #334155;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
}

.nav-item::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 0;
  background: #1f6feb;
  border-radius: 0 2px 2px 0;
  transition: height 0.2s ease;
}

.nav-item:hover {
  background: #f8fafc;
  border-color: #e2e8f0;
  transform: translateX(2px);
}

.nav-item.active {
  background: linear-gradient(135deg, #eaf2ff 0%, #dbeafe 100%);
  border-color: rgba(31, 111, 235, 0.2);
  color: #1e40af;
  box-shadow: 0 2px 8px rgba(31, 111, 235, 0.1);
}

.nav-item.active::before {
  height: 60%;
}

.badge {
  background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
  color: #fff;
  border-radius: 2px;
  padding: 2px 8px;
  font-size: 11px;
  font-weight: 800;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.3);
}

.content {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.panel {
  background: #fff;
  border: 1px solid #eef2f7;
  border-radius: 2px;
  box-shadow: 0 4px 20px rgba(15, 23, 42, 0.08), 0 1px 3px rgba(15, 23, 42, 0.04);
  overflow: hidden;
  transition: box-shadow 0.3s ease;
}

.panel:hover {
  box-shadow: 0 6px 24px rgba(15, 23, 42, 0.1), 0 2px 6px rgba(15, 23, 42, 0.06);
}

.panel-header {
  padding: 12px 14px;
  border-bottom: 1px solid #ebeef5;
  background: #f6faff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.panel-header h3 {
  margin: 0;
  font-size: 16px;
}

.panel-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.panel-body {
  padding: 14px;
}

.meta {
  color: #5f6f86;
  font-size: 12px;
}

.inline-hint {
  border: 1px solid #e2e8f0;
  border-radius: 2px;
  background: #f8fafc;
  padding: 10px 12px;
  margin-bottom: 12px;
}

.hint-title {
  font-weight: 900;
  color: #0f172a;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.progress-percent {
  font-size: 12px;
  color: #666;
  font-weight: 400;
}

.hint-sub {
  margin-top: 6px;
  color: #475569;
  font-size: 12px;
  line-height: 1.5;
}

.progress {
  height: 10px;
  border-radius: 2px;
  overflow: hidden;
  background: rgba(226, 232, 240, 0.9);
  margin-top: 10px;
}

.bar {
  height: 100%;
  background: linear-gradient(90deg, #60a5fa 0%, #1f6feb 55%, #22c55e 100%);
}

.cards {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.card {
  border: 1px solid #eef2f7;
  border-radius: 2px;
  padding: 12px;
  background: #ffffff;
}

.card-label {
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
}

.card-value {
  margin-top: 8px;
  font-size: 18px;
  font-weight: 900;
  color: #0f172a;
}

.chart-card {
  margin-top: 12px;
  border: 1px solid #eef2f7;
  border-radius: 2px;
  overflow: hidden;
}

.chart-header {
  padding: 10px 12px;
  background: #f8fafc;
  border-bottom: 1px solid #eef2f7;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.chart-title {
  font-weight: 900;
  font-size: 13px;
  color: #0f172a;
}

.chart-meta {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.meta-chip {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 2px;
  background: #ecfdf5;
  border: 1px solid #86efac;
  color: #166534;
  font-weight: 800;
}

.meta-chip.muted {
  background: #f8fafc;
  border-color: #e2e8f0;
  color: #64748b;
}

.chart-body {
  height: 340px;
  position: relative;
}

.chart-canvas {
  width: 100%;
  height: 100%;
}

.table-scroll {
  overflow: auto;
  border: 1px solid #eef2f7;
  border-radius: 2px;
}

.table {
  width: 100%;
  border-collapse: collapse;
  min-width: 920px;
}

.table th,
.table td {
  padding: 10px 12px;
  border-bottom: 1px solid #eef2f7;
  text-align: left;
  font-size: 12px;
  color: #0f172a;
}

.table thead th {
  position: sticky;
  top: 0;
  background: #f8fafc;
  color: #475569;
  font-weight: 800;
  z-index: 1;
}

.pager {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 12px;
}

.pager-meta {
  font-size: 12px;
  color: #64748b;
}

.btn {
  border: 1px solid #d1d5db;
  background: #ffffff;
  color: #1f2937;
  padding: 8px 12px;
  border-radius: 2px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 700;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-mini {
  padding: 6px 10px;
  border-radius: 9px;
  font-size: 12px;
}

.link-btn {
  border: none;
  padding: 0;
  background: transparent;
  color: #1f6feb;
  font-weight: 900;
  cursor: pointer;
}

.empty {
  padding: 18px;
  border: 1px dashed #e2e8f0;
  border-radius: 2px;
  background: #f8fafc;
  color: #64748b;
  font-weight: 700;
}

.log {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 12px;
  line-height: 1.5;
  background: #0b1220;
  color: #e5e7eb;
  border-radius: 2px;
  padding: 10px 12px;
  min-height: 360px;
}

.kv-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.performance-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.kv {
  border: 1px solid #eef2f7;
  border-radius: 2px;
  background: #ffffff;
  padding: 10px 12px;
}

.kv .k {
  font-size: 12px;
  color: #64748b;
  font-weight: 800;
}

.kv .v {
  margin-top: 6px;
  font-size: 16px;
  font-weight: 900;
  color: #0f172a;
}

.toast {
  position: fixed;
  right: 16px;
  bottom: 18px;
  padding: 10px 12px;
  border-radius: 2px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.12);
  font-size: 13px;
  z-index: 9999;
  background: #0f172a;
  color: #fff;
}

.toast.error {
  background: #991b1b;
}

.toast-enter-active,
.toast-leave-active {
  transition: all 0.2s ease;
}

.toast-enter-from,
.toast-leave-to {
  transform: translateY(6px);
  opacity: 0;
}

@media (max-width: 980px) {
  .layout {
    grid-template-columns: 1fr;
  }
  .left-nav {
    position: static;
    top: auto;
  }
  .cards {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .performance-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
