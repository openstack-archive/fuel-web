'use strict';

module.exports = function(grunt) {
    var _ = require('lodash-node');

    grunt.registerTask('i18n', 'Comparing the keys in translation.json file with English. Can accept different ' +
        'languages via ","', function(task, param) {
        if (task == 'validate') {
            startValidationTask(param);
        }

        function startValidationTask(language) {

            //default language to compare - Chinese
            var optionsLang = _.isUndefined(language) ? 'zh-CN': (_.indexOf(language,',') > 0) ? language.split(',') : language;
            var existingTranslationLanguages = ['zh-CN'];
            grunt.log.writeln('translations language: ' + optionsLang);
            var file = 'static/i18n/translation.json',
                globalValues = {};
            if (_.isArray(optionsLang)) {
                _.each(optionsLang, function(lang){
                    initializeLanguage(lang);
                });
            }
            else {
                initializeLanguage(optionsLang);
            }

            function initializeLanguage(language) {
                var fileContents = grunt.file.readJSON(file),
                    englishTranslations,
                    comparingTranslations;
                if (_.indexOf(_.keys(fileContents), language) < 0) {
                    grunt.log.errorlns('No language, named ' + language + ' found!');
                }
                else {
                    englishTranslations = _.first(_.pluck(_.pick(fileContents, 'en-US'), 'translation'));
                    comparingTranslations = _.first(_.pluck(_.pick(fileContents, language), 'translation'));
                    globalValues.languageToCompareToEnglish = language;
                    globalValues.viceVersaComparison = false;
                    initializeForCalculation(englishTranslations, comparingTranslations);
                    globalValues.viceVersaComparison = true;
                    initializeForCalculation(comparingTranslations, englishTranslations);
                }
            }

            function initializeForCalculation(obj1, obj2) {
                globalValues.stackedValues = [];
                globalValues.path = [];
                globalValues.arrayToCompareWith = obj2;
                globalValues.missingKeys = [];
                grunt.log.writeln();
                grunt.log.writeln('Comparing translation keys with en-US translations...');
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
                _.each(globalValues.stackedValues, function (elem, index) {
                    temp = temp[elem];
                }, this);
                return temp;
            }

            function displayMissingKeys() {
                (globalValues.viceVersaComparison)
                    ? grunt.log.errorlns('The list of keys present in ' + globalValues.languageToCompareToEnglish + ' but absent in en-US:')
                    : grunt.log.errorlns('The list of keys missing in ' + globalValues.languageToCompareToEnglish + ':');
                _.each(globalValues.missingKeys, function(elem) {
                    grunt.log.writeln(elem);
                });
            }
        }
    });
};