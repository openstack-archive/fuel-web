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
                    grunt.log.writeln('Analyzing locale: ' + language);
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
                globalValues.stackedValues = [];
                globalValues.arrayToCompareWith = obj2;
                globalValues.missingKeys = [];
                globalValues.currentDepth = globalValues.arrayToCompareWith;
                grunt.log.writeln();
                grunt.log.writeln('Comparing translation keys with ' +  globalValues.baseLang + ' translations...');
                grunt.log.writeln();
                compare(obj1);
                (globalValues.missingKeys.length) ? displayMissingKeys() : grunt.log.oklns('No mismatches found!');
            }

            function compare(obj) {
                _.each(obj, function (value, key) {
                    if (!_.isArray(value)) {
                        if (!_.contains(_.keys(getLastObject()), key)) {
                            globalValues.missingKeys.push(globalValues.stackedValues.join('.')+'.'+key);
                        }
                        else {
                            if (_.isObject(value)) {
                                globalValues.stackedValues.push(key);
                                compare(value);
                                globalValues.stackedValues.pop();
                            }
                        }
                    }
                });
            }

            function getLastObject() {
                var temp = globalValues.arrayToCompareWith;
                _.each(globalValues.stackedValues, function (elem) {
                    temp = temp[elem];
                }, this);
                return temp;
            }

            function displayMissingKeys() {
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