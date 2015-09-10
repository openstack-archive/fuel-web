/*eslint-disable strict*/

var webpackConfig = require('./webpack.config');

module.exports = function(config) {
    config.set({
        browsers: ['phantomjs'],
        files: [
            'node_modules/es5-shim/es5-shim.js',
            'static/tests/unit/expression.js'
        ],
        frameworks: [
            'chai',
            'mocha',
            'sinon'
        ],
        plugins: [
            'karma-webdriver-launcher',
            'karma-chai',
            'karma-mocha',
            'karma-sinon',
            'karma-webpack'
        ],
        preprocessors: {
            'static/tests/unit/**/*.js': ['webpack']
        },
        reporters: ['dots'],
        singleRun: true,
        client: {
            mocha: {
                ui: 'tdd'
            }
        },
        customLaunchers: {
            chrome: {
                base: 'WebDriver',
                browserName: 'chrome'
            },
            firefox: {
                base: 'WebDriver',
                browserName: 'firefox'
            },
            phantomjs: {
                base: 'WebDriver',
                browserName: 'phantomjs',
                'phantomjs.binary.path': require('phantomjs').path
            }
        },
        webpack: webpackConfig,
        webpackMiddleware: {
            noInfo: true
        }
    });
};
