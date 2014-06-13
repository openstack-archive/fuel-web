// Karma configuration
// Generated on Fri May 30 2014 20:43:19 GMT+0300 (EEST)

module.exports = function(config) {
    config.set({
        // base path that will be used to resolve all patterns (eg. files, exclude)
        basePath: '',
        // frameworks to use
        // available frameworks: https://npmjs.org/browse/keyword/karma-adapter
        frameworks: ['mocha', 'requirejs'],
        // list of files / patterns to load in the browser
        files: [
            // libs required for test framework
//            {pattern: 'node_modules/chai/chai.js', included: false},

            'static/js/libs/bower/jquery/js/jquery.js',
            'static/js/libs/bower/lodash/js/lodash.js',
            'static/js/libs/custom/backbone.js',
//            {pattern: 'static/js/libs/**/*.js', included: false},
//            {pattern: 'static/js/*', included: false},
//            {pattern: 'static/js/views/*.js', included: false},
            {pattern: 'static/js/test/test-parser.js', included: false},
            'static/js/test/test-main.js'
//            'static/js/libs/**/*.js'
        ],
        // list of files to exclude
        exclude: [
            'static/js/libs/bower/require-css/**/*',

        ],
        plugins: [
            'karma-mocha',
            'karma-chai',
            'karma-coverage',
            'karma-requirejs',
            'karma-sinon',
            'karma-phantomjs-launcher',
            'karma-mocha-reporter',
            'karma-firefox-launcher'
        ],
        // preprocess matching files before serving them to the browser
        // available preprocessors: https://npmjs.org/browse/keyword/karma-preprocessor
        preprocessors: {
            '*.js': 'coverage' // for coverage
        },
        // test results reporter to use
        // possible values: 'dots', 'progress'
        // available reporters: https://npmjs.org/browse/keyword/karma-reporter
        reporters: ['mocha', 'coverage'],
        coverageReporter: {
            type: 'html',
            dir: 'coverage/'
        },
        // web server port
        port: 9876,
        // enable / disable colors in the output (reporters and logs)
        colors: true,
        // level of logging
        // possible values: config.LOG_DISABLE || config.LOG_ERROR || config.LOG_WARN || config.LOG_INFO || config.LOG_DEBUG
        logLevel: config.LOG_INFO,
        // enable / disable watching file and executing tests whenever any file changes
        autoWatch: false,
        // start these browsers
        // available browser launchers: https://npmjs.org/browse/keyword/karma-launcher
        browsers: ['Firefox'],
        // If browser does not capture in given timeout [ms], kill it
        captureTimeout: 60000,
        // Continuous Integration mode
        // if true, Karma captures browsers, runs the tests and exits
        singleRun: false
    });
};
