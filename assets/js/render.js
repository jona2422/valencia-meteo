/* Dibujado de tablas, avisos y graficos. Sin librerias: SVG a mano. */
const R = (() => {
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  const NIVEL = ['sin aviso', 'amarillo', 'naranja', 'rojo'];
  const ICONO = { Rain: '🌧️', Thunderstorm: '⛈️', Flood: '🌊', Wind: '💨',
                  coastalevent: '🌊', 'snow-ice': '❄️', Fog: '🌫️',
                  'high-temperature': '🌡️', 'low-temperature': '🥶' };

  const hora = iso => {
    if (!iso) return '';
    const d = new Date(iso);
    return new Intl.DateTimeFormat('es-ES', {
      hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Madrid', hour12: false }).format(d);
  };
  const diaHora = iso => {
    if (!iso) return '';
    return new Intl.DateTimeFormat('es-ES', {
      day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit',
      timeZone: 'Europe/Madrid', hour12: false }).format(new Date(iso));
  };
  const desde = iso => {
    const t = Date.parse(iso);
    if (!t) return '';
    const m = Math.round((Date.now() - t) / 6e4);
    if (m < 60) return `hace ${Math.max(1, m)} min`;
    const h = Math.round(m / 60);
    if (h < 24) return `hace ${h} h`;
    const d = Math.round(h / 24);
    return d === 1 ? 'ayer' : `hace ${d} días`;
  };
  const n1 = v => (v === null || v === undefined) ? '–' : (Math.round(v * 10) / 10).toString();

  return {
    esc, hora, diaHora, desde, n1, NIVEL,

    kpis(el, m, sea, mods) {
      const r = m.resumen;
      const cls = n => ['', 'w', 'o', 'r'][n] || '';
      const disp = mods && mods.dispersion;
      el.innerHTML = `
        <div class="kpi ${cls(r.nivel)}"><div class="l">Nivel general</div>
          <div class="v">${esc(r.nivel_texto)}</div>
          <div class="s">${r.avisos_activos} aviso${r.avisos_activos === 1 ? '' : 's'} activo${r.avisos_activos === 1 ? '' : 's'} de AEMET</div></div>
        <div class="kpi a"><div class="l">Lloviendo</div>
          <div class="v">${r.lloviendo}<s>/${r.puntos}</s></div>
          <div class="s">puntos con precipitación ahora</div></div>
        <div class="kpi a"><div class="l">Máximo 12 h</div>
          <div class="v">${n1(r.max_acum_12h)}<s>mm</s></div>
          <div class="s">${r.zona_mas_expuesta ? esc(r.zona_mas_expuesta) : 'sin acumulados'}</div></div>
        <div class="kpi ${r.max_prev_24h >= 40 ? 'o' : 'a'}"><div class="l">Previsto 24 h</div>
          <div class="v">${n1(r.max_prev_24h)}<s>mm</s></div>
          <div class="s">máximo entre los 28 puntos</div></div>
        <div class="kpi ${r.max_cape >= 1500 ? 'r' : r.max_cape >= 800 ? 'o' : ''}"><div class="l">Inestabilidad</div>
          <div class="v">${Math.round(r.max_cape)}<s>J/kg</s></div>
          <div class="s">${r.max_cape >= 1500 ? 'muy alta · tormentas fuertes'
                        : r.max_cape >= 800 ? 'moderada · chubascos' : 'baja'}</div></div>
        <div class="kpi ${sea.sst >= 26 ? 'o' : 'a'}"><div class="l">Mar</div>
          <div class="v">${n1(sea.sst)}<s>°C</s></div>
          <div class="s">${sea.sst >= 26 ? 'muy cálido · combustible de DANA' : 'temperatura del agua'}</div></div>
        <div class="kpi ${disp >= 30 ? 'r' : disp >= 15 ? 'o' : ''}"><div class="l">Acuerdo entre modelos</div>
          <div class="v">${disp >= 30 ? 'bajo' : disp >= 15 ? 'medio' : 'alto'}</div>
          <div class="s">se separan ${n1(disp)} mm en 48 h</div></div>
        <div class="kpi ${r.levante ? 'o' : ''}"><div class="l">Flujo de levante</div>
          <div class="v">${r.levante}<s>/${r.puntos}</s></div>
          <div class="s">${r.levante ? 'aire húmedo entrando del mar' : 'sin componente de levante'}</div></div>`;
    },

    tabla(el, puntos, todos) {
      const lista = todos ? puntos : puntos.slice(0, 12);
      if (!lista.length) { el.innerHTML = '<div class="empty">Sin datos.</div>'; return; }
      const max = Math.max(1, ...lista.map(p => Math.max(p.acum_12h || 0, p.prev_24h || 0)));
      el.innerHTML = `<table class="tabla">
        <thead><tr>
          <th>Punto</th><th>Estado</th>
          <th class="num">Ahora</th><th class="num">12 h</th><th class="num">Próx. 24 h</th>
          ${todos ? '<th class="num">Pico</th><th class="num">CAPE</th>' : ''}
        </tr></thead><tbody>
        ${lista.map(p => `<tr>
          <td class="nom">${esc(p.nombre)}<span class="sub">${esc(p.comarca)} · ${esc(p.cuenca)}</span></td>
          <td><span class="pill n${p.nivel}">${esc(NIVEL[p.nivel])}</span>
            <span class="sub">${p.nivel_lluvia > p.nivel_oficial ? 'por lluvia medida'
              : p.nivel_oficial ? 'aviso AEMET' : 'sin aviso'}${p.levante ? ' · levante' : ''}</span></td>
          <td class="num">${n1(p.lluvia_ahora)}<span class="sub">${esc(p.intensidad)}</span></td>
          <td class="num">${n1(p.acum_12h)}
            <div class="mini"><i style="width:${((p.acum_12h || 0) / max * 100).toFixed(1)}%"></i></div></td>
          <td class="num">${n1(p.prev_24h)}
            <div class="mini"><i style="width:${((p.prev_24h || 0) / max * 100).toFixed(1)}%;background:var(--n1)"></i></div></td>
          ${todos ? `<td class="num">${n1(p.pico_mmh)}</td><td class="num">${p.cape ?? '–'}</td>` : ''}
        </tr>`).join('')}</tbody></table>`;
    },

    avisos(el, items, limite) {
      const lista = limite ? items.slice(0, limite) : items;
      if (!lista.length) {
        el.innerHTML = `<div class="empty">Ningún aviso de AEMET en vigor para la Comunitat.<br>
          <span style="color:var(--n0)">Situación tranquila.</span></div>`;
        return;
      }
      el.innerHTML = lista.map(a => `
        <div class="aviso n${a.nivel}">
          <div class="ico">${ICONO[a.tipo] || '⚠️'}</div>
          <div class="c">
            <b>${esc(a.evento || a.tipo)}</b>
            <p>${esc(a.zonas_nombre.join(' · '))}</p>
            ${a.desc ? `<p style="color:var(--tx3)">${esc(a.desc.slice(0, 150))}</p>` : ''}
            <time>${esc(diaHora(a.inicio))} → ${esc(diaHora(a.fin))}</time>
          </div>
          <div class="est ${a.activo ? 'on' : 'off'}">${a.activo ? 'en vigor' : 'previsto'}</div>
        </div>`).join('');
    },

    rios(el, items) {
      if (!items.length) { el.innerHTML = '<div class="empty">Sin datos de caudal.</div>'; return; }
      const orden = [...items].sort((a, b) =>
        (b.nivel - a.nivel) || ((b.pico || 0) - (a.pico || 0)));
      el.innerHTML = `<table class="tabla">
        <thead><tr><th>Río · punto</th><th class="num">Caudal hoy</th>
          <th class="num">Pico 7 días</th><th class="num">Crecida</th><th>Tendencia</th></tr></thead>
        <tbody>${orden.map(r => `<tr>
            <td class="nom">${esc(r.nombre)}${r.significativo ? ''
              : '<span class="sub">caudal muy bajo</span>'}</td>
            <td class="num">${n1(r.actual)}<span class="sub">m³/s</span></td>
            <td class="num">${n1(r.pico)}<span class="sub">m³/s</span></td>
            <td class="num">${r.significativo
              ? `<span class="pill n${r.nivel}">×${n1(r.factor)}</span>`
              : '<span class="sub" style="text-align:right;display:block">sin relevancia</span>'}</td>
            <td style="width:150px">${this.sparkline(r.caudal, 'var(--rio)', 140, 30)}</td>
          </tr>`).join('')}</tbody></table>`;
    },

    sparkline(vals, color, w = 140, h = 30) {
      const v = vals.filter(x => x !== null && x !== undefined);
      if (v.length < 2) return '<span style="color:var(--tx3)">–</span>';
      const max = Math.max(...v), min = Math.min(...v), span = Math.max(1e-6, max - min);
      const pts = v.map((x, i) => `${(i / (v.length - 1) * w).toFixed(1)},${(h - (x - min) / span * (h - 3) - 1.5).toFixed(1)}`);
      return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}">
        <polyline points="${pts.join(' ')}" fill="none" stroke="${color}" stroke-width="1.7"
          stroke-linejoin="round" stroke-linecap="round"/></svg>`;
    },

    // Barras horarias de lluvia por modelo: donde se separan esta la incertidumbre.
    modelos(el, m) {
      const series = m.series || {}, nombres = m.nombres || {};
      const claves = Object.keys(series);
      if (!claves.length) { el.innerHTML = '<div class="empty">Sin datos de modelos.</div>'; return; }
      const COL = ['#38bdf8', '#a78bfa', '#fbbf24', '#f472b6'];
      const H = 170, W = 1000, N = 48, M = 26;   // M = margen lateral
      const max = Math.max(1, ...claves.flatMap(k => series[k].slice(0, N).map(v => v || 0)));
      const paso = (W - M * 2) / N;

      const capas = claves.map((k, ci) => {
        const pts = series[k].slice(0, N).map((v, i) =>
          `${(M + i * paso + paso / 2).toFixed(1)},${(H - 20 - (v || 0) / max * (H - 44)).toFixed(1)}`);
        return `<polyline points="${pts.join(' ')}" fill="none" stroke="${COL[ci % 4]}"
                  stroke-width="2" stroke-linejoin="round"/>`;
      }).join('');

      const horas = (m.horas || []).slice(0, N);
      const ejes = horas.map((t, i) => i % 6 === 0
        ? `<text x="${(M + i * paso + paso / 2).toFixed(1)}" y="${H - 5}" fill="#5d6b83"
             font-size="9" font-family="ui-monospace,monospace" text-anchor="middle">${t.slice(11, 16)}</text>` : '').join('');

      const tot = m.totales_48h || {};
      const vals = Object.values(tot);
      el.innerHTML = `
        <div class="kpis" style="margin-bottom:14px">
          ${claves.map((k, i) => `<div class="kpi"><div class="l">${esc(nombres[k] || k)}</div>
            <div class="v" style="color:${COL[i % 4]}">${n1(tot[k])}<s>mm</s></div>
            <div class="s">acumulado en 48 h</div></div>`).join('')}
        </div>
        <svg class="chart" viewBox="0 0 ${W} ${H}">
          <line x1="${M}" y1="${H - 20}" x2="${W - M}" y2="${H - 20}" stroke="#232c3d"/>
          ${capas}${ejes}
        </svg>
        <div class="chart-l">${claves.map((k, i) =>
          `<span><i style="background:${COL[i % 4]}"></i>${esc(nombres[k] || k)}</span>`).join('')}
          <span style="margin-left:auto">mm/h · próximas 48 h en València</span></div>
        <div class="nota">
          ${vals.length > 1 && (Math.max(...vals) - Math.min(...vals)) >= 25
            ? `<b>Los modelos no se ponen de acuerdo.</b> Van de ${n1(Math.min(...vals))} a
               ${n1(Math.max(...vals))} mm en 48 h. En una situación así la cifra concreta no
               es fiable: lo que sí indica es potencial de lluvia fuerte y muy localizada.
               Guíate por los avisos de AEMET y por lo que ya está cayendo, no por el número.`
            : `Los modelos van bastante alineados, así que la previsión es razonablemente fiable.`}
          Ningún modelo global resuelve bien una tormenta de unos pocos kilómetros: pueden
          acertar el día y fallar el sitio por 20 km.
        </div>`;
    },

    ingredientes(el, m, sea, obs) {
      const r = m.resumen;
      const levante = obs.filter(o => o.levante).length;
      const fila = (t, v, nota, n) => `
        <div style="display:flex;gap:12px;align-items:baseline;padding:9px 0;border-bottom:1px solid rgba(35,44,61,.5)">
          <div style="flex:0 0 108px;font:700 10px/1.3 var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--tx3)">${t}</div>
          <div style="font-weight:700;font-size:14px;color:var(--n${n ?? 0})">${v}</div>
          <div style="color:var(--tx2);font-size:12px;flex:1">${nota}</div>
        </div>`;
      el.innerHTML =
        fila('Mar', `${n1(sea.sst)} °C`,
          sea.sst >= 26 ? 'Muy cálido. Evapora mucha humedad: es el combustible de las lluvias torrenciales.'
                        : 'Dentro de lo normal para la época.', sea.sst >= 26 ? 2 : 0) +
        fila('CAPE', `${Math.round(r.max_cape)} J/kg`,
          r.max_cape >= 1500 ? 'Inestabilidad muy alta. Aire listo para levantarse: tormentas de desarrollo rápido.'
          : r.max_cape >= 800 ? 'Inestabilidad moderada. Chubascos y tormentas posibles.'
                              : 'Atmósfera estable.', r.max_cape >= 1500 ? 3 : r.max_cape >= 800 ? 2 : 0) +
        fila('Levante', `${levante} de ${obs.length}`,
          levante ? 'Viento del mar hacia la costa. Al chocar con el relieve, la lluvia se dispara.'
                  : 'Sin flujo de levante. Falta el mecanismo que dispara los episodios grandes.',
          levante > obs.length / 3 ? 2 : 0) +
        fila('Oleaje', `${n1(sea.ola)} m`,
          sea.ola >= 2 ? 'Mar alterada. Dificulta el desagüe de barrancos y ramblas al mar.'
                       : 'Mar tranquila.', sea.ola >= 2 ? 2 : 0) +
        `<div class="nota" style="margin-top:12px">Una DANA necesita las tres cosas a la vez:
          <b>mar caliente</b> que aporte humedad, <b>inestabilidad</b> que la haga subir y
          <b>viento del mar</b> que la empuje contra las montañas. Cuando coinciden y además
          la tormenta se queda quieta sobre la misma cuenca, es cuando se desborda un barranco.</div>`;
    },

    news(el, items) {
      if (!items.length) { el.innerHTML = '<div class="empty">Sin noticias relevantes ahora mismo.</div>'; return; }
      el.innerHTML = items.map(n => `
        <a class="nw" href="${esc(n.link)}" target="_blank" rel="noopener">
          ${n.image ? `<img src="${esc(n.image)}" alt="" loading="lazy">` : ''}
          <div class="b"><div class="s">${esc(n.source)}</div>
            <h4>${esc(n.title)}</h4><time>${esc(desde(n.date))}</time></div>
        </a>`).join('');
    },
  };
})();
