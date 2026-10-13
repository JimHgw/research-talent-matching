# 使用 ngrok 的固定免费网址

前端在 Windows 上是 `http://127.0.0.1:5173`，在 Docker 网络里是
`http://frontend:80`。ngrok Docker Desktop 扩展 1.0.0 使用固定的
`172.17.0.1:<映射端口>` 作为上游。在本项目只绑定回环地址的配置下，这个地址
可能拒绝连接，即使控制台显示端点在线，网页也会返回 `ERR_NGROK_3004`。

这里使用官方 ngrok 代理容器，与前端加入同一 Docker 网络，并明确连接
`http://frontend:80`，无需修改路由器或将本机端口开放到其他网卡。

先在 Docker Desktop 的 ngrok 扩展中关闭相同网址的端点开关。
保留扩展中已有的账号配置，脚本首次运行会从本机扩展读取已有令牌，保存到
被 Git 忽略的 `data/public-sharing/ngrok-agent.env`。令牌不作为命令行参数，
也不打印到输出。没有配置扩展时，可以在本机设置 `NGROK_AUTHTOKEN` 后启动。

在项目根目录运行，使用账号实际分配的地址替换示例：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\share-ngrok.ps1 -Url https://your-name.ngrok-free.dev
```

网址末尾带 `/` 也可以，脚本会自动移除。请使用网站根网址，不要附带页面路径或查询参数。

首次启动会下载官方代理镜像，并重新创建前后端容器以更新允许来源和 HTTPS
cookie。已有数据库和上传文件保留。脚本保留已记录的 Cloudflare 临时网址
作为另一个允许来源，也保留本机 `http://127.0.0.1:5173` 和
`http://localhost:5173` 的访问及登录配置（端口会跟随 `FRONTEND_PORT`）。
不同网址使用各自的浏览器会话，需要分别登录。

脚本成功检查公网前端和会话接口后会显示 `Share this URL`。
ngrok 免费方案的提示页需要访客点击 **Visit Site** 才能进入网站。
注册和密码重置继续使用根目录 `.env` 中已有的 SMTP 配置。

以后启动、检查和停止：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\share-ngrok.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\share-ngrok.ps1 -Action status
powershell -NoProfile -ExecutionPolicy Bypass -File .\share-ngrok.ps1 -Action logs
powershell -NoProfile -ExecutionPolicy Bypass -File .\share-ngrok.ps1 -Action stop
```

保持电脑联网、不休眠并运行 Docker Desktop。ngrok 容器设为自动重启，所以
Docker 重启后会恢复连接；主动停止后，需要重新运行启动命令。
停止 ngrok 不会停止原有 Cloudflare 隧道。如需关闭后者，使用 `share.ps1 -Action stop`；
该操作也会恢复普通本地登录配置，随后再启动 ngrok 时，脚本会重新配置公网登录。

相关说明：[ngrok Docker 镜像](https://github.com/ngrok/docker-ngrok)、
[ERR_NGROK_3004](https://ngrok.com/docs/errors/err_ngrok_3004)。
