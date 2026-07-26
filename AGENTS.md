# AGENTS.md

## 项目概览
社团作品展示 - 纯静态 HTML 页面，支持作品分类筛选、B站视频嵌入播放、详情页展示。

## 技术栈
- 原生 HTML/CSS/JS（无构建步骤）
- 通过 Python http.server 提供静态文件服务

## 文件结构
- `index.html` - 唯一页面文件，包含所有样式（内联 `<style>`）和逻辑（内联 `<script>`）

## 关键功能
- 分类 Tab 筛选：全部作品 / 原创作品 / 数字媒体 / 校园传媒
- 作品卡片列表：响应式网格布局（移动端单列，>=600px 双列）
- 详情页：B站 iframe 播放器 + 作品简介 + 活动介绍 + 演职人员
- 数据源：`worksData` 数组，直接在 JS 中维护

## 开发命令
- 本地预览：`python -m http.server ${DEPLOY_RUN_PORT} --bind 0.0.0.0`
- 无构建/无 lint/无测试
