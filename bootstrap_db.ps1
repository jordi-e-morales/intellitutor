param(
    [string]$ContainerName = "pg",
    [string]$PgSuperUser = "postgres",
    [string]$DbName = "tutor_db",
    [string]$DbUser = "tutor_user",
    [string]$DbPass = "tutor_pass"
)

$ErrorActionPreference = "Stop"

function Write-Info($msg) { Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Write-Warn($msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Err($msg)  { Write-Host "[ERROR] $msg" -ForegroundColor Red }

# Check docker is available
try { docker version | Out-Null } catch { Write-Err "Docker is not available in PATH."; exit 1 }

# Check container exists
$container = docker ps -a --format '{{.Names}}' | Where-Object { $_ -eq $ContainerName }
if (-not $container) {
  Write-Err "Container '$ContainerName' not found. Start your postgres container (e.g.,: docker run -d --name pg -e POSTGRES_PASSWORD=postgres -p 5432:5432 postgres:15)"
  exit 1
}

# Check container is running
$running = docker ps --format '{{.Names}}' | Where-Object { $_ -eq $ContainerName }
if (-not $running) {
  Write-Warn "Container '$ContainerName' is not running. Attempting to start..."
  docker start $ContainerName | Out-Null
}

Write-Info "Bootstrapping database and user inside container '$ContainerName'..."

# Idempotent user creation
$createUser = @"
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '$DbUser') THEN
    CREATE ROLE $DbUser LOGIN PASSWORD '$DbPass';
  END IF;
END$$;
"@

docker exec -i $ContainerName psql -U $PgSuperUser -v ON_ERROR_STOP=1 -c "$createUser" | Out-Null

# Idempotent database creation
$createDb = @"
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_database WHERE datname = '$DbName') THEN
    CREATE DATABASE $DbName OWNER $DbUser;
  END IF;
END$$;
"@

docker exec -i $ContainerName psql -U $PgSuperUser -v ON_ERROR_STOP=1 -c "$createDb" | Out-Null

# Grants (safe if repeated)
$grant = "GRANT ALL PRIVILEGES ON DATABASE \"$DbName\" TO $DbUser;"

docker exec -i $ContainerName psql -U $PgSuperUser -v ON_ERROR_STOP=1 -d postgres -c "$grant" | Out-Null

Write-Info "Bootstrap complete. Database '$DbName' and user '$DbUser' are ready."
