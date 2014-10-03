define(['js/config'], function(config) {
    'use strict';

    var baseDependencies = [
        'jquery',
        'underscore',
        'backbone',
        'stickit',
        'coccyx',
        'react',
        'react.backbone',
        'cocktail',
        'i18next',
        'bootstrap',
        'jquery-cookie',
        'jquery-checkbox',
        'jquery-timeout',
        'jquery-ui',
        'jquery-autoNumeric',
        'text',
//>>excludeStart("compressed", pragmas.compressed);
        'jsx',
//>>excludeEnd("compressed");
        'less!/static/css/styles'
    ];

    config.baseUrl = '';
    config.waitSeconds = 7;
    config.shim['jsx!views'] = {deps: baseDependencies};
    config.shim['jsx!component_mixins'] = {deps: baseDependencies};
    config.shim.app = {deps: baseDependencies};

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
        // A regular expression matching URLs to files that should not be included in code coverage analysis
        excludeInstrumentation: /^/,
        loader: config
    };
});
