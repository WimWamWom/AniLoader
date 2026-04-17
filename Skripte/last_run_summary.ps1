Write-Host '=========================================' -ForegroundColor Cyan
Write-Host 'AniLoader - LastRun Auswertung' -ForegroundColor Cyan
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

# Alternativ: Lokale Datei (wird nur verwendet wenn API_ENDPOINT leer ist)
$LASTRUN_FILE = '/mnt/user/Docker/AniLoader/data/last_run.txt'

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

function Get-LastRunContent {
    if (-not [string]::IsNullOrWhiteSpace($API_ENDPOINT)) {
        Write-Host "Lade Logs von API: $API_ENDPOINT/last_run"
        $response = Invoke-AniLoaderApi -Method GET -Uri "$API_ENDPOINT/last_run"
        return [string]$response.log
    }

    if (-not (Test-Path -LiteralPath $LASTRUN_FILE)) {
        throw "Datei nicht gefunden: $LASTRUN_FILE"
    }

    Write-Host "Lese Datei: $LASTRUN_FILE"
    return Get-Content -LiteralPath $LASTRUN_FILE -Raw -Encoding UTF8
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
    param(
        [string]$LogContent,
        [bool]$GermanOnly = $false
    )

    $episodes = New-Object System.Collections.Generic.List[string]
    $currentUrl = ''
    $currentIsGerman = $false

    foreach ($line in ($LogContent -split "`r?`n")) {
        if ($GermanOnly) {
            if ($line -match '\[DOWNLOAD\].*Versuche.*German.*Dub.*->\s*(https?://\S+)') {
                $currentUrl = $Matches[1]
                $currentIsGerman = $true
                continue
            }

            if ($line -match '\[VERIFY\].*wurde.*erfolgreich.*erstellt' -and $currentUrl -and $currentIsGerman) {
                $parsedEpisode = Convert-UrlToEpisodeLabel -Url $currentUrl
                if ($parsedEpisode) {
                    [void]$episodes.Add($parsedEpisode)
                }
                $currentUrl = ''
                $currentIsGerman = $false
            }
        } else {
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

function Get-DetectedMode {
    param([string]$LogContent)

    if ($LogContent -match 'Modus:\s*german' -or $LogContent -match 'Download-Modus:\s*german') { return 'german' }
    if ($LogContent -match 'Modus:\s*new' -or $LogContent -match 'Download-Modus:\s*new') { return 'new' }
    if ($LogContent -match 'Modus:\s*default' -or $LogContent -match 'Download-Modus:\s*default') { return 'default' }
    if ($LogContent -match 'Modus:\s*check' -or $LogContent -match 'Download-Modus:\s*check') { return 'check' }
    return 'unknown'
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
        [string[]]$Episodes,
        [string]$ContinuationPrefix
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
            $description = if ($embedIndex -eq 1) { $Summary } else { "$ContinuationPrefix **Fortsetzung (Teil $embedIndex)...**" }
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
        $description = if ($embedIndex -eq 1) { $Summary } else { "$ContinuationPrefix **Fortsetzung (Teil $embedIndex)...**" }
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

function Send-DiscordPayload {
    param([object]$Payload)

    if (-not $DISCORD_WEBHOOK_URLS -or $DISCORD_WEBHOOK_URLS.Count -eq 0) {
        return $true
    }

    $json = $Payload | ConvertTo-Json -Depth 15 -Compress
    $failed = 0

    foreach ($webhookUrl in $DISCORD_WEBHOOK_URLS) {
        if ([string]::IsNullOrWhiteSpace($webhookUrl)) {
            continue
        }

        try {
            $response = Invoke-WebRequest -Uri $webhookUrl -Method POST -ContentType 'application/json' -Body $json -UseBasicParsing -ErrorAction Stop
            if ($response.StatusCode -ne 200 -and $response.StatusCode -ne 204) {
                $failed += 1
                Write-Host "[FEHLER] Discord Webhook fehlgeschlagen (HTTP $($response.StatusCode))"
            }
        } catch {
            $failed += 1
            $statusCode = $_.Exception.Response.StatusCode.value__
            if ($statusCode) {
                Write-Host "[FEHLER] Discord Webhook fehlgeschlagen (HTTP $statusCode)"
            } else {
                Write-Host "[FEHLER] Discord Webhook fehlgeschlagen: $($_.Exception.Message)"
            }
        }
    }

    return ($failed -eq 0)
}

function Send-DiscordMessage {
    param(
        [string]$Title,
        [string]$Message,
        [int]$Color
    )

    return (Send-DiscordPayload -Payload @{
        embeds = @(
            @{
                title = $Title
                description = $Message
                color = $Color
                timestamp = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ss.000Z')
                footer = @{ text = 'Unraid AniLoader' }
            }
        )
    })
}

function Send-DiscordMultiEmbed {
    param(
        [string]$Title,
        [string]$Summary,
        [int]$Color,
        [string]$ErrorInfo,
        [string[]]$Episodes,
        [string]$ContinuationPrefix
    )

    return (Send-DiscordPayload -Payload @{ embeds = (New-DiscordEmbeds -Title $Title -Summary $Summary -Color $Color -ErrorInfo $ErrorInfo -Episodes $Episodes -ContinuationPrefix $ContinuationPrefix) })
}

try {
    $logContent = Get-LastRunContent

    if ([string]::IsNullOrWhiteSpace($logContent)) {
        Write-Host '[WARNUNG] Keine Logs verfügbar.'
        exit 0
    }

    Write-Host 'Werte Logs aus...'
    Write-Host ''

    $mode = Get-DetectedMode -LogContent $logContent
    Write-Host "Erkannter Modus: $mode"

    $parsedEpisodes = if ($mode -eq 'german') {
        @(Parse-DownloadedEpisodes -LogContent $logContent -GermanOnly $true)
    } else {
        @(Parse-DownloadedEpisodes -LogContent $logContent)
    }

    $errorCount = Get-LogMatchCount -LogContent $logContent -Pattern '\[ERROR\]'
    $skippedCount = Get-LogMatchCount -LogContent $logContent -Pattern '\[SKIP\]'
    $episodesCount = $parsedEpisodes.Count
    $seriesCount = Get-UniqueSeriesCount -Episodes $parsedEpisodes

    Write-Host '=== ZUSAMMENFASSUNG ==='
    if ($mode -eq 'german') {
        Write-Host "Neue deutsche Episoden gefunden: $episodesCount"
    } elseif ($mode -eq 'new') {
        Write-Host "Neue Episoden gefunden: $episodesCount"
        Write-Host "Betroffene Serien: $seriesCount"
        Write-Host "Übersprungen: $skippedCount"
    } else {
        Write-Host "Episoden heruntergeladen: $episodesCount"
        Write-Host "Betroffene Serien: $seriesCount"
        Write-Host "Übersprungen: $skippedCount"
    }
    Write-Host "Fehler: $errorCount"
    Write-Host ''

    if ($episodesCount -gt 0) {
        Write-Host 'Gefundene Episoden (gruppiert):'
        foreach ($episode in $parsedEpisodes) {
            Write-Host "  - $episode"
        }
        Write-Host ''
    }

    if ($episodesCount -gt 0) {
        $title = '📊 AniLoader - LastRun Auswertung'
        $summary = "✅ **$episodesCount neue Episode(n) gefunden!**"
        $continuationPrefix = '📊'

        if ($mode -eq 'german') {
            $title = '🇩🇪 AniLoader - Deutsche Episoden Check'
            $summary = "✅ **$episodesCount neue deutsche Episode(n) gefunden!**"
            $continuationPrefix = '🇩🇪'
        } elseif ($mode -eq 'new') {
            $title = '📺 AniLoader - Neue Episoden Check'
            $summary = "✅ **$episodesCount neue Episode(n) heruntergeladen!**`n📊 **$seriesCount Serie(n) aktualisiert**"
            $continuationPrefix = '📺'
        } elseif ($mode -eq 'default') {
            $title = '📥 AniLoader - Standard Download'
            $summary = "✅ **$episodesCount Episode(n) heruntergeladen!**`n📊 **$seriesCount Serie(n) aktualisiert**"
            $continuationPrefix = '📥'
        } elseif ($mode -eq 'check') {
            $title = '🔍 AniLoader - Integritäts-Check'
            $summary = "✅ **$episodesCount Episode(n) repariert/nachgeladen!**`n📊 **$seriesCount Serie(n) betroffen**"
            $continuationPrefix = '🔍'
        }

        $errorInfo = ''
        if ($errorCount -gt 0) {
            $errorInfo = "⚠️ $errorCount Fehler aufgetreten"
        }

        if ($parsedEpisodes.Count -gt 0) {
            if (Send-DiscordMultiEmbed -Title $title -Summary $summary -Color 3066993 -ErrorInfo $errorInfo -Episodes $parsedEpisodes -ContinuationPrefix $continuationPrefix) {
                Write-Host "[OK] Discord Benachrichtigung gesendet mit $episodesCount Episoden!"
            } else {
                Write-Host '[FEHLER] Discord Benachrichtigung konnte nicht gesendet werden!'
            }
        } else {
            $message = $summary
            if ($errorInfo) {
                $message += "`n`n$errorInfo"
            }

            if (Send-DiscordMessage -Title $title -Message $message -Color 3066993) {
                Write-Host '[OK] Discord Benachrichtigung gesendet!'
            } else {
                Write-Host '[FEHLER] Discord Benachrichtigung konnte nicht gesendet werden!'
            }
        }
    } else {
        if ($mode -eq 'german') {
            Write-Host '[INFO] Keine neuen deutschen Episoden - keine Discord-Benachrichtigung.'
        } elseif ($mode -eq 'new') {
            Write-Host '[INFO] Keine neuen Episoden - keine Discord-Benachrichtigung.'
        } else {
            Write-Host '[INFO] Keine Episoden gefunden - keine Discord-Benachrichtigung.'
        }
    }

    Write-Host ''
    Write-Host "Script abgeschlossen: $(Get-Date)"
} catch {
    Write-Host "[FEHLER] $($_.Exception.Message)"
    exit 1
}