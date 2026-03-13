<template>
  <div class="market-data-page">
    <div class="page-container">
      <div class="page-header">
        <div class="title-section">
          <h2>数据管理</h2>
        </div>
        <div class="nav-section">
          <router-link
            v-for="tab in tabs"
            :key="tab.id"
            :to="tab.path"
            class="nav-tab"
          >
            <svg class="nav-icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path
                :d="tab.iconPath"
                stroke="currentColor"
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="1.8"
              />
            </svg>
            <span>{{ tab.label }}</span>
          </router-link>
        </div>
      </div>

      <div class="page-body">
        <router-view />
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'MarketDataLayout',
  data() {
    return {
      tabs: [
        {
          id: 'overview',
          label: '数据全景',
          path: '/market-data/overview',
          iconPath: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z'
        },
        {
          id: 'config',
          label: '下载配置',
          path: '/market-data/config',
          iconPath: 'M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4'
        },
        {
          id: 'packages',
          label: 'Python包管理',
          path: '/market-data/packages',
          iconPath: 'M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4'
        },
        {
          id: 'vnpy',
          label: 'VNPY管理',
          path: '/market-data/vnpy',
          iconPath: 'M13 10V3L4 14h7v7l9-11h-7z'
        },
        {
          id: 'logs',
          label: '运行日志',
          path: '/market-data/logs',
          iconPath: 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z'
        }
      ]
    };
  }
};
</script>

<style scoped>
.market-data-page {
  display: flex;
  flex-direction: column;
  gap: 0;
  flex: 1;
  min-height: 0;
}

.page-container {
  background: #fff;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 16px;
  border-bottom: 1px solid #e0e0e0;
  background: #fafafa;
}

.title-section {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.title-section h2 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #000;
}

.nav-section {
  display: flex;
  gap: 4px;
  align-items: center;
}

.nav-tab {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border: 1px solid transparent;
  border-radius: 2px;
  text-decoration: none;
  color: #666;
  font-size: 12px;
  font-weight: 500;
  transition: all 0.15s ease;
}

.nav-tab:hover {
  background: #f5f5f5;
  color: #000;
}

.nav-tab.router-link-active {
  background: #fff;
  border-color: #d0d0d0;
  color: #000;
}

.nav-icon {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

.page-body {
  padding: 16px;
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  overflow: auto;
}
</style>
