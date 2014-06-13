var tests = [];
// we want require to load our test(spec) files
for (var file in window.__karma__.files) {
  if (window.__karma__.files.hasOwnProperty(file)) {
    // simple pattern that matches our files
    // note that these files are available here
    // because of our settings in the karma.conf.js files[]
    if (/test.+\.js$/.test(file)) {
      tests.push(file);
    }
  }
}

requirejs.config({
    // Karma serves files from '/base'
    baseUrl: '/base',


    paths: {
        'jquery': 'static/js/libs/bower/jquery/js/jquery',
        'underscore': 'static/js/libs/bower/lodash/js/lodash',
        'backbone'  : 'static/js/libs/custom/backbone',
        'deepModel': 'static/js/libs/bower/backbone-deep-model/js/deep-model',
        'chai': 'static/js/libs/custom/chai',
        'stickit': 'static/js/libs/bower/backbone.stickit/js/backbone.stickit',
        utils: 'static/js/utils',
        expression_parser: 'static/js/expression_parser',
        app: 'static/js/app',
        models: 'static/js/models',
        collections: 'static/js/collections',
        views: 'static/js/views'
    },

    shim: {
        // Vendor shims
        'underscore': {
            'exports': '_'
        },
        'jquery': {
            'exports': '$'
        },
        'backbone': {
            'deps': ['jquery', 'underscore'],
            'exports': 'Backbone'
        },
        'stickit': {
            'deps' : ['backbone'],
            'exports' : 'Stickit'
        },
        'deepModel': {
            deps: ['backbone']
        },
        expression_parser: {
            exports: 'parser'
        }
    },

    // ask Require.js to load these files (all our tests)
    deps: tests,

    // start test run, once Require.js is done
    callback: function(){
        window.__karma__.start();
    }

});