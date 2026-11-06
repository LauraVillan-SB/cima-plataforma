<#
.SYNOPSIS
    Mergea automaticamente los Pull Requests ya APROBADOS que apuntan a develop.

.DESCRIPTION
    Recorre los PRs abiertos del repositorio con base develop y mergea solo
    aquellos que cumplen TODAS estas condiciones de seguridad:
      - reviewDecision == APPROVED  (el CODEOWNER ya aprobo; respeta CODEOWNERS)
      - mergeable      == MERGEABLE (sin conflictos)
      - mergeStateStatus distinto de BLOCKED/DIRTY/BEHIND

    Para cada PR que califica hace un merge squash y borra la rama remota.
    Es NO destructivo: si un PR no esta aprobado o tiene conflictos, lo deja
    intacto y lo reporta. Nunca fuerza, nunca saltea revisiones.

    Requiere la CLI gh autenticada. Pensado para correr desde un hook
    SessionStart o a mano:  powershell -File .kiro/scripts/merge-prs-aprobados.ps1

    Nota: sin caracteres no-ASCII a proposito, porque Windows PowerShell 5.1
    lee los .ps1 con el codepage ANSI del sistema y los acentos romperian el
    parser.

.NOTES
    No modifica configuracion de git. No usa --admin ni bypass de reglas.
#>

$ErrorActionPreference = "Stop"

# Solo consideramos PRs cuya base sea develop (flujo del proyecto: nunca a main).
$baseBranch = "develop"

# gh disponible?
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Host "[merge-prs] gh CLI no esta instalada; nada que hacer." -ForegroundColor Yellow
    return
}

try {
    $prsJson = gh pr list --state open --base $baseBranch `
        --json number,title,reviewDecision,mergeable,mergeStateStatus,headRefName 2>$null
} catch {
    Write-Host "[merge-prs] No se pudo consultar los PRs (sin red o sin auth). Se omite." -ForegroundColor Yellow
    return
}

if ([string]::IsNullOrWhiteSpace($prsJson)) {
    Write-Host "[merge-prs] No hay PRs abiertos hacia $baseBranch." -ForegroundColor Green
    return
}

$prs = $prsJson | ConvertFrom-Json
if ($prs.Count -eq 0) {
    Write-Host "[merge-prs] No hay PRs abiertos hacia $baseBranch." -ForegroundColor Green
    return
}

$mergeados = 0
foreach ($pr in $prs) {
    $id = $pr.number
    $titulo = $pr.title
    $aprobado = ($pr.reviewDecision -eq "APPROVED")
    $sinConflicto = ($pr.mergeable -eq "MERGEABLE")
    $estadoOk = ($pr.mergeStateStatus -notin @("BLOCKED", "DIRTY", "BEHIND"))

    if ($aprobado -and $sinConflicto -and $estadoOk) {
        Write-Host "[merge-prs] #$id aprobado y mergeable: mergeando (squash)..." -ForegroundColor Cyan
        try {
            gh pr merge $id --squash --delete-branch 2>&1 | Out-Host
            $mergeados = $mergeados + 1
            Write-Host "[merge-prs] #$id mergeado y rama borrada." -ForegroundColor Green
        } catch {
            $msg = $_.Exception.Message
            Write-Host "[merge-prs] #$id fallo al mergear: $msg" -ForegroundColor Red
        }
    } else {
        $motivos = @()
        if (-not $aprobado)     { $motivos += "no aprobado ($($pr.reviewDecision))" }
        if (-not $sinConflicto) { $motivos += "no mergeable ($($pr.mergeable))" }
        if (-not $estadoOk)     { $motivos += "estado $($pr.mergeStateStatus)" }
        $detalle = $motivos -join ", "
        Write-Host "[merge-prs] #$id en espera: $detalle - '$titulo'" -ForegroundColor DarkGray
    }
}

Write-Host "[merge-prs] Listo. PRs mergeados en esta pasada: $mergeados" -ForegroundColor Green
