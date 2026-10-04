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

  // vignette d'une référence : l'affiche en grand et repère la ligne
  document.querySelectorAll('.js-ref-ph').forEach(b => b.addEventListener('click', () => {
    if (!main) return;
    main.src = b.dataset.src;
    document.querySelectorAll('.js-thumb').forEach(x => x.classList.remove('on'));
    document.querySelectorAll('.refs tr.sel').forEach(r => r.classList.remove('sel'));
    b.closest('tr').classList.add('sel');
    if (main.getBoundingClientRect().top < 0) main.scrollIntoView({ behavior: 'smooth', block: 'start' });
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

  // fiche avec choix (dimensions, coloris…) : un bouton par valeur, la référence et le prix suivent
  document.querySelectorAll('.js-pick').forEach(f => {
    const arts = JSON.parse(f.dataset.arts);
    const axes = [...f.querySelectorAll('[data-axis]')].map(x => x.dataset.axis);
    const radios = a => [...f.querySelectorAll('input[type=radio]')].filter(i => i.name === a);
    const fits = (x, s) => axes.every(a => x.v[a] === s[a]);
    let cur = arts[0];
    function sync(changed) {
      const s = Object.fromEntries(axes.map(a => [a, radios(a).find(i => i.checked)?.value]));
      cur = arts.find(x => fits(x, s));
      if (!cur) { // combinaison non fabriquée : l'article le plus proche qui garde la valeur cliquée
        const score = x => axes.filter(a => x.v[a] === s[a]).length;
        cur = arts.filter(x => x.v[changed] === s[changed]).sort((p, q) => score(q) - score(p))[0] || arts[0];
        axes.forEach(a => radios(a).forEach(i => { i.checked = i.value === cur.v[a]; }));
      }
      axes.forEach(a => {
        radios(a).forEach(i => i.parentElement.classList.toggle('off', !arts.some(x => fits(x, { ...cur.v, [a]: i.value }))));
        f.querySelector(`[data-axis="${CSS.escape(a)}"] [data-cur]`).textContent = cur.v[a];
      });
      f.querySelector('[data-code]').textContent = cur.code;
      f.querySelector('[data-des]').textContent = [cur.des, cur.col].filter(Boolean).join(' · ');
      f.querySelector('[data-price]').innerHTML = cur.prix != null
        ? `<span class="from">Prix unitaire</span><b>${eur(cur.prix)}</b> <span class="ht">HT</span>`
        : '<b class="quote">Sur devis</b><span class="muted">Ajoutez-le à votre demande, nous vous envoyons le prix sous 48 h.</span>';
      f.querySelector('[data-btn]').textContent = cur.prix != null ? 'Ajouter au panier' : 'Ajouter à ma demande';
      if (main && cur.photo && changed) {
        main.src = cur.photo;
        document.querySelectorAll('.js-thumb').forEach(x => x.classList.toggle('on', x.dataset.src === cur.photo));
      }
    }
    f.addEventListener('change', e => { if (e.target.type === 'radio') sync(e.target.name); });
    f.addEventListener('submit', e => {
      e.preventDefault();
      const qty = Math.max(1, Math.floor(+f.querySelector('.qty').value) || 1);
      add([{ ...cur.line, opt: '', qty }]);
      done(f.querySelector('[data-msg]'), qty);
    });
    sync();
  });

  // fiche simple (avec options éventuelles)
  document.querySelectorAll('.js-add-one').forEach(f => f.addEventListener('change', e => {
    if (e.target.type === 'radio') e.target.closest('fieldset').querySelector('[data-cur]').textContent = e.target.value;
  }));
  document.querySelectorAll('.js-add-one').forEach(f => f.addEventListener('submit', e => {
    e.preventDefault();
    const opt = [...f.querySelectorAll('select, input[type=radio]:checked')].map(s => `${s.name} : ${s.value}`).join(' · ');
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
