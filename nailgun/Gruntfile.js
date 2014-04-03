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
    var staticDir = grunt.option('static-dir') || '/tmp/static_compressed';
    grunt.initConfig({
        pkg: grunt.file.readJSON('package.json'),
        requirejs: {
            compile: {
                options: {
                    baseUrl: '.',
                    appDir: 'static',
                    dir: staticDir,
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
        },
        clean: {
            trim: {
                expand: true,
                cwd: staticDir,
                src: [
                    '**/*.js',
                    '!js/main.js',
                    '!js/libs/bower/requirejs/js/require.js',
                    '**/*.css',
                    '**/*.less',
                    '!css/styles.css',
                    'templates',
                    'i18n'
                ]
            },
            options: {
                force: true
            }
        },
        cleanempty: {
            trim: {
                expand: true,
                cwd: staticDir,
                src: ['**']
            },
            options: {
                files: false,
                force: true
            }
        }
    });

    grunt.loadNpmTasks('grunt-contrib-requirejs');
    grunt.loadNpmTasks('grunt-contrib-less');
    grunt.loadNpmTasks('grunt-contrib-clean');
    grunt.loadNpmTasks('grunt-cleanempty');
    grunt.loadNpmTasks('grunt-jslint');
    grunt.loadNpmTasks('grunt-bower-task');
    grunt.loadNpmTasks('grunt-debug-task');
    grunt.registerTask('trimstatic', ['clean', 'cleanempty']);
    grunt.registerTask('build', ['bower', 'less', 'requirejs', 'trimstatic']);
    grunt.registerTask('default', ['build']);
    grunt.task.loadTasks('grunt');
};
