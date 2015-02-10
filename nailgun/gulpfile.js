//jshint strict:false

var gulp = require('gulp');
var fs = require('fs');
var _ = require('lodash-node');
var filter = require('gulp-filter');
var react = require('gulp-react');
var jscs = require('gulp-jscs');
var jscsConfig = JSON.parse(fs.readFileSync('./.jscsrc'));
var jshint = require('gulp-jshint');
var jshintConfig = JSON.parse(fs.readFileSync('./.jshintrc'));
var lintspaces = require('gulp-lintspaces');
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

var jsxFilter = filter('**/*.jsx');

var dest = '/tmp/static_compressed';

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
        }));
});

gulp.task('lint', ['jscs:js', 'jscs:jsx', 'jshint', 'lintspaces']);

gulp.task('rjs', function() {
    return gulp.src(jsxFiles.concat(jsFiles))
        //.pipe(jsxFilter)
        //.pipe(react())
        //.pipe(jsxFilter.restore())
        .pipe(require('./gulp/gulp-rjs')(rjsConfig));
});
