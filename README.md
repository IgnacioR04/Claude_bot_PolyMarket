# Polymarket Paper Trading Bot

Dashboard de paper trading para Polymarket. Simula 5 estrategias, actualiza cada 15 min via GitHub Actions y se sirve como página web pública en GitHub Pages.

## Estrategias simuladas

| Estrategia | Riesgo | Descripción |
|---|---|---|
| Arbitraje YES+NO | Muy bajo | Compra ambos lados cuando suman < $0.97 |
| Arbitraje Lógico | Bajo | Inconsistencias entre mercados correlacionados |
| Market Making | Medio-bajo | Captura spread + rewards de liquidez |
| Mean Reversion 15min | Medio | Reversión tras caídas bruscas en BTC/ETH/SOL |
| Momentum Chainlink | Alto | Sigue precio spot antes que el mercado |

## Setup (5 minutos)

### 1. Fork o crea el repo

Crea un repositorio nuevo en GitHub y sube estos archivos manteniendo la estructura:

```
tu-repo/
├── bot.py
├── docs/
│   ├── index.html
│   └── data.json        ← se crea automáticamente
└── .github/
    └── workflows/
        └── run_bot.yml
```

### 2. Activa GitHub Pages

1. Ve a **Settings** → **Pages**
2. Source: **Deploy from a branch**
3. Branch: `main` / folder: `/docs`
4. Guarda. En ~1 minuto tendrás URL pública: `https://TU_USUARIO.github.io/TU_REPO`

### 3. Activa GitHub Actions

1. Ve a la pestaña **Actions** de tu repo
2. Si aparece un aviso de "Workflows disabled", haz clic en **Enable**
3. Ejecuta el workflow manualmente la primera vez: **Actions → Polymarket Paper Trading Bot → Run workflow**

### 4. Verifica permisos

En **Settings → Actions → General → Workflow permissions**, asegúrate de que está en **Read and write permissions**.

## El dashboard

Accesible desde móvil en: `https://TU_USUARIO.github.io/TU_REPO`

- Se actualiza automáticamente cada 60 segundos en el navegador
- Los datos se refrescan cada 15 minutos via GitHub Actions
- Muestra PnL acumulado, capital por estrategia, mini-gráficas y feed de señales

## Notas

- Todo es **paper trading** — ninguna transacción real
- Los datos vienen de la API pública de Polymarket (sin autenticación)
- `data.json` crece ~1KB por tick; tras 2000 ticks (~3 semanas) se auto-trunca
