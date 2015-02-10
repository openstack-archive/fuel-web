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

var _ = require('lodash-node');
var fs = require('fs');
var path = require('path');
var async = require('async');
var mkdirp = require('mkdirp');
var through = require('through2');
var rjs = require('requirejs');
var tmp = require('tmp');

module.exports = function(config) {
    'use strict';
    var sourceFiles = [];

    function eachFile(file, encoding, done) {
        sourceFiles.push(file);
        done();
    }

    function endStream(done) {
        if (!sourceFiles.length) {
            return done();
        }

        var src, dest, srcCleanupCallback, destCleanupCallback;
        async.waterfall([
            function(callback) {
                tmp.dir(function(err, path, cleanupCallback) {
                    src = path;
                    srcCleanupCallback = cleanupCallback;
                    callback();
                });
            },
            function(callback) {
                tmp.dir(function(err, path, cleanupCallback) {
                    dest = path;
                    destCleanupCallback = cleanupCallback;
                    callback();
                });
            },
            function(callback) {
                async.each(sourceFiles, function(file, callback) {
                    if (!file.stat.isFile()) return callback();
                    var filePath = path.join(src, config.baseUrl, path.relative(config.appDir, file.path));
                    mkdirp.sync(path.dirname(filePath));
                    var stream = fs.createWriteStream(filePath, {flags: 'w'}).write(file.contents, '', callback);
                }, callback);
            },
            function(callback) {
                //srcCleanupCallback();
                //destCleanupCallback();
                console.log(src, dest);
                rjs.optimize(_.extend({}, config, {appDir: src, dir: dest}), function(buildStatus) {
                    console.log('ok');
                }, function(err) {
                    console.log('err', err);
                });
            }
        ]);
    }

    return through.obj(eachFile, endStream);
};
