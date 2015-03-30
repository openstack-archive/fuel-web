/*
 * Copyright 2015 Mirantis, Inc.
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

//jshint strict:false

var argv = require('minimist')(process.argv.slice(2));

var fs = require('fs');
var path = require('path');
var spawn = require('child_process').spawn;
var rimraf = require('rimraf');
var _ = require('lodash-node');

var gulp = require('gulp');
var gutil = require('gulp-util');
var runSequence = require('run-sequence');

var bower = require('gulp-bower');
var mainBowerFiles = require('main-bower-files');

var filter = require('gulp-filter');
var react = require('gulp-react');
var less = require('gulp-less');
var replace = require('gulp-replace');
var jison = require('gulp-jison');
var lintspaces = require('gulp-lintspaces');

var jscs = require('gulp-jscs');
var jscsConfig = JSON.parse(fs.readFileSync('./.jscsrc'));
var jshint = require('gulp-jshint');
var jshintConfig = JSON.parse(fs.readFileSync('./.jshintrc'));

var intermediate = require('gulp-intermediate');
var rjs = require('requirejs');
var rjsConfig = _.merge(rjs('static/js/config.js'), {
    baseUrl: '.',
    appDir: 'static',
    optimize: 'uglify2',
    optimizeCss: 'standard',
    wrapShim: true,
    pragmas: {
        compressed: true
    },
    map: {
        '*': {
            JSXTransformer: 'empty:'
        }
    },
    paths: {
        react: 'js/libs/bower/react/react-with-addons.min'
    },
    stubModules: ['jsx'],
    modules: [
        {
            name: 'js/main',
            exclude: ['require-css/normalize']
        }
    ]
});

var jsFilter = filter('**/*.js');
var jsxFilter = filter('**/*.jsx');
var lessFilter = filter('**/*.less');
var indexFilter = filter('index.html');
var buildResultFilter = filter([
    'index.html',
    'js/main.js',
    'js/libs/bower/requirejs/require.js',
    'css/styles.css',
    'favicon.ico',
    'img/**',
    'font/**',
    'plugins/**'
]);

var validateTranslations = require('./gulp/i18n').validate;
gulp.task('i18n:validate', function() {
    var tranlations = JSON.parse(fs.readFileSync('static/translations/core.json'));
    var locales = argv.locales ? argv.locales.split(',') : null;
    validateTranslations(tranlations, locales);
});

gulp.task('bower:fetch', bower);

gulp.task('bower:copy-main', function() {
    var bowerDir = 'static/js/libs/bower/';
    rimraf.sync(bowerDir);
    return gulp.src(mainBowerFiles({checkExistence: true}), {base: 'bower_components'})
        .pipe(gulp.dest(bowerDir));
});

gulp.task('bower', function(cb) {
    runSequence('bower:fetch', 'bower:copy-main', cb);
});

gulp.task('jison', function() {
    return gulp.src('static/js/expression/parser.jison')
        .pipe(jison({moduleType: 'js'}))
        .pipe(gulp.dest('static/js/expression/'));
});

var jsFiles = ['static/js/**/*.js', '!static/js/libs/**', '!static/js/expression/parser.js'];
var jsxFiles = ['static/js/**/*.jsx', '!static/js/libs/**'];
var styleFiles = 'static/styles/*.less';

gulp.task('jscs', function() {
    return gulp.src(jsxFiles.concat(jsFiles))
        .pipe(jscs(jscsConfig));
});

gulp.task('jshint', function() {
    return gulp.src(jsxFiles.concat(jsFiles))
        .pipe(jsxFilter)
        .pipe(react())
        .pipe(jsxFilter.restore())
        .pipe(jshint(jshintConfig))
        .pipe(jshint.reporter('jshint-stylish'));
});

var lintspacesConfig = {
    showValid: true,
    newline: true,
    trailingspaces: true,
    indentation: 'spaces'
};

gulp.task('lintspaces:js', function() {
    return gulp.src(jsxFiles.concat(jsFiles))
        .pipe(lintspaces(_.extend({}, lintspacesConfig, {
            ignores: ['js-comments'],
            spaces: 4
        })))
        .pipe(lintspaces.reporter());
});

gulp.task('lintspaces:styles', function() {
    return gulp.src(styleFiles)
        .pipe(lintspaces(_.extend({}, lintspacesConfig, {
            ignores: ['js-comments'],
            spaces: 2,
            newlineMaximum: 2
        })))
        .pipe(lintspaces.reporter());
});

gulp.task('lint', [
    'jscs',
    'jshint',
    'lintspaces:js',
    'lintspaces:styles'
]);

gulp.task('rjs', function() {
    var targetDir = argv['static-dir'] || '/tmp/static_compressed';
    rimraf.sync(targetDir);

    return gulp.src(['static/**'])
        .pipe(jsxFilter)
        .pipe(react())
        .pipe(jsxFilter.restore())
        .pipe(lessFilter)
        .pipe(less())
        .pipe(lessFilter.restore())
        .pipe(jsFilter)
        // use CSS loader instead LESS loader - styles are precompiled
        .pipe(replace(/less!/g, 'require-css/css!'))
        // remove explicit calls to JSX loader plugin
        .pipe(replace(/jsx!/g, ''))
        .pipe(jsFilter.restore())
        .pipe(indexFilter)
        .pipe(replace('__COMMIT_SHA__', Date.now()))
        .pipe(indexFilter.restore())
        .pipe(intermediate({output: '_build'}, function(tempDir, cb) {
            var configFile = path.join(tempDir, 'build.json');
            rjsConfig.appDir = tempDir;
            rjsConfig.dir = path.join(tempDir, '_build');
            fs.createWriteStream(configFile).write(JSON.stringify(rjsConfig));

            var rjs = spawn('./node_modules/.bin/r.js', ['-o', configFile]);
            rjs.stdout.on('data', function(data) {
                _(data.toString().split('\n')).compact().map(function(line) {
                    gutil.log(line);
                });
            });
            rjs.on('close', cb);
        }))
        .pipe(buildResultFilter)
        .pipe(gulp.dest(targetDir));
});

gulp.task('build', function(cb) {
    runSequence('bower', 'rjs', cb);
});

gulp.task('default', ['build']);
