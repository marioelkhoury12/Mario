const items = require('../data/flyer-items.json');

module.exports = (req, res) => {
  const products = [...new Set(items.map(i => i.name))].sort();
  res.json(products);
};
