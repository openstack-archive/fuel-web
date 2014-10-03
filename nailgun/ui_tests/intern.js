define({
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
		// Packages that should be registered with the loader in each testing environment
		packages: [
			{ name: 'jquery', location: 'static/js/libs/bower/jquery' },
			{ name: 'underscore', location: 'static/js/libs/bower/underscore' },
			{ name: 'backbone', location: 'static/js/libs/custom/backbone' },
            { name: 'js', location: 'static/js' }
		]
    }
  });
