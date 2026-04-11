# Academic Paper Assistant - 快速启动脚本

Write-Host "🚀 启动 Academic Paper Assistant..." -ForegroundColor Green
Write-Host ""

# ── 激活 conda 环境 ────────────────────────────────────────────────────────
$condaHook = "D:\Application\Anaconda\shell\condabin\conda-hook.ps1"
if (Test-Path $condaHook) {
    & $condaHook
    conda activate keenPoint
    Write-Host "✅ conda 环境已激活: keenPoint" -ForegroundColor Green
}
else {
    Write-Host "⚠️  未找到 conda-hook，请手动执行 conda activate keenPoint" -ForegroundColor Yellow
}

# 确认使用正确的 Python
$pythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
Write-Host "🐍 Python: $pythonExe" -ForegroundColor DarkGray

# 检查 Python 环境
Write-Host "📋 检查 Python 环境..." -ForegroundColor Cyan
python --version

# 检查是否安装了依赖
Write-Host ""
Write-Host "📦 检查依赖..." -ForegroundColor Cyan

$pipList = python -m pip list
if ($pipList -match "fastapi") {
    Write-Host "✅ 依赖已安装" -ForegroundColor Green
}
else {
    Write-Host "⚠️ 需要安装依赖" -ForegroundColor Yellow
    Write-Host "正在安装依赖..." -ForegroundColor Cyan
    python -m pip install -r requirements.txt
}

# 创建必要的目录
Write-Host ""
Write-Host "📁 创建必要的目录..." -ForegroundColor Cyan
$directories = @("uploads", "outputs", "logs", "temp", "static")
foreach ($dir in $directories) {
    if (!(Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir | Out-Null
        Write-Host "  ✅ 创建目录: $dir" -ForegroundColor Green
    }
}

# 复制环境变量文件（如果不存在）
if (!(Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Host "✅ 已创建 .env 文件" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "🎓 Academic Paper Assistant" -ForegroundColor Yellow
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "📍 API 地址: http://127.0.0.1:8000" -ForegroundColor White
Write-Host "📚 API 文档: http://127.0.0.1:8000/docs" -ForegroundColor White
Write-Host "📖 ReDoc: http://127.0.0.1:8000/redoc" -ForegroundColor White
Write-Host ""
Write-Host "按 Ctrl+C 停止服务器" -ForegroundColor Gray
Write-Host ""

# 启动服务器
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
