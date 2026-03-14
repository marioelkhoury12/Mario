const allItems = require('../data/flyer-items.json');

module.exports = (req, res) => {
  let items = [...allItems];
  const { storeId, category, search, onSale } = req.query;

  if (storeId) items = items.filter(i => i.storeId === storeId);
  if (category) items = items.filter(i => i.category === category);
  if (search) {
    const term = search.toLowerCase();
    items = items.filter(i => i.name.toLowerCase().includes(term) || i.description.toLowerCase().includes(term));
  }
  if (onSale === 'true') items = items.filter(i => i.onSale);

  res.json(items);
};
