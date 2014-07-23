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
var rewire = require('rewire');
var proxyquire = require('proxyquire');
var react = require('react-tools');

var jshintcli = rewire('jshint/src/cli');
var docblock = require('jstransform/src/docblock');

//Get the original lint function 
var origLint = jshintcli.__get__("lint");

var jsxSuffix = ".jsx";

//override the lint function to also transform the jsx code
jshintcli.__set__("lint", function myLint(code, results, config, data, file) {
  var isJsxFile = file.indexOf(jsxSuffix, file.length - jsxSuffix.length) !== -1;
  var hasDocblock = docblock.parseAsObject(docblock.extract(code)).jsx;

  if (isJsxFile && !hasDocblock) {
    code = '/** @jsx React.DOM */' + code;
  }
  if (isJsxFile || hasDocblock) {
    origLint(react.transform(code, {harmony: true}), results, config, data, file);
  }
  else {
    origLint(code, results, config, data, file);
  }
});

//override the jshint cli in the grunt-contrib-jshint lib folder 
var libJsHint = proxyquire('grunt-contrib-jshint/tasks/lib/jshint',{
  'jshint/src/cli': jshintcli
});


//insert the modified version of the jshint lib to the grunt-contrib-jshint taks
var gruntContribJshint = proxyquire('grunt-contrib-jshint/tasks/jshint',{
  './lib/jshint': libJsHint
});

//return the modified grunt-contrib-jshint version
module.exports = gruntContribJshint;

