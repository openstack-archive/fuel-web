define(['static/js/config'], function(config) {
    var paths = {
            templates: '/static/templates',
            i18n: '/static/i18n'
        },
        baseDependencies = [
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
            'jsx',
            'less!/static/css/styles'
        ];

    var shouldAddShim = function(path) {
        return (path.indexOf('js/app') > -1) ||
            (path.indexOf('js/models') > -1) ||
            (path.indexOf('js/views') > -1) ||
            (path.indexOf('js/view_mixins') > -1) ||
            (path.indexOf('js/component_mixins') > -1);
    };

    for (var key in config.paths) {
        if (config.paths.hasOwnProperty(key)) {
            var old_path = config.paths[key];

            paths[key] = '/static/' + old_path;
            config.shim[old_path] = config.shim[old_path] || {};
            if (shouldAddShim(old_path)) {
                config.shim[old_path].deps = config.shim[old_path].deps || [];
                [].push.apply(config.shim[old_path].deps, baseDependencies);
            }
        }
    }

    config.jsx.baseUrl = 'static';

    config.shim['jsx!views/dialogs'] = baseDependencies;
    config.shim['jsx!component_mixins'] = baseDependencies;

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
    };
});
