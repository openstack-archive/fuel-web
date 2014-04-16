'use strict';

module.exports = function(grunt) {
    var _ = require('lodash-node');

    grunt.registerTask('i18n', 'Search for missing keys from different locales in translation.json', function(task, param) {
        if (task == 'validate') {
            startValidationTask(param);
        }

        function startValidationTask(param) {
            var baseLocale = 'en-US';
            var translations = grunt.file.readJSON('static/i18n/translation.json');
            var existingLocales = _.keys(translations);
            var locales = param ? param.split(',') : existingLocales;

            var processedTranslations = {};
            function processTranslations(translations) {
                function processPiece(base, piece) {
                    return _.map(piece, function(value, key) {
                        var localBase = base ? base + '.' + key : key;
                        return _.isPlainObject(value) ? processPiece(localBase, value) : localBase;
                    });
                }
                return _.uniq(_.flatten(processPiece(null, translations.translation))).sort();
            }
            _.each(_.union(locales, [baseLocale]), function(locale) {
                processedTranslations[locale] = processTranslations(translations[locale]);
            });

            function compareLocales(locale1, locale2) {
                return _.without.apply(null, [processedTranslations[locale1]].concat(processedTranslations[locale2]));
            }
            _.each(_.without(locales, baseLocale), function(locale) {
                grunt.log.errorlns('The list of keys present in %s but absent in %s:', baseLocale, locale);
                grunt.log.writeln(compareLocales(baseLocale, locale).join('\n'));
                grunt.log.errorlns('The list of keys missing in %s:', baseLocale);
                grunt.log.writeln(compareLocales(locale, baseLocale).join('\n'));
            });

        }
    });
};