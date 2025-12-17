# PDF 黑白转换服务 - 项目规格说明

## 项目概述

一个基于 Python 3.12 的 Web 服务，支持上传 PDF 文件并将其转换为黑白/灰度版本，提供多档灰度级别选择，并支持实时预览转换前后的对比效果。

## 技术栈

| 组件 | 技术选型 |
|------|----------|
| 语言 | Python 3.12 |
| Web 框架 | FastAPI |
| 前端 | HTML + CSS + JavaScript (原生) |
| PDF 处理 | PyMuPDF (fitz) / pdf2image + Pillow |
| 容器化 | Docker |
| 本地开发环境 | Conda (fta-xrun-chat-bot) |

## 功能需求

### 1. PDF 上传与转换

- **上传功能**: 支持上传 PDF 文件（限制文件大小：50MB）
- **灰度转换**: 将彩色 PDF 转换为黑白/灰度版本
- **灰度档位选择**: 支持 1-4 档灰度级别
  - `1 档`: 纯黑白（仅黑色和白色，阈值二值化）
  - `2 档`: 黑白 + 50% 灰（3 色阶）
  - `3 档`: 黑白 + 33%/66% 灰（4 色阶）
  - `4 档`: 黑白 + 25%/50%/75% 灰（5 色阶）
- **输出格式**: 返回转换后的 PDF 文件

### 2. Web 界面

- **上传区域**: 拖拽或点击上传 PDF 文件
- **灰度选择器**: 下拉菜单或滑块选择灰度档位（1-4）
- **实时预览对比**:
  - 左侧显示原始 PDF 页面
  - 右侧显示转换后的页面
  - 支持翻页浏览
  - 支持缩放查看
- **下载按钮**: 下载转换完成的 PDF 文件

### 3. API 接口

```
POST /api/convert
- 请求: multipart/form-data
  - file: PDF 文件
  - gray_levels: 灰度档位 (1-4, 默认: 2)
- 响应: 转换后的 PDF 文件

GET /api/preview/{task_id}/{page}
- 请求: URL 参数
  - task_id: 任务 ID
  - page: 页码
  - type: original | converted
- 响应: 页面图片 (PNG/JPEG)

GET /api/status/{task_id}
- 响应: 转换状态和进度
```

## 项目结构

```
pdf-convert/
├── SPEC.md                 # 项目规格说明
├── README.md               # 项目说明文档
├── requirements.txt        # Python 依赖
├── Dockerfile              # Docker 镜像构建文件
├── docker-compose.yml      # Docker Compose 配置
├── start.sh                # Docker 启动脚本
├── dev.sh                  # 本地开发启动脚本
├── app/
│   ├── __init__.py
│   ├── main.py             # FastAPI 应用入口
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py       # API 路由定义
│   ├── services/
│   │   ├── __init__.py
│   │   └── pdf_converter.py # PDF 转换核心逻辑
│   ├── static/
│   │   ├── css/
│   │   │   └── style.css   # 样式文件
│   │   └── js/
│   │       └── app.js      # 前端交互逻辑
│   └── templates/
│       └── index.html      # Web 页面模板
├── uploads/                # 上传文件临时存储
└── outputs/                # 转换结果临时存储
```

## 环境配置

### 本地开发环境

```bash
# 激活 Conda 环境
conda activate fta-xrun-chat-bot

# 安装依赖
pip install -r requirements.txt

# 启动开发服务器
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Docker 部署

```bash
# 使用启动脚本
./start.sh

# 或手动构建运行
docker build -t pdf-convert .
docker run -p 8000:8000 pdf-convert
```

## 灰度转换算法说明

### 灰度量化公式

对于 N 档灰度（N 个色阶），量化步骤如下：

1. 将 RGB 图像转换为灰度图像
2. 计算量化级别: `levels = N + 1`（档位 + 1 = 色阶数）
3. 量化公式: `quantized = round(gray / 255 * N) * (255 / N)`

### 示例

| 档位 | 色阶数 | 灰度值 |
|------|--------|--------|
| 1 | 2 | 0, 255 |
| 2 | 3 | 0, 127, 255 |
| 3 | 4 | 0, 85, 170, 255 |
| 4 | 5 | 0, 64, 127, 191, 255 |

## 性能要求

- 单页 PDF 转换时间: < 2 秒
- 支持最大 PDF 页数: 100 页
- 支持最大文件大小: 50 MB
- 并发处理能力: 10 个同时转换任务

## 安全考虑

- 文件类型验证（仅接受 PDF）
- 文件大小限制
- 临时文件定期清理（1小时后自动删除）
- 防止路径遍历攻击

## 版本信息

- 版本: 1.0.0
- 创建日期: 2024-12-17
- Python 版本: 3.12
