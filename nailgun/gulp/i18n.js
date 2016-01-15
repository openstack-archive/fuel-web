'use strict';

var fs = require('fs');
var gutil = require('gulp-util');
var _ = require('lodash');

function validate(translations, locales) {
  var processedTranslations = {};
  var baseLocale = 'en-US';
  var existingLocales = _.keys(translations);
  if (!locales) locales = existingLocales;

  function processTranslations(translations) {
    function processPiece(base, piece) {
      return _.map(piece, function(value, key) {
        var localBase = base ? base + '.' + key : key;
        return _.isPlainObject(value) ? processPiece(localBase, value) : localBase;
      });
    }
    return _.uniq(_.flatten(processPiece(null, translations.translation), true)).sort();
  }

  _.each(_.union(locales, [baseLocale]), function(locale) {
    processedTranslations[locale] = processTranslations(translations[locale]);
  });

  function compareLocales(locale1, locale2) {
    return _.without.apply(null, [processedTranslations[locale1]].concat(processedTranslations[locale2]));
  }

  _.each(_.without(locales, baseLocale), function(locale) {
    gutil.log(gutil.colors.red('The list of keys present in', baseLocale, 'but absent in', locale, ':\n') + compareLocales(baseLocale, locale).join('\n'));
    gutil.log(gutil.colors.red('The list of keys missing in', baseLocale, ':\n') + compareLocales(locale, baseLocale).join('\n'));
  });
}

module.exports = {validate: validate};
