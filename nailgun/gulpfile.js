//jshint strict:false

var argv = require('minimist')(process.argv.slice(2));

var fs = require('fs');
var rimraf = require('rimraf');
var _ = require('lodash-node');

var gulp = require('gulp');
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

var gulpRjs = require('./gulp/gulp-rjs');
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
        react: 'js/libs/bower/react/js/react-with-addons.min'
    },
    stubModules: ['jsx'],
    modules: [
        {
            name: 'js/main',
            exclude: ['require-css/normalize']
        }
    ]
});

var jsFiles = ['static/js/**/*.js', '!static/js/libs/**', '!static/js/expression/parser.js'];
var jsxFiles = ['static/js/**/*.jsx', '!static/js/libs/**'];

var jsFilter = filter('**/*.js');
var jsxFilter = filter('**/*.jsx');
var lessFilter = filter('**/*.less');
var indexFilter = filter('index.html');
var buildResultFilter = filter([
    'index.html',
    'js/main.js',
    'js/libs/bower/requirejs/js/require.js',
    'css/styles.css',
    'img/**',
    'font/**',
    'favicon.ico'
]);

var dest = argv['static-dir'] || '/tmp/static_compressed';

gulp.task('jison', function() {
    return gulp.src('static/js/expression/parser.jison')
        .pipe(jison({moduleType: 'js'}))
        .pipe(gulp.dest('static/js/expression/'));
});

gulp.task('jscs:jsx', function() {
    return gulp.src(jsxFiles)
        .pipe(jscs(_.extend({esprima: 'esprima-fb'}, jscsConfig)));
});

gulp.task('jscs:js', function() {
    return gulp.src(jsFiles)
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

gulp.task('lintspaces', function() {
    return gulp.src(jsxFiles.concat(jsFiles))
        .pipe(lintspaces({
            showValid: true,
            newline: true,
            indentation: 'spaces',
            spaces: 4,
            trailingspaces: true,
            ignores: ['js-comments']
        }))
        .pipe(lintspaces.reporter());
});

gulp.task('lint', ['jscs:js', 'jscs:jsx', 'jshint', 'lintspaces']);

gulp.task('build', function() {
    rimraf.sync(dest);

    return gulp.src([
        'static/**/*',
        'static/**/*.js',
        'static/**/*.jsx',
        'static/**/styles.less'
    ])
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
        .pipe(gulpRjs(rjsConfig))
        .pipe(buildResultFilter)
        .pipe(gulp.dest(dest));
});
