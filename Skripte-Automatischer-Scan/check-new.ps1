# check-new.ps1 - Prüft auf neue Episoden (PowerShell Version)
# Führt den AniLoader im "new" Modus aus und sendet Discord-Benachrichtigung

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "AniLoader - Check New Episodes" -ForegroundColor Cyan
Write-Host "Gestartet am: $(Get-Date)" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

# ============================================
# KONFIGURATION
# ============================================
$API_ENDPOINT="https://your-domain.example.com"

# Basic Auth (falls Domain AUTH-geschützt ist)
# Format: "username:password" oder leer lassen
$API_AUTH="username:password"

# Discord Webhook URLs (als Array - leer lassen um Discord zu deaktivieren)
$DISCORD_WEBHOOK_URLS=(
    "https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN"
    # "https://discord.com/api/webhooks/ZWEITE_WEBHOOK_URL"
)

# ============================================
# HILFSFUNKTIONEN
# ============================================

function Get-AuthHeader {
    if ($API_AUTH) {
        $bytes = [System.Text.Encoding]::ASCII.GetBytes($API_AUTH)
        $base64 = [Convert]::ToBase64String($bytes)
        return @{ Authorization = "Basic $base64" }
    }
    return @{}
}

function ConvertTo-JsonEscape {
    param([string]$String)
    $String = $String -replace '\\', '\\'
    $String = $String -replace '"', '\"'
    $String = $String -replace "`n", '\n'
    $String = $String -replace "`r", '\r'
    $String = $String -replace "`t", '\t'
    return $String
}

function Send-DiscordGroupedEmbed {
    param(
        [string]$Title,
        [string]$Summary,
        [int]$Color,
        [string]$ErrorInfo,
        [string[]]$Episodes
    )
    
    if ($DISCORD_WEBHOOK_URLS.Count -eq 0) { return $true }
    
    # Gruppiere nach Serie
    $seriesEpisodes = @{}
    foreach ($ep in $Episodes) {
        if ($ep -match '^(.+)\s+(S\d{2}E\d{2}|Film\s+\d+)$') {
            $seriesName = $Matches[1]
            $episodeInfo = $Matches[2]
            if (-not $seriesEpisodes.ContainsKey($seriesName)) {
                $seriesEpisodes[$seriesName] = @()
            }
            $seriesEpisodes[$seriesName] += $episodeInfo
        }
    }
    
    # Baue Fields
    $fields = @()
    $count = 0
    foreach ($series in $seriesEpisodes.Keys) {
        if ($count -ge 25) { break }
        
        $eps = $seriesEpisodes[$series]
        $epCount = $eps.Count
        
        if ($epCount -eq 1) {
            $fields += @{
                name = $series
                value = "- $($eps[0])"
                inline = $false
            }
        } else {
            $value = ($eps | ForEach-Object { "- $_" }) -join "`n"
            $fields += @{
                name = "$series ($epCount x)"
                value = $value
                inline = $false
            }
        }
        $count++
    }
    
    $description = $Summary
    if ($ErrorInfo) {
        $description += "`n`n$ErrorInfo"
    }
    
    $payload = @{
        embeds = @(
            @{
                title = $Title
                description = $description
                color = $Color
                timestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ss.fffZ")
                fields = $fields
                footer = @{ text = "Unraid AniLoader" }
            }
        )
    } | ConvertTo-Json -Depth 10
    
    foreach ($webhookUrl in $DISCORD_WEBHOOK_URLS) {
        if (-not $webhookUrl) { continue }
        try {
            $response = Invoke-RestMethod -Uri $webhookUrl -Method Post -Body $payload -ContentType "application/json"
            Write-Host "[OK] Discord Webhook erfolgreich!" -ForegroundColor Green
            return $true
        } catch {
            Write-Host "[FEHLER] Discord Webhook fehlgeschlagen: $($_.Exception.Message)" -ForegroundColor Red
        }
    }
    return $false
}

# ============================================
# HAUPTPROGRAMM
# ============================================

$headers = Get-AuthHeader

# Prüfe Status
Write-Host "`nPrüfe ob System frei ist..." -ForegroundColor Yellow
try {
    $statusResponse = Invoke-RestMethod -Uri "$API_ENDPOINT/status" -Headers $headers -UseBasicParsing
    $status = $statusResponse.status
    Write-Host "[OK] System Status: $status" -ForegroundColor Green
} catch {
    Write-Host "[FEHLER] Konnte Status nicht abrufen: $($_.Exception.Message)" -ForegroundColor Red
}

# API Aufruf auskommentiert für Tests
# Write-Host "`nStarte New-Check via $API_ENDPOINT..." -ForegroundColor Yellow
# $body = '{"mode":"new"}'
# Invoke-RestMethod -Uri "$API_ENDPOINT/start_download" -Method Post -Headers $headers -Body $body -ContentType "application/json"

# ============================================
# LOGS AUSWERTEN
# ============================================
Write-Host "`nWerte Logs aus..." -ForegroundColor Yellow

try {
    $response = Invoke-WebRequest -Uri "$API_ENDPOINT/last_run" -Headers $headers -UseBasicParsing
    $rawResponse = $response.Content
} catch {
    Write-Host "[FEHLER] Konnte Logs nicht abrufen: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

if (-not $rawResponse) {
    Write-Host "Keine Logs verfügbar."
    exit 0
}

# Konvertiere JSON-Array zu Zeilen
$cleaned = $rawResponse -replace "`n|`r", ""
$lines = $cleaned -replace '^\["', '' -replace '"\]$', '' -split '","'

# Unicode-Escape dekodieren
$lines = $lines | ForEach-Object {
    $_ -replace '\\u00e4', 'ä' -replace '\\u00f6', 'ö' -replace '\\u00fc', 'ü' `
       -replace '\\u00df', 'ß' -replace '\\u00c4', 'Ä' -replace '\\u00d6', 'Ö' -replace '\\u00dc', 'Ü'
}

Write-Host "[DEBUG] Zeilen im Log: $($lines.Count)" -ForegroundColor Gray

# Parsing für NEW Modus
$parsedEpisodes = @()
$currentUrl = ""

foreach ($line in $lines) {
    # [DOWNLOAD] Versuche ... -> URL
    if ($line -match '\[DOWNLOAD\].*Versuche.*->\s*(https?://[^\s]+)') {
        $currentUrl = $Matches[1]
    }
    # [VERIFY] ... wurde erfolgreich erstellt
    elseif ($line -match '\[VERIFY\].*wurde.*erfolgreich.*erstellt' -and $currentUrl) {
        $url = $currentUrl
        
        # Parse URL
        if ($url -match '/(?:anime|serie)/stream/([^/]+)/staffel-(\d+)/episode-(\d+)') {
            $seriesSlug = $Matches[1]
            $season = [int]$Matches[2]
            $episode = [int]$Matches[3]
            
            # Slug zu Title Case
            $textInfo = (Get-Culture).TextInfo
            $seriesName = $textInfo.ToTitleCase(($seriesSlug -replace '-', ' '))
            $formatted = "{0} S{1:D2}E{2:D2}" -f $seriesName, $season, $episode
            
            Write-Host "  [GEFUNDEN] $formatted" -ForegroundColor Green
            $parsedEpisodes += $formatted
        }
        elseif ($url -match '/(?:anime|serie)/stream/([^/]+)/filme/film-(\d+)') {
            $seriesSlug = $Matches[1]
            $filmNr = $Matches[2]
            
            $textInfo = (Get-Culture).TextInfo
            $seriesName = $textInfo.ToTitleCase(($seriesSlug -replace '-', ' '))
            $formatted = "$seriesName Film $filmNr"
            
            Write-Host "  [GEFUNDEN] $formatted" -ForegroundColor Green
            $parsedEpisodes += $formatted
        }
        
        $currentUrl = ""
    }
}

# Zähle
$skipCount = ($lines | Where-Object { $_ -match '\[SKIP\]' }).Count
$errorCount = ($lines | Where-Object { $_ -match '\[ERROR\]' }).Count
$newEpisodesCount = $parsedEpisodes.Count

# Unique Serien
$uniqueSeries = @{}
foreach ($ep in $parsedEpisodes) {
    if ($ep -match '^(.+)\s+(S\d{2}E\d{2}|Film\s+\d+)$') {
        $uniqueSeries[$Matches[1]] = $true
    }
}
$seriesCount = $uniqueSeries.Count

Write-Host "`n=== ZUSAMMENFASSUNG ===" -ForegroundColor Yellow
Write-Host "Neue Episoden gefunden: $newEpisodesCount"
Write-Host "Betroffene Serien: $seriesCount"
Write-Host "Übersprungen: $skipCount"
Write-Host "Fehler: $errorCount"

# ============================================
# DISCORD BENACHRICHTIGUNG
# ============================================

if ($newEpisodesCount -gt 0) {
    $summary = "[OK] **$newEpisodesCount neue Episode(n) heruntergeladen!**`n[INFO] **$seriesCount Serie(n) aktualisiert**"
    
    $errorInfo = ""
    if ($errorCount -gt 0) {
        $errorInfo = "[WARN] $errorCount Fehler aufgetreten"
    }
    
    Write-Host "`nSende Discord Benachrichtigung..." -ForegroundColor Yellow
    Send-DiscordGroupedEmbed -Title "AniLoader - Neue Episoden Check" -Summary $summary -Color 3066993 -ErrorInfo $errorInfo -Episodes $parsedEpisodes
} else {
    Write-Host "`n[INFO] Keine neuen Episoden - keine Discord-Benachrichtigung." -ForegroundColor Gray
}

Write-Host "`nScript abgeschlossen: $(Get-Date)" -ForegroundColor Cyan
