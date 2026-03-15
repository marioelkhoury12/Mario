document.addEventListener('DOMContentLoaded', () => {
  // Tab navigation
  const navBtns = document.querySelectorAll('.nav-btn');
  const tabs = document.querySelectorAll('.tab-content');

  navBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      navBtns.forEach(b => b.classList.remove('active'));
      tabs.forEach(t => t.classList.remove('active'));
      btn.classList.add('active');
      document.getElementById(btn.dataset.tab).classList.add('active');
    });
  });

  let stores = [];

  // --- Local coupon storage ---
  function getLocalCoupons() {
    try {
      return JSON.parse(localStorage.getItem('grocery-coupons') || '[]');
    } catch { return []; }
  }

  function saveLocalCoupons(coupons) {
    localStorage.setItem('grocery-coupons', JSON.stringify(coupons));
  }

  // Load initial data
  async function init() {
    stores = await fetchJSON('/api/stores');
    const categories = await fetchJSON('/api/categories');
    const products = await fetchJSON('/api/products');

    // Populate store dropdowns
    const storeSelects = ['store-filter', 'coupon-store', 'item-store'];
    storeSelects.forEach(id => {
      const el = document.getElementById(id);
      if (!el) return;
      const isFilter = id === 'store-filter';
      if (!isFilter) el.innerHTML = '';
      stores.forEach(s => {
        const opt = document.createElement('option');
        opt.value = s.id;
        opt.textContent = `${s.logo} ${s.name}`;
        el.appendChild(opt);
      });
    });

    // Populate category filter
    const catFilter = document.getElementById('category-filter');
    categories.forEach(c => {
      const opt = document.createElement('option');
      opt.value = c;
      opt.textContent = c;
      catFilter.appendChild(opt);
    });

    // Populate product suggestions
    const datalist = document.getElementById('product-suggestions');
    products.forEach(p => {
      const opt = document.createElement('option');
      opt.value = p;
      datalist.appendChild(opt);
    });

    loadFlyers();
    loadCoupons();
  }

  async function fetchJSON(url, options) {
    const res = await fetch(url, options);
    return res.json();
  }

  // --- Compare ---
  const compareBtn = document.getElementById('compare-btn');
  const compareInput = document.getElementById('compare-search');
  const compareResults = document.getElementById('compare-results');

  compareBtn.addEventListener('click', doCompare);
  compareInput.addEventListener('keydown', e => { if (e.key === 'Enter') doCompare(); });

  document.querySelectorAll('.chip').forEach(chip => {
    chip.addEventListener('click', () => {
      compareInput.value = chip.dataset.product;
      doCompare();
    });
  });

  async function doCompare() {
    const product = compareInput.value.trim();
    if (!product) return;

    const results = await fetchJSON(`/api/compare?product=${encodeURIComponent(product)}`);
    const coupons = getLocalCoupons();
    const term = product.toLowerCase();

    // Apply local coupons to results
    results.forEach(item => {
      const applicableCoupons = coupons.filter(c =>
        c.storeId === item.storeId &&
        c.productName.toLowerCase().includes(term) &&
        (!c.validTo || new Date(c.validTo) >= new Date())
      );
      const couponDiscount = applicableCoupons.reduce((sum, c) => {
        if (c.discountType === 'fixed') return sum + parseFloat(c.discountValue);
        if (c.discountType === 'percentage') return sum + (item.price * parseFloat(c.discountValue) / 100);
        return sum;
      }, 0);
      item.couponDiscount = Math.round(couponDiscount * 100) / 100;
      item.finalPrice = Math.round(Math.max(0, item.price - couponDiscount) * 100) / 100;
      item.appliedCoupons = applicableCoupons;
    });

    results.sort((a, b) => a.finalPrice - b.finalPrice);

    if (results.length === 0) {
      compareResults.innerHTML = `
        <div class="empty-state">
          <div class="emoji">🔍</div>
          <p>No results found for "${product}". Try a different search term or add items manually.</p>
        </div>`;
      return;
    }

    compareResults.innerHTML = results.map((item, i) => {
      const isCheapest = i === 0;
      const savings = item.originalPrice > item.finalPrice
        ? `Save $${(item.originalPrice - item.finalPrice).toFixed(2)}`
        : '';

      return `
        <div class="compare-card ${isCheapest ? 'cheapest' : ''}" style="border-left-color: ${item.storeColor}">
          ${isCheapest ? '<div class="best-deal-badge">Best Price</div>' : ''}
          <div class="rank">#${i + 1}</div>
          <div class="store-badge">${item.storeLogo}</div>
          <div class="compare-info">
            <h3>${item.name}</h3>
            <div class="store-name">${item.storeName}</div>
            <div class="item-desc">${item.description}</div>
            ${item.appliedCoupons.length > 0 ? item.appliedCoupons.map(c =>
              `<span class="coupon-tag">Coupon: -${c.discountType === 'fixed' ? '$' + parseFloat(c.discountValue).toFixed(2) : c.discountValue + '%'}${c.code ? ' (' + c.code + ')' : ''}</span>`
            ).join(' ') : ''}
          </div>
          <div class="compare-pricing">
            <div class="final-price">$${item.finalPrice.toFixed(2)}</div>
            <div class="compare-unit">${item.unit}</div>
            ${item.originalPrice > item.price ? `<div class="original-price">$${item.originalPrice.toFixed(2)}</div>` : ''}
            ${item.couponDiscount > 0 ? `<div class="coupon-tag">-$${item.couponDiscount.toFixed(2)} coupon</div>` : ''}
            ${savings ? `<div class="savings-badge">${savings}</div>` : ''}
          </div>
        </div>`;
    }).join('');
  }

  // --- Flyers ---
  const storeFilter = document.getElementById('store-filter');
  const categoryFilter = document.getElementById('category-filter');
  const saleFilter = document.getElementById('sale-filter');
  const flyerSearch = document.getElementById('flyer-search');
  const flyerGrid = document.getElementById('flyer-grid');

  [storeFilter, categoryFilter, saleFilter, flyerSearch].forEach(el => {
    el.addEventListener('change', loadFlyers);
    if (el.tagName === 'INPUT' && el.type === 'text') el.addEventListener('input', loadFlyers);
  });

  async function loadFlyers() {
    const params = new URLSearchParams();
    if (storeFilter.value) params.set('storeId', storeFilter.value);
    if (categoryFilter.value) params.set('category', categoryFilter.value);
    if (saleFilter.checked) params.set('onSale', 'true');
    if (flyerSearch.value) params.set('search', flyerSearch.value);

    const items = await fetchJSON(`/api/flyer-items?${params}`);
    const storeMap = {};
    stores.forEach(s => { storeMap[s.id] = s; });

    if (items.length === 0) {
      flyerGrid.innerHTML = `
        <div class="empty-state">
          <div class="emoji">📭</div>
          <p>No flyer items match your filters.</p>
        </div>`;
      return;
    }

    flyerGrid.innerHTML = items.map(item => {
      const store = storeMap[item.storeId] || {};
      return `
        <div class="flyer-card" style="border-top-color: ${store.color || '#ccc'}">
          ${item.onSale ? '<div class="sale-tag">Sale</div>' : ''}
          <div class="store-row">
            <span class="store-emoji">${store.logo || ''}</span>
            <span class="store-label">${store.name || item.storeId}</span>
          </div>
          <div class="item-name">${item.name}</div>
          <span class="item-category">${item.category}</span>
          <div class="price-row">
            <span class="sale-price">$${item.price.toFixed(2)}</span>
            ${item.originalPrice > item.price ? `<span class="reg-price">$${item.originalPrice.toFixed(2)}</span>` : ''}
            <span class="unit">${item.unit}</span>
          </div>
          <div class="item-description">${item.description}</div>
          <div class="valid-dates">Valid: ${item.validFrom} to ${item.validTo}</div>
        </div>`;
    }).join('');
  }

  // --- Coupons (localStorage) ---
  const addCouponBtn = document.getElementById('add-coupon-btn');
  const couponForm = document.getElementById('coupon-form');
  const couponFormEl = document.getElementById('coupon-form-el');
  const cancelCoupon = document.getElementById('cancel-coupon');
  const couponList = document.getElementById('coupon-list');

  addCouponBtn.addEventListener('click', () => {
    couponForm.classList.remove('hidden');
    couponFormEl.reset();
    document.getElementById('coupon-form-title').textContent = 'Add New Coupon';
    couponFormEl.dataset.editId = '';
  });

  cancelCoupon.addEventListener('click', () => {
    couponForm.classList.add('hidden');
  });

  couponFormEl.addEventListener('submit', (e) => {
    e.preventDefault();
    const data = {
      id: couponFormEl.dataset.editId || crypto.randomUUID(),
      storeId: document.getElementById('coupon-store').value,
      productName: document.getElementById('coupon-product').value,
      discountType: document.getElementById('coupon-discount-type').value,
      discountValue: document.getElementById('coupon-discount-value').value,
      code: document.getElementById('coupon-code').value,
      description: document.getElementById('coupon-desc').value,
      validFrom: document.getElementById('coupon-valid-from').value,
      validTo: document.getElementById('coupon-valid-to').value
    };

    const coupons = getLocalCoupons();
    const editId = couponFormEl.dataset.editId;
    if (editId) {
      const idx = coupons.findIndex(c => c.id === editId);
      if (idx !== -1) coupons[idx] = data;
      showToast('Coupon updated!', 'success');
    } else {
      coupons.push(data);
      showToast('Coupon added!', 'success');
    }

    saveLocalCoupons(coupons);
    couponForm.classList.add('hidden');
    loadCoupons();
  });

  function loadCoupons() {
    const coupons = getLocalCoupons();
    const storeMap = {};
    stores.forEach(s => { storeMap[s.id] = s; });

    if (coupons.length === 0) {
      couponList.innerHTML = `
        <div class="empty-state">
          <div class="emoji">🎟️</div>
          <p>No coupons yet. Add coupons to see them applied to price comparisons!</p>
        </div>`;
      return;
    }

    couponList.innerHTML = coupons.map(c => {
      const store = storeMap[c.storeId] || {};
      const discountDisplay = c.discountType === 'fixed'
        ? `$${parseFloat(c.discountValue).toFixed(2)} off`
        : `${c.discountValue}% off`;

      return `
        <div class="coupon-card">
          <div class="coupon-store">${store.logo || ''} ${store.name || c.storeId}</div>
          <div class="coupon-product">${c.productName}</div>
          <div class="coupon-discount">${discountDisplay}</div>
          ${c.code ? `<div class="coupon-code">${c.code}</div>` : ''}
          ${c.description ? `<div class="coupon-desc">${c.description}</div>` : ''}
          <div class="coupon-dates">${c.validFrom ? 'Valid: ' + c.validFrom : ''}${c.validTo ? ' to ' + c.validTo : ''}</div>
          <div class="coupon-actions">
            <button class="btn-secondary btn-small" onclick="editCoupon('${c.id}')">Edit</button>
            <button class="btn-danger btn-small" onclick="deleteCoupon('${c.id}')">Delete</button>
          </div>
        </div>`;
    }).join('');
  }

  window.editCoupon = function(id) {
    const coupons = getLocalCoupons();
    const c = coupons.find(x => x.id === id);
    if (!c) return;

    couponForm.classList.remove('hidden');
    document.getElementById('coupon-form-title').textContent = 'Edit Coupon';
    document.getElementById('coupon-store').value = c.storeId;
    document.getElementById('coupon-product').value = c.productName;
    document.getElementById('coupon-discount-type').value = c.discountType;
    document.getElementById('coupon-discount-value').value = c.discountValue;
    document.getElementById('coupon-code').value = c.code || '';
    document.getElementById('coupon-desc').value = c.description || '';
    document.getElementById('coupon-valid-from').value = c.validFrom || '';
    document.getElementById('coupon-valid-to').value = c.validTo || '';
    couponFormEl.dataset.editId = id;
  };

  window.deleteCoupon = function(id) {
    if (!confirm('Delete this coupon?')) return;
    const coupons = getLocalCoupons().filter(c => c.id !== id);
    saveLocalCoupons(coupons);
    showToast('Coupon deleted', 'success');
    loadCoupons();
  };

  // --- Shopping List ---
  const shoppingTextarea = document.getElementById('shopping-textarea');
  const scanFlyersBtn = document.getElementById('scan-flyers-btn');
  const clearShoppingBtn = document.getElementById('clear-shopping-list');
  const shoppingResults = document.getElementById('shopping-results');
  const shoppingScanResults = document.getElementById('shopping-scan-results');
  const shoppingItemCount = document.getElementById('shopping-item-count');

  // Load saved list from localStorage
  const savedList = localStorage.getItem('shopping-list-text');
  if (savedList) shoppingTextarea.value = savedList;

  // Update item count as user types
  shoppingTextarea.addEventListener('input', () => {
    const items = getShoppingItems();
    shoppingItemCount.textContent = `${items.length} item${items.length !== 1 ? 's' : ''}`;
    localStorage.setItem('shopping-list-text', shoppingTextarea.value);
  });

  // Trigger initial count
  shoppingTextarea.dispatchEvent(new Event('input'));

  clearShoppingBtn.addEventListener('click', () => {
    shoppingTextarea.value = '';
    shoppingResults.classList.add('hidden');
    shoppingItemCount.textContent = '0 items';
    localStorage.removeItem('shopping-list-text');
    showToast('Shopping list cleared', 'success');
  });

  function getShoppingItems() {
    return shoppingTextarea.value
      .split('\n')
      .map(line => line.trim())
      .filter(line => line.length > 0);
  }

  scanFlyersBtn.addEventListener('click', scanFlyers);

  async function scanFlyers() {
    const items = getShoppingItems();
    if (items.length === 0) {
      showToast('Add some items to your list first!', 'error');
      return;
    }

    localStorage.setItem('shopping-list-text', shoppingTextarea.value);

    shoppingResults.classList.remove('hidden');
    shoppingScanResults.innerHTML = `
      <div class="empty-state">
        <div class="emoji">🔍</div>
        <p>Scanning flyers for ${items.length} item(s)...</p>
      </div>`;
    document.getElementById('best-store-section').classList.add('hidden');

    const coupons = getLocalCoupons();
    const storeMap = {};
    stores.forEach(s => { storeMap[s.id] = s; });

    // --- Per-item best price (across all stores) ---
    let totalBestPrice = 0;
    let totalOriginalPrice = 0;
    let foundCount = 0;
    let notFoundCount = 0;
    const itemResults = [];

    for (const itemName of items) {
      const results = await fetchJSON(`/api/compare?product=${encodeURIComponent(itemName)}`);

      results.forEach(r => {
        const term = itemName.toLowerCase();
        const applicableCoupons = coupons.filter(c =>
          c.storeId === r.storeId &&
          c.productName.toLowerCase().includes(term) &&
          (!c.validTo || new Date(c.validTo) >= new Date())
        );
        const couponDiscount = applicableCoupons.reduce((sum, c) => {
          if (c.discountType === 'fixed') return sum + parseFloat(c.discountValue);
          if (c.discountType === 'percentage') return sum + (r.price * parseFloat(c.discountValue) / 100);
          return sum;
        }, 0);
        r.couponDiscount = Math.round(couponDiscount * 100) / 100;
        r.finalPrice = Math.round(Math.max(0, r.price - couponDiscount) * 100) / 100;
        r.appliedCoupons = applicableCoupons;
      });

      results.sort((a, b) => a.finalPrice - b.finalPrice);
      const best = results[0] || null;
      if (best) {
        foundCount++;
        totalBestPrice += best.finalPrice;
        totalOriginalPrice += best.originalPrice || best.price;
      } else {
        notFoundCount++;
      }
      itemResults.push({ itemName, results, best });
    }

    const totalSavings = Math.max(0, totalOriginalPrice - totalBestPrice);

    // Update summary cards
    document.getElementById('shop-summary-found').textContent = foundCount;
    document.getElementById('shop-summary-notfound').textContent = notFoundCount;
    document.getElementById('shop-summary-total').textContent = `$${totalBestPrice.toFixed(2)}`;
    document.getElementById('shop-summary-savings').textContent = `$${totalSavings.toFixed(2)}`;

    // --- Best Single Store Recommendation ---
    try {
      const storeResults = await fetchJSON('/api/best-store', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ items })
      });

      // Apply local coupons to each store's results
      storeResults.forEach(sr => {
        let couponSavingsTotal = 0;
        sr.foundItems.forEach(fi => {
          const term = fi.searchTerm.toLowerCase();
          const applicableCoupons = coupons.filter(c =>
            c.storeId === sr.storeId &&
            c.productName.toLowerCase().includes(term) &&
            (!c.validTo || new Date(c.validTo) >= new Date())
          );
          const couponDiscount = applicableCoupons.reduce((sum, c) => {
            if (c.discountType === 'fixed') return sum + parseFloat(c.discountValue);
            if (c.discountType === 'percentage') return sum + (fi.price * parseFloat(c.discountValue) / 100);
            return sum;
          }, 0);
          fi.couponDiscount = Math.round(couponDiscount * 100) / 100;
          fi.finalPrice = Math.round(Math.max(0, fi.price - couponDiscount) * 100) / 100;
          fi.appliedCoupons = applicableCoupons;
          couponSavingsTotal += fi.couponDiscount;
        });
        sr.couponSavings = Math.round(couponSavingsTotal * 100) / 100;
        sr.total = Math.round(sr.foundItems.reduce((s, fi) => s + fi.finalPrice, 0) * 100) / 100
          + sr.missingItems.reduce((s, mi) => s + mi.estimatedPrice, 0);
        sr.total = Math.round(sr.total * 100) / 100;
        sr.totalSavings = Math.round((sr.flyerSavings + sr.couponSavings) * 100) / 100;
      });

      storeResults.sort((a, b) => a.total - b.total);

      if (storeResults.length > 0) {
        const bestStore = storeResults[0];
        const runnerUp = storeResults[1];
        const bestStoreSection = document.getElementById('best-store-section');
        bestStoreSection.classList.remove('hidden');

        document.getElementById('best-store-card').innerHTML = `
          <div class="rec-store-card" style="border-left-color: ${bestStore.storeColor}">
            <div class="rec-store-top">
              <span class="rec-store-logo">${bestStore.storeLogo}</span>
              <div class="rec-store-info">
                <div class="rec-store-name">${bestStore.storeName}</div>
                <div class="rec-store-subtitle">Cheapest single store for your entire list</div>
              </div>
              <div class="rec-store-total">
                <div class="rec-total-label">Estimated Total</div>
                <div class="rec-total-amount">$${bestStore.total.toFixed(2)}</div>
              </div>
            </div>
            <div class="rec-store-stats">
              <div class="rec-stat">
                <span class="rec-stat-label">Flyer Savings</span>
                <span class="rec-stat-value green">$${bestStore.flyerSavings.toFixed(2)}</span>
              </div>
              <div class="rec-stat">
                <span class="rec-stat-label">Coupon Savings</span>
                <span class="rec-stat-value green">$${bestStore.couponSavings.toFixed(2)}</span>
              </div>
              <div class="rec-stat">
                <span class="rec-stat-label">Total Savings</span>
                <span class="rec-stat-value green bold">$${bestStore.totalSavings.toFixed(2)}</span>
              </div>
              <div class="rec-stat">
                <span class="rec-stat-label">Items in Flyer</span>
                <span class="rec-stat-value">${bestStore.foundCount} / ${items.length}</span>
              </div>
              ${runnerUp ? `
              <div class="rec-stat">
                <span class="rec-stat-label">vs. ${runnerUp.storeName}</span>
                <span class="rec-stat-value green">Save $${Math.max(0, runnerUp.total - bestStore.total).toFixed(2)}</span>
              </div>` : ''}
            </div>
          </div>`;

        // Build breakdown table
        const allBreakdownItems = [
          ...bestStore.foundItems.map(fi => ({
            name: fi.name,
            searchTerm: fi.searchTerm,
            price: fi.finalPrice,
            originalPrice: fi.originalPrice,
            unit: fi.unit,
            onSale: fi.onSale,
            couponDiscount: fi.couponDiscount,
            inFlyer: true,
            source: 'flyer'
          })),
          ...bestStore.missingItems.map(mi => ({
            name: mi.name,
            searchTerm: mi.searchTerm,
            price: mi.estimatedPrice,
            originalPrice: mi.estimatedPrice,
            unit: mi.unit,
            onSale: false,
            couponDiscount: 0,
            inFlyer: false,
            source: mi.source
          }))
        ];

        document.getElementById('best-store-breakdown').innerHTML = `
          <div class="breakdown-title">Full Price Breakdown at ${bestStore.storeLogo} ${bestStore.storeName}</div>
          <table class="breakdown-table">
            <thead>
              <tr>
                <th>Item</th>
                <th>Source</th>
                <th>Regular</th>
                <th>You Pay</th>
                <th>Savings</th>
              </tr>
            </thead>
            <tbody>
              ${allBreakdownItems.map(item => {
                const saving = Math.max(0, item.originalPrice - item.price);
                return `
                  <tr class="${!item.inFlyer ? 'row-estimated' : ''}">
                    <td>
                      <div class="bd-item-name">${item.searchTerm}</div>
                      ${item.name !== item.searchTerm ? `<div class="bd-item-match">${item.name}</div>` : ''}
                    </td>
                    <td>
                      ${item.inFlyer
                        ? (item.onSale ? '<span class="scan-sale-tag">FLYER SALE</span>' : '<span class="bd-flyer-tag">FLYER</span>')
                        : (item.source === 'not found' ? '<span class="bd-none-tag">NOT FOUND</span>' : '<span class="bd-est-tag">EST. PRICE</span>')}
                      ${item.couponDiscount > 0 ? `<span class="scan-coupon-tag">-$${item.couponDiscount.toFixed(2)}</span>` : ''}
                    </td>
                    <td class="td-price">${item.originalPrice > 0 ? '$' + item.originalPrice.toFixed(2) : '—'}</td>
                    <td class="td-price td-final">${item.price > 0 ? '$' + item.price.toFixed(2) : '—'}${item.unit ? '<span class="bd-unit">/' + item.unit + '</span>' : ''}</td>
                    <td class="td-price ${saving > 0 ? 'td-saving' : ''}">${saving > 0 ? '-$' + saving.toFixed(2) : '—'}</td>
                  </tr>`;
              }).join('')}
            </tbody>
            <tfoot>
              <tr class="breakdown-total-row">
                <td colspan="3"><strong>Total at ${bestStore.storeName}</strong></td>
                <td class="td-price td-final"><strong>$${bestStore.total.toFixed(2)}</strong></td>
                <td class="td-price td-saving"><strong>-$${bestStore.totalSavings.toFixed(2)}</strong></td>
              </tr>
            </tfoot>
          </table>

          ${storeResults.length > 1 ? `
          <div class="other-stores-compare">
            <div class="other-stores-title">Other Store Totals</div>
            <div class="store-compare-chips">
              ${storeResults.slice(1, 5).map(sr => `
                <div class="store-total-chip">
                  <span class="stc-logo">${sr.storeLogo}</span>
                  <span class="stc-name">${sr.storeName}</span>
                  <span class="stc-total">$${sr.total.toFixed(2)}</span>
                  <span class="stc-diff">+$${(sr.total - bestStore.total).toFixed(2)} more</span>
                </div>
              `).join('')}
            </div>
          </div>` : ''}
        `;
      }
    } catch (err) {
      console.error('Best store API error:', err);
    }

    // --- Render per-item results ---
    shoppingScanResults.innerHTML = itemResults.map(({ itemName, results, best }) => {
      if (!best) {
        return `
          <div class="scan-item-card not-found">
            <div class="scan-item-name">${itemName}</div>
            <div class="scan-not-found">No matches found in current flyers</div>
          </div>`;
      }

      const bestStore = storeMap[best.storeId] || {};
      const hasCoupon = best.appliedCoupons && best.appliedCoupons.length > 0;
      const allCoupons = results.flatMap(r => (r.appliedCoupons || []).map(c => ({ ...c, storeName: (storeMap[c.storeId] || {}).name || c.storeId })));
      const otherOptions = results.slice(1, 4);

      return `
        <div class="scan-item-card">
          <div class="scan-item-top">
            <div class="scan-item-name">${itemName}</div>
            ${best.onSale ? '<span class="scan-sale-tag">ON SALE</span>' : ''}
            ${hasCoupon ? '<span class="scan-coupon-tag">COUPON</span>' : '<span class="scan-no-coupon-tag">NO COUPON</span>'}
          </div>

          <div class="scan-best-deal" style="border-left-color: ${bestStore.color || '#16a34a'}">
            <div class="scan-best-label">CHEAPEST</div>
            <div class="scan-best-content">
              <span class="scan-store-logo">${bestStore.logo || ''}</span>
              <div class="scan-best-details">
                <div class="scan-store-name">${bestStore.name || best.storeId}</div>
                <div class="scan-product-match">${best.name} &mdash; ${best.description || ''}</div>
              </div>
              <div class="scan-price-block">
                <div class="scan-final-price">$${best.finalPrice.toFixed(2)}</div>
                <div class="scan-unit">${best.unit}</div>
                ${best.originalPrice > best.finalPrice ? `<div class="scan-original-price">was $${best.originalPrice.toFixed(2)}</div>` : ''}
                ${best.couponDiscount > 0 ? `<div class="scan-coupon-savings">-$${best.couponDiscount.toFixed(2)} coupon</div>` : ''}
                ${best.originalPrice > best.finalPrice ? `<div class="scan-you-save">You save $${(best.originalPrice - best.finalPrice).toFixed(2)}</div>` : ''}
              </div>
            </div>
          </div>

          ${allCoupons.length > 0 ? `
            <div class="scan-coupons-row">
              <span class="scan-coupons-label">Available coupons:</span>
              ${allCoupons.map(c =>
                `<span class="coupon-tag">${c.discountType === 'fixed' ? '-$' + parseFloat(c.discountValue).toFixed(2) : '-' + c.discountValue + '%'}${c.code ? ' (' + c.code + ')' : ''} at ${c.storeName}</span>`
              ).join(' ')}
            </div>` : ''}

          ${otherOptions.length > 0 ? `
            <div class="scan-other-stores">
              <span class="scan-other-label">Other stores:</span>
              ${otherOptions.map(r => {
                const s = storeMap[r.storeId] || {};
                return `<span class="scan-other-chip">${s.logo || ''} ${s.name || r.storeId} <strong>$${r.finalPrice.toFixed(2)}</strong>/${r.unit}</span>`;
              }).join('')}
            </div>` : ''}
        </div>`;
    }).join('');
  }

  // --- Add Item (posts to server API, falls back for display) ---
  const addItemForm = document.getElementById('add-item-form');
  addItemForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const data = {
      storeId: document.getElementById('item-store').value,
      name: document.getElementById('item-name').value,
      category: document.getElementById('item-category').value,
      unit: document.getElementById('item-unit').value,
      price: document.getElementById('item-price').value,
      originalPrice: document.getElementById('item-original-price').value || document.getElementById('item-price').value,
      onSale: document.getElementById('item-on-sale').checked,
      validFrom: document.getElementById('item-valid-from').value,
      validTo: document.getElementById('item-valid-to').value,
      description: document.getElementById('item-description').value
    };

    try {
      await fetch('/api/flyer-items', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
    } catch (err) {
      // Serverless mode — item add may not persist, but that's OK
    }
    showToast('Flyer item added!', 'success');
    addItemForm.reset();
    document.getElementById('item-on-sale').checked = true;
    loadFlyers();
  });

  // --- Toast ---
  function showToast(message, type) {
    const toast = document.createElement('div');
    toast.className = `toast ${type || ''}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
  }

  init();
});
