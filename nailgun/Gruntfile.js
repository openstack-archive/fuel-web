/*
 * Copyright 2013 Mirantis, Inc.
 *
 * Licensed under the Apache License, Version 2.0 (the "License"); you may
 * not use this file except in compliance with the License. You may obtain
 * a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
 * WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
 * License for the specific language governing permissions and limitations
 * under the License.
 **/
module.exports = function(grunt) {
    grunt.initConfig({
        pkg: grunt.file.readJSON('package.json'),
        requirejs: {
            compile: {
                options: {
                    baseUrl: '.',
                    appDir: 'static',
                    dir: grunt.option('static-dir') || '/tmp/static_compressed',
                    mainConfigFile: 'static/js/main.js',
                    waitSeconds: 60,
                    optimize: 'uglify2',
                    optimizeCss: 'standard',
                    pragmas: {
                        compressed: true
                    },
                    map: {
                        '*': {
                            'css': 'require-css'
                        }
                    },
                    modules: [
                        {
                            name: 'js/main',
                            exclude: ['css/normalize']
                        }
                    ]
                }
            }
        },
        jslint: {
            client: {
                src: [
                    'static/js/*.js',
                    'static/js/views/**/*.js',
                ],
                directives: {
                    predef: ['requirejs', 'require', 'define', 'app', 'Backbone', '$', '_'],
                    ass: true,
                    browser: true,
                    unparam: true,
                    nomen: true,
                    eqeq: true,
                    vars: true,
                    white: true,
                    es5: false
                }
            }
        },
        less: {
            all: {
                src: 'static/css/styles.less',
                dest: 'static/css/styles.css',
            }
        },
        bower: {
            install: {
                options: {
                    //set install to true to load Bower packages from inet
                    install: true,
                    targetDir: 'static/js/libs/bower',
                    verbose: true,
                    cleanTargetDir: false,
                    cleanBowerDir: true,
                    layout: "byComponent",
                    bowerOptions: {
                        production: true,
                        install: '--offline'
                    }
                }
            }
        }
    });

    grunt.loadNpmTasks('grunt-contrib-requirejs');
    grunt.loadNpmTasks('grunt-contrib-less');
    grunt.loadNpmTasks('grunt-jslint');
    grunt.loadNpmTasks('grunt-bower-task');
    grunt.loadNpmTasks('grunt-debug-task');
    grunt.registerTask('build', ['bower', 'less', 'requirejs']);
    grunt.registerTask('default', ['build']);
    grunt.registerTask('validate_translations', function() {
        var _ = require('lodash-node');
        var file = 'static/i18n/translation.json',
            fileContents = grunt.file.readJSON(file),
            englishTranslations = _.pluck(fileContents, 'translation')[0],
            chineseTranslations = _.pluck(fileContents, 'translation')[1],
            GlobalValues = {};
        GlobalValues.languageToCompareToEnglish = 'Chinese';
        GlobalValues.viceVersaComparison = false;
        initializeForCalculation(englishTranslations, chineseTranslations);

        GlobalValues.viceVersaComparison = true;
        initializeForCalculation(chineseTranslations, englishTranslations);

        function initializeForCalculation(obj1, obj2) {
            GlobalValues.stackedValues = [];
            GlobalValues.path = [];
            GlobalValues.arrayToCompareWith = obj2;
            GlobalValues.missingKeys = [];
            grunt.log.writeln();
            grunt.log.writeln('Comparing translation keys...');
            grunt.log.writeln();
            compare(obj1);
            (GlobalValues.missingKeys.length) ? displayMissingKeys() : grunt.log.oklns('No mismatches found!');
        }
        function compare(obj) {
            _.each(obj, function (value, key) {
                if (!_.isArray(value)) {
                    if (!_.contains(_.keys(getLastObject()), key)) {
                        GlobalValues.missingKeys.push(GlobalValues.stackedValues.join('.')+'.'+key);
                    }
                    else {
                        if (_.isObject(value)) {
                            GlobalValues.stackedValues.push(key);
                            compare(value);
                            GlobalValues.stackedValues.pop();
                        }
                    }
                }
            });
        }
        function getLastObject() {
            var temp = GlobalValues.arrayToCompareWith;
            _.each(GlobalValues.stackedValues, function (elem, index) {
                temp = temp[elem];
            }, this);
            return temp;
        }
        function displayMissingKeys() {
            (GlobalValues.viceVersaComparison)
                ? grunt.log.errorlns('The list of keys present in ' + GlobalValues.languageToCompareToEnglish + ' but absent in English:')
                : grunt.log.errorlns('The list of keys missing in ' + GlobalValues.languageToCompareToEnglish + ':');
            _.each(GlobalValues.missingKeys, function(elem) {
                grunt.log.writeln(elem);
            });
        }
    });
};
