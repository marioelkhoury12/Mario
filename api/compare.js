const items = require('../data/flyer-items.json');
const stores = require('../data/stores.json');

module.exports = (req, res) => {
  const { product } = req.query;
  if (!product) return res.status(400).json({ error: 'product query param required' });

  const term = product.toLowerCase();
  const matches = items.filter(i => i.name.toLowerCase().includes(term));

  const storeMap = {};
  stores.forEach(s => { storeMap[s.id] = s; });

  // In serverless mode, coupons are stored in localStorage on the client
  // so we just return items without coupon adjustments from server
  const coupons = [];

  const results = matches.map(item => {
    const store = storeMap[item.storeId] || {};
    return {
      ...item,
      storeName: store.name,
      storeLogo: store.logo,
      storeColor: store.color,
      couponDiscount: 0,
      finalPrice: item.price,
      appliedCoupons: []
    };
  });

  results.sort((a, b) => a.finalPrice - b.finalPrice);
  res.json(results);
};
