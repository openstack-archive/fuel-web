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
            'node_modules/sinon/pkg/sinon.js',                    // sinon will be accessable from global context
            {pattern: 'static/js/libs/bower/**/*.js', included: false},
            {pattern: 'static/js/libs/custom/*.js', included: false},
            {pattern: 'static/js/*.js', included: false},
            {pattern: 'static/js/views/**/*.js', included: false},
            {pattern: 'static/js/test/test-parser.js', included: false},
            'static/js/test/test-main.js'
        ],
        // list of files to exclude
        exclude: [
            'static/js/main.js'
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
        browsers: ['PhantomJS'],
        // If browser does not capture in given timeout [ms], kill it
        captureTimeout: 60000,
        // Continuous Integration mode
        // if true, Karma captures browsers, runs the tests and exits
        singleRun: true
    });
};
