// rayonnages.eu — panier (stocké dans le navigateur) et petites interactions
(() => {
  const KEY = 'rsl-panier';
  const BASE = document.currentScript.src.replace(/assets\/app\.js.*$/, '');
  const read = () => { try { return JSON.parse(localStorage.getItem(KEY) || '[]'); } catch { return []; } };
  const write = c => { try { localStorage.setItem(KEY, JSON.stringify(c)); } catch {} badge(); };
  const keyOf = l => [l.id, l.ref || '', l.opt || ''].join('|');
  const eur = n => n.toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' });
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  function badge() {
    const n = read().reduce((t, l) => t + l.qty, 0);
    document.querySelectorAll('[data-cart-count]').forEach(b => { b.textContent = n; b.hidden = n === 0; });
  }
  function add(lines) {
    const c = read();
    for (const l of lines) {
      const k = keyOf(l), ex = c.find(x => keyOf(x) === k);
      ex ? (ex.qty += l.qty) : c.push(l);
    }
    write(c);
  }
  function done(msgEl, n) {
    if (!msgEl) return;
    msgEl.hidden = false; msgEl.className = 'hint ok';
    msgEl.innerHTML = `${n} article${n > 1 ? 's' : ''} ajouté${n > 1 ? 's' : ''} au panier. <a href="${BASE}panier/index.html">Voir le panier</a>`;
  }

  // galerie
  const main = document.querySelector('.js-main');
  document.querySelectorAll('.js-thumb').forEach(b => b.addEventListener('click', () => {
    main.src = b.dataset.src;
    document.querySelectorAll('.js-thumb').forEach(x => x.classList.toggle('on', x === b));
  }));

  // fiche avec tableau de références
  const addRefs = document.querySelector('.js-add-refs');
  addRefs?.addEventListener('click', () => {
    const lines = [];
    document.querySelectorAll('.refs .qty').forEach(i => {
      const q = Math.floor(+i.value);
      if (q > 0) { lines.push({ ...JSON.parse(i.dataset.line), opt: '', qty: q }); i.value = 0; }
    });
    const msg = addRefs.parentElement.querySelector('[data-msg]');
    if (!lines.length) { msg.hidden = false; msg.className = 'hint'; msg.textContent = 'Indiquez une quantité sur au moins une référence.'; return; }
    add(lines); done(msg, lines.reduce((t, l) => t + l.qty, 0));
  });

  // fiche simple (avec options éventuelles)
  document.querySelectorAll('.js-add-one').forEach(f => f.addEventListener('submit', e => {
    e.preventDefault();
    const opt = [...f.querySelectorAll('select')].map(s => `${s.name} : ${s.value}`).join(' · ');
    const qty = Math.max(1, Math.floor(+f.querySelector('.qty').value) || 1);
    add([{ ...JSON.parse(f.dataset.line), opt, qty }]);
    done(f.querySelector('[data-msg]'), qty);
  }));

  // page panier
  const cartEl = document.querySelector('[data-cart]');
  function render() {
    const c = read(), ul = cartEl.querySelector('[data-lines]'), form = cartEl.querySelector('[data-checkout]');
    cartEl.querySelector('[data-empty]').hidden = c.length > 0;
    form.hidden = c.length === 0;
    ul.innerHTML = c.map((l, i) => `<li>
      ${l.photo ? `<img src="${esc(String(l.photo).startsWith('/') ? BASE + l.photo.slice(1) : l.photo)}" alt="">` : '<span class="ph"></span>'}
      <div><h3><a href="${esc(BASE + String(l.url).replace(/^\//, '') + 'index.html')}">${esc(l.nom)}</a></h3>
        <div class="meta">${esc([l.refLabel, l.opt].filter(Boolean).join(' · '))}</div>
        <div class="meta">${l.prix != null ? `${eur(l.prix)} HT l’unité` : 'Prix sur devis'}</div>
        <div class="ctl"><label class="sr" for="cq${i}">Quantité</label><input class="qty" id="cq${i}" type="number" min="1" value="${l.qty}" data-i="${i}"><button type="button" class="linkbtn" data-del="${i}">Retirer</button></div></div>
      <b class="num">${l.prix != null ? eur(l.prix * l.qty) : '<span class="muted">sur devis</span>'}</b></li>`).join('');
    const ht = c.reduce((t, l) => t + (l.prix != null ? l.prix * l.qty : 0), 0), tva = +cartEl.dataset.tva;
    cartEl.querySelector('[data-ht]').textContent = eur(ht);
    cartEl.querySelector('[data-tva-amt]').textContent = eur(ht * tva);
    cartEl.querySelector('[data-ttc]').textContent = eur(ht * (1 + tva));
    const allQuote = c.every(l => l.prix == null);
    cartEl.querySelector('[data-quote-note]').hidden = !c.some(l => l.prix == null);
    cartEl.querySelector('[data-submit]').textContent = allQuote ? 'Envoyer ma demande de devis' : 'Envoyer ma commande';
    cartEl.querySelector('[data-cart-json]').value = JSON.stringify(c.map(({ id, ref, opt, qty }) => ({ id, ref, opt, qty })));
  }
  if (cartEl) {
    cartEl.addEventListener('change', e => {
      const i = e.target.dataset.i; if (i == null) return;
      const c = read(); c[i].qty = Math.max(1, Math.floor(+e.target.value) || 1); write(c); render();
    });
    cartEl.addEventListener('click', e => {
      const i = e.target.dataset.del; if (i == null) return;
      const c = read(); c.splice(+i, 1); write(c); render();
    });
    render();
  }

  if (document.querySelector('[data-clear-cart]')) write([]);
  badge();
})();
