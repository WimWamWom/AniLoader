# last_run_summary.ps1 - Liest Logs und sendet Discord-Benachrichtigung (PowerShell Version)
# Analysiert die Log-Datei nach Episoden

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "AniLoader - LastRun Auswertung" -ForegroundColor Cyan
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
                footer = @{ text = "AniLoader" }
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

Write-Host "Lade Logs von API: $API_ENDPOINT/last_run" -ForegroundColor Yellow

try {
    $response = Invoke-WebRequest -Uri "$API_ENDPOINT/last_run" -Headers $headers -UseBasicParsing
    $rawResponse = $response.Content
} catch {
    Write-Host "[FEHLER] Konnte Logs nicht abrufen: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

if (-not $rawResponse) {
    Write-Host "[WARNUNG] Keine Logs verfügbar."
    exit 0
}

Write-Host "Werte Logs aus..." -ForegroundColor Yellow

# Konvertiere JSON-Array zu Zeilen
$cleaned = $rawResponse -replace "`n|`r", ""
$lines = $cleaned -replace '^\["', '' -replace '"\]$', '' -split '","'

# Unicode-Escape dekodieren
$lines = $lines | ForEach-Object {
    $_ -replace '\\u00e4', 'ä' -replace '\\u00f6', 'ö' -replace '\\u00fc', 'ü' `
       -replace '\\u00df', 'ß' -replace '\\u00c4', 'Ä' -replace '\\u00d6', 'Ö' -replace '\\u00dc', 'Ü'
}

Write-Host "[DEBUG] Zeilen im Log: $($lines.Count)" -ForegroundColor Gray

# Erkenne Modus
$mode = "unknown"
foreach ($line in $lines) {
    if ($line -match 'Modus: german') {
        $mode = "german"
        break
    }
    elseif ($line -match 'Modus: new') {
        $mode = "new"
        break
    }
}

Write-Host "Erkannter Modus: $mode" -ForegroundColor Yellow

# Parsing
$parsedEpisodes = @()
$currentUrl = ""
$currentIsGerman = $false

foreach ($line in $lines) {
    if ($mode -eq "german") {
        # [DOWNLOAD] Versuche German Dub -> URL
        if ($line -match '\[DOWNLOAD\].*Versuche.*German.*Dub.*->\s*(https?://[^\s]+)') {
            $currentUrl = $Matches[1]
            $currentIsGerman = $true
        }
        # [VERIFY] (nur wenn German Dub)
        elseif ($line -match '\[VERIFY\].*wurde.*erfolgreich.*erstellt' -and $currentUrl -and $currentIsGerman) {
            $url = $currentUrl
            
            if ($url -match '/(?:anime|serie)/stream/([^/]+)/staffel-(\d+)/episode-(\d+)') {
                $seriesSlug = $Matches[1]
                $season = [int]$Matches[2]
                $episode = [int]$Matches[3]
                
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
            $currentIsGerman = $false
        }
    }
    else {
        # NEW oder UNKNOWN Modus
        if ($line -match '\[DOWNLOAD\].*Versuche.*->\s*(https?://[^\s]+)') {
            $currentUrl = $Matches[1]
        }
        elseif ($line -match '\[VERIFY\].*wurde.*erfolgreich.*erstellt' -and $currentUrl) {
            $url = $currentUrl
            
            if ($url -match '/(?:anime|serie)/stream/([^/]+)/staffel-(\d+)/episode-(\d+)') {
                $seriesSlug = $Matches[1]
                $season = [int]$Matches[2]
                $episode = [int]$Matches[3]
                
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
}

# Zähle
$errorCount = ($lines | Where-Object { $_ -match '\[ERROR\]' }).Count
$skipCount = ($lines | Where-Object { $_ -match '\[SKIP\]' }).Count
$episodesCount = $parsedEpisodes.Count

# Unique Serien
$uniqueSeries = @{}
foreach ($ep in $parsedEpisodes) {
    if ($ep -match '^(.+)\s+(S\d{2}E\d{2}|Film\s+\d+)$') {
        $uniqueSeries[$Matches[1]] = $true
    }
}
$seriesCount = $uniqueSeries.Count

# ============================================
# ZUSAMMENFASSUNG
# ============================================

Write-Host "`n=== ZUSAMMENFASSUNG ===" -ForegroundColor Yellow
if ($mode -eq "german") {
    Write-Host "Neue deutsche Episoden gefunden: $episodesCount"
} elseif ($mode -eq "new") {
    Write-Host "Neue Episoden gefunden: $episodesCount"
    Write-Host "Betroffene Serien: $seriesCount"
    Write-Host "Übersprungen: $skipCount"
}
Write-Host "Fehler: $errorCount"

if ($episodesCount -gt 0) {
    Write-Host "`nGefundene Episoden (gruppiert):" -ForegroundColor Yellow
    foreach ($ep in $parsedEpisodes) {
        Write-Host "  - $ep"
    }
}

# ============================================
# DISCORD BENACHRICHTIGUNG
# ============================================

if ($episodesCount -gt 0) {
    if ($mode -eq "german") {
        $title = "[DE] AniLoader - Deutsche Episoden Check"
        $summary = "[OK] **$episodesCount neue deutsche Episode(n) gefunden!**"
    } elseif ($mode -eq "new") {
        $title = "AniLoader - Neue Episoden Check"
        $summary = "[OK] **$episodesCount neue Episode(n) heruntergeladen!**`n[INFO] **$seriesCount Serie(n) aktualisiert**"
    } else {
        $title = "AniLoader - LastRun Auswertung"
        $summary = "[OK] **$episodesCount neue Episode(n) gefunden!**"
    }
    
    $errorInfo = ""
    if ($errorCount -gt 0) {
        $errorInfo = "[WARN] $errorCount Fehler aufgetreten"
    }
    
    Write-Host "`nSende Discord Benachrichtigung..." -ForegroundColor Yellow
    Send-DiscordGroupedEmbed -Title $title -Summary $summary -Color 3066993 -ErrorInfo $errorInfo -Episodes $parsedEpisodes
} else {
    if ($mode -eq "german") {
        Write-Host "`n[INFO] Keine neuen deutschen Episoden - keine Discord-Benachrichtigung." -ForegroundColor Gray
    } elseif ($mode -eq "new") {
        Write-Host "`n[INFO] Keine neuen Episoden - keine Discord-Benachrichtigung." -ForegroundColor Gray
    } else {
        Write-Host "`n[INFO] Keine Episoden gefunden - keine Discord-Benachrichtigung." -ForegroundColor Gray
    }
}

Write-Host "`nScript abgeschlossen: $(Get-Date)" -ForegroundColor Cyan
