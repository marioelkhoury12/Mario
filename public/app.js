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

  async function fetchJSON(url) {
    const res = await fetch(url);
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
    if (results.length === 0) {
      compareResults.innerHTML = `
        <div class="empty-state">
          <div class="emoji">🔍</div>
          <p>No results found for "${product}". Try a different search term or add items manually.</p>
        </div>`;
      return;
    }

    const cheapest = results[0].finalPrice;
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
              `<span class="coupon-tag">Coupon: -$${c.discountType === 'fixed' ? c.discountValue.toFixed(2) : c.discountValue + '%'}${c.code ? ' (' + c.code + ')' : ''}</span>`
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

  // --- Coupons ---
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

  couponFormEl.addEventListener('submit', async (e) => {
    e.preventDefault();
    const data = {
      storeId: document.getElementById('coupon-store').value,
      productName: document.getElementById('coupon-product').value,
      discountType: document.getElementById('coupon-discount-type').value,
      discountValue: document.getElementById('coupon-discount-value').value,
      code: document.getElementById('coupon-code').value,
      description: document.getElementById('coupon-desc').value,
      validFrom: document.getElementById('coupon-valid-from').value,
      validTo: document.getElementById('coupon-valid-to').value
    };

    const editId = couponFormEl.dataset.editId;
    if (editId) {
      await fetch(`/api/coupons/${editId}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
      showToast('Coupon updated!', 'success');
    } else {
      await fetch('/api/coupons', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
      showToast('Coupon added!', 'success');
    }

    couponForm.classList.add('hidden');
    loadCoupons();
  });

  async function loadCoupons() {
    const coupons = await fetchJSON('/api/coupons');
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

  window.editCoupon = async function(id) {
    const coupons = await fetchJSON('/api/coupons');
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

  window.deleteCoupon = async function(id) {
    if (!confirm('Delete this coupon?')) return;
    await fetch(`/api/coupons/${id}`, { method: 'DELETE' });
    showToast('Coupon deleted', 'success');
    loadCoupons();
  };

  // --- Add Item ---
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

    await fetch('/api/flyer-items', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
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
