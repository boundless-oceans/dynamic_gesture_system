# 首次安装 / 卸载：桌面快捷方式
#
#   setup.ps1              -> 安装（建桌面快捷方式 + 启动程序）
#   setup.ps1 -Uninstall   -> 卸载（删快捷方式 + 删整个程序目录）
#
# 一般不用直接调用 —— 双击 install.bat 或 uninstall.bat 即可，它们会带上
# -ExecutionPolicy Bypass，并用 pushd + 相对路径把本文件找出来（那条路径在
# 中文目录下也验证过可用）。
#
# ⚠ 本文件**必须存成 UTF-8 带 BOM**：PowerShell 5.1 读没有 BOM 的 .ps1 会按
#   系统 ANSI(GBK) 解，下面的中文提示就全成乱码了。文件头那个 BOM 不能删。
#   （.bat 那边相反，刻意只用 ASCII —— 见其文件头说明。）
#
# 绿色部署：不复制任何文件。程序就待在这个文件夹里，"安装"只是建一个快捷方式。
# 不写注册表、不装服务、**不做开机自启**。卸载 = 删掉快捷方式 + 删掉本文件夹。

param([switch]$Uninstall)

$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot

# --------------------------------------------------------------------
# 工具函数
# --------------------------------------------------------------------

function Test-Under([string]$path, [string]$parent) {
    if ([string]::IsNullOrWhiteSpace($parent)) { return $false }
    $p = $path.TrimEnd('\')
    $q = $parent.TrimEnd('\')
    return $p.Equals($q, [StringComparison]::OrdinalIgnoreCase) -or
           $p.StartsWith($q + '\', [StringComparison]::OrdinalIgnoreCase)
}

function Get-AppExe {
    return Get-ChildItem -LiteralPath $here -Filter '*.exe' -File |
           Select-Object -First 1
}

function Get-ShortcutPaths([string]$name) {
    # 用 GetFolderPath 取真实的 shell 文件夹，所以 OneDrive 把桌面重定向过也照样
    # 正确（中文版 Win11 上很常见）。
    #
    # 一并返回"启动"文件夹的路径：**我们现在不往那儿装**（不做开机自启），
    # 但卸载时要顺手清掉——万一装过老版本，那儿会留一个失效的快捷方式。
    $desktop = Join-Path ([Environment]::GetFolderPath('Desktop')) ($name + '.lnk')
    $startup = Join-Path ([Environment]::GetFolderPath('Startup')) ($name + '.lnk')
    return @($desktop, $startup)
}

# --------------------------------------------------------------------
# 卸载
# --------------------------------------------------------------------

if ($Uninstall) {
    Write-Host ''
    Write-Host ('程序目录：' + $here)

    $exe = Get-AppExe
    if (-not $exe) {
        Write-Host '【错误】这个文件夹里没有找到 .exe —— 是不是找错目录了？'
        exit 3
    }
    $name = [IO.Path]::GetFileNameWithoutExtension($exe.Name)
    $lnks = Get-ShortcutPaths $name

    # 程序开着的时候删不掉（exe 被占用），而且失败原因很难看懂。先检查再说清楚。
    $running = Get-Process -Name $name -ErrorAction SilentlyContinue
    if ($running) {
        Write-Host ('【错误】程序还在运行（进程号 ' + ($running.Id -join ', ') + '）。')
        Write-Host '        请先关掉它，然后再运行本脚本。'
        exit 4
    }

    Write-Host ''
    Write-Host '将要删除：'
    foreach ($l in $lnks) {
        if (Test-Path -LiteralPath $l) { Write-Host ('  [有] ' + $l) }
    }
    Write-Host ('  [有] ' + $here + '   <-- 整个程序目录')
    Write-Host ''
    Write-Host '⚠ 注意：程序目录里还有 logs\ 和 config_local.json ——'
    Write-Host '        也就是现场的历史日志、以及调过的参数。想留就先拷出来。'
    Write-Host ''
    $answer = Read-Host '确认请输入 yes 再回车'
    if ($answer -ne 'yes') {
        Write-Host '已取消，什么都没动。'
        exit 0
    }

    foreach ($l in $lnks) {
        if (Test-Path -LiteralPath $l) {
            Remove-Item -LiteralPath $l -Force
            Write-Host ('已删除快捷方式：' + $l)
        }
    }

    # 脚本删不掉自己正在用的文件夹，所以另起一个独立进程，等几秒再删。
    # 这里用 PowerShell 而不是生成一个 .cmd —— PS 原生支持 Unicode 路径，
    # 免得又踩 cmd 的中文路径/代码页的老坑。
    $escaped = $here.Replace("'", "''")
    $inner = "Start-Sleep -Seconds 3;" +
             "Set-Location -LiteralPath `$env:TEMP;" +
             "Remove-Item -LiteralPath '$escaped' -Recurse -Force -ErrorAction SilentlyContinue"
    Start-Process -FilePath 'powershell' `
                  -ArgumentList @('-NoProfile', '-Command', $inner) `
                  -WorkingDirectory $env:TEMP `
                  -WindowStyle Hidden
    Write-Host ''
    Write-Host '快捷方式已删除。程序目录会在几秒后自动删除。'
    Write-Host '（这个窗口可以关掉了。）'
    exit 0
}

# --------------------------------------------------------------------
# 安装
# --------------------------------------------------------------------

Write-Host ''
Write-Host ('程序目录：' + $here)
Write-Host ''

# 拒绝"会被清理/移动"的位置。快捷方式里存的是**绝对路径**，这个文件夹以后要是
# 被挪走或清掉，图标就会悄悄失效，而且没人知道为什么。不如现在就拦住。
$risky = @(
    @{ Name = '临时目录 TEMP'; Path = [IO.Path]::GetTempPath() },
    @{ Name = '下载目录';      Path = (Join-Path $env:USERPROFILE 'Downloads') },
    @{ Name = '桌面';          Path = [Environment]::GetFolderPath('Desktop') }
)
foreach ($r in $risky) {
    if (Test-Under $here $r.Path) {
        Write-Host ('【错误】这个文件夹在「' + $r.Name + '」里面：')
        Write-Host ('        ' + $r.Path)
        Write-Host ''
        Write-Host '        请先把整个文件夹搬到一个固定的位置（自己挑），再运行本脚本。'
        Write-Host ''
        Write-Host '        原因：快捷方式记的是绝对路径，装完再搬、或者被系统清理掉，'
        Write-Host '        刚建的这个图标就打不开了。'
        exit 2
    }
}

$exe = Get-AppExe
if (-not $exe) {
    Write-Host '【错误】这个文件夹里没有找到 .exe。'
    Write-Host '        请在解压出来的程序目录里运行本脚本。'
    exit 3
}
$name = [IO.Path]::GetFileNameWithoutExtension($exe.Name)
Write-Host ('程序：' + $exe.Name)
Write-Host ''

$lnks = Get-ShortcutPaths $name
$shell = New-Object -ComObject WScript.Shell

$lnk = $shell.CreateShortcut($lnks[0])
$lnk.TargetPath = $exe.FullName
$lnk.WorkingDirectory = $here
$lnk.Description = $name
$lnk.Save()
Write-Host ('[1/2] 桌面快捷方式：' + $lnks[0])

Write-Host '[2/2] 启动程序…'
Start-Process -FilePath $exe.FullName -WorkingDirectory $here

Write-Host ''
Write-Host '完成。'
Write-Host '⚠ 装完之后**不要移动这个文件夹** —— 快捷方式指的就是这里。'
Write-Host '（本脚本不设置开机自启；需要的话手工把桌面那个快捷方式复制到'
Write-Host '  Win+R → shell:startup 打开的文件夹里即可。）'
exit 0
