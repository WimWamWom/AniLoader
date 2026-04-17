Write-Host '=========================================' -ForegroundColor Cyan
Write-Host 'AniLoader - Check New Episodes' -ForegroundColor Cyan
Write-Host "Gestartet am: $(Get-Date)" -ForegroundColor Cyan
Write-Host '=========================================' -ForegroundColor Cyan

# ============================================
# KONFIGURATION
# ============================================
$API_ENDPOINT = 'https://your-domain.example.com'

# Basic Auth (falls Domain AUTH-geschützt ist)
# Format: username:password oder leer lassen
$API_AUTH = 'username:password'

# Discord Webhook URLs (als Array - leer lassen um Discord zu deaktivieren)
$DISCORD_WEBHOOK_URLS = @(
    'https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN'
)

# Maximale Wartezeit in Minuten, falls System beschäftigt ist
# 0 = unbegrenzt warten
$MAX_WAIT_MINUTES = 180

function Get-AuthHeaders {
    if ([string]::IsNullOrWhiteSpace($API_AUTH)) {
        return @{}
    }

    $bytes = [System.Text.Encoding]::ASCII.GetBytes($API_AUTH)
    $base64 = [Convert]::ToBase64String($bytes)
    return @{ Authorization = "Basic $base64" }
}

function Invoke-AniLoaderApi {
    param(
        [ValidateSet('GET', 'POST')]
        [string]$Method,
        [string]$Uri,
        [object]$Body = $null,
        [int]$TimeoutSec = 60
    )

    $params = @{
        Method = $Method
        Uri = $Uri
        Headers = (Get-AuthHeaders)
        TimeoutSec = $TimeoutSec
        ErrorAction = 'Stop'
    }

    if ($null -ne $Body) {
        $params['ContentType'] = 'application/json'
        $params['Body'] = ($Body | ConvertTo-Json -Depth 10)
    }

    return Invoke-RestMethod @params
}

function Convert-SlugToSeriesName {
    param([string]$Slug)

    $textInfo = [System.Globalization.CultureInfo]::CurrentCulture.TextInfo
    return $textInfo.ToTitleCase(($Slug -replace '-', ' ').ToLower())
}

function Convert-UrlToEpisodeLabel {
    param([string]$Url)

    if ($Url -match '/(?:anime|serie)/stream/([^/]+)/staffel-([0-9]+)/episode-([0-9]+)') {
        $seriesName = Convert-SlugToSeriesName -Slug $Matches[1]
        $season = '{0:D2}' -f [int]$Matches[2]
        $episode = '{0:D2}' -f [int]$Matches[3]
        return "$seriesName S${season}E${episode}"
    }

    if ($Url -match '/(?:anime|serie)/stream/([^/]+)/filme/film-([0-9]+)') {
        $seriesName = Convert-SlugToSeriesName -Slug $Matches[1]
        return "$seriesName Film $([int]$Matches[2])"
    }

    return $null
}

function Parse-DownloadedEpisodes {
    param([string]$LogContent)

    $episodes = New-Object System.Collections.Generic.List[string]
    $currentUrl = ''

    foreach ($line in ($LogContent -split "`r?`n")) {
        if ($line -match '\[DOWNLOAD\].*Versuche.*->\s*(https?://\S+)') {
            $currentUrl = $Matches[1]
            continue
        }

        if ($line -match '\[VERIFY\].*wurde.*erfolgreich.*erstellt' -and $currentUrl) {
            $parsedEpisode = Convert-UrlToEpisodeLabel -Url $currentUrl
            if ($parsedEpisode) {
                [void]$episodes.Add($parsedEpisode)
            }
            $currentUrl = ''
        }
    }

    return ,$episodes.ToArray()
}

function Get-LogMatchCount {
    param(
        [string]$LogContent,
        [string]$Pattern
    )

    return ([regex]::Matches($LogContent, $Pattern)).Count
}

function Get-UniqueSeriesCount {
    param([string[]]$Episodes)

    $series = New-Object 'System.Collections.Generic.HashSet[string]'
    foreach ($episode in $Episodes) {
        if ($episode -match '^(.+)\s+(S\d{2}E\d{2}|Film\s+\d+)$') {
            [void]$series.Add($Matches[1])
        }
    }
    return $series.Count
}

function New-DiscordFields {
    param([string[]]$Episodes)

    $grouped = [ordered]@{}
    foreach ($episode in $Episodes) {
        if ($episode -match '^(.+)\s+(S\d{2}E\d{2}|Film\s+\d+)$') {
            $seriesName = $Matches[1]
            $episodeInfo = $Matches[2]
            if (-not $grouped.Contains($seriesName)) {
                $grouped[$seriesName] = New-Object System.Collections.Generic.List[string]
            }
            [void]$grouped[$seriesName].Add($episodeInfo)
        }
    }

    $fields = New-Object System.Collections.Generic.List[object]
    foreach ($seriesName in $grouped.Keys) {
        $seriesEpisodes = $grouped[$seriesName]
        $fieldName = $seriesName
        if ($seriesEpisodes.Count -gt 1) {
            $fieldName = "$seriesName ($($seriesEpisodes.Count) x)"
        }

        $value = (($seriesEpisodes | ForEach-Object { "- $_" }) -join "`n")
        if ($value.Length -gt 1024) {
            $value = $value.Substring(0, 1004) + "`n... (gekürzt)"
        }

        [void]$fields.Add([pscustomobject]@{
            name = $fieldName
            value = $value
            inline = $false
        })
    }

    return ,$fields.ToArray()
}

function New-DiscordEmbeds {
    param(
        [string]$Title,
        [string]$Summary,
        [int]$Color,
        [string]$ErrorInfo,
        [string[]]$Episodes
    )

    $fields = New-DiscordFields -Episodes $Episodes
    $embeds = New-Object System.Collections.Generic.List[object]
    $currentFields = New-Object System.Collections.Generic.List[object]
    $embedIndex = 0
    $currentChars = 0

    foreach ($field in $fields) {
        $fieldChars = $field.name.Length + $field.value.Length + 30
        if ($currentFields.Count -eq 0) {
            if ($embedIndex -eq 0) {
                $currentChars = $Title.Length + $Summary.Length + $ErrorInfo.Length + 80
            } else {
                $currentChars = $Title.Length + 130
            }
        }

        if ($currentFields.Count -gt 0 -and ($currentFields.Count -ge 25 -or ($currentChars + $fieldChars) -gt 5800)) {
            $embedIndex += 1
            $description = if ($embedIndex -eq 1) { $Summary } else { "📺 **Fortsetzung (Teil $embedIndex)...**" }
            [void]$embeds.Add([pscustomobject]@{
                title = $Title
                description = $description
                color = $Color
                timestamp = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ss.000Z')
                fields = @($currentFields.ToArray())
                footer = @{ text = 'Unraid AniLoader' }
            })
            $currentFields = New-Object System.Collections.Generic.List[object]
            $currentChars = $Title.Length + 130
        }

        [void]$currentFields.Add($field)
        $currentChars += $fieldChars
    }

    if ($currentFields.Count -gt 0) {
        $embedIndex += 1
        $description = if ($embedIndex -eq 1) { $Summary } else { "📺 **Fortsetzung (Teil $embedIndex)...**" }
        if ($ErrorInfo) {
            $description += "`n`n$ErrorInfo"
        }
        [void]$embeds.Add([pscustomobject]@{
            title = $Title
            description = $description
            color = $Color
            timestamp = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ss.000Z')
            fields = @($currentFields.ToArray())
            footer = @{ text = 'Unraid AniLoader' }
        })
    }

    return ,$embeds.ToArray()
}

function Send-DiscordMultiEmbed {
    param(
        [string]$Title,
        [string]$Summary,
        [int]$Color,
        [string]$ErrorInfo,
        [string[]]$Episodes
    )

    if (-not $DISCORD_WEBHOOK_URLS -or $DISCORD_WEBHOOK_URLS.Count -eq 0) {
        return $true
    }

    $payload = @{ embeds = (New-DiscordEmbeds -Title $Title -Summary $Summary -Color $Color -ErrorInfo $ErrorInfo -Episodes $Episodes) }
    $json = $payload | ConvertTo-Json -Depth 15 -Compress
    $failed = 0

    foreach ($webhookUrl in $DISCORD_WEBHOOK_URLS) {
        if ([string]::IsNullOrWhiteSpace($webhookUrl)) {
            continue
        }

        try {
            $response = Invoke-WebRequest -Uri $webhookUrl -Method POST -ContentType 'application/json' -Body $json -UseBasicParsing -ErrorAction Stop
            if ($response.StatusCode -ne 200 -and $response.StatusCode -ne 204) {
                $failed += 1
                Write-Host "[FEHLER] Discord Multi-Embed fehlgeschlagen (HTTP $($response.StatusCode))"
            }
        } catch {
            $failed += 1
            $statusCode = $_.Exception.Response.StatusCode.value__
            if ($statusCode) {
                Write-Host "[FEHLER] Discord Multi-Embed fehlgeschlagen (HTTP $statusCode)"
            } else {
                Write-Host "[FEHLER] Discord Multi-Embed fehlgeschlagen: $($_.Exception.Message)"
            }
        }
    }

    return ($failed -eq 0)
}

try {
    $waited = 0
    Write-Host 'Prüfe ob System frei ist...'
    while ($true) {
        $statusResponse = Invoke-AniLoaderApi -Method GET -Uri "$API_ENDPOINT/status" -TimeoutSec 30
        if ([string]$statusResponse.status -ne 'running') {
            Write-Host '[OK] System ist frei, starte New-Check...'
            break
        }

        if ($MAX_WAIT_MINUTES -gt 0 -and $waited -ge $MAX_WAIT_MINUTES) {
            throw "Timeout nach $MAX_WAIT_MINUTES Minuten"
        }

        if ($MAX_WAIT_MINUTES -eq 0) {
            Write-Host "[WARTE] System beschäftigt, warte... ($waited Min, unbegrenzt)"
        } else {
            Write-Host "[WARTE] System beschäftigt, warte... ($waited/$MAX_WAIT_MINUTES Min)"
        }

        Start-Sleep -Seconds 60
        $waited += 1
    }

    Write-Host "Starte New-Check via $API_ENDPOINT..."
    [void](Invoke-AniLoaderApi -Method POST -Uri "$API_ENDPOINT/start_download" -Body @{ mode = 'new' })

    Write-Host 'Warte auf Abschluss...'
    Start-Sleep -Seconds 10
    while ($true) {
        $statusResponse = Invoke-AniLoaderApi -Method GET -Uri "$API_ENDPOINT/status" -TimeoutSec 30
        $status = [string]$statusResponse.status
        if ($status -ne 'running') {
            Write-Host "Check abgeschlossen (Status: $status)"
            break
        }
        Write-Host 'Läuft noch...'
        Start-Sleep -Seconds 30
    }

    Write-Host ''
    Write-Host 'Werte Logs aus...'
    $lastRunResponse = Invoke-AniLoaderApi -Method GET -Uri "$API_ENDPOINT/last_run"
    $logContent = [string]$lastRunResponse.log

    if ([string]::IsNullOrWhiteSpace($logContent)) {
        Write-Host 'Keine Logs verfügbar.'
        exit 0
    }

    Write-Host "[DEBUG] Zeilen im Log: $(($logContent -split "`r?`n").Count)"

    $parsedEpisodes = @(Parse-DownloadedEpisodes -LogContent $logContent)
    $skippedCount = Get-LogMatchCount -LogContent $logContent -Pattern '\[SKIP\]'
    $errorCount = Get-LogMatchCount -LogContent $logContent -Pattern '\[ERROR\]'
    $newEpisodesCount = $parsedEpisodes.Count
    $seriesCount = Get-UniqueSeriesCount -Episodes $parsedEpisodes

    Write-Host ''
    Write-Host '=== ZUSAMMENFASSUNG ==='
    Write-Host "Neue Episoden gefunden: $newEpisodesCount"
    Write-Host "Betroffene Serien: $seriesCount"
    Write-Host "Übersprungen: $skippedCount"
    Write-Host "Fehler: $errorCount"

    if ($newEpisodesCount -gt 0) {
        $summary = "✅ **$newEpisodesCount neue Episode(n) heruntergeladen!**`n📊 **$seriesCount Serie(n) aktualisiert**"
        $errorInfo = ''
        if ($errorCount -gt 0) {
            $errorInfo = "⚠️ $errorCount Fehler aufgetreten"
        }

        if (Send-DiscordMultiEmbed -Title '📺 AniLoader - Neue Episoden Check' -Summary $summary -Color 3066993 -ErrorInfo $errorInfo -Episodes $parsedEpisodes -WebhookUrls $DISCORD_WEBHOOK_URLS -FooterText 'Unraid AniLoader' -ContinuationPrefix '📺') {
            Write-Host '[OK] Discord Benachrichtigung gesendet!'
        }
    } else {
        Write-Host '[INFO] Keine neuen Episoden - keine Discord-Benachrichtigung.'
    }

    Write-Host ''
    Write-Host "Script abgeschlossen: $(Get-Date)"
} catch {
    Write-Host "[FEHLER] $($_.Exception.Message)"
    exit 1
}