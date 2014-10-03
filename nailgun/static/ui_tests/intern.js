define(['js/config'], function(config) {
    'use strict';

    config.baseUrl = '';
    config.waitSeconds = 7;
    config.paths.helpers = 'ui_tests/helpers';

    return {
        proxyPort: 9057,
        proxyUrl: 'http://localhost:9057/',
        capabilities: {
            'selenium-version': '2.45.0'
        },
        environments: [
            {browserName: 'firefox'}
        ],
        maxConcurrency: 1,
        useLoader: {
            'host-node': 'requirejs',
            'host-browser': '/js/libs/bower/requirejs/require.js'
        },
        // A regular expression matching URLs to files that should not be included in code coverage analysis
        excludeInstrumentation: /^/,
        loader: config
    };
});
