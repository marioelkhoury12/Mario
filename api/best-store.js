const allItems = require('../data/flyer-items.json');
const storesData = require('../data/stores.json');

module.exports = (req, res) => {
  if (req.method !== 'POST') return res.status(405).json({ error: 'POST required' });

  const { items: shoppingItems } = req.body || {};
  if (!shoppingItems || !Array.isArray(shoppingItems)) {
    return res.status(400).json({ error: 'items array required' });
  }

  // In serverless mode, coupons are in localStorage on the client
  const coupons = [];

  const storeResults = storesData.map(store => {
    let total = 0;
    let totalOriginal = 0;
    let flyerSavings = 0;
    const foundItems = [];
    const missingItems = [];

    shoppingItems.forEach(itemName => {
      const term = itemName.toLowerCase();
      const storeMatches = allItems.filter(i =>
        i.storeId === store.id && i.name.toLowerCase().includes(term)
      );

      if (storeMatches.length > 0) {
        const best = storeMatches.sort((a, b) => a.price - b.price)[0];
        const origPrice = best.originalPrice || best.price;
        total += best.price;
        totalOriginal += origPrice;
        flyerSavings += Math.max(0, origPrice - best.price);

        foundItems.push({
          searchTerm: itemName,
          name: best.name,
          price: best.price,
          finalPrice: best.price,
          originalPrice: origPrice,
          unit: best.unit,
          onSale: best.onSale,
          couponDiscount: 0,
          appliedCoupons: [],
          description: best.description,
          category: best.category,
          inFlyer: true
        });
      } else {
        const anyMatch = allItems.filter(i => i.name.toLowerCase().includes(term));
        if (anyMatch.length > 0) {
          const avgOriginal = anyMatch.reduce((s, i) => s + (i.originalPrice || i.price), 0) / anyMatch.length;
          const estPrice = Math.round(avgOriginal * 100) / 100;
          total += estPrice;
          totalOriginal += estPrice;
          missingItems.push({
            searchTerm: itemName, name: anyMatch[0].name, estimatedPrice: estPrice,
            unit: anyMatch[0].unit, category: anyMatch[0].category, inFlyer: false, source: 'estimated from other stores'
          });
        } else {
          missingItems.push({
            searchTerm: itemName, name: itemName, estimatedPrice: 0,
            unit: '', category: '', inFlyer: false, source: 'not found'
          });
        }
      }
    });

    return {
      storeId: store.id, storeName: store.name, storeLogo: store.logo, storeColor: store.color,
      total: Math.round(total * 100) / 100,
      totalOriginal: Math.round(totalOriginal * 100) / 100,
      flyerSavings: Math.round(flyerSavings * 100) / 100,
      couponSavings: 0,
      totalSavings: Math.round(flyerSavings * 100) / 100,
      foundItems, missingItems,
      foundCount: foundItems.length, missingCount: missingItems.length
    };
  });

  storeResults.sort((a, b) => a.total - b.total);
  res.json(storeResults);
};
