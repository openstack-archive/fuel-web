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

var path = '';

if (typeof window.__karma__ !== 'undefined') {
  path += '';
}
debugger;
requirejs.config({
    // Karma serves files from '/base'
    baseUrl: '/base',

    map: {
        '*': {
            'underscore': 'static/js/libs/bower/lodash/js/lodash',
            'jquery'    : 'static/js/libs/bower/jquery/js/jquery',
            'backbone'  : 'static/js/libs/custom/backbone',
            'stickit'   : 'static/js/libs/bower/backbone.stickit/js/backbone.stickit'
        }
    },


//    shim: {
//
//        // Vendor shims
//
//        'underscore': {
//            'exports': '_'
//        },
//
//        'jquery': {
//            'exports': '$'
//        },
//
//        'backbone': {
//            'deps': ['jquery', 'underscore'],
//            'exports': 'Backbone'
//        },
//
//        'stickit': {
//            'deps' : ['backbone'],
//            'exports' : 'Stickit'
//        }
//    },

    // ask Require.js to load these files (all our tests)
    deps: tests,

    // start test run, once Require.js is done
    // the original callback here was just:
    // callback: window.__karma__.start
    // I was running into issues with jasmine-jquery though
    // specifically specifying where my fixtures were located
    // this solved it for me.
    callback: function(){
        debugger;
        console.log('before karma start test-main');
        window.__karma__.start();
        console.log('after karma start test-main');
    }

});
debugger;


//var tests = Object.keys(window.__karma__.files).filter(function (file) {
//  return /\.test\.js$/.test(file);
//});
//
//require({
//  baseUrl: '',
//  paths: {
//    require: '../libs/requirejs/js/require',
//    text: '../libs/requirejs-text/js/text',
//    'jquery': '../libs/bower/jquery/js/jquery',
//    lodash: '../libs/bower/lodash/js/lodash',
//    backbone: '../libs/custom/backbone'
//  },
//  // ask requirejs to load these files (all our tests)
//  deps: tests,
//  // start test run, once requirejs is done
//  callback: window.__karma__.start
//});




