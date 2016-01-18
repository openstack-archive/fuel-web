/*eslint-disable strict*/

module.exports = function(config) {
  config.set({
    browsers: ['firefox'],
    files: [
      'static/tests/unit/**/*.js'
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
        browserName: 'phantomjs'
      }
    },
    webpack: require('./webpack.config'),
    webpackMiddleware: {
      noInfo: true
    }
  });
};
