'use strict';

module.exports = function(grunt) {
    var _ = require('lodash-node');

    grunt.registerTask('i18n', 'Search for missing keys from different locales in translation.json', function(task, param) {
        if (task == 'validate') {
            startValidationTask(param);
        }

        function startValidationTask(language) {
             var file = 'static/i18n/translation.json',
                 globalValues = {},
                 fileContents = grunt.file.readJSON(file),
                 existingTranslationLanguages = _.keys(fileContents),
                 optionsLang = _.isUndefined(language) ? existingTranslationLanguages : (_.indexOf(language,',') > 0) ? language.split(',') : language;
            globalValues.baseLang = 'en-US';

            if (_.isArray(optionsLang)) {
                _.each(optionsLang, function(lang){
                    initializeLanguage(lang, fileContents);
                });
            }
            else {
                initializeLanguage(optionsLang, fileContents);
            }

            function initializeLanguage(language, fileContent) {
                var englishTranslations,
                    comparingTranslations;
                if (_.indexOf(_.keys(fileContent), language) < 0) {
                    grunt.log.errorlns('No language named ' + language + ' found!');
                }
                else {
                    englishTranslations = _.first(_.pluck(_.pick(fileContent, globalValues.baseLang), 'translation'));
                    comparingTranslations = _.first(_.pluck(_.pick(fileContent, language), 'translation'));
                    globalValues.languageToCompareToEnglish = language;
                    globalValues.viceVersaComparison = false;
                    initializeForCalculation(englishTranslations, comparingTranslations);
                    globalValues.viceVersaComparison = true;
                    initializeForCalculation(comparingTranslations, englishTranslations);
                }
            }

            function initializeForCalculation(obj1, obj2) {
                globalValues.stackedKeys = [];
                globalValues.arrayToCompareWith = obj2;
                globalValues.missingKeys = [];
                globalValues.currentDepth = globalValues.arrayToCompareWith;
                compare(obj1);
                if (globalValues.missingKeys.length) displayMissingKeys();
            }

            function compare(obj) {
                _.each(obj, function (value, key) {
                    if (!_.isArray(value)) {
                        if (!_.contains(_.keys(getLastObject()), key)) {
                            globalValues.missingKeys.push(globalValues.stackedKeys.join('.')+'.'+key);
                        }
                        else {
                            if (_.isObject(value)) {
                                globalValues.stackedKeys.push(key);
                                compare(value);
                                globalValues.stackedKeys.pop();
                            }
                        }
                    }
                });
            }

            function getLastObject() {
                var temp = globalValues.arrayToCompareWith;
                _.each(globalValues.stackedKeys, function (elem) {
                    temp = temp[elem];
                }, this);
                return temp;
            }

            function displayMissingKeys() {
                grunt.log.writeln();
                (globalValues.viceVersaComparison)
                    ? grunt.log.errorlns('The list of keys present in ' + globalValues.languageToCompareToEnglish + ' but absent in '+ globalValues.baseLang + ':')
                    : grunt.log.errorlns('The list of keys missing in ' + globalValues.languageToCompareToEnglish + ':');
                _.each(globalValues.missingKeys, function(elem) {
                    grunt.log.writeln(elem);
                });
            }
        }
    });
};