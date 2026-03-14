// In serverless/static deployment, coupons are managed client-side via localStorage
// This endpoint returns an empty array as a fallback
module.exports = (req, res) => {
  res.json([]);
};
