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
        var file = 'static/i18n/translation.json';
        var fileContents = grunt.file.readJSON(file);
        var englishTranslations = _.pluck(fileContents, 'translation')[0];
        var chineseTranslations = _.pluck(fileContents, 'translation')[1];
        var englishTranslationStack = [];
        var chineseTranslationStack = [];
       _.map(englishTranslations, function(el){
            englishTranslationStack.push(_.keys(el));
            return _.map(el, function(el2) {
                return (_.isObject(el2)) ? englishTranslationStack.push(_.keys(el2)) : el2;
            });
        });
       _.map(chineseTranslations, function(el){
           chineseTranslationStack.push(_.keys(el));
           return _.map(el, function(el2) {
               return (_.isObject(el2)) ? chineseTranslationStack.push(_.keys(el2)) : el2;
           });
       });
        for (var i= 0; i<englishTranslationStack.length; i++) {
            for (var j=0; j<chineseTranslationStack.length; j++) {
                if (i==j) {
                     if (englishTranslationStack[i].length != chineseTranslationStack[j].length) {
                         var translationsHavingMoreKeys,
                             translationHavingLessKeys;
                         if (englishTranslationStack[i].length > chineseTranslationStack[j].length) {
                             translationsHavingMoreKeys = englishTranslationStack[i];
                             translationHavingLessKeys = chineseTranslationStack[j];
                         } else {
                             translationsHavingMoreKeys = englishTranslationStack[i];
                             translationHavingLessKeys = chineseTranslationStack[j];
                         }
                         _.each(translationsHavingMoreKeys, function (key) {
                             if (_.indexOf(translationHavingLessKeys, key) < 0) {
                                   grunt.log.errorlns('Mismatches found! The missing key - '+ key);
                             }
                         });
                    }
                }
            }
        }
    });
};
