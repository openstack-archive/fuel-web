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
    var pkg = grunt.file.readJSON('package.json');
    var staticDir = grunt.option('static-dir') || '/tmp/static_compressed';
    var staticBuildPreparationDir = staticDir + '/_prepare_build';
    var staticBuildDir = staticDir + '/_build';

    grunt.initConfig({
        pkg: pkg,
        requirejs: {
            compile: {
                options: {
                    baseUrl: '.',
                    appDir: staticBuildPreparationDir + '/static',
                    dir: staticBuildDir,
                    mainConfigFile: 'static/js/main.js',
                    waitSeconds: 60,
                    optimize: 'uglify2',
                    optimizeCss: 'standard',
                    pragmas: {
                        compressed: true
                    },
                    map: {
                        '*': {
                            'css': 'require-css',
                            'JSXTransformer': 'empty:'
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
                    'static/js/**/*.js',
                    '!static/js/libs/**',
                    '!static/js/expression_parser.js'
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
                dest: staticBuildPreparationDir + '/static/css/styles.css',
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
        react: {
            compile: {
                files: [
                    {
                        expand: true,
                        src: [staticBuildPreparationDir + '/static/**/*.jsx'],
                        ext: '.js'
                    }
                ]
            }
        },
        copy: {
            prepare_build: {
                files: [
                    {
                        expand: true,
                        src: [
                            'static/**',
                            '!**/*.less',
                            '!**/*.js',
                            '!**/*.jsx',
                            '!**/*.jison'
                        ],
                        dest: staticBuildPreparationDir + '/'
                    }
                ]
            },
            preprocess_js: {
                files: [
                    {
                        expand: true,
                        src: [
                            'static/**/*.js',
                            'static/**/*.jsx',
                            '!**/JSXTransformer.js'
                        ],
                        dest: staticBuildPreparationDir + '/'
                    }
                ],
                options: {
                    process: function (content, path) {
                        content = content.replace(/jsx!/g, '');
                        if (/\.jsx$/.test(path)) {
                            content = '/** @jsx React.DOM */\n' + content;
                        }
                        return content;
                    }
                }
            },
            finalize_build: {
                files: [
                    {
                        expand: true,
                        cwd: staticBuildDir,
                        src: ['**'],
                        dest: staticDir
                    }
                ],
                options: {
                    force: true
                }
            }
        },
        clean: {
            trim: {
                expand: true,
                cwd: staticBuildDir,
                src: [
                    '**/*.js',
                    '!js/main.js',
                    '!js/libs/bower/requirejs/js/require.js',
                    '**/*.css',
                    '!css/styles.css',
                    'templates',
                    'i18n'
                ]
            },
            jsx: {
                expand: true,
                cwd: staticBuildPreparationDir,
                src: ['**/*.jsx']
            },
            prepare_build: {
                src: [staticDir]
            },
            finalize_build: {
                src: [staticBuildDir, staticBuildPreparationDir]
            },
            options: {
                force: true
            }
        },
        cleanempty: {
            trim: {
                expand: true,
                cwd: staticBuildDir,
                src: ['**']
            },
            options: {
                files: false,
                force: true
            }
        },
        replace: {
            sha: {
                src: 'static/index.html',
                dest: staticBuildDir + '/',
                replacements: [{
                    from: '__COMMIT_SHA__',
                    to: function() {
                        return grunt.config.get('meta.revision');
                    }
                }]
            }
        },
        revision: {
            options: {
                short: false
            }
        },
        jison: {
            target : {
                src: 'static/config_expression.jison',
                dest: 'static/js/expression_parser.js',
                options: {
                    moduleType: 'js'
                }
            }
        }
    });

    Object.keys(pkg.devDependencies)
        .filter(function(npmTaskName) { return npmTaskName.indexOf('grunt-') === 0; })
        .forEach(grunt.loadNpmTasks.bind(grunt));

    grunt.registerTask('build', [
        'bower',
        'clean:prepare_build',
        'copy:prepare_build',
        'copy:preprocess_js',
        'less',
        'react',
        'clean:jsx',
        'requirejs',
        'clean:trim',
        'cleanempty:trim',
        'revision',
        'replace',
        'copy:finalize_build',
        'clean:finalize_build'
    ]);
    grunt.registerTask('default', ['build']);
    grunt.task.loadTasks('grunt');
};
