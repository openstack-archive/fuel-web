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
	// Configuration options for the module loader; any AMD configuration options supported by the Dojo loader can be
	// used here
	loader: {
	},
	// A regular expression matching URLs to files that should not be included in code coverage analysis
	excludeInstrumentation: /^/
});
