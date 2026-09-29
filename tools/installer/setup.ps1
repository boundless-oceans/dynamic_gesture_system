# 首次安装 / 卸载：桌面快捷方式
#
#   setup.ps1              -> 安装（建桌面快捷方式 + 启动程序）
#   setup.ps1 -Uninstall   -> 卸载（删快捷方式 + Qt 缓存 + 删整个程序目录）
#
# 一般不用直接调用 —— 双击 install.bat 或 uninstall.bat 即可，它们会带上
# -ExecutionPolicy Bypass，并用 pushd + 相对路径把本文件找出来（那条路径在
# 中文目录下也验证过可用）。
#
# ⚠ 本文件**必须存成 UTF-8 带 BOM**：PowerShell 5.1 读没有 BOM 的 .ps1 会按
#   系统 ANSI(GBK) 解，下面的中文提示就全成乱码了。文件头那个 BOM 不能删。
#   （.bat 那边相反，刻意只用 ASCII —— 见其文件头说明。）
#
# 绿色部署：安装不复制任何文件，只是建一个快捷方式；不写注册表、不装服务、
# **不做开机自启**。
#
# ⚠ 删目录是危险操作，所以下面有一整套守卫（见 Test-RiskyReason）。
#   任何一条不过，都只删快捷方式、绝不碰文件夹。

param([switch]$Uninstall)

$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot

# --------------------------------------------------------------------
# 工具函数
# --------------------------------------------------------------------

function Test-Under([string]$path, [string]$parent) {
    if ([string]::IsNullOrWhiteSpace($path) -or [string]::IsNullOrWhiteSpace($parent)) {
        return $false
    }
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
    # 用 GetFolderPath 取真实的 shell 文件夹，OneDrive 把桌面重定向过也正确。
    # 一并返回"启动"文件夹的路径：**我们现在不往那儿装**（不做开机自启），
    # 但卸载时顺手清掉 —— 万一装过老版本，那儿会留一个失效的快捷方式。
    $desktop = Join-Path ([Environment]::GetFolderPath('Desktop')) ($name + '.lnk')
    $startup = Join-Path ([Environment]::GetFolderPath('Startup')) ($name + '.lnk')
    return @($desktop, $startup)
}

function Test-RiskyReason([string]$path) {
    # 返回"为什么这个目录不能作为程序目录"，安全则返回 $null。
    #
    # 这是本脚本最重要的一个函数：卸载要删掉整个程序目录，一旦路径判断错了，
    # 就可能删掉盘根、桌面、甚至是系统目录。所以宁可拒得严一点。
    if ([string]::IsNullOrWhiteSpace($path)) {
        return '脚本拿不到自己的所在路径（请用 install.bat / uninstall.bat 启动，别用管道）'
    }
    $p = $path.TrimEnd('\')
    if ($p -match '^[A-Za-z]:$') {
        return '它就是一个盘符的根目录'
    }
    if ($p -match '^[A-Za-z]:\\?$') {
        return '它就是一个盘符的根目录'
    }
    # 顺序有讲究：**最具体的排前面**。用户主目录那条最宽（桌面、下载、文档都在它下面），
    # 要是放前面，提示语就会变成笼统的"在用户主目录里"，帮不上忙。
    $forbidden = @(
        @{ N = '桌面';              P = [Environment]::GetFolderPath('Desktop') },
        @{ N = '下载目录';          P = (Join-Path $env:USERPROFILE 'Downloads') },
        @{ N = '文档';              P = [Environment]::GetFolderPath('MyDocuments') },
        @{ N = '启动目录';          P = [Environment]::GetFolderPath('Startup') },
        @{ N = '临时目录';          P = [IO.Path]::GetTempPath() },
        @{ N = 'Windows 目录';      P = $env:WINDIR },
        @{ N = 'Program Files';     P = $env:ProgramFiles },
        @{ N = 'Program Files (x86)'; P = ${env:ProgramFiles(x86)} },
        @{ N = 'ProgramData';       P = $env:ProgramData },
        @{ N = '用户主目录';        P = $env:USERPROFILE }
    )
    foreach ($f in $forbidden) {
        if (Test-Under $p $f.P) {
            return ('它在「' + $f.N + '」里（或就是它本身）')
        }
    }
    return $null
}

function Test-LooksLikeOurApp {
    # 只有"确实是我们打出来的产物"才允许整目录删除。
    # _internal\ 是 PyInstaller onedir 的签名，光看有没有 exe 不够
    # （随便一个目录里放个 exe 就会被误判）。
    if (-not (Test-Path -LiteralPath (Join-Path $here '_internal') -PathType Container)) {
        return $false
    }
    return ($null -ne (Get-AppExe))
}

# ====================================================================
# 卸载
# ====================================================================

if ($Uninstall) {
    Write-Host ''
    Write-Host ('脚本所在目录：' + $here)
    Write-Host ''

    $exe = Get-AppExe
    if (-not $exe) {
        Write-Host '【错误】这个文件夹里没有找到 .exe —— 是不是找错目录了？'
        exit 3
    }
    $name = [IO.Path]::GetFileNameWithoutExtension($exe.Name)
    $lnks = Get-ShortcutPaths $name
    # 应用运行时 Qt 建的图形缓存（在用户目录里，不在程序目录里）
    $cacheDir = Join-Path $env:LOCALAPPDATA $name

    # 程序开着时删不掉（exe 被占用），而且失败原因很难看懂。先检查再说清楚。
    $running = Get-Process -Name $name -ErrorAction SilentlyContinue
    if ($running) {
        Write-Host ('【错误】程序还在运行（进程号 ' + ($running.Id -join ', ') + '）。')
        Write-Host '        请先关掉它，然后再运行本脚本。'
        exit 4
    }

    # ---- 决定"能不能删文件夹"：四道守卫 ----
    $why = Test-RiskyReason $here
    $canDeleteFolder = $true
    if ($why) {
        $canDeleteFolder = $false
        $blockReason = $why
    } elseif (-not (Test-LooksLikeOurApp)) {
        $canDeleteFolder = $false
        $blockReason = ('它里面没有 _internal\ 这个文件夹，' +
                        '看起来不像本程序的产物目录')
    }

    Write-Host '将要删除：'
    foreach ($l in $lnks) {
        if (Test-Path -LiteralPath $l) { Write-Host ('  [有] ' + $l) }
    }
    if (Test-Path -LiteralPath $cacheDir) {
        Write-Host ('  [有] ' + $cacheDir + '   （应用的图形缓存）')
    }
    if ($canDeleteFolder) {
        Write-Host ('  [有] ' + $here + '   <-- 整个程序目录')
    } else {
        Write-Host '  [跳过] 程序目录**不动** ——'
        Write-Host ('         ' + $blockReason)
        Write-Host '         只删上面的快捷方式与缓存，文件夹请你手工确认后删除。'
    }
    Write-Host ''
    if ($canDeleteFolder) {
        Write-Host '⚠ 注意：程序目录里还有 logs\ 和 config_local.json ——'
        Write-Host '        也就是现场的历史日志、以及调过的参数。想留就先拷出来。'
        Write-Host ''
    }
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
    if (Test-Path -LiteralPath $cacheDir) {
        if (Test-Under $cacheDir $env:LOCALAPPDATA) {
            Remove-Item -LiteralPath $cacheDir -Recurse -Force
            Write-Host ('已删除应用缓存：' + $cacheDir)
        } else {
            Write-Host ('跳过缓存目录（路径异常）：' + $cacheDir)
        }
    }

    if (-not $canDeleteFolder) {
        Write-Host ''
        Write-Host '快捷方式与缓存已删除。程序目录**未动**（原因见上）。'
        exit 0
    }

    # 脚本删不掉自己正在用的文件夹，所以另起一个独立进程，等几秒再删。
    # 用 PowerShell 而不是生成 .cmd —— PS 原生支持 Unicode 路径，
    # 免得又踩 cmd 的中文路径/代码页的老坑。
    # 用 -LiteralPath：通配符**不会**被展开，路径里就算有 * 也当字面量处理。
    $escaped = $here.Replace("'", "''")
    $inner = "Start-Sleep -Seconds 3;" +
             "Set-Location -LiteralPath `$env:TEMP;" +
             "Remove-Item -LiteralPath '$escaped' -Recurse -Force -ErrorAction SilentlyContinue"
    Start-Process -FilePath 'powershell' `
                  -ArgumentList @('-NoProfile', '-Command', $inner) `
                  -WorkingDirectory $env:TEMP `
                  -WindowStyle Hidden
    Write-Host ''
    Write-Host '已提交删除。程序目录会在几秒后消失。'
    Write-Host '（这个窗口可以关掉了。）'
    exit 0
}

# ====================================================================
# 安装
# ====================================================================

Write-Host ''
Write-Host ('程序目录：' + $here)
Write-Host ''

# 拒绝"会被清理/移动"以及"绝不该装"的位置。快捷方式里存的是**绝对路径**，
# 这个文件夹以后要是被挪走或清掉，图标就会悄悄失效，而且没人知道为什么。
$why = Test-RiskyReason $here
if ($why) {
    Write-Host ('【错误】不能装在这里：' + $why)
    Write-Host ('        ' + $here)
    Write-Host ''
    Write-Host '        请把整个文件夹搬到一个固定的位置（自己挑），再运行本脚本。'
    Write-Host ''
    Write-Host '        原因：快捷方式记的是绝对路径，装完再搬、或被系统清理掉，'
    Write-Host '        刚建的这个图标就打不开了。'
    exit 2
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
