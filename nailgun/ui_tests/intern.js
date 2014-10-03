define(['static/js/config'], function(config) {
    var paths = {};

    for (var i in config.paths) {
        if (config.paths.hasOwnProperty(i)) {
            paths[i] = 'static/' + config.paths[i];
        }
    }

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
            'host-browser': '/static/js/libs/bower/requirejs/js/require.js'
        },
        reporters: ['console', 'lcovhtml'],
        // A regular expression matching URLs to files that should not be included in code coverage analysis
        excludeInstrumentation: /^/,
        loader: {
            baseUrl: '.',
            paths: paths,
            shim: config.shim,
            map: config.map,
            jsx: config.jsx
            //packages: [{
            //    name: 'intern', location: '../../__intern'
            //}]
        }
    }
});
