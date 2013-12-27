'use strict';

module.exports = function(grunt) {
    var _ = require('lodash-node');

    grunt.registerTask('validate_translations', 'Comparing the keys in translation.json file. Can accept different ' +
        'languages via ","', function(params) {
        //default language to compare - Chinese
        var options = _.isUndefined(params) ? 'Chinese': (_.indexOf(params,',') > 0) ? params.split(',') : params;
        var existingTranslationLanguages = ['Chinese'];
        grunt.log.writeln('translations language: ' + options);
        var file = 'static/i18n/translation.json',
            globalValues = {};
        _.each(options, function(lang){
            switch (lang) {
                case 'Chinese':
                     initializeChinese();
                    break;
                default:
                    grunt.log.errorlns('No language, named ' + lang + ' found!');
            }
        });

        function initializeChinese() {
            var fileContents = grunt.file.readJSON(file),
                englishTranslations = _.pluck(fileContents, 'translation')[0],
                chineseTranslations = _.pluck(fileContents, 'translation')[1];
            globalValues.languageToCompareToEnglish = 'Chinese';
            globalValues.viceVersaComparison = false;
            initializeForCalculation(englishTranslations, chineseTranslations);
            globalValues.viceVersaComparison = true;
            initializeForCalculation(chineseTranslations, englishTranslations);
        }

        function initializeForCalculation(obj1, obj2) {
            globalValues.stackedValues = [];
            globalValues.path = [];
            globalValues.arrayToCompareWith = obj2;
            globalValues.missingKeys = [];
            grunt.log.writeln();
            grunt.log.writeln('Comparing translation keys...');
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
                ? grunt.log.errorlns('The list of keys present in ' + globalValues.languageToCompareToEnglish + ' but absent in English:')
                : grunt.log.errorlns('The list of keys missing in ' + globalValues.languageToCompareToEnglish + ':');
            _.each(globalValues.missingKeys, function(elem) {
                grunt.log.writeln(elem);
            });
        }
    });
};