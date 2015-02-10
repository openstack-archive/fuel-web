/*
 * Copyright 2015 Mirantis, Inc.
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

var gutil = require('gulp-util');
var _ = require('lodash-node');
var spawn = require('child_process').spawn;
var fs = require('fs');
var vinylFs = require('vinyl-fs');
var path = require('path');
var rimraf = require('rimraf');
var async = require('async');
var mkdirp = require('mkdirp');
var through = require('through2');
var tmp = require('tmp');

var PLUGIN_NAME = 'gulp-rjs';

module.exports = function(config) {
    'use strict';
    var sourceFiles = [];

    return through.obj(function(file, encoding, callback) {
        sourceFiles.push(file);
        callback();
    }, function(callback) {
        if (!sourceFiles.length) {
            return callback();
        }

        var self = this;

        var src, dest, configFile;
        async.waterfall([
            function(callback) {
                tmp.dir(function(err, path) {
                    src = path;
                    callback();
                });
            },
            function(callback) {
                tmp.dir(function(err, path) {
                    dest = path;
                    callback(err);
                });
            },
            function(callback) {
                tmp.file(function(err, path, fd) {
                    configFile = path;
                    fs.createWriteStream(null, {fd: fd}).write(JSON.stringify(_.extend({}, config, {appDir: src, dir: dest})));
                    fs.close(fd);
                    callback(err);
                });
            },
            function(callback) {
                async.each(sourceFiles, function(file, callback) {
                    if (!file.stat.isFile()) return callback();
                    var filePath = path.join(src, config.baseUrl, path.relative(config.appDir, file.path));
                    mkdirp(path.dirname(filePath), function(err) {
                        if (err) return callback(err);
                        fs.createWriteStream(filePath, {mode: file.stat.mode}).write(file.contents, '', callback);
                    });
                }, callback);
            },
            function(callback) {
                var rjs = spawn('./node_modules/requirejs/bin/r.js', ['-o', configFile]);
                rjs.stdout.on('data', function(data) {
                    _(data.toString().split('\n')).compact().map(function(line) {
                        gutil.log(line);
                    });
                });
                rjs.on('close', function(code) {
                    callback(code ? new gutil.PluginError(PLUGIN_NAME, 'r.js failed') : null);
                });
            },
            function(callback) {
                rimraf(src, callback);
            },
            function(callback) {
                var output = vinylFs.src(path.join(dest, '**'));
                output.on('data', function(file) {
                    self.push(file);
                });
                output.on('error', callback);
                output.on('end', callback);
            },
            function(callback) {
                rimraf(dest, callback);
            }
        ], callback);
    });
};
