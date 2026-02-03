<#
PowerShell script to update s.to links in the AniLoader SQLite DB.
Usage:
  .\update_s_to_links.ps1                # uses default data/AniLoader.db
  .\update_s_to_links.ps1 -DbPath path  # custom DB path

The script creates a timestamped backup and attempts to run the UPDATE using `sqlite3` CLI.
If `sqlite3` is not available it falls back to Python (requires `python` in PATH).
#>
param(
    [string]$DbPath = "data/AniLoader.db"
)

Set-StrictMode -Version Latest

if (-not (Test-Path $DbPath)) {
    Write-Error "Database not found: $DbPath"
    exit 2
}

$timestamp = Get-Date -Format "yyyyMMddHHmmss"
$backup = "${DbPath}.$timestamp.bak"
Copy-Item -Path $DbPath -Destination $backup -Force
Write-Host "Backup created: $backup"

$selectSql = "SELECT COUNT(*) FROM anime WHERE url LIKE '%/serie/stream/%';"
$updateSql = "UPDATE anime SET url = REPLACE(url, '/serie/stream/', '/serie/') WHERE url LIKE '%/serie/stream/%';"

$selectSql2 = "SELECT COUNT(*) FROM anime WHERE fehlende_deutsch_folgen LIKE '%/serie/stream/%';"
$updateSql2 = "UPDATE anime SET fehlende_deutsch_folgen = REPLACE(fehlende_deutsch_folgen, '/serie/stream/', '/serie/') WHERE fehlende_deutsch_folgen LIKE '%/serie/stream/%';"

function Run-WithSqliteCli {
    param($db, $sql)
    $exe = "sqlite3"
    $out = & $exe $db $sql 2>&1
    if ($LASTEXITCODE -ne 0) { Write-Error "sqlite3 error: $out"; return $null }
    return $out
}

if (Get-Command sqlite3 -ErrorAction SilentlyContinue) {
    try {
        $before = Run-WithSqliteCli -db $DbPath -sql $selectSql
        Write-Host "Entries matching (url) before: $before"
        Run-WithSqliteCli -db $DbPath -sql $updateSql | Out-Null
        $after = Run-WithSqliteCli -db $DbPath -sql $selectSql
        Write-Host "Entries matching (url) after: $after"

        # fehlende_deutsch_folgen
        $before2 = Run-WithSqliteCli -db $DbPath -sql $selectSql2
        Write-Host "Entries matching (fehlende_deutsch_folgen) before: $before2"
        Run-WithSqliteCli -db $DbPath -sql $updateSql2 | Out-Null
        $after2 = Run-WithSqliteCli -db $DbPath -sql $selectSql2
        Write-Host "Entries matching (fehlende_deutsch_folgen) after: $after2"
        Write-Host "Done."
        exit 0
    } catch {
        Write-Error "Error while running sqlite3: $_"
        exit 3
    }
} elseif ((Get-Command python -ErrorAction SilentlyContinue) -or (Get-Command python3 -ErrorAction SilentlyContinue)) {
    $pyCmd = if (Get-Command python -ErrorAction SilentlyContinue) { 'python' } else { 'python3' }
    $py = @"
import sqlite3,sys
db = r'${DbPath}'
conn = sqlite3.connect(db)
c = conn.cursor()
# url field
before = c.execute("SELECT COUNT(*) FROM anime WHERE url LIKE '%/serie/stream/%'").fetchone()[0]
print(before)
c.execute("UPDATE anime SET url = REPLACE(url, '/serie/stream/', '/serie/') WHERE url LIKE '%/serie/stream/%'")
conn.commit()
after = c.execute("SELECT COUNT(*) FROM anime WHERE url LIKE '%/serie/stream/%'").fetchone()[0]
print(after)
# fehlende_deutsch_folgen field
before2 = c.execute("SELECT COUNT(*) FROM anime WHERE fehlende_deutsch_folgen LIKE '%/serie/stream/%'").fetchone()[0]
print(before2)
c.execute("UPDATE anime SET fehlende_deutsch_folgen = REPLACE(fehlende_deutsch_folgen, '/serie/stream/', '/serie/') WHERE fehlende_deutsch_folgen LIKE '%/serie/stream/%'")
conn.commit()
after2 = c.execute("SELECT COUNT(*) FROM anime WHERE fehlende_deutsch_folgen LIKE '%/serie/stream/%'").fetchone()[0]
print(after2)
conn.close()
"@
    try {
        Write-Host "Using Python fallback ($pyCmd)"
        $tmp = [IO.Path]::Combine([IO.Path]::GetTempPath(), [IO.Path]::GetRandomFileName() + ".py")
        Set-Content -Path $tmp -Value $py -Encoding UTF8
        try {
            $out = & $pyCmd $tmp 2>&1
            if ($LASTEXITCODE -ne 0) { Write-Error "Python error: $out"; Remove-Item -Path $tmp -Force -ErrorAction SilentlyContinue; exit 4 }
            $lines = $out -split "`n"
            if ($lines.Count -ge 2) {
                Write-Host "Entries matching before: $($lines[0].Trim())"
                Write-Host "Entries matching after: $($lines[1].Trim())"
            } else {
                Write-Host $out
            }
            Write-Host "Done."
            Remove-Item -Path $tmp -Force -ErrorAction SilentlyContinue
            exit 0
        } finally {
            if (Test-Path $tmp) { Remove-Item -Path $tmp -Force -ErrorAction SilentlyContinue }
        }
    } catch {
        Write-Error "Error while running Python fallback: $_"
        exit 5
    }
} else {
    Write-Error "Neither 'sqlite3' CLI nor 'python' found in PATH. Install sqlite3 or Python to run this script."
    exit 6
}
