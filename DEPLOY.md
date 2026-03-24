# 阿里云 ECS 部署指南

## 系统架构

```
用户浏览器
    ↓ HTTP
阿里云 ECS（公网 IP）
    ↓
Nginx（80 端口，反向代理）
    ↓
FastAPI / uvicorn（8000 端口）
    ├── 静态文件：static/index.html（前端页面）
    ├── 题库数据：exam_data/（Markdown 格式）
    └── 错题记录：mistakes.json
```

---

## 前置要求

| 项目 | 要求 |
|------|------|
| ECS 系统 | Ubuntu 22.04 LTS |
| ECS 规格 | 1核2G 及以上 |
| 安全组端口 | 80（Nginx）或 8000（直接访问） |
| Python | 3.10+ |

---

## 第一步：配置阿里云安全组

在阿里云控制台 → ECS → 安全组 → 配置规则，添加**入方向**规则：

| 协议 | 端口范围 | 授权对象 | 说明 |
|------|----------|----------|------|
| TCP | 80 | 0.0.0.0/0 | Nginx（推荐） |
| TCP | 8000 | 0.0.0.0/0 | 直接访问（备用） |

---

## 第二步：连接服务器，安装基础环境

```bash
# SSH 连接服务器
ssh root@你的ECS公网IP

# 更新系统
apt update && apt upgrade -y

# 安装 Python 3、pip、venv、Nginx
apt install -y python3 python3-pip python3-venv nginx
```

---

## 第三步：上传项目文件（在本地 Mac 执行）

```bash
# 上传 exam_system 目录（后端 + 前端）
scp -r /Users/tapo/Projects/qoder-work-space/exam_system root@你的ECS公网IP:/opt/

# 上传题库数据（Markdown 文件 + 图片）
scp -r /Users/tapo/Projects/qoder-work-space/exam_md root@你的ECS公网IP:/opt/exam_system/

# 如果有已解析好的 exam_data 目录也一并上传
# scp -r /Users/tapo/Projects/qoder-work-space/exam_system/exam_data root@你的ECS公网IP:/opt/exam_system/
```

---

## 第四步：修改前端 API 地址（在本地 Mac 执行）

编辑 `exam_system/static/index.html`，找到以下这行：

```javascript
const API_BASE_URL = 'http://127.0.0.1:8000';
```

改为（使用 Nginx 80 端口方案时，不需要端口号）：

```javascript
const API_BASE_URL = 'http://你的ECS公网IP';
```

修改后重新上传：

```bash
scp /Users/tapo/Projects/qoder-work-space/exam_system/static/index.html \
    root@你的ECS公网IP:/opt/exam_system/static/
```

---

## 第五步：服务器上安装 Python 依赖

```bash
# 进入项目目录
cd /opt/exam_system

# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

---

## 第六步：配置 systemd 守护进程（开机自启）

```bash
cat > /etc/systemd/system/exam-system.service << 'EOF'
[Unit]
Description=Exam System FastAPI Service
After=network.target

[Service]
User=root
WorkingDirectory=/opt/exam_system
ExecStart=/opt/exam_system/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

# 重载 systemd 配置
systemctl daemon-reload

# 设置开机自启
systemctl enable exam-system

# 启动服务
systemctl start exam-system

# 查看运行状态（应显示 active (running)）
systemctl status exam-system
```

---

## 第七步：配置 Nginx 反向代理

```bash
cat > /etc/nginx/sites-available/exam-system << 'EOF'
server {
    listen 80;
    server_name _;

    # 增大请求体限制（支持图片等静态资源）
    client_max_body_size 50M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 60s;
    }
}
EOF

# 启用站点配置
ln -s /etc/nginx/sites-available/exam-system /etc/nginx/sites-enabled/

# 删除默认站点（避免冲突）
rm -f /etc/nginx/sites-enabled/default

# 测试 Nginx 配置语法
nginx -t

# 重启 Nginx
systemctl restart nginx
systemctl enable nginx
```

---

## 第八步：验证部署

浏览器访问：`http://你的ECS公网IP`

如果无法访问，按以下顺序排查：

```bash
# 1. 检查 FastAPI 服务是否正常运行
systemctl status exam-system

# 2. 查看 FastAPI 实时日志
journalctl -u exam-system -f

# 3. 检查 Nginx 是否正常运行
systemctl status nginx

# 4. 检查端口监听情况
ss -tlnp | grep -E '80|8000'

# 5. 本地测试 FastAPI 是否响应
curl http://127.0.0.1:8000/api/chapters
```

---

## 常用运维命令

```bash
# 查看服务状态
systemctl status exam-system

# 查看实时日志
journalctl -u exam-system -f

# 重启服务（更新代码后执行）
systemctl restart exam-system

# 停止服务
systemctl stop exam-system

# 重启 Nginx
systemctl restart nginx
```

---

## 更新代码流程

每次更新代码后，在本地执行：

```bash
# 1. 上传更新的文件
scp -r /Users/tapo/Projects/qoder-work-space/exam_system root@你的ECS公网IP:/opt/

# 2. 在服务器上重启服务
ssh root@你的ECS公网IP "systemctl restart exam-system"
```

---

## 目录结构（服务器端）

```
/opt/exam_system/
├── main.py              # FastAPI 后端主程序
├── parser.py            # 题库解析器
├── requirements.txt     # Python 依赖
├── venv/                # Python 虚拟环境
├── static/
│   └── index.html       # 前端单页应用
├── exam_data/           # 解析后的题库数据（JSON）
├── exam_md/             # Markdown 格式题库 + 图片
│   └── images/
└── mistakes.json        # 错题记录（自动生成）
```

---

## 注意事项

1. **mistakes.json 权限**：服务首次运行时会自动创建，确保 `/opt/exam_system/` 目录有写权限
2. **exam_md/images 图片**：题库中的图片需要一并上传，否则题目图片无法显示
3. **防火墙**：除阿里云安全组外，如果 ECS 内部开启了 `ufw`，也需要放行端口：
   ```bash
   ufw allow 80
   ufw allow 8000  # 如果直接访问 8000 端口
   ```