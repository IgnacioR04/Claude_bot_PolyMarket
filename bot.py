#!/usr/bin/env python3
"""
Polymarket Paper Trading Bot
Simula 5 estrategias en paper trading y guarda resultados en data.json
Se ejecuta cada 15 minutos via GitHub Actions
"""

import json
import os
import time
import random
from datetime import datetime, timezone
import urllib.request
import urllib.error

# ── Configuración ──────────────────────────────────────────────────────────────
DATA_FILE = "docs/data.json"
CAPITAL_INICIAL = 1000.0  # USDC simulado por estrategia

ESTRATEGIAS = {
    "arb_yes_no": {
        "nombre": "Arbitraje YES+NO",
        "descripcion": "Compra YES+NO cuando suman < $0.97. Risk-free matemático.",
        "riesgo": "muy_bajo",
        "capital": CAPITAL_INICIAL,
    },
    "arb_logico": {
        "nombre": "Arbitraje Lógico",
        "descripcion": "Explota inconsistencias entre mercados correlacionados.",
        "riesgo": "bajo",
        "capital": CAPITAL_INICIAL,
    },
    "market_making": {
        "nombre": "Market Making",
        "descripcion": "Captura spread bid-ask en mercados de baja volatilidad.",
        "riesgo": "medio_bajo",
        "capital": CAPITAL_INICIAL,
    },
    "mean_reversion": {
        "nombre": "Mean Reversion 15min",
        "descripcion": "Compra caídas bruscas en mercados BTC/ETH/SOL de 15 min.",
        "riesgo": "medio",
        "capital": CAPITAL_INICIAL,
    },
    "momentum": {
        "nombre": "Momentum Chainlink",
        "descripcion": "Sigue el precio spot con ventana de 2-15s antes que el mercado.",
        "riesgo": "alto",
        "capital": CAPITAL_INICIAL,
    },
}

# ── Fetcher de Polymarket ──────────────────────────────────────────────────────

def fetch_json(url, timeout=10):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"[WARN] fetch {url}: {e}")
        return None


def get_markets():
    """Obtiene mercados activos de Polymarket Gamma API"""
    url = "https://gamma-api.polymarket.com/markets?active=true&closed=false&limit=100"
    data = fetch_json(url)
    if not data:
        return []
    # Gamma devuelve lista directa o dict con 'markets'
    if isinstance(data, list):
        return data
    return data.get("markets", [])


def get_btc_15min_markets():
    """Obtiene mercados de BTC/ETH/SOL de 15 minutos"""
    url = "https://gamma-api.polymarket.com/markets?active=true&closed=false&limit=200"
    data = fetch_json(url)
    if not data:
        return []
    markets = data if isinstance(data, list) else data.get("markets", [])
    keywords = ["btc", "eth", "sol", "bitcoin", "ethereum", "solana", "up or down", "15-minute", "15 minute"]
    result = []
    for m in markets:
        q = (m.get("question", "") or "").lower()
        if any(k in q for k in keywords):
            result.append(m)
    return result[:20]


def parse_prices(market):
    """Extrae best bid/ask de un mercado"""
    try:
        tokens = market.get("tokens", [])
        if not tokens or len(tokens) < 2:
            return None
        yes_price = float(tokens[0].get("price", 0) or 0)
        no_price = float(tokens[1].get("price", 0) or 0)
        if yes_price <= 0 or no_price <= 0:
            return None
        return {"yes": yes_price, "no": no_price, "sum": yes_price + no_price}
    except Exception:
        return None


# ── Simuladores de estrategia ─────────────────────────────────────────────────

def sim_arb_yes_no(markets, capital, historial):
    """
    Escanea mercados buscando YES+NO < 0.97.
    Simula compra de ambos lados y espera resolución.
    """
    trades = []
    profit_tick = 0.0
    oportunidades = 0

    for m in markets[:80]:
        prices = parse_prices(m)
        if not prices:
            continue
        total = prices["sum"]
        if total < 0.97 and total > 0.50:
            spread = 1.0 - total
            # Tamaño de posición: máx 5% del capital por trade
            size = min(capital * 0.05, 50.0)
            profit_estimado = size * spread
            oportunidades += 1
            trades.append({
                "mercado": m.get("question", "")[:60],
                "yes": prices["yes"],
                "no": prices["no"],
                "spread": round(spread, 4),
                "profit_estimado": round(profit_estimado, 4),
            })
            profit_tick += profit_estimado * 0.6  # factor de éxito realista

    return {
        "profit_tick": round(profit_tick, 4),
        "oportunidades": oportunidades,
        "trades_muestra": trades[:3],
    }


def sim_arb_logico(markets, capital, historial):
    """
    Detecta inconsistencias lógicas entre mercados correlacionados.
    Ej: P(A wins) > P(A in final) — imposible lógicamente.
    Usa heurística sobre mercados con términos similares.
    """
    import re
    grupos = {}
    for m in markets[:100]:
        q = (m.get("question", "") or "").lower()
        # Agrupa por palabras clave compartidas
        words = re.findall(r'\b[a-z]{4,}\b', q)
        for w in words[:3]:
            grupos.setdefault(w, []).append(m)

    oportunidades = 0
    profit_tick = 0.0
    trades = []

    for key, group in grupos.items():
        if len(group) < 2:
            continue
        prices_list = [(m, parse_prices(m)) for m in group[:5]]
        prices_list = [(m, p) for m, p in prices_list if p]
        if len(prices_list) < 2:
            continue
        # Detecta si algún par suma > 1.05 (over-priced combinado)
        for i in range(len(prices_list)):
            for j in range(i+1, len(prices_list)):
                p1 = prices_list[i][1]["yes"]
                p2 = prices_list[j][1]["yes"]
                if p1 + p2 > 1.05:
                    spread = p1 + p2 - 1.0
                    size = min(capital * 0.03, 30.0)
                    profit_estimado = size * spread * 0.5
                    oportunidades += 1
                    profit_tick += profit_estimado
                    trades.append({
                        "par": key,
                        "spread": round(spread, 4),
                        "profit_estimado": round(profit_estimado, 4),
                    })

    return {
        "profit_tick": round(min(profit_tick, capital * 0.008), 4),
        "oportunidades": oportunidades,
        "trades_muestra": trades[:3],
    }


def sim_market_making(markets, capital, historial):
    """
    Simula market making en mercados con spread > 0.03 y baja volatilidad.
    Gana el spread × volumen estimado + rewards de liquidez (0.1% anual aprox).
    """
    mercados_validos = []
    for m in markets[:100]:
        prices = parse_prices(m)
        if not prices:
            continue
        spread = abs(prices["yes"] - prices["no"])
        yes = prices["yes"]
        # Baja volatilidad: precio estable entre 0.20-0.80, spread razonable
        if 0.03 < spread < 0.25 and 0.15 < yes < 0.85:
            vol_estimado = float(m.get("volume24hr", 0) or 0)
            mercados_validos.append({
                "mercado": m.get("question", "")[:60],
                "spread": spread,
                "yes": yes,
                "volumen_24h": vol_estimado,
            })

    mercados_validos.sort(key=lambda x: x["spread"] * min(x["volumen_24h"], 10000), reverse=True)

    profit_tick = 0.0
    for mv in mercados_validos[:10]:
        # Ganancia = spread × fracción del volumen que capturamos × capital asignado
        fraccion_volumen = 0.02  # capturamos ~2% del volumen como MM
        capital_asignado = capital * 0.10
        profit_tick += mv["spread"] * fraccion_volumen * capital_asignado

    # Rewards de liquidez Polymarket (~4% anual en posiciones elegibles)
    rewards_tick = capital * (0.04 / (365 * 96))  # cada 15 min

    return {
        "profit_tick": round(profit_tick + rewards_tick, 4),
        "mercados_activos": len(mercados_validos[:10]),
        "trades_muestra": mercados_validos[:3],
    }


def sim_mean_reversion(btc_markets, capital, historial):
    """
    En mercados de 15 min, si el precio cayó bruscamente respecto
    a la media histórica reciente, apuesta a reversión.
    """
    profit_tick = 0.0
    trades = []
    señales = 0

    prev_prices = {}
    if historial:
        ultimo = historial[-1] if historial else {}
        prev_prices = ultimo.get("estrategias", {}).get("mean_reversion", {}).get("precios_snapshot", {})

    precios_snapshot = {}

    for m in btc_markets[:30]:
        prices = parse_prices(m)
        if not prices:
            continue
        mid = (prices["yes"] + prices["no"]) / 2
        mid_id = m.get("id", m.get("question", "")[:20])
        precios_snapshot[mid_id] = mid

        prev = prev_prices.get(mid_id)
        if prev and prev > 0:
            cambio = (mid - prev) / prev
            if cambio < -0.15:  # caída > 15%: señal de reversión
                size = min(capital * 0.04, 40.0)
                profit_estimado = size * abs(cambio) * 0.4
                profit_tick += profit_estimado
                señales += 1
                trades.append({
                    "mercado": m.get("question", "")[:60],
                    "caida": round(cambio * 100, 2),
                    "profit_estimado": round(profit_estimado, 4),
                })

    return {
        "profit_tick": round(profit_tick, 4),
        "señales": señales,
        "precios_snapshot": precios_snapshot,
        "trades_muestra": trades[:3],
    }


def sim_momentum(btc_markets, capital, historial):
    """
    Estrategia más agresiva: sigue momentum de precio spot simulado.
    En producción real usaría Chainlink feed; aquí simula con
    movimientos de precio entre ticks.
    """
    profit_tick = 0.0
    trades = []

    prev_prices = {}
    if historial:
        ultimo = historial[-1] if historial else {}
        prev_prices = ultimo.get("estrategias", {}).get("momentum", {}).get("precios_snapshot", {})

    precios_snapshot = {}

    for m in btc_markets[:20]:
        prices = parse_prices(m)
        if not prices:
            continue
        mid = (prices["yes"] + prices["no"]) / 2
        mid_id = m.get("id", m.get("question", "")[:20])
        precios_snapshot[mid_id] = mid

        prev = prev_prices.get(mid_id)
        if prev and prev > 0:
            cambio = (mid - prev) / prev
            # Sigue movimiento fuerte (> 8%) antes de que el mercado lo absorba
            if abs(cambio) > 0.08:
                size = min(capital * 0.08, 80.0)
                # Momentum: ganamos si acertamos la dirección (60% histórico)
                profit_esperado = size * abs(cambio) * 0.6
                perdida_esperada = size * abs(cambio) * 0.4
                profit_neto = profit_esperado - perdida_esperada
                profit_tick += profit_neto
                trades.append({
                    "mercado": m.get("question", "")[:60],
                    "movimiento": round(cambio * 100, 2),
                    "profit_neto": round(profit_neto, 4),
                })

    return {
        "profit_tick": round(profit_tick, 4),
        "señales": len(trades),
        "precios_snapshot": precios_snapshot,
        "trades_muestra": trades[:3],
    }


# ── Carga / Guarda estado ─────────────────────────────────────────────────────

def cargar_estado():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {
        "capital": {k: CAPITAL_INICIAL for k in ESTRATEGIAS},
        "historial": [],
        "ultima_actualizacion": None,
        "stats": {k: {"trades": 0, "profit_total": 0.0, "mejor_tick": 0.0, "peor_tick": 0.0} for k in ESTRATEGIAS},
    }


def guardar_estado(estado):
    os.makedirs("docs", exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(estado, f, indent=2, default=str)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"[{datetime.now(timezone.utc).isoformat()}] Iniciando tick de paper trading...")

    estado = cargar_estado()
    markets = get_markets()
    btc_markets = get_btc_15min_markets()

    print(f"  Mercados cargados: {len(markets)} generales, {len(btc_markets)} BTC/15min")

    historial = estado.get("historial", [])
    capital = estado.get("capital", {k: CAPITAL_INICIAL for k in ESTRATEGIAS})

    tick = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mercados_disponibles": len(markets),
        "estrategias": {},
    }

    # Simula cada estrategia
    sims = {
        "arb_yes_no":    sim_arb_yes_no(markets, capital.get("arb_yes_no", CAPITAL_INICIAL), historial),
        "arb_logico":    sim_arb_logico(markets, capital.get("arb_logico", CAPITAL_INICIAL), historial),
        "market_making": sim_market_making(markets, capital.get("market_making", CAPITAL_INICIAL), historial),
        "mean_reversion":sim_mean_reversion(btc_markets, capital.get("mean_reversion", CAPITAL_INICIAL), historial),
        "momentum":      sim_momentum(btc_markets, capital.get("momentum", CAPITAL_INICIAL), historial),
    }

    for key, sim in sims.items():
        profit = sim.get("profit_tick", 0.0)
        capital[key] = capital.get(key, CAPITAL_INICIAL) + profit

        stats = estado.get("stats", {}).get(key, {"trades": 0, "profit_total": 0.0, "mejor_tick": 0.0, "peor_tick": 0.0})
        stats["trades"] += 1
        stats["profit_total"] = round(stats["profit_total"] + profit, 4)
        if profit > stats.get("mejor_tick", 0):
            stats["mejor_tick"] = round(profit, 4)
        if profit < stats.get("peor_tick", 0):
            stats["peor_tick"] = round(profit, 4)
        estado.setdefault("stats", {})[key] = stats

        tick["estrategias"][key] = {
            "profit_tick": profit,
            "capital_actual": round(capital[key], 4),
            "retorno_pct": round((capital[key] - CAPITAL_INICIAL) / CAPITAL_INICIAL * 100, 4),
            **{k: v for k, v in sim.items() if k != "precios_snapshot"},
        }

        print(f"  {ESTRATEGIAS[key]['nombre']}: profit_tick={profit:.4f} | capital={capital[key]:.2f}")

    historial.append(tick)
    # Guarda máx 2000 ticks (~3 semanas a 15 min)
    if len(historial) > 2000:
        historial = historial[-2000:]

    estado["historial"] = historial
    estado["capital"] = capital
    estado["ultima_actualizacion"] = tick["timestamp"]

    guardar_estado(estado)
    print(f"  Estado guardado en {DATA_FILE}")
    print("  Tick completado.")


if __name__ == "__main__":
    main()
