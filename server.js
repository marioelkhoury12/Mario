const express = require('express');
const fs = require('fs');
const path = require('path');
const { v4: uuidv4 } = require('uuid');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

function readJSON(filename) {
  return JSON.parse(fs.readFileSync(path.join(__dirname, 'data', filename), 'utf8'));
}

function writeJSON(filename, data) {
  fs.writeFileSync(path.join(__dirname, 'data', filename), JSON.stringify(data, null, 2));
}

// GET all stores
app.get('/api/stores', (req, res) => {
  const stores = readJSON('stores.json');
  res.json(stores);
});

// GET all flyer items, with optional filters
app.get('/api/flyer-items', (req, res) => {
  let items = readJSON('flyer-items.json');
  const { storeId, category, search, onSale } = req.query;

  if (storeId) {
    items = items.filter(i => i.storeId === storeId);
  }
  if (category) {
    items = items.filter(i => i.category === category);
  }
  if (search) {
    const term = search.toLowerCase();
    items = items.filter(i => i.name.toLowerCase().includes(term) || i.description.toLowerCase().includes(term));
  }
  if (onSale === 'true') {
    items = items.filter(i => i.onSale);
  }

  res.json(items);
});

// GET price comparison for a specific product name
app.get('/api/compare', (req, res) => {
  const { product } = req.query;
  if (!product) return res.status(400).json({ error: 'product query param required' });

  const items = readJSON('flyer-items.json');
  const stores = readJSON('stores.json');
  const coupons = readJSON('coupons.json');
  const term = product.toLowerCase();

  const matches = items.filter(i => i.name.toLowerCase().includes(term));

  const storeMap = {};
  stores.forEach(s => { storeMap[s.id] = s; });

  const results = matches.map(item => {
    const store = storeMap[item.storeId] || {};
    const applicableCoupons = coupons.filter(c =>
      c.storeId === item.storeId &&
      c.productName.toLowerCase().includes(term) &&
      new Date(c.validTo) >= new Date()
    );
    const couponDiscount = applicableCoupons.reduce((sum, c) => {
      if (c.discountType === 'fixed') return sum + c.discountValue;
      if (c.discountType === 'percentage') return sum + (item.price * c.discountValue / 100);
      return sum;
    }, 0);
    const finalPrice = Math.max(0, item.price - couponDiscount);

    return {
      ...item,
      storeName: store.name,
      storeLogo: store.logo,
      storeColor: store.color,
      couponDiscount: Math.round(couponDiscount * 100) / 100,
      finalPrice: Math.round(finalPrice * 100) / 100,
      appliedCoupons: applicableCoupons
    };
  });

  results.sort((a, b) => a.finalPrice - b.finalPrice);
  res.json(results);
});

// GET all categories
app.get('/api/categories', (req, res) => {
  const items = readJSON('flyer-items.json');
  const categories = [...new Set(items.map(i => i.category))].sort();
  res.json(categories);
});

// GET all unique product names
app.get('/api/products', (req, res) => {
  const items = readJSON('flyer-items.json');
  const products = [...new Set(items.map(i => i.name))].sort();
  res.json(products);
});

// --- Coupon CRUD ---
app.get('/api/coupons', (req, res) => {
  let coupons = readJSON('coupons.json');
  const { storeId } = req.query;
  if (storeId) {
    coupons = coupons.filter(c => c.storeId === storeId);
  }
  res.json(coupons);
});

app.post('/api/coupons', (req, res) => {
  const coupons = readJSON('coupons.json');
  const coupon = {
    id: uuidv4(),
    storeId: req.body.storeId,
    productName: req.body.productName,
    description: req.body.description || '',
    discountType: req.body.discountType || 'fixed',
    discountValue: parseFloat(req.body.discountValue) || 0,
    code: req.body.code || '',
    validFrom: req.body.validFrom || new Date().toISOString().split('T')[0],
    validTo: req.body.validTo || '',
    createdAt: new Date().toISOString()
  };
  coupons.push(coupon);
  writeJSON('coupons.json', coupons);
  res.status(201).json(coupon);
});

app.put('/api/coupons/:id', (req, res) => {
  const coupons = readJSON('coupons.json');
  const idx = coupons.findIndex(c => c.id === req.params.id);
  if (idx === -1) return res.status(404).json({ error: 'Coupon not found' });

  coupons[idx] = { ...coupons[idx], ...req.body, id: coupons[idx].id };
  writeJSON('coupons.json', coupons);
  res.json(coupons[idx]);
});

app.delete('/api/coupons/:id', (req, res) => {
  let coupons = readJSON('coupons.json');
  const idx = coupons.findIndex(c => c.id === req.params.id);
  if (idx === -1) return res.status(404).json({ error: 'Coupon not found' });

  coupons.splice(idx, 1);
  writeJSON('coupons.json', coupons);
  res.status(204).send();
});

// --- Flyer Item CRUD (for manual entry) ---
app.post('/api/flyer-items', (req, res) => {
  const items = readJSON('flyer-items.json');
  const item = {
    id: uuidv4(),
    storeId: req.body.storeId,
    name: req.body.name,
    category: req.body.category || 'Other',
    price: parseFloat(req.body.price) || 0,
    unit: req.body.unit || 'each',
    originalPrice: parseFloat(req.body.originalPrice) || parseFloat(req.body.price) || 0,
    onSale: req.body.onSale || false,
    validFrom: req.body.validFrom || new Date().toISOString().split('T')[0],
    validTo: req.body.validTo || '',
    description: req.body.description || ''
  };
  items.push(item);
  writeJSON('flyer-items.json', items);
  res.status(201).json(item);
});

app.delete('/api/flyer-items/:id', (req, res) => {
  let items = readJSON('flyer-items.json');
  const idx = items.findIndex(i => i.id === req.params.id);
  if (idx === -1) return res.status(404).json({ error: 'Item not found' });

  items.splice(idx, 1);
  writeJSON('flyer-items.json', items);
  res.status(204).send();
});

// GET best store recommendation for a shopping list
// POST body: { items: ["Chicken Breast", "Milk", ...] }
// Returns per-store totals and regular prices for items not found on sale
app.post('/api/best-store', (req, res) => {
  const { items: shoppingItems } = req.body;
  if (!shoppingItems || !Array.isArray(shoppingItems)) {
    return res.status(400).json({ error: 'items array required' });
  }

  const allItems = readJSON('flyer-items.json');
  const storesData = readJSON('stores.json');
  const coupons = readJSON('coupons.json');
  const storeMap = {};
  storesData.forEach(s => { storeMap[s.id] = s; });

  // For each store, calculate total cost if you bought everything there
  const storeResults = storesData.map(store => {
    let total = 0;
    let totalOriginal = 0;
    let flyerSavings = 0;
    let couponSavings = 0;
    const foundItems = [];
    const missingItems = [];

    shoppingItems.forEach(itemName => {
      const term = itemName.toLowerCase();
      // Find items matching this product at this store
      const storeMatches = allItems.filter(i =>
        i.storeId === store.id && i.name.toLowerCase().includes(term)
      );

      if (storeMatches.length > 0) {
        // Pick cheapest match at this store
        const best = storeMatches.sort((a, b) => a.price - b.price)[0];

        // Apply coupons
        const applicableCoupons = coupons.filter(c =>
          c.storeId === store.id &&
          c.productName.toLowerCase().includes(term) &&
          (!c.validTo || new Date(c.validTo) >= new Date())
        );
        const couponDiscount = applicableCoupons.reduce((sum, c) => {
          if (c.discountType === 'fixed') return sum + (typeof c.discountValue === 'number' ? c.discountValue : parseFloat(c.discountValue));
          if (c.discountType === 'percentage') return sum + (best.price * (typeof c.discountValue === 'number' ? c.discountValue : parseFloat(c.discountValue)) / 100);
          return sum;
        }, 0);

        const finalPrice = Math.round(Math.max(0, best.price - couponDiscount) * 100) / 100;
        const origPrice = best.originalPrice || best.price;

        total += finalPrice;
        totalOriginal += origPrice;
        flyerSavings += Math.max(0, origPrice - best.price);
        couponSavings += Math.round(couponDiscount * 100) / 100;

        foundItems.push({
          searchTerm: itemName,
          name: best.name,
          price: best.price,
          finalPrice,
          originalPrice: origPrice,
          unit: best.unit,
          onSale: best.onSale,
          couponDiscount: Math.round(couponDiscount * 100) / 100,
          appliedCoupons: applicableCoupons,
          description: best.description,
          category: best.category,
          inFlyer: true
        });
      } else {
        // Not in flyer for this store — find regular price from ANY store's originalPrice
        const anyMatch = allItems.filter(i => i.name.toLowerCase().includes(term));
        if (anyMatch.length > 0) {
          // Use the average originalPrice as the estimated regular price
          const avgOriginal = anyMatch.reduce((s, i) => s + (i.originalPrice || i.price), 0) / anyMatch.length;
          const estPrice = Math.round(avgOriginal * 100) / 100;
          total += estPrice;
          totalOriginal += estPrice;

          missingItems.push({
            searchTerm: itemName,
            name: anyMatch[0].name,
            estimatedPrice: estPrice,
            unit: anyMatch[0].unit,
            category: anyMatch[0].category,
            inFlyer: false,
            source: 'estimated from other stores'
          });
        } else {
          missingItems.push({
            searchTerm: itemName,
            name: itemName,
            estimatedPrice: 0,
            unit: '',
            category: '',
            inFlyer: false,
            source: 'not found'
          });
        }
      }
    });

    return {
      storeId: store.id,
      storeName: store.name,
      storeLogo: store.logo,
      storeColor: store.color,
      total: Math.round(total * 100) / 100,
      totalOriginal: Math.round(totalOriginal * 100) / 100,
      flyerSavings: Math.round(flyerSavings * 100) / 100,
      couponSavings: Math.round(couponSavings * 100) / 100,
      totalSavings: Math.round((flyerSavings + couponSavings) * 100) / 100,
      foundItems,
      missingItems,
      foundCount: foundItems.length,
      missingCount: missingItems.length
    };
  });

  storeResults.sort((a, b) => a.total - b.total);
  res.json(storeResults);
});

app.listen(PORT, () => {
  console.log(`Toronto Grocery Compare running at http://localhost:${PORT}`);
});
