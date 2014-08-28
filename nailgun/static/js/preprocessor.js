// preprocessor.js
var ReactTools = require('react-tools');
module.exports = {
  process: function(src) {
    src = '/** @jsx React.DOM */' + src;
    return ReactTools.transform(src);
  }
};