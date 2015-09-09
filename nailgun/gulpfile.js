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
var rimraf = require('rimraf');
var _ = require('lodash');

var webpack = require('webpack');

var gulp = require('gulp');
var gutil = require('gulp-util');
var shell = require('gulp-shell');
var runSequence = require('run-sequence');

var filter = require('gulp-filter');
var replace = require('gulp-replace');
var jison = require('gulp-jison');

var validateTranslations = require('./gulp/i18n').validate;
gulp.task('i18n:validate', function() {
    var tranlations = JSON.parse(fs.readFileSync('static/translations/core.json'));
    var locales = argv.locales ? argv.locales.split(',') : null;
    validateTranslations(tranlations, locales);
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

gulp.task('intern:unit', runIntern({suites: argv.suites || 'static/tests/unit/**/*.js', browser: 'phantomjs'}));
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
    '!static/build/**',
    '!static/vendor/**',
    '!static/expression/parser.js',
    'static/tests/**/*.js'
];
var styleFiles = [
    'static/**/*.less',
    'static/**/*.css',
    '!static/build/**',
    '!static/vendor/**'
];

gulp.task('jscs:fix', function() {
    var jscs = require('gulp-jscs');
    var jscsConfig = JSON.parse(fs.readFileSync('./.jscsrc'));
    return gulp.src(jsFiles, {base: '.'})
        .pipe(jscs(_.extend({fix: true}, jscsConfig)))
        .pipe(gulp.dest('.'));
});

gulp.task('jscs', function() {
    var jscs = require('gulp-jscs');
    var jscsConfig = JSON.parse(fs.readFileSync('./.jscsrc'));
    return gulp.src(jsFiles)
        .pipe(jscs(jscsConfig));
});

gulp.task('eslint', function() {
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
    var lintspaces = require('gulp-lintspaces');
    return gulp.src(jsFiles)
        .pipe(lintspaces(_.extend({}, lintspacesConfig, {
            ignores: ['js-comments'],
            spaces: 4
        })))
        .pipe(lintspaces.reporter());
});

gulp.task('lintspaces:styles', function() {
    var lintspaces = require('gulp-lintspaces');
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

var WEBPACK_STATS_OPTIONS = {
    colors: true,
    hash: false,
    version: false,
    assets: false,
    chunks: false
};

gulp.task('dev-server', function() {
    var devServerHost = argv['dev-server-host'] || '127.0.0.1';
    var devServerPort = argv['dev-server-port'] || 8080;
    var nailgunHost = argv['nailgun-host'] || '127.0.0.1';
    var nailgunPort = argv['nailgun-port'] || 8000;
    var hot = argv.hot;

    var config = require('./webpack.config');
    config.entry.push('webpack-dev-server/client?http://' + devServerHost + ':' + devServerPort);
    if (hot) {
        config.entry.push('webpack/hot/dev-server');
        config.plugins.push(new webpack.HotModuleReplacementPlugin());
    }

    var compiler = webpack(config);
    var WebpackDevServer = require('webpack-dev-server');
    var options = {
        stats: WEBPACK_STATS_OPTIONS,
        proxy: {
            '*': 'http://' + nailgunHost + ':' + nailgunPort
        }
    };
    _.extend(options, config.output);
    new WebpackDevServer(compiler, options).listen(devServerPort, devServerHost, function(err) {
        if (err) throw err;
        gutil.log('Development server started at http://' + devServerHost + ':' + devServerPort);
    });
});

gulp.task('build', function(cb) {
    var dev = argv.dev;
    var sourceDir = path.resolve('static');
    var targetDir = path.resolve(argv['static-dir'] || '') || sourceDir;

    var config = require('./webpack.config');
    config.output.path = path.join(targetDir, 'build');
    if (!dev) {
        config.plugins.push(
            new webpack.DefinePlugin({'process.env': {NODE_ENV: '"production"'}}),
            new webpack.optimize.DedupePlugin(),
            new webpack.optimize.UglifyJsPlugin({compress: {warnings: false}})
        );
    }

    rimraf.sync(config.output.path);

    webpack(config).run(function(err, stats) {
        if (err) return cb(err);

        gutil.log(stats.toString(WEBPACK_STATS_OPTIONS));

        if (stats.hasErrors()) return cb('Build failed');

        if (targetDir != sourceDir) {
            var indexFilter = filter('index.html');
            gulp
                .src([
                    'index.html',
                    'favicon.ico',
                    'img/loader-bg.svg',
                    'img/loader-logo.svg',
                    'styles/layout.css'
                ], {cwd: sourceDir, base: sourceDir})
                .pipe(indexFilter)
                .pipe(replace('__CACHE_BUST__', Date.now()))
                .pipe(indexFilter.restore())
                .pipe(gulp.dest(targetDir))
                .on('end', cb);
        } else {
            cb();
        }
    });
});

gulp.task('default', ['build']);
