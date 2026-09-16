/* Mapa SVG de la Comunitat Valenciana, dibujado a mano desde el GeoJSON que vive
   en el repo (nada de CDN). Proyeccion equirectangular corregida por latitud:
   a 39 N un grado de longitud mide ~0.78 de uno de latitud, y sin esa correccion
   la Comunitat sale estirada a lo ancho. */
const Mapa = (() => {
  const W = 620, H = 720, PAD = 14;
  let geo = null, proj = null;

  async function cargar() {
    if (geo) return geo;
    const r = await fetch('assets/geo/cv.geojson');
    geo = await r.json();
    return geo;
  }

  function calcularProyeccion(features) {
    let x0 = 180, x1 = -180, y0 = 90, y1 = -90;
    const visit = c => {
      if (typeof c[0] === 'number') {
        x0 = Math.min(x0, c[0]); x1 = Math.max(x1, c[0]);
        y0 = Math.min(y0, c[1]); y1 = Math.max(y1, c[1]);
      } else c.forEach(visit);
    };
    features.forEach(f => visit(f.geometry.coordinates));

    const kx = Math.cos((y0 + y1) / 2 * Math.PI / 180);   // correccion de longitud
    const anchoGeo = (x1 - x0) * kx, altoGeo = y1 - y0;
    const esc = Math.min((W - PAD * 2) / anchoGeo, (H - PAD * 2) / altoGeo);
    const offX = (W - anchoGeo * esc) / 2, offY = (H - altoGeo * esc) / 2;

    return (lon, lat) => [
      offX + (lon - x0) * kx * esc,
      offY + (y1 - lat) * esc,          // la latitud crece hacia arriba, la Y hacia abajo
    ];
  }

  const path = (coords, p) => {
    const anillo = r => 'M' + r.map(c => p(c[0], c[1]).map(v => v.toFixed(1)).join(',')).join('L') + 'Z';
    return (typeof coords[0][0][0] === 'number' ? [coords] : coords)
      .map(poly => poly.map(anillo).join('')).join('');
  };

  return {
    proyectar: (lon, lat) => proj ? proj(lon, lat) : [0, 0],
    ancho: W, alto: H,

    async dibujar(el, puntos, onClick) {
      const g = await cargar();
      if (!proj) proj = calcularProyeccion(g.features);

      const tierra = g.features.map(f =>
        `<path class="prov" d="${path(f.geometry.coordinates, proj)}"/>`).join('');

      // Escala de radio por raiz: sin ella un punto con 60 mm aplasta a todos los demas.
      const maxAcum = Math.max(8, ...puntos.map(p => p.acum_12h || 0));
      const marcas = puntos.map(p => {
        const [x, y] = proj(p.lon, p.lat);
        const r = 4 + Math.sqrt((p.acum_12h || 0) / maxAcum) * 15;
        const c = `var(--n${p.nivel})`;
        const lluvia = (p.lluvia_ahora || 0) >= 0.1;
        return `<g class="pt" data-id="${p.id}" transform="translate(${x.toFixed(1)},${y.toFixed(1)})">
            ${lluvia ? `<circle r="${(r + 5).toFixed(1)}" fill="${c}" opacity=".16"/>` : ''}
            <circle class="core" r="${r.toFixed(1)}" fill="${c}" opacity=".62" stroke="${c}"/>
            ${p.prio === 1 ? `<circle r="2" fill="#fff" opacity=".85"/>` : ''}
            <title>${p.nombre} · ${p.comarca}
${p.acum_12h} mm en 12 h · ahora ${p.lluvia_ahora ?? 0} mm/h
Próximas 24 h: ${p.prev_24h} mm</title>
          </g>`;
      }).join('');

      el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Mapa de la Comunitat Valenciana">
        ${tierra}${marcas}</svg>`;

      if (onClick) el.querySelectorAll('.pt').forEach(n =>
        n.addEventListener('click', () => onClick(n.dataset.id)));
    },
  };
})();
