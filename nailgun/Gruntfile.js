/*
 * Copyright 2013 Mirantis, Inc.
 *
 * Licensed under the Apache License, Version 2.0 (the "License"); you may
 * not use this file except in compliance with the License. You may obtain
 * a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
 * WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
 * License for the specific language governing permissions and limitations
 * under the License.
**/
module.exports = function(grunt) {
  grunt.initConfig({
    pkg: grunt.file.readJSON('package.json'),
    requirejs: {
      compile: {
        options: {
          baseUrl: '.',
          appDir: 'static',
          dir: grunt.option('static-dir') || '/tmp/static_compressed',
          mainConfigFile: 'static/js/main.js',
          modules: [{name: 'js/main'}],
          waitSeconds: 60,
          optimize: 'uglify2',
        }
      }
    },
    less: {
      all: {
          src: ['static/less/bootstrap/bootstrap.less'],
          dest: 'static/css/less.css'
      }
    },
    jslint: {
      client: {
        src: [
          'static/js/*.js',
          'static/js/views/*.js',
        ],
        directives: {
          predef: ['requirejs', 'require', 'define', 'app', 'Backbone', '$', '_'],
          ass: true,
          browser: true,
          unparam: true,
          nomen: true,
          eqeq: true,
          vars: true,
          white: true,
          es5: false
        }
      }
    }
  });

  grunt.loadNpmTasks('grunt-contrib-requirejs');
  grunt.loadNpmTasks('grunt-contrib-less');
  grunt.loadNpmTasks('grunt-jslint');
  grunt.registerTask('build', ['requirejs']);
};
