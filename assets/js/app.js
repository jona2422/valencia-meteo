/* Carga los JSON del robot, pinta las vistas y se refresca solo.
   En una emergencia nadie recarga a mano: la pagina se actualiza cada 5 minutos. */
(() => {
  const $ = s => document.querySelector(s);
  const VISTAS = ['ahora', 'avisos', 'zonas', 'rios', 'modelos', 'noticias'];
  const D = {};
  const deHash = () => {
    const h = location.hash.replace('#', '');
    return VISTAS.includes(h) ? h : 'ahora';
  };
  let vista = deHash();

  const json = async n => {
    try {
      const r = await fetch(`data/${n}.json?v=${Date.now()}`);
      return r.ok ? await r.json() : null;
    } catch { return null; }
  };

  function reloj() {
    $('#clock').textContent = new Intl.DateTimeFormat('es-ES', {
      day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit',
      timeZone: 'Europe/Madrid', hour12: false }).format(new Date()) + ' CEST';
  }

  const TEXTO = {
    0: ['Sin avisos en vigor',
        'No hay avisos de AEMET activos para la Comunitat. El panel sigue vigilando: se actualiza solo cada pocos minutos.'],
    1: ['Aviso amarillo',
        'Hay riesgo para actividades concretas. Precaución en barrancos, ramblas y pasos inundables, y ojo con el acumulado si la lluvia se queda parada sobre la misma cuenca.'],
    2: ['Aviso naranja — riesgo importante',
        'Fenómenos no habituales y con cierto peligro. Evita barrancos, ramblas, garajes subterráneos y desplazamientos no imprescindibles. Sigue a AEMET y al 112 de la Generalitat.'],
    3: ['AVISO ROJO — riesgo extremo',
        'Fenómenos de intensidad excepcional y peligro muy alto. Sigue únicamente las indicaciones oficiales del 112 y Emergencias GVA. No te acerques a cauces ni intentes cruzarlos, ni a pie ni en coche.'],
  };

  const XS = [
    ['AEMET C. Valenciana', '@AEMET_CValencia', 'https://x.com/AEMET_CValencia', 'oficial · avisos'],
    ['Emergències GVA', '@GVA112', 'https://x.com/GVA112', 'oficial · emergencias'],
    ['AEMET España', '@AEMET_Esp', 'https://x.com/AEMET_Esp', 'oficial · estatal'],
    ['C. H. del Júcar', '@CHJucar', 'https://x.com/CHJucar', 'oficial · caudales'],
    ['Protección Civil', '@proteccioncivil', 'https://x.com/proteccioncivil', 'oficial · estatal'],
    ['Generalitat', '@GVAes', 'https://x.com/GVAes', 'oficial · institucional'],
    ['Búsqueda: DANA Valencia', 'live', 'https://x.com/search?q=DANA%20Valencia&f=live', 'lo último'],
    ['Búsqueda: inundación', 'live', 'https://x.com/search?q=(inundaci%C3%B3n%20OR%20riada)%20(Valencia%20OR%20Val%C3%A8ncia)&f=live', 'lo último'],
    ['Búsqueda: barranco', 'live', 'https://x.com/search?q=barranco%20(Poyo%20OR%20Valencia)&f=live', 'lo último'],
  ];

  function pintar() {
    document.body.dataset.view = vista;
    document.querySelectorAll('.tab').forEach(t => t.classList.toggle('on', t.dataset.go === vista));
    VISTAS.forEach(v => $(`#v-${v}`).classList.toggle('hide', v !== vista));

    const meta = D.meta, obs = (D.obs && D.obs.items) || [];
    if (!meta) return;
    const orden = [...obs].sort((a, b) =>
      (b.nivel - a.nivel) || ((b.acum_12h || 0) - (a.acum_12h || 0))
      || ((b.prev_24h || 0) - (a.prev_24h || 0)) || (a.prio - b.prio));

    if (vista === 'ahora') {
      R.kpis($('#kpis'), meta, D.sea || {}, D.models || {});
      R.tabla($('#tabla-top'), orden, false);
      R.avisos($('#avisos-top'), (D.alerts.items || []).filter(a => a.activo), 6);
      R.ingredientes($('#ingredientes'), meta, D.sea || {}, obs);
      Mapa.dibujar($('#mapa'), obs, id => {
        const p = obs.find(x => x.id === id);
        if (p) alert(`${p.nombre} · ${p.comarca}\nCuenca: ${p.cuenca}\n\n`
          + `Ahora: ${p.lluvia_ahora ?? 0} mm/h (${p.intensidad})\n`
          + `Últimas 12 h: ${p.acum_12h} mm\nPróximas 24 h: ${p.prev_24h} mm\n`
          + `Pico previsto: ${p.pico_mmh} mm/h\nCAPE: ${p.cape ?? '–'} J/kg`);
      });
      $('#map-sub').textContent = `${obs.length} puntos · ${meta.resumen.lloviendo} con lluvia`;
      $('#av-sub').textContent = `${meta.resumen.avisos_activos} en vigor`;
    }
    if (vista === 'avisos') R.avisos($('#avisos-todos'), D.alerts.items || []);
    if (vista === 'zonas') R.tabla($('#tabla-todo'), orden, true);
    if (vista === 'rios') R.rios($('#rios'), (D.rivers && D.rivers.items) || []);
    if (vista === 'modelos') R.modelos($('#modelos'), D.models || {});
    if (vista === 'noticias') {
      R.news($('#news'), (D.news && D.news.items) || []);
      $('#xs').innerHTML = XS.map(([n, h, u, s]) =>
        `<a class="x" href="${u}" target="_blank" rel="noopener">
           <div><b>${n}</b><span>${h} · ${s}</span></div></a>`).join('');
    }
  }

  function cabecera() {
    const m = D.meta;
    if (!m) return;
    const r = m.resumen, n = r.nivel;
    const [titulo, texto] = TEXTO[n];
    $('#banda').className = `banda n${n}`;
    $('#banda-n').textContent = n === 0 ? 'VERDE' : r.nivel_texto.toUpperCase();
    $('#banda-h').textContent = titulo;

    const extra = [];
    if (r.lloviendo) extra.push(`Llueve en ${r.lloviendo} de ${r.puntos} puntos vigilados`);
    if (r.max_acum_12h >= 1) extra.push(`máximo ${R.n1(r.max_acum_12h)} mm en 12 h${r.zona_mas_expuesta ? ` (${r.zona_mas_expuesta})` : ''}`);
    if (r.max_prev_24h >= 10) extra.push(`hasta ${R.n1(r.max_prev_24h)} mm previstos en 24 h`);
    $('#banda-p').textContent = texto + (extra.length ? ' — ' + extra.join(' · ') + '.' : '');

    const av = r.avisos_activos, nv = $('#n-avisos');
    nv.textContent = av;
    nv.className = 'n' + (n >= 3 ? ' crit' : n >= 2 ? ' hot' : '');
    $('#n-zonas').textContent = r.puntos;
    $('#n-noticias').textContent = ((D.news && D.news.items) || []).length;
    $('#dot').style.background = `var(--n${n})`;

    const act = R.diaHora(m.updated);
    $('#foot').innerHTML = `Actualizado <b>${act}</b> · fuentes <b>${m.fuentes_ok}/${m.fuentes_total}</b> ·
      se refresca solo cada 5 min.<br>
      Avisos: <b>AEMET</b> vía MeteoAlarm (CAP) · atmósfera y mar: <b>Open-Meteo</b> ·
      caudales: <b>GloFAS / Copernicus</b> · prensa valenciana y GDACS.<br>
      Esto es una herramienta de seguimiento, <b>no una fuente oficial</b>. En una emergencia
      manda siempre AEMET, el 112 y Emergencias GVA.`;
  }

  async function cargar() {
    const nombres = ['meta', 'alerts', 'obs', 'rivers', 'models', 'sea', 'news'];
    const res = await Promise.all(nombres.map(json));
    nombres.forEach((n, i) => { if (res[i]) D[n] = res[i]; });
    if (!D.alerts) D.alerts = { items: [] };
    cabecera();
    pintar();
    $('#pulse-t').textContent = 'en vivo';
  }

  document.addEventListener('click', e => {
    const t = e.target.closest('[data-go]');
    if (t) location.hash = t.dataset.go;
  });
  window.addEventListener('hashchange', () => { vista = deHash(); pintar(); });

  reloj();
  setInterval(reloj, 20000);
  cargar();
  setInterval(cargar, 300000);   // 5 min
})();
