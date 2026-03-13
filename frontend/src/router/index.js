import { createRouter, createWebHashHistory } from 'vue-router';

const ExperimentalFeatures = () => import(
  /* webpackChunkName: "route-login" */
  '@/components/ExperimentalFeatures.vue'
);
const BacktestStrategyEditor = () => import(
  /* webpackChunkName: "route-backtest-legacy" */
  '@/components/BacktestStrategyEditor.vue'
);
const BacktestHistory = () => import(
  /* webpackChunkName: "route-backtest-legacy" */
  '@/components/BacktestHistory.vue'
);
const StrategiesIndex = () => import(
  /* webpackChunkName: "route-strategies" */
  '@/pages/StrategiesIndex.vue'
);
const StrategyEditor = () => import(
  /* webpackChunkName: "route-strategies" */
  '@/pages/StrategyEditor.vue'
);
const BacktestResult = () => import(
  /* webpackChunkName: "route-backtests" */
  '@/pages/BacktestResult.vue'
);
const ResearchIndex = () => import(
  /* webpackChunkName: "route-research" */
  '@/pages/ResearchIndex.vue'
);
const ResearchNotebook = () => import(
  /* webpackChunkName: "route-research" */
  '@/pages/ResearchNotebook.vue'
);
const MarketDataLayout = () => import(
  /* webpackChunkName: "route-market-data" */
  '@/pages/MarketData/Layout.vue'
);
const MarketDataOverview = () => import(
  /* webpackChunkName: "route-market-data" */
  '@/pages/MarketData/Overview.vue'
);
const MarketDataConfig = () => import(
  /* webpackChunkName: "route-market-data" */
  '@/pages/MarketData/Config.vue'
);
const MarketDataPackages = () => import(
  /* webpackChunkName: "route-market-data" */
  '@/pages/MarketData/Packages.vue'
);
const MarketDataLogs = () => import(
  /* webpackChunkName: "route-market-data" */
  '@/pages/MarketData/Logs.vue'
);
const MarketDataVnpy = () => import(
  /* webpackChunkName: "route-market-data" */
  '@/pages/MarketData/Vnpy.vue'
);

const routes = [
    { path: '/', redirect: '/login' },
    { path: '/login', component: ExperimentalFeatures, name: 'login' },
    // 新信息架构（聚宽风格）
    { path: '/strategies', component: StrategiesIndex, name: 'strategies' },
    { path: '/strategies/:id/edit', component: StrategyEditor, name: 'strategy-edit' },
    { path: '/backtests/:runId', component: BacktestResult, name: 'backtest-result' },
    { path: '/research', component: ResearchIndex, name: 'research-index' },
    { path: '/research/:id/notebook', component: ResearchNotebook, name: 'research-notebook' },
    {
      path: '/market-data',
      component: MarketDataLayout,
      name: 'market-data',
      children: [
        { path: '', redirect: { name: 'market-data-overview' } },
        { path: 'overview', component: MarketDataOverview, name: 'market-data-overview' },
        { path: 'config', component: MarketDataConfig, name: 'market-data-config' },
        { path: 'packages', component: MarketDataPackages, name: 'market-data-packages' },
        { path: 'vnpy', component: MarketDataVnpy, name: 'market-data-vnpy' },
        { path: 'logs', component: MarketDataLogs, name: 'market-data-logs' }
      ]
    },

    // 旧页面保留（避免破坏已有能力 / 兼容历史入口）
    { path: '/backtest/workbench', redirect: '/strategies', name: 'backtest-workbench' },
    { path: '/backtest/strategy-editor', component: BacktestStrategyEditor, name: 'backtest-strategy-editor' },
    { path: '/backtest/history', component: BacktestHistory, name: 'backtest-history' },
    { path: '/backtest/other', redirect: '/research', name: 'backtest-other' },
    { path: '/:pathMatch(.*)*', redirect: '/login' }
];

const router = createRouter({
    history: createWebHashHistory(),
    routes
});

// 路由守卫
router.beforeEach((to, from, next) => {
    const token = localStorage.getItem('token');
    if (!token && to.name !== 'login') {
        next({ name: 'login' });
    } else if (token && to.name === 'login') {
        next({ name: 'market-data-overview' });
    } else {
        next();
    }
});

export default router;
