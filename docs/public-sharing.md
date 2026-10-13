# 用自己的 Windows 电脑提供临时访问网址

已有 ngrok 固定免费网址时，见[ngrok 使用指南](ngrok-sharing.md)。

其他 Wi-Fi、学校网络或手机流量中的访问者，需要一个公网网址。
`localhost` 和 `192.168.x.x` 地址不能直接跨这些网络访问。
本项目使用 Cloudflare Quick Tunnel，把临时 HTTPS 网址连接到你电脑上的
Docker 前端；前端再转发 `/api/v1` 到同一电脑上的后端。数据库和上传文件
仍保存在现有 Docker 数据卷中。

## 启动并取得网址

先启动 Docker Desktop，并使用 Linux containers。然后在项目根目录运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\share.ps1
```

首次运行会下载 Cloudflare 的官方镜像并构建应用。成功后显示：

```text
Share this URL: https://<随机名称>.trycloudflare.com
```

把实际显示的网址发给其他人。他们直接用浏览器访问即可，不需要安装软件，
也不需要和你连接同一个 Wi-Fi。可以用手机关闭 Wi-Fi、使用移动数据验证。
本机入口 `http://127.0.0.1:5173` 和 `http://localhost:5173` 仍保留，
共享配置也保留这两个地址的登录允许来源（端口会跟随 `FRONTEND_PORT`）。

脚本会把这个精确的网址配置到后端的允许来源，并启用 HTTPS 会话 cookie，
避免网页能打开却无法登录或保存。它还会检查公网健康地址和 API 会话，再报告
成功。当前网址保存到被 Git 忽略的 `data/public-sharing/public-url.txt`。
已有账号继续使用；新用户注册仍需要根目录 `.env` 中配置好的 SMTP 邮件服务。
隧道不会替代邮件服务。没有 SMTP 时，可按照
[Docker 部署文档](docker-integration.md)在本机交互式创建账号。

应用代码没有更新时，可以跳过重新构建：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\share.ps1 -NoBuild
```

## 查看状态和停止

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\share.ps1 -Action status
powershell -NoProfile -ExecutionPolicy Bypass -File .\share.ps1 -Action logs
powershell -NoProfile -ExecutionPolicy Bypass -File .\share.ps1 -Action stop
```

停止操作关闭公网隧道，然后恢复普通本地 Docker 配置，不删除数据库。
关机、睡眠、断网或关闭 Docker 后，外部访问也会停止。重新创建隧道时网址会变化，
请重新运行启动脚本，让后端配置同步更新。容器不会自动重新启动隧道，防止网址
改变后允许来源仍指向旧网址。关闭 PowerShell 窗口不会停止 Docker 中的隧道。
默认保持现有 Compose 项目名；若之前设置过 `COMPOSE_PROJECT_NAME`，继续使用相同值。

Quick Tunnel 适合临时演示和测试，没有可用性保证，最多支持 200 个同时进行中的
请求，不支持 SSE。任何拿到网址的人都能到达网站的登录/注册页面，应用原有的
账号权限仍然生效。长期使用固定网址时，可以改为绑定自己域名的 Cloudflare Tunnel。
详见 [Cloudflare 官方 Quick Tunnel 文档](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/)。
