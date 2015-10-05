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

/*eslint-disable strict*/

var argv = require('minimist')(process.argv.slice(2));

var fs = require('fs');
var path = require('path');
var glob = require('glob');
var spawn = require('child_process').spawn;
var rimraf = require('rimraf');
var es = require('event-stream');
var _ = require('lodash');

var gulp = require('gulp');
var gutil = require('gulp-util');
var shell = require('gulp-shell');
var runSequence = require('run-sequence');

var filter = require('gulp-filter');
var react = require('gulp-react');
var less = require('gulp-less');
var autoprefixer = require('gulp-autoprefixer');
var replace = require('gulp-replace');
var jison = require('gulp-jison');
var lintspaces = require('gulp-lintspaces');

var jscs = require('gulp-jscs');
var jscsConfig = JSON.parse(fs.readFileSync('./.jscsrc'));

var intermediate = require('gulp-intermediate');
var rjs = require('requirejs');
var rjsConfig = _.merge(rjs('static/config.js'), {
    baseUrl: '.',
    appDir: 'static',
    optimize: 'uglify2',
    optimizeCss: 'standard',
    generateSourceMaps: true,
    preserveLicenseComments: false, // required for generateSourceMaps
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
        react: 'vendor/npm/react/dist/react-with-addons.min'
    },
    stubModules: ['jsx'],
    modules: [
        {
            name: 'main',
            exclude: ['require-css/normalize']
        }
    ]
});

var jsFilter = filter('**/*.js');
var jsxFilter = filter('**/*.jsx');
var lessFilter = filter('**/*.less');
var indexFilter = filter('index.html');
var buildSourceFilter = filter([
    '**',
    '!tests/**'
]);
var buildResultFilter = filter([
    'index.html',
    'main.js',
    'main.js.map',
    'vendor/npm/requirejs/require.js',
    'vendor/npm/requirejs/require.js.map',
    'styles/*.css',
    'favicon.ico',
    'img/**',
    '**/*.+(ttf|eot|svg|woff|woff2)',
    'plugins/**'
]);

var validateTranslations = require('./gulp/i18n').validate;
gulp.task('i18n:validate', function() {
    var tranlations = JSON.parse(fs.readFileSync('static/translations/core.json'));
    var locales = argv.locales ? argv.locales.split(',') : null;
    validateTranslations(tranlations, locales);
});

gulp.task('copy-main', function() {
    var config = JSON.parse(fs.readFileSync('package.json'));
    var streams = _.map(config.mainFiles, function(files, package) {
        if (!(package in config.dependencies) && !(package in config.devDependencies)) {
            throw new Error(package + ' is not a dependency');
        }
        return _.map(_.isArray(files) ? files : [files], function(file) {
            return gulp.src('node_modules/' + package + '/' + file, {base: 'node_modules'})
                .pipe(gulp.dest('static/vendor/npm/'));
        });
    });
    return es.merge(_.flatten(streams));
});

var selenium = require('selenium-standalone');
var seleniumProcess = null;
function shutdownSelenium() {
    if (seleniumProcess) {
        seleniumProcess.kill();
        seleniumProcess = null;
    }
}

gulp.task('selenium:fetch', function(cb) {
    var defaultVersion = '2.45.0';
    selenium.install({version: argv.version || defaultVersion}, cb);
});

gulp.task('selenium', ['selenium:fetch'], function(cb) {
    var port = process.env.SELENIUM_SERVER_PORT || 4444;
    selenium.start(
        {seleniumArgs: ['--port', port], spawnOptions: {stdio: 'pipe'}},
        function(err, child) {
            if (err) throw err;
            child.on('exit', function() {
                if (seleniumProcess) {
                    gutil.log(gutil.colors.yellow('Selenium process died unexpectedly. Probably port', port, 'is already in use.'));
                }
            });
            ['exit', 'uncaughtException', 'SIGTERM', 'SIGINT'].forEach(function(event) {
                process.on(event, shutdownSelenium);
            });
            seleniumProcess = child;
            cb();
        }
    );
});

function runIntern(params) {
    return function() {
        var baseDir = 'static';
        var runner = './node_modules/.bin/intern-runner';
        var browser = params.browser || argv.browser || 'firefox';
        var options = [['config', 'tests/intern-' + browser + '.js']];
        var suiteOptions = [];
        ['suites', 'functionalSuites'].forEach(function(suiteType) {
            if (params[suiteType]) {
                var suiteFiles = glob.sync(path.relative(baseDir, params[suiteType]), {cwd: baseDir});
                suiteOptions = suiteOptions.concat(suiteFiles.map(function(suiteFile) {
                    return [suiteType, suiteFile.replace(/\.js$/, '')];
                }));
            }
        });
        if (!suiteOptions.length) {
            throw new Error('No matching suites');
        }
        options = options.concat(suiteOptions);
        var command = [path.relative(baseDir, runner)].concat(options.map(function(o) {
            return o.join('=');
        })).join(' ');
        gutil.log('Executing', command);
        return shell.task(command, {cwd: baseDir})();
    };
}

gulp.task('intern:unit', runIntern({suites: argv.suites || 'static/tests/unit/**/*.js'}));
gulp.task('intern:functional', runIntern({functionalSuites: argv.suites || 'static/tests/functional/**/test_*.js'}));

gulp.task('unit-tests', function(cb) {
    runSequence('selenium', 'intern:unit', function(err) {
        shutdownSelenium();
        cb(err);
    });
});

gulp.task('functional-tests', function(cb) {
    runSequence('selenium', 'intern:functional', function(err) {
        shutdownSelenium();
        cb(err);
    });
});

gulp.task('jison', function() {
    return gulp.src('static/expression/parser.jison')
        .pipe(jison({moduleType: 'js'}))
        .pipe(gulp.dest('static/expression/'));
});

var jsFiles = [
    'static/**/*.js',
    'static/**/*.jsx',
    '!static/vendor/**',
    '!static/expression/parser.js',
    'static/tests/**/*.js'
];
var styleFiles = [
    'static/**/*.less',
    'static/**/*.css',
    '!static/vendor/**'
];

gulp.task('jscs:fix', function() {
    return gulp.src(jsFiles, {base: '.'})
        .pipe(jscs(_.extend({fix: true}, jscsConfig)))
        .pipe(gulp.dest('.'));
});

gulp.task('jscs', function() {
    return gulp.src(jsFiles)
        .pipe(jscs(jscsConfig));
});

gulp.task('eslint', function() {
    // FIXME(vkramskikh): move to top after fixing packaging issues
    var eslint = require('gulp-eslint');
    var eslintConfig = JSON.parse(fs.readFileSync('./.eslintrc'));
    return gulp.src(jsFiles)
        .pipe(eslint(eslintConfig))
        .pipe(eslint.format())
        .pipe(eslint.failAfterError());
});

var lintspacesConfig = {
    showValid: true,
    newline: true,
    trailingspaces: true,
    indentation: 'spaces'
};

gulp.task('lintspaces:js', function() {
    return gulp.src(jsFiles)
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
    'eslint',
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
        .pipe(autoprefixer())
        .pipe(lessFilter.restore())
        .pipe(jsFilter)
        // use CSS loader instead LESS loader - styles are precompiled
        .pipe(replace(/less!/g, 'require-css/css!'))
        // remove explicit calls to JSX loader plugin
        .pipe(replace(/jsx!/g, ''))
        .pipe(jsFilter.restore())
        .pipe(indexFilter)
        .pipe(replace('__CACHE_BUST__', Date.now()))
        .pipe(indexFilter.restore())
        .pipe(buildSourceFilter)
        .pipe(intermediate({output: '_build'}, function(tempDir, cb) {
            var configFile = path.join(tempDir, 'build.json');
            rjsConfig.appDir = tempDir;
            rjsConfig.dir = path.join(tempDir, '_build');
            fs.createWriteStream(configFile).write(JSON.stringify(rjsConfig));

            var rjs = spawn('./node_modules/.bin/r.js', ['-o', configFile]);
            rjs.stdout.on('data', function(data) {
                _(data.toString().split('\n')).compact().each(_.ary(gutil.log, 1)).value();
            });
            rjs.on('close', cb);
        }))
        .pipe(buildResultFilter)
        .pipe(gulp.dest(targetDir));
});

gulp.task('build', function(cb) {
    runSequence('copy-main', 'rjs', cb);
});

gulp.task('default', ['build']);
