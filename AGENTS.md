# AGENTS.md

## 项目概览
社团作品展示 - 纯静态 HTML 页面，支持作品分类筛选、B站视频嵌入播放、详情页展示。

## 技术栈
- 原生 HTML/CSS/JS（无构建步骤）
- 通过 Python http.server 提供静态文件服务

## 文件结构
- `index.html` - 唯一页面文件，包含所有样式（内联 `<style>`）和逻辑（内联 `<script>`）

## 关键功能
- 分类 Tab 筛选：全部作品 / 原创作品 / 校园活动 / 体育赛事 / 音乐现场 / 舞蹈表演 / 校园新闻 / 数字创意（Tab 上显示各分类作品数）
- 搜索框：按作品标题 / 简介即时过滤
- 作品卡片列表：响应式网格布局（移动端单列，>=600px 双列）
- 详情页：B站 iframe 播放器 + 作品简介 + 活动介绍 + 演职人员 + 上一个/下一个作品
- 分享链接：每个作品有独立 URL（`#/work/作品ID`），详情页可一键复制链接
- App 嵌入适配：暴露 `window.ShumeiBridge`（setCategory / setSearch / hideTabs / hideSearch），供 iOS/Android 原生筛选器调用
- 数据源：`works.csv`（页面通过 fetch 动态加载，新增作品只需在表格里加一行）
- 修改 `works.csv` 后运行 `python3 sync_works_fallback.py`，同步页面内置备份数据

## 开发命令
- 本地预览：`python -m http.server ${DEPLOY_RUN_PORT} --bind 0.0.0.0`（需 Python 3.11+，旧版本不支持 HTTP Range 请求，会导致广播音频进度条无法跳转；或改用 `npx serve`）
- 无构建/无 lint/无测试
