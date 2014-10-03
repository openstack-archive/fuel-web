define(['js/config'], function(config) {
    var deps = config.shim.app.deps;
    deps[deps.length - 1] = 'less!/css/styles';

    config.baseUrl = '';
    config.waitSeconds = 7;
    config.shim['jsx!views'] = {deps: deps};
    config.shim['jsx!component_mixins'] = {deps: deps};

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
