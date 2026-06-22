// Transform the frontend's native ES modules to CommonJS so Jest can run them.
module.exports = {
  presets: [['@babel/preset-env', { targets: { node: 'current' } }]],
};
