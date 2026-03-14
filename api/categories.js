const items = require('../data/flyer-items.json');

module.exports = (req, res) => {
  const categories = [...new Set(items.map(i => i.category))].sort();
  res.json(categories);
};
