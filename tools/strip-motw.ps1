[CmdletBinding()]
param(
  [Parameter(Mandatory)][string]$Path,
  [switch]$Verify
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath $Path).ProviderPath

# 需要处理的扩展名：可执行文件与压缩包（用户解压后仍会继承标记）
$exts = @('.exe', '.dll', '.pyd', '.msi', '.zip', '.7z', '.rar', '.ps1', '.bat', '.cmd')

function Get-MotwStreams {
  param([string]$File)
  try { (Get-Item -LiteralPath $File -Stream Zone.Identifier -ErrorAction Stop) | Out-Null; $true }
  catch { $false }
}

$files = Get-ChildItem -LiteralPath $root -Recurse -File |
         Where-Object { $exts -contains $_.Extension.ToLower() }

if ($Verify) {
  $bad = $files | Where-Object { Get-MotwStreams $_.FullName }
  if ($bad) {
    Write-Host "MOTW 残留 $($bad.Count) 个文件：" -ForegroundColor Red
    $bad | ForEach-Object { Write-Host "  $($_.FullName)" }
    exit 1
  }
  Write-Host "clean：$($files.Count) 个文件均无 Zone.Identifier" -ForegroundColor Green
  exit 0
}

$done = 0
foreach ($f in $files) {
  if (Get-MotwStreams $f.FullName) {
    Unblock-File -LiteralPath $f.FullName
    $done++
  }
}
Write-Host "已解除 $done 个文件的锁定（扫描 $($files.Count) 个）" -ForegroundColor Green
if ($done -eq 0) { Write-Host '全部原本就干净，无需处理' }
