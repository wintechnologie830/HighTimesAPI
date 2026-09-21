(function(){
  "use strict";

  const store = {
    get base(){ return localStorage.getItem('lp_base') || 'http://localhost:8000'; },
    set base(v){ localStorage.setItem('lp_base', v); },
    get key(){ return localStorage.getItem('lp_key') || ''; },
    set key(v){ localStorage.setItem('lp_key', v); },
    get customerId(){ return localStorage.getItem('lp_customer') || ''; },
    set customerId(v){ localStorage.setItem('lp_customer', v); },
    get customerName(){ return localStorage.getItem('lp_customer_name') || ''; },
    set customerName(v){ localStorage.setItem('lp_customer_name', v); },
    clearSession(){
      localStorage.removeItem('lp_customer');
      localStorage.removeItem('lp_customer_name');
    },
  };

  // Separate from the customer `store` above on purpose - a staff member
  // signing in on a shared kiosk shouldn't touch the logged-in customer's
  // session, and vice versa.
  const staffSession = {
    get token(){ return localStorage.getItem('lp_staff_token') || ''; },
    set token(v){ v ? localStorage.setItem('lp_staff_token', v) : localStorage.removeItem('lp_staff_token'); },
    get name(){ return localStorage.getItem('lp_staff_name') || ''; },
    set name(v){ v ? localStorage.setItem('lp_staff_name', v) : localStorage.removeItem('lp_staff_name'); },
    clear(){ this.token = ''; this.name = ''; },
  };

  let pointValueCurrency = 0.05; // fallback display ratio, refined once balance loads
  let mode = 'buy';
  let products = [];

  // ---------- toast ----------
  const toastEl = document.getElementById('toast');
  let toastTimer;
  function toast(msg, type){
    toastEl.textContent = msg;
    toastEl.className = 'toast show' + (type ? ' ' + type : '');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { toastEl.classList.remove('show'); }, 3600);
  }

  // ---------- api ----------
  async function api(path, opts){
    opts = opts || {};
    const headers = Object.assign({ 'X-API-Key': store.key }, opts.headers || {});
    if (opts.body) headers['Content-Type'] = 'application/json';
    let res;
    try{
      res = await fetch(store.base.replace(/\/$/, '') + path, {
        method: opts.method || 'GET',
        headers,
        body: opts.body ? JSON.stringify(opts.body) : undefined,
      });
    }catch(e){
      throw new Error('Could not reach fidelityAPI at ' + store.base + '. Is it running?');
    }
    let data = null;
    try{ data = await res.json(); }catch(e){ /* no body */ }
    if(!res.ok){
      const detail = (data && data.detail) ? data.detail : (res.status + ' ' + res.statusText);
      throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
    }
    return data;
  }

  // ---------- setup / auth ----------
  const setupOverlay = document.getElementById('setupOverlay');
  const appRoot = document.getElementById('appRoot');

  function openSetup(){
    document.getElementById('cfgBase').value = store.base;
    document.getElementById('cfgKey').value = store.key;
    setupOverlay.classList.remove('hidden');
    appRoot.classList.add('hidden');
  }

  function requireConnection(){
    store.base = document.getElementById('cfgBase').value.trim() || store.base;
    store.key = document.getElementById('cfgKey').value.trim();
    if(!store.key){
      toast('Set the fidelityAPI X-API-Key under "connection settings" first.', 'err');
      return false;
    }
    return true;
  }

  // advanced connection fields toggle
  document.getElementById('toggleAdvanced').addEventListener('click', () => {
    document.getElementById('advancedFields').classList.toggle('hidden');
  });

  // sign in / sign up tabs
  const authTabSignin = document.getElementById('authTabSignin');
  const authTabSignup = document.getElementById('authTabSignup');
  const signinForm = document.getElementById('signinForm');
  const signupForm = document.getElementById('signupForm');
  const authTitle = document.getElementById('authTitle');
  const authSub = document.getElementById('authSub');

  authTabSignin.addEventListener('click', () => {
    authTabSignin.classList.add('active'); authTabSignup.classList.remove('active');
    signinForm.classList.remove('hidden'); signupForm.classList.add('hidden');
    authTitle.textContent = 'Sign in';
    authSub.textContent = 'Welcome back to your High Times account.';
  });
  authTabSignup.addEventListener('click', () => {
    authTabSignup.classList.add('active'); authTabSignin.classList.remove('active');
    signupForm.classList.remove('hidden'); signinForm.classList.add('hidden');
    authTitle.textContent = 'Create account';
    authSub.textContent = 'Sign up once, then earn and spend points on every visit.';
  });

  signinForm.addEventListener('submit', async (ev) => {
    ev.preventDefault();
    if(!requireConnection()) return;
    const name = document.getElementById('siName').value.trim();
    const password = document.getElementById('siPassword').value;
    const btn = signinForm.querySelector('button[type="submit"]');
    btn.disabled = true;
    try{
      const auth = await api('/auth/login', { method: 'POST', body: { name, password } });
      store.customerId = String(auth.aronium_customer_id);
      store.customerName = auth.name;
      setupOverlay.classList.add('hidden');
      appRoot.classList.remove('hidden');
      await bootstrap();
    }catch(e){
      toast(e.message, 'err');
    }finally{
      btn.disabled = false;
    }
  });

  signupForm.addEventListener('submit', async (ev) => {
    ev.preventDefault();
    if(!requireConnection()) return;
    const name = document.getElementById('suName').value.trim();
    const phone = document.getElementById('suPhone').value.trim();
    const password = document.getElementById('suPassword').value;
    const btn = signupForm.querySelector('button[type="submit"]');
    btn.disabled = true;
    try{
      const auth = await api('/auth/register', {
        method: 'POST',
        body: { name, password, phone: phone || null },
      });
      store.customerId = String(auth.aronium_customer_id);
      store.customerName = auth.name;
      setupOverlay.classList.add('hidden');
      appRoot.classList.remove('hidden');
      toast('Account created — welcome, ' + auth.name + '.', 'ok');
      await bootstrap();
    }catch(e){
      toast(e.message, 'err');
    }finally{
      btn.disabled = false;
    }
  });

  document.getElementById('changeConn').addEventListener('click', () => {
    document.getElementById('advancedFields').classList.remove('hidden');
    openSetup();
  });

  document.getElementById('logoutBtn').addEventListener('click', () => {
    store.clearSession();
    openSetup();
  });

  // ---------- ledger sidebar ----------
  async function refreshCustomer(){
    if(store.customerName){
      document.getElementById('custName').textContent = store.customerName;
      document.getElementById('custMeta').textContent = 'ID ' + store.customerId;
    }
    try{
      const c = await api('/customers/' + encodeURIComponent(store.customerId));
      document.getElementById('custName').textContent = c.Name;
      document.getElementById('custMeta').textContent = 'ID ' + c.Id + (c.Code ? ' · card ' + c.Code : '');
      store.customerName = c.Name;
    }catch(e){
      if(!store.customerName){
        document.getElementById('custName').textContent = 'Unknown customer';
        document.getElementById('custMeta').textContent = e.message;
      }
    }
  }

  async function refreshBalance(){
    try{
      const b = await api('/points/' + encodeURIComponent(store.customerId));
      document.getElementById('balNum').textContent = formatPoints(b.points_balance);
      document.getElementById('balCash').textContent = 'worth $' + b.point_value_currency.toFixed(2);
      if(b.points_balance > 0){
        pointValueCurrency = b.point_value_currency / b.points_balance;
      }
    }catch(e){
      toast(e.message, 'err');
    }
  }

  async function refreshHistory(){
    const list = document.getElementById('txList');
    try{
      const txs = await api('/points/' + encodeURIComponent(store.customerId) + '/history?limit=6');
      if(!txs.length){
        list.innerHTML = '<div class="empty" style="padding:6px 0;color:rgba(241,239,228,0.5);">no activity yet</div>';
        return;
      }
      list.innerHTML = txs.map(t => {
        const pos = t.points >= 0;
        const date = new Date(t.date_created);
        return '<div class="tx"><span>' +
          '<div>' + escapeHtml(t.type) + '</div>' +
          '<div class="meta">' + date.toLocaleDateString() + (t.reference ? ' · ' + escapeHtml(t.reference) : '') + '</div>' +
          '</span><span class="amt ' + (pos ? 'pos' : 'neg') + '">' + (pos ? '+' : '') + formatPoints(t.points) + '</span></div>';
      }).join('');
    }catch(e){
      list.innerHTML = '<div class="empty" style="padding:6px 0;color:rgba(241,239,228,0.5);">' + escapeHtml(e.message) + '</div>';
    }
  }

  function formatPoints(n){
    return Number(n).toLocaleString(undefined, { maximumFractionDigits: 2 });
  }
  function escapeHtml(s){
    return String(s).replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  }
  function formatTimeHHMMSS(d){
    const pad = n => String(n).padStart(2, '0');
    return pad(d.getHours()) + ':' + pad(d.getMinutes()) + ':' + pad(d.getSeconds());
  }

  // ---------- products ----------
  async function loadProducts(search){
    const grid = document.getElementById(mode === 'buy' ? 'buyGrid' : 'redeemGrid');
    grid.innerHTML = '<div class="empty">loading products…</div>';
    try{
      const q = search ? ('?search=' + encodeURIComponent(search)) : '';
      products = await api('/products' + q);
      renderGrid();
    }catch(e){
      grid.innerHTML = '<div class="empty">' + escapeHtml(e.message) + '</div>';
    }
  }

  const qtyState = {}; // productId -> qty for buy mode

  function renderGrid(){
    const grid = document.getElementById(mode === 'buy' ? 'buyGrid' : 'redeemGrid');
    if(!products.length){
      grid.innerHTML = '<div class="empty">No products found.</div>';
      return;
    }
    grid.innerHTML = '';
    products.forEach(p => {
      const card = document.createElement('div');
      card.className = 'card';

      if(mode === 'buy'){
        if(qtyState[p.Id] === undefined) qtyState[p.Id] = 1;
        const qty = qtyState[p.Id];
        const stock = p.Quantity; // live Aronium stock - this is what goes down on purchase
        const outOfStock = stock !== null && stock !== undefined && stock <= 0;
        card.innerHTML =
          '<div class="pname">' + escapeHtml(p.Name) + '</div>' +
          '<div class="stock' + (outOfStock ? ' low' : '') + '">' +
            (stock === null || stock === undefined ? 'stock not tracked' : (outOfStock ? 'out of stock' : stock + ' in stock')) +
          '</div>' +
          '<div class="qty-row">' +
            '<button data-act="dec" aria-label="decrease quantity">−</button>' +
            '<span class="qty-val">' + qty + '</span>' +
            '<button data-act="inc" aria-label="increase quantity">+</button>' +
          '</div>' +
          '<div class="price-row"><span class="price">$' + p.Price.toFixed(2) + '</span>' +
          '<button class="btn small" data-act="buy" ' + (outOfStock ? 'disabled' : '') + '>Buy</button></div>';

        card.querySelector('[data-act="dec"]').addEventListener('click', () => {
          qtyState[p.Id] = Math.max(1, qtyState[p.Id] - 1);
          renderGrid();
        });
        card.querySelector('[data-act="inc"]').addEventListener('click', () => {
          qtyState[p.Id] = qtyState[p.Id] + 1;
          renderGrid();
        });
        card.querySelector('[data-act="buy"]').addEventListener('click', () => buyProduct(p, qtyState[p.Id]));
      } else {
        const estCost = pointValueCurrency > 0 ? Math.ceil(p.Price / pointValueCurrency) : null;
        const inv = p.Inventory;
        const lowStock = inv !== null && inv !== undefined && inv <= 0;
        card.innerHTML =
          '<div class="pname">' + escapeHtml(p.Name) + '</div>' +
          '<div class="stock' + (lowStock ? ' low' : '') + '">' +
            (inv === null || inv === undefined ? 'stock not tracked' : (lowStock ? 'out of redeemable stock' : inv + ' redeemable in stock')) +
          '</div>' +
          (estCost !== null ? '<span class="redeem-cost">~' + estCost + ' pts</span>' : '') +
          '<div class="price-row"><span class="price">$' + p.Price.toFixed(2) + '</span>' +
          '<button class="btn small" data-act="redeem" ' + (lowStock ? 'disabled' : '') + '>Redeem</button></div>';

        const btn = card.querySelector('[data-act="redeem"]');
        btn.addEventListener('click', () => redeemProduct(p));
      }

      grid.appendChild(card);
    });
  }

  async function buyProduct(p, qty){
    try{
      const tx = await api('/points/purchase', {
        method: 'POST',
        body: {
          aronium_customer_id: Number(store.customerId),
          product_id: p.Id,
          quantity: qty,
          reference: 'webapp-' + Date.now(),
        },
      });
      toast('Bought ' + qty + ' × ' + p.Name + ' — earned ' + formatPoints(tx.points) + ' pts', 'ok');
      qtyState[p.Id] = 1;
      await Promise.all([refreshBalance(), refreshHistory()]);
      await loadProducts(document.getElementById('buySearch').value.trim());
    }catch(e){
      toast('Purchase failed: ' + e.message, 'err');
    }
  }

  async function redeemProduct(p){
    try{
      const tx = await api('/points/redeem-product', {
        method: 'POST',
        body: {
          aronium_customer_id: Number(store.customerId),
          product_id: p.Id,
          quantity: 1,
        },
      });
      showPickupModal(tx);
      await Promise.all([refreshBalance(), refreshHistory()]);
      await loadProducts(document.getElementById('redeemSearch').value.trim());
    }catch(e){
      toast('Redeem failed: ' + e.message, 'err');
    }
  }

  // ---------- pickup code modal ----------
  const pickupModal = document.getElementById('pickupModal');
  function showPickupModal(tx){
    document.getElementById('pickupModalDesc').textContent =
      tx.quantity + ' × ' + tx.product_name + ' - show this code at the counter to pick it up.';
    document.getElementById('pickupModalCode').textContent = tx.redemption_code;
    pickupModal.classList.remove('hidden');
  }
  document.getElementById('pickupModalClose').addEventListener('click', () => {
    pickupModal.classList.add('hidden');
  });

  // ---------- my pickups ----------
  async function loadPickups(){
    const list = document.getElementById('pickupsList');
    list.innerHTML = '<div class="empty">loading…</div>';
    try{
      const redemptions = await api('/redemptions/customer/' + encodeURIComponent(store.customerId));
      if(!redemptions.length){
        list.innerHTML = '<div class="empty">No redemptions yet — spend points under "Redeem points" to get a pickup code.</div>';
        return;
      }
      list.innerHTML = redemptions.map(renderPickupRow).join('');
    }catch(e){
      list.innerHTML = '<div class="empty">' + escapeHtml(e.message) + '</div>';
    }
  }

  function renderPickupRow(r){
    const isPending = r.status === 'PENDING';
    const date = new Date(r.date_created);
    let pickedUpMeta = '';
    if(!isPending && r.date_fulfilled){
      const fulfilledDate = new Date(r.date_fulfilled);
      const staffTag = r.staff_id ? (' by staff #' + escapeHtml(String(r.staff_id))) : '';
      pickedUpMeta = '<div class="pmeta">picked up ' + fulfilledDate.toLocaleDateString() + ' ' +
        formatTimeHHMMSS(fulfilledDate) + staffTag + '</div>';
    }
    return '<div class="pickup-row">' +
      '<div class="pinfo">' +
        '<div class="pname">' + escapeHtml(r.quantity + ' × ' + r.product_name) + '</div>' +
        '<div class="pmeta">redeemed ' + date.toLocaleDateString() + ' ' + formatTimeHHMMSS(date) + ' · ' + formatPoints(r.points_spent) + ' pts</div>' +
        pickedUpMeta +
      '</div>' +
      (isPending
        ? '<span class="pcode-tag mono">' + escapeHtml(r.code) + '</span>'
        : '<span class="status-tag fulfilled">picked up</span>') +
      '</div>';
  }

  // ---------- staff pickup desk ----------
  let staffPin = '';

  async function staffApi(path, opts){
    opts = opts || {};
    opts.headers = Object.assign({ 'X-Staff-Pin': staffPin }, opts.headers || {});
    return api(path, opts);
  }

  const staffOverlay = document.getElementById('staffOverlay');
  const staffPinGate = document.getElementById('staffPinGate');
  const staffTools = document.getElementById('staffTools');
  const staffLoginBox = document.getElementById('staffLoginBox');
  const staffSignedInBox = document.getElementById('staffSignedInBox');

  document.getElementById('staffToggle').addEventListener('click', () => {
    staffOverlay.classList.remove('hidden');
    refreshStaffLoginUI();
  });
  document.getElementById('staffClose').addEventListener('click', () => {
    staffOverlay.classList.add('hidden');
  });

  document.getElementById('staffPinSubmit').addEventListener('click', async () => {
    const pin = document.getElementById('staffPinInput').value.trim();
    if(!pin){ return; }
    staffPin = pin;
    try{
      await staffApi('/redemptions/staff/pending');
      staffPinGate.classList.add('hidden');
      staffTools.classList.remove('hidden');
      refreshStaffLoginUI();
      // Land on Account when nobody's signed in yet (so pickups get
      // attributed correctly), otherwise go straight to the pickup queue.
      setStaffSection(staffSession.token ? 'pickups' : 'account');
    }catch(e){
      staffPin = '';
      toast('Wrong staff PIN', 'err');
    }
  });

  // ---------- section tabs: Account / Migrate customer / Pickups ----------
  const staffSectionAccountBtn = document.getElementById('staffSectionAccountBtn');
  const staffSectionMigrateBtn = document.getElementById('staffSectionMigrateBtn');
  const staffSectionPickupsBtn = document.getElementById('staffSectionPickupsBtn');
  const staffSectionAccount = document.getElementById('staffSectionAccount');
  const staffSectionMigrate = document.getElementById('staffSectionMigrate');
  const staffSectionPickups = document.getElementById('staffSectionPickups');

  function setStaffSection(section){
    staffSectionAccountBtn.classList.toggle('active', section === 'account');
    staffSectionMigrateBtn.classList.toggle('active', section === 'migrate');
    staffSectionPickupsBtn.classList.toggle('active', section === 'pickups');
    staffSectionAccount.classList.toggle('hidden', section !== 'account');
    staffSectionMigrate.classList.toggle('hidden', section !== 'migrate');
    staffSectionPickups.classList.toggle('hidden', section !== 'pickups');
    if(section === 'pickups'){
      refreshStaffQueue();
    }
  }
  staffSectionAccountBtn.addEventListener('click', () => setStaffSection('account'));
  staffSectionMigrateBtn.addEventListener('click', () => setStaffSection('migrate'));
  staffSectionPickupsBtn.addEventListener('click', () => setStaffSection('pickups'));

  // ---------- individual staff sign-in / sign-up ----------
  // Separate from the PIN above: the PIN just gets you into the back
  // room, this is who's actually standing at the counter. Required
  // before "Mark picked up" will work, so every fulfilled redemption is
  // attributed to a real person.
  //
  // The status line at the top of the panel mirrors this regardless of
  // which section is open, so staff don't have to flip to Account just to
  // check whether they're signed in.
  function refreshStaffLoginUI(){
    const signedIn = !!staffSession.token;
    staffLoginBox.classList.toggle('hidden', signedIn);
    staffSignedInBox.classList.toggle('hidden', !signedIn);
    if(signedIn){
      document.getElementById('staffSignedInName').textContent = staffSession.name;
    }
    const statusEl = document.getElementById('staffStatusLine');
    statusEl.classList.toggle('signed-out', !signedIn);
    if(signedIn){
      statusEl.innerHTML = 'Signed in as <strong>' + escapeHtml(staffSession.name) +
        '</strong> · <button class="link-btn" id="staffStatusLogoutBtn">sign out</button>';
      document.getElementById('staffStatusLogoutBtn').addEventListener('click', () => {
        document.getElementById('staffLogoutBtn').click();
      });
    }else{
      statusEl.innerHTML = 'Not signed in — pickups need a signed-in staff account to be attributed. ' +
        '<button class="link-btn" id="staffStatusAccountBtn">Go to Account</button>';
      document.getElementById('staffStatusAccountBtn').addEventListener('click', () => setStaffSection('account'));
    }
  }

  const staffSigninForm = document.getElementById('staffSigninForm');
  const staffSignupForm = document.getElementById('staffSignupForm');
  const staffTabSignin = document.getElementById('staffTabSignin');
  const staffTabSignup = document.getElementById('staffTabSignup');

  staffTabSignin.addEventListener('click', () => {
    staffTabSignin.classList.add('active');
    staffTabSignup.classList.remove('active');
    staffSigninForm.classList.remove('hidden');
    staffSignupForm.classList.add('hidden');
  });
  staffTabSignup.addEventListener('click', () => {
    staffTabSignup.classList.add('active');
    staffTabSignin.classList.remove('active');
    staffSignupForm.classList.remove('hidden');
    staffSigninForm.classList.add('hidden');
  });

  document.getElementById('staffLoginBtn').addEventListener('click', async () => {
    const username = document.getElementById('staffUsernameInput').value.trim();
    const password = document.getElementById('staffPasswordInput').value;
    if(!username || !password){ return; }
    try{
      const res = await api('/staff/auth/login', { method: 'POST', body: { username, password } });
      staffSession.token = res.token;
      staffSession.name = res.name;
      document.getElementById('staffPasswordInput').value = '';
      refreshStaffLoginUI();
      refreshStaffQueue();
      toast('Signed in as ' + res.name, 'ok');
    }catch(e){
      toast('Sign-in failed: ' + e.message, 'err');
    }
  });

  document.getElementById('staffSignupBtn').addEventListener('click', async () => {
    const username = document.getElementById('staffSignupUsernameInput').value.trim();
    const name = document.getElementById('staffSignupNameInput').value.trim();
    const password = document.getElementById('staffSignupPasswordInput').value;
    if(!username || !name || !password){
      toast('Fill in a username, your name, and a password.', 'err');
      return;
    }
    if(password.length < 8){
      toast('Password must be at least 8 characters.', 'err');
      return;
    }
    try{
      const res = await api('/staff/auth/register', { method: 'POST', body: { username, name, password } });
      staffSession.token = res.token;
      staffSession.name = res.name;
      document.getElementById('staffSignupUsernameInput').value = '';
      document.getElementById('staffSignupNameInput').value = '';
      document.getElementById('staffSignupPasswordInput').value = '';
      refreshStaffLoginUI();
      refreshStaffQueue();
      toast('Account created - signed in as ' + res.name, 'ok');
    }catch(e){
      toast('Could not create account: ' + e.message, 'err');
    }
  });

  document.getElementById('staffLogoutBtn').addEventListener('click', async () => {
    try{
      await api('/staff/auth/logout', { method: 'POST', headers: { 'X-Staff-Token': staffSession.token } });
    }catch(e){
      // Token may already be gone server-side - clearing it locally is what matters.
    }
    staffSession.clear();
    staffTabSignin.click();
    refreshStaffLoginUI();
    refreshStaffQueue();
  });

  // ---------- migrate a legacy (Aronium) customer ----------
  // Uses the same fidelityAPI X-API-Key as the rest of the app (via `api()`),
  // not the staff PIN/token - POST /auth/claim is gated by require_mobile_api_key,
  // same as /auth/login and /auth/register.
  document.getElementById('migrateClaimBtn').addEventListener('click', async () => {
    const claim_code = document.getElementById('migrateClaimCodeInput').value.trim();
    const username = document.getElementById('migrateUsernameInput').value.trim();
    const password = document.getElementById('migratePasswordInput').value;
    const resultEl = document.getElementById('migrateClaimResult');
    const btn = document.getElementById('migrateClaimBtn');

    if(!claim_code){ toast('Enter the activation code first.', 'err'); return; }
    if(!password || password.length < 8){ toast('Password needs at least 8 characters.', 'err'); return; }

    btn.disabled = true;
    try{
      const body = { claim_code, password };
      if(username) body.username = username;
      const auth = await api('/auth/claim', { method: 'POST', body });
      resultEl.innerHTML = '<div class="empty">Activated <strong>' +
        escapeHtml(auth.name) + '</strong> (customer #' + escapeHtml(String(auth.aronium_customer_id)) + ').</div>';
      document.getElementById('migrateClaimCodeInput').value = '';
      document.getElementById('migrateUsernameInput').value = '';
      document.getElementById('migratePasswordInput').value = '';
      toast('Account activated.', 'ok');
    }catch(e){
      // 409 from the API means the username is taken - let staff pick a
      // different one and resubmit with the same claim code + password.
      resultEl.innerHTML = '';
      toast(e.message, 'err');
    }finally{
      btn.disabled = false;
    }
  });

  document.getElementById('staffCodeLookupBtn').addEventListener('click', async () => {
    const code = document.getElementById('staffCodeInput').value.trim();
    const resultEl = document.getElementById('staffLookupResult');
    if(!code){ return; }
    resultEl.innerHTML = '<div class="empty">looking up…</div>';
    try{
      const r = await staffApi('/redemptions/staff/by-code/' + encodeURIComponent(code));
      resultEl.innerHTML = renderStaffRow(r);
      wireStaffFulfillButtons(resultEl);
    }catch(e){
      resultEl.innerHTML = '<div class="empty">' + escapeHtml(e.message) + '</div>';
    }
  });

  function renderStaffRow(r){
    const isPending = r.status === 'PENDING';
    const date = new Date(r.date_created);
    let pickedUpMeta = '';
    if(!isPending && r.date_fulfilled){
      const fulfilledDate = new Date(r.date_fulfilled);
      pickedUpMeta = '<div class="pmeta">picked up ' + fulfilledDate.toLocaleDateString() + ' ' +
        formatTimeHHMMSS(fulfilledDate) + ' by ' + escapeHtml(r.staff_name || 'unknown staff') + '</div>';
    }
    return '<div class="pickup-row">' +
      '<div class="pinfo">' +
        '<div class="pname">' + escapeHtml(r.customer_name || ('customer #' + r.aronium_customer_id)) + ' — ' + escapeHtml(r.quantity + ' × ' + r.product_name) + '</div>' +
        '<div class="pmeta">code ' + escapeHtml(r.code) + '</div>' + 
        '<div class="pmeta">redeemed ' + date.toLocaleDateString() + ' ' + formatTimeHHMMSS(date) + '</div>' +
          pickedUpMeta +
      '</div>' +
      (isPending
        ? '<button class="btn small" data-fulfill="' + r.id + '">Mark picked up</button>'
        : '<span class="status-tag fulfilled">picked up</span>') +
      '</div>';
  }

  function wireStaffFulfillButtons(container){
    container.querySelectorAll('[data-fulfill]').forEach(btn => {
      btn.addEventListener('click', async () => {
        if(!staffSession.token){
          toast('Sign in as staff first so this pickup can be attributed to you.', 'err');
          return;
        }
        btn.disabled = true;
        try{
          await staffApi('/redemptions/staff/' + btn.getAttribute('data-fulfill') + '/fulfill', {
            method: 'POST',
            headers: { 'X-Staff-Token': staffSession.token },
          });
          toast('Marked as picked up', 'ok');
          document.getElementById('staffCodeInput').value = '';
          document.getElementById('staffLookupResult').innerHTML = '';
          refreshStaffQueue();
        }catch(e){
          toast(e.message, 'err');
          btn.disabled = false;
        }
      });
    });
  }

  // Three views onto the same list widget: pending pickups (everyone's,
  // unfulfilled), "mine" (this signed-in staff member's own completed
  // pickups), and "all" (everyone's completed pickups - the shop-wide
  // log). Each row already carries a resolved staff_name from the
  // backend, so the desk always shows a real name, never a bare id.
  let staffQueueMode = 'pending';
  const staffTabPending = document.getElementById('staffTabPending');
  const staffTabMine = document.getElementById('staffTabMine');
  const staffTabAll = document.getElementById('staffTabAll');
  const staffSearchRow = document.getElementById('staffSearchRow');

  function setStaffQueueMode(mode){
    staffQueueMode = mode;
    staffTabPending.classList.toggle('active', mode === 'pending');
    staffTabMine.classList.toggle('active', mode === 'mine');
    staffTabAll.classList.toggle('active', mode === 'all');
    // Searching by customer name only makes sense across everyone's
    // pickups, not a single staff member's own short list.
    staffSearchRow.classList.toggle('hidden', mode === 'mine');
    refreshStaffQueue();
  }
  staffTabPending.addEventListener('click', () => setStaffQueueMode('pending'));
  staffTabMine.addEventListener('click', () => setStaffQueueMode('mine'));
  staffTabAll.addEventListener('click', () => setStaffQueueMode('all'));

  async function refreshStaffQueue(){
    const list = document.getElementById('staffPendingList');
    const search = document.getElementById('staffSearchInput').value.trim();

    if(staffQueueMode === 'mine' && !staffSession.token){
      list.innerHTML = '<div class="empty">Sign in to your staff account to see your own pickups.</div>';
      return;
    }

    list.innerHTML = '<div class="empty">loading…</div>';
    try{
      let redemptions;
      if(staffQueueMode === 'pending'){
        const q = search ? ('?search=' + encodeURIComponent(search)) : '';
        redemptions = await staffApi('/redemptions/staff/pending' + q);
      }else if(staffQueueMode === 'all'){
        const q = search ? ('?search=' + encodeURIComponent(search)) : '';
        redemptions = await staffApi('/redemptions/staff/fulfilled' + q);
      }else{
        redemptions = await staffApi('/redemptions/staff/mine', {
          headers: { 'X-Staff-Token': staffSession.token },
        });
      }
      if(!redemptions.length){
        const emptyMsg = staffQueueMode === 'pending' ? 'Nothing pending.'
          : staffQueueMode === 'mine' ? "You haven't picked up any orders yet."
          : 'No pickups yet.';
        list.innerHTML = '<div class="empty">' + emptyMsg + '</div>';
        return;
      }
      list.innerHTML = redemptions.map(renderStaffRow).join('');
      wireStaffFulfillButtons(list);
    }catch(e){
      list.innerHTML = '<div class="empty">' + escapeHtml(e.message) + '</div>';
    }
  }

  let staffSearchTimer;
  document.getElementById('staffSearchInput').addEventListener('input', () => {
    clearTimeout(staffSearchTimer);
    staffSearchTimer = setTimeout(refreshStaffQueue, 300);
  });

  // ---------- mode switching ----------
  const buyView = document.getElementById('buyView');
  const redeemView = document.getElementById('redeemView');
  const pickupsView = document.getElementById('pickupsView');
  const modeBuyBtn = document.getElementById('modeBuyBtn');
  const modeRedeemBtn = document.getElementById('modeRedeemBtn');
  const modePickupsBtn = document.getElementById('modePickupsBtn');

  function setMode(m){
    mode = m;
    modeBuyBtn.classList.toggle('active', m === 'buy');
    modeRedeemBtn.classList.toggle('active', m === 'redeem');
    modePickupsBtn.classList.toggle('active', m === 'pickups');
    buyView.classList.toggle('hidden', m !== 'buy');
    redeemView.classList.toggle('hidden', m !== 'redeem');
    pickupsView.classList.toggle('hidden', m !== 'pickups');
    if(m === 'pickups'){
      loadPickups();
      return;
    }
    const search = m === 'buy' ? document.getElementById('buySearch').value.trim() : document.getElementById('redeemSearch').value.trim();
    loadProducts(search);
  }
  modeBuyBtn.addEventListener('click', () => setMode('buy'));
  modeRedeemBtn.addEventListener('click', () => setMode('redeem'));
  modePickupsBtn.addEventListener('click', () => setMode('pickups'));

  let searchTimer;
  function debounceSearch(inputEl){
    inputEl.addEventListener('input', () => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => loadProducts(inputEl.value.trim()), 300);
    });
  }
  debounceSearch(document.getElementById('buySearch'));
  debounceSearch(document.getElementById('redeemSearch'));

  // ---------- bootstrap ----------
  async function bootstrap(){
    await refreshCustomer();
    await refreshBalance();
    await refreshHistory();
    await loadProducts('');
  }

  if(store.key && store.customerId){
    appRoot.classList.remove('hidden');
    setupOverlay.classList.add('hidden');
    bootstrap();
  } else {
    openSetup();
  }
})();
