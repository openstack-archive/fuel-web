define(['js/config'], function(config) {

    config.baseUrl = '';

    return {
        proxyPort: 9057,
        proxyUrl: 'http://localhost:9057/',
        capabilities: {
            'selenium-version': '2.43.1'
        },
        environments: [
            {browserName: 'firefox'}
        ],
        maxConcurrency: 1,
        useLoader: {
            'host-node': 'requirejs',
            'host-browser': '/js/libs/bower/requirejs/js/require.js'
        },
        reporters: ['console', 'lcovhtml'],
        suites: ['ui_tests/unit/example'],
        // A regular expression matching URLs to files that should not be included in code coverage analysis
        excludeInstrumentation: /^/,
        loader: config
    };
});
