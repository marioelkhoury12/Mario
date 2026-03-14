const stores = require('../data/stores.json');

module.exports = (req, res) => {
  res.json(stores);
};
